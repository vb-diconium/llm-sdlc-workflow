"""
Tests for the Pipeline orchestrator and PipelineResult dataclass.

Unit tests cover PipelineResult properties (review, infrastructure, passed).
Integration tests mock every agent and verify orchestration logic:
  - Happy path: all steps complete, review passes first try
  - Review retry loop: review fails once then passes
  - PipelineHaltError captured after max review iterations
  - Infrastructure property prefers apply over plan phase
  - _save_report writes the JSON report file
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_sdlc_workflow.models.artifacts import (
    DiscoveryArtifact,
    EngineeringArtifact,
    GeneratedSpecArtifact,
    InfrastructureArtifact,
    IaCFile,
    ReviewArtifact,
    TestingArtifact,
    TestCase,
)
from llm_sdlc_workflow.pipeline import Pipeline, PipelineHaltError, PipelineResult


# ─── PipelineResult properties ───────────────────────────────────────────────


class TestPipelineResult:
    def test_passed_is_false_when_no_tests_run(self):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        assert result.passed is False

    def test_review_returns_none_when_no_iterations(self):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        assert result.review is None

    def test_review_returns_last_iteration(self):
        r1 = ReviewArtifact(iteration=1, passed=False)
        r2 = ReviewArtifact(iteration=2, passed=True)
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.review_iterations = [r1, r2]
        assert result.review is r2

    def test_infrastructure_returns_none_when_both_missing(self):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        assert result.infrastructure is None

    def test_infrastructure_prefers_apply_over_plan(self):
        plan = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="plan")
        apply_ = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="apply")
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.infra_plan = plan
        result.infra_apply = apply_
        assert result.infrastructure is apply_

    def test_infrastructure_falls_back_to_plan_when_no_apply(self):
        plan = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="plan")
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.infra_plan = plan
        assert result.infrastructure is plan

    def test_passed_requires_all_three_test_stages_and_review(
        self, testing_passed, review_passed
    ):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.test_architecture = testing_passed
        result.test_infrastructure = testing_passed
        result.test_review = testing_passed
        result.review_iterations = [review_passed]
        assert result.passed is True

    def test_passed_is_false_if_any_stage_fails(self, testing_passed, review_passed):
        failed = TestingArtifact(
            stage="infrastructure",
            test_cases=[],
            coverage_areas=[],
            uncovered_areas=[],
            findings=[],
            blocking_issues=["fatal"],
            passed=False,
            recommendations=[],
        )
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.test_architecture = testing_passed
        result.test_infrastructure = failed
        result.test_review = testing_passed
        result.review_iterations = [review_passed]
        assert result.passed is False

    def test_passed_is_false_if_review_failed(self, testing_passed, review_failed):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.test_architecture = testing_passed
        result.test_infrastructure = testing_passed
        result.test_review = testing_passed
        result.review_iterations = [review_failed]
        assert result.passed is False


# ─── Pipeline init ────────────────────────────────────────────────────────────


class TestPipelineInit:
    def test_pipeline_creates_all_agents(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path))
        assert p.discovery_agent is not None
        assert p.architecture_agent is not None
        assert p.spec_agent is not None
        assert p.engineering_agent is not None
        assert p.infrastructure_agent is not None
        assert p.review_agent is not None
        assert p.testing_agent is not None

    def test_pipeline_stores_artifacts_dir(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path))
        assert p.artifacts_dir == str(tmp_path)

    def test_pipeline_stores_human_checkpoints_flag(self, tmp_path):
        p_auto = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        p_manual = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=True)
        assert p_auto.human_checkpoints is False
        assert p_manual.human_checkpoints is True

    def test_pipeline_creates_artifacts_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "artifacts"
        Pipeline(artifacts_dir=str(new_dir))
        assert new_dir.exists()


# ─── Pipeline.run() integration tests ────────────────────────────────────────


def _make_testing_artifact(stage: str, passed: bool = True) -> TestingArtifact:
    return TestingArtifact(
        stage=stage,
        test_cases=[
            TestCase(
                id="tc001",
                name="smoke",
                description="smoke test",
                requirement_covered="x",
                test_type="unit",
                steps=["run"],
                expected_outcome="pass",
                status="passed" if passed else "failed",
            )
        ],
        coverage_areas=["auth"],
        uncovered_areas=[],
        findings=[],
        blocking_issues=[] if passed else ["fatal error"],
        passed=passed,
        failed_services=[] if passed else ["backend"],
        recommendations=[],
    )


def _make_discovery() -> DiscoveryArtifact:
    return DiscoveryArtifact(
        raw_requirements="Build API",
        requirements=["Auth", "CRUD"],
        user_goals=["Speed"],
        constraints=["PostgreSQL"],
        success_criteria=["200ms"],
        key_features=["JWT"],
        domain_context="API",
        scope="backend",
    )


def _make_engineering() -> EngineeringArtifact:
    return EngineeringArtifact(generated_files=[], review_iteration=1)


def _make_infra(phase: str = "plan") -> InfrastructureArtifact:
    return InfrastructureArtifact(
        iac_files=[IaCFile(path="Dockerfile", content="FROM python:3.11", purpose="app")],
        primary_service_port=8080,
        phase=phase,
        container_running=False,
    )


def _make_review(passed: bool = True, iteration: int = 1) -> ReviewArtifact:
    return ReviewArtifact(
        iteration=iteration,
        overall_score=85 if passed else 30,
        passed=passed,
        critical_issues=[] if passed else ["SQL injection"],
    )


def _make_spec() -> GeneratedSpecArtifact:
    return GeneratedSpecArtifact(
        openapi_spec="openapi: '3.0.0'",
        database_schema="CREATE TABLE t (id SERIAL);",
        monorepo_services=["backend"],
        service_ports={"backend": 8080},
    )


class TestPipelineRunHappyPath:
    async def test_run_returns_pipeline_result(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)

        # Wire up mocks for all agent methods
        p.discovery_agent.run = AsyncMock(return_value=_make_discovery())
        p.architecture_agent.run = AsyncMock(return_value=MagicMock(
            components=[],
            architecture_style="Monolith",
            model_dump=lambda: {},
        ))
        p.spec_agent.run = AsyncMock(return_value=_make_spec())
        p.testing_agent.run = AsyncMock(side_effect=[
            _make_testing_artifact("architecture", passed=True),
            _make_testing_artifact("infrastructure", passed=True),
            _make_testing_artifact("review", passed=True),
        ])
        p.engineering_agent.run = AsyncMock(return_value=_make_engineering())
        p.infrastructure_agent.run = AsyncMock(side_effect=[
            _make_infra("plan"),   # step 5 parallel: skip_start=True
            _make_infra("apply"),  # step 7: start containers
        ])
        p.review_agent.run = AsyncMock(return_value=_make_review(passed=True))

        result = await p.run("Build API")

        assert isinstance(result, PipelineResult)
        assert result.intent is not None
        assert result.generated_spec is not None
        assert result.engineering is not None

    async def test_run_calls_discovery_agent_once(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        p.discovery_agent.run = AsyncMock(return_value=_make_discovery())
        p.architecture_agent.run = AsyncMock(return_value=MagicMock(components=[], architecture_style="x", model_dump=lambda: {}))
        p.spec_agent.run = AsyncMock(return_value=_make_spec())
        p.testing_agent.run = AsyncMock(side_effect=[
            _make_testing_artifact("architecture"),
            _make_testing_artifact("infrastructure"),
            _make_testing_artifact("review"),
        ])
        p.engineering_agent.run = AsyncMock(return_value=_make_engineering())
        p.infrastructure_agent.run = AsyncMock(side_effect=[_make_infra("plan"), _make_infra("apply")])
        p.review_agent.run = AsyncMock(return_value=_make_review(passed=True))

        await p.run("Build API")

        p.discovery_agent.run.assert_called_once_with("Build API")

    async def test_run_writes_pipeline_report(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        p.discovery_agent.run = AsyncMock(return_value=_make_discovery())
        p.architecture_agent.run = AsyncMock(return_value=MagicMock(components=[], architecture_style="x", model_dump=lambda: {}))
        p.spec_agent.run = AsyncMock(return_value=_make_spec())
        p.testing_agent.run = AsyncMock(side_effect=[
            _make_testing_artifact("architecture"),
            _make_testing_artifact("infrastructure"),
            _make_testing_artifact("review"),
        ])
        p.engineering_agent.run = AsyncMock(return_value=_make_engineering())
        p.infrastructure_agent.run = AsyncMock(side_effect=[_make_infra("plan"), _make_infra("apply")])
        p.review_agent.run = AsyncMock(return_value=_make_review(passed=True))

        await p.run("Build API")

        report_path = tmp_path / "00_pipeline_report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert "started_at" in report
        assert "completed_at" in report
        assert "passed" in report

    async def test_review_passes_on_first_iteration_no_feedback_loop(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        p.discovery_agent.run = AsyncMock(return_value=_make_discovery())
        p.architecture_agent.run = AsyncMock(return_value=MagicMock(components=[], architecture_style="x", model_dump=lambda: {}))
        p.spec_agent.run = AsyncMock(return_value=_make_spec())
        p.testing_agent.run = AsyncMock(side_effect=[
            _make_testing_artifact("architecture"),
            _make_testing_artifact("infrastructure"),
            _make_testing_artifact("review"),
        ])
        p.engineering_agent.run = AsyncMock(return_value=_make_engineering())
        p.infrastructure_agent.run = AsyncMock(side_effect=[_make_infra("plan"), _make_infra("apply")])
        p.review_agent.run = AsyncMock(return_value=_make_review(passed=True))
        p.engineering_agent.apply_review_feedback = AsyncMock()
        p.infrastructure_agent.apply_review_feedback = AsyncMock()

        result = await p.run("Build API")

        # Review passed first time: no feedback loop calls
        p.engineering_agent.apply_review_feedback.assert_not_called()
        p.infrastructure_agent.apply_review_feedback.assert_not_called()
        assert len(result.review_iterations) == 1


class TestPipelineReviewLoop:
    async def test_applies_feedback_when_review_fails_first_iteration(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        p.discovery_agent.run = AsyncMock(return_value=_make_discovery())
        p.architecture_agent.run = AsyncMock(return_value=MagicMock(components=[], architecture_style="x", model_dump=lambda: {}))
        p.spec_agent.run = AsyncMock(return_value=_make_spec())
        p.testing_agent.run = AsyncMock(side_effect=[
            _make_testing_artifact("architecture"),
            _make_testing_artifact("infrastructure"),
            _make_testing_artifact("review"),
        ])
        # First engineering call (step 5) + after-feedback call
        p.engineering_agent.run = AsyncMock(return_value=_make_engineering())
        p.engineering_agent.apply_review_feedback = AsyncMock(return_value=_make_engineering())
        p.infrastructure_agent.run = AsyncMock(side_effect=[_make_infra("plan"), _make_infra("apply")])
        p.infrastructure_agent.apply_review_feedback = AsyncMock(return_value=_make_infra("plan"))
        # Fail first review, pass second
        p.review_agent.run = AsyncMock(side_effect=[
            _make_review(passed=False, iteration=1),
            _make_review(passed=True, iteration=2),
        ])

        result = await p.run("Build API")

        assert len(result.review_iterations) == 2
        p.engineering_agent.apply_review_feedback.assert_called_once()
        p.infrastructure_agent.apply_review_feedback.assert_called_once()

    async def test_halts_when_review_fails_all_max_iterations(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        p.discovery_agent.run = AsyncMock(return_value=_make_discovery())
        p.architecture_agent.run = AsyncMock(return_value=MagicMock(components=[], architecture_style="x", model_dump=lambda: {}))
        p.spec_agent.run = AsyncMock(return_value=_make_spec())
        p.testing_agent.run = AsyncMock(return_value=_make_testing_artifact("architecture"))
        p.engineering_agent.run = AsyncMock(return_value=_make_engineering())
        p.engineering_agent.apply_review_feedback = AsyncMock(return_value=_make_engineering())
        p.infrastructure_agent.run = AsyncMock(return_value=_make_infra("plan"))
        p.infrastructure_agent.apply_review_feedback = AsyncMock(return_value=_make_infra("plan"))
        # All 3 review iterations fail
        p.review_agent.run = AsyncMock(side_effect=[
            _make_review(passed=False, iteration=1),
            _make_review(passed=False, iteration=2),
            _make_review(passed=False, iteration=3),
        ])

        result = await p.run("Build API")

        # PipelineHaltError is caught internally — verify it's in errors
        assert any("Review failed" in err for err in result.errors)


class TestPipelineAwaithuman:
    async def test_checkpoint_skipped_when_human_checkpoints_false(self, tmp_path):
        """With human_checkpoints=False _await_human must return immediately."""
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        # Should complete instantly — no input() call
        import asyncio
        with patch("asyncio.to_thread", new=AsyncMock(return_value="")) as mock_input:
            await p._await_human(
                checkpoint="Test checkpoint",
                details=["detail 1"],
                artifact_path=str(tmp_path / "dummy.json"),
            )
        mock_input.assert_not_called()

    async def test_checkpoint_skipped_when_stdin_not_tty(self, tmp_path):
        """Checkpoint must be skipped in CI/CD (non-TTY stdin)."""
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=True)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with patch("asyncio.to_thread", new=AsyncMock(return_value="")) as mock_input:
                await p._await_human(
                    checkpoint="Test checkpoint",
                    details=["detail 1"],
                    artifact_path=str(tmp_path / "dummy.json"),
                )
        mock_input.assert_not_called()


class TestSaveReport:
    def test_save_report_contains_required_keys(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        result = PipelineResult(
            requirements="Build API",
            started_at="2026-01-01T00:00:00",
            completed_at="2026-01-01T00:05:00",
            artifacts_dir=str(tmp_path),
        )
        p._save_report(result)

        report = json.loads((tmp_path / "00_pipeline_report.json").read_text())
        assert report["started_at"] == "2026-01-01T00:00:00"
        assert report["completed_at"] == "2026-01-01T00:05:00"
        assert "passed" in report
        assert "errors" in report
        assert "summary" in report

    def test_save_report_records_passed_false_by_default(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        p._save_report(result)
        report = json.loads((tmp_path / "00_pipeline_report.json").read_text())
        assert report["passed"] is False

    def test_save_report_records_errors(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path), human_checkpoints=False)
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.errors.append("Something went wrong")
        p._save_report(result)
        report = json.loads((tmp_path / "00_pipeline_report.json").read_text())
        assert "Something went wrong" in report["errors"]
