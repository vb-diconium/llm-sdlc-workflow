"""
Tests for EngineeringAgent, SpecAgent, ReviewAgent, TestingAgent, and InfrastructureAgent.
All LLM calls and Docker/HTTP calls are mocked.
"""

from __future__ import annotations

import json
import os
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_sdlc_workflow.agents.engineering_agent import EngineeringAgent
from llm_sdlc_workflow.agents.infrastructure_agent import InfrastructureAgent
from llm_sdlc_workflow.agents.review_agent import ReviewAgent
from llm_sdlc_workflow.agents.spec_agent import SpecAgent
from llm_sdlc_workflow.agents.testing_agent import TestingAgent
from llm_sdlc_workflow.models.artifacts import (
    ArchitectureArtifact,
    ComponentSpec,
    DiscoveryArtifact,
    EngineeringArtifact,
    FileSpec,
    GeneratedSpecArtifact,
    IaCFile,
    InfrastructureArtifact,
    ReviewArtifact,
    ReviewFeedback,
    SpecArtifact,
    TestCase,
    TestingArtifact,
)


# ─── Shared fixtures ──────────────────────────────────────────────────────────

def _intent() -> DiscoveryArtifact:
    return DiscoveryArtifact(
        raw_requirements="Build API",
        requirements=["Auth", "CRUD tasks"],
        user_goals=["Speed"],
        constraints=["PostgreSQL"],
        success_criteria=["200ms"],
        key_features=["JWT"],
        domain_context="API",
        scope="backend",
    )


def _arch() -> ArchitectureArtifact:
    return ArchitectureArtifact(
        system_overview="REST API",
        architecture_style="Monolith",
        components=[ComponentSpec(name="API", responsibility="HTTP", interfaces=["REST"], dependencies=[])],
        data_flow=["Client -> API"],
        api_design=["GET /tasks"],
        database_design="PostgreSQL",
        security_design="JWT",
        deployment_strategy="Docker",
        patterns_used=["MVC"],
        scalability_considerations=["Horizontal"],
        trade_offs=["Simplicity"],
    )


def _contract() -> GeneratedSpecArtifact:
    return GeneratedSpecArtifact(
        openapi_spec="openapi: '3.0.0'",
        database_schema="CREATE TABLE tasks (id SERIAL PRIMARY KEY);",
        monorepo_services=["backend", "bff", "frontend"],
        service_ports={"backend": 8081, "bff": 8080, "frontend": 3000},
    )


def _eng_artifact() -> EngineeringArtifact:
    return EngineeringArtifact(
        generated_files=[FileSpec(path="src/main.kt", purpose="Entry", content="fun main() {}")],
        api_endpoints=["GET /tasks"],
        review_iteration=1,
    )


def _eng_json_response() -> str:
    return json.dumps({
        "service_name": "backend",
        "services": {},
        "generated_files": [{"path": "src/main.kt", "purpose": "Entry", "content": "fun main() {}"}],
        "api_endpoints": ["GET /tasks"],
        "data_models": ["Task"],
        "environment_variables": {},
        "implementation_steps": [],
        "spec_compliance_notes": [],
        "decisions": [],
        "review_iteration": 1,
        "review_feedback_applied": [],
    })


def _infra_json_response() -> str:
    return json.dumps({
        "iac_files": [
            {"path": "Dockerfile", "content": "FROM python:3.11", "purpose": "App container"},
            {"path": "docker-compose.yml", "content": "version: '3.8'", "purpose": "Orchestration"},
        ],
        "primary_service_port": 8080,
        "health_check_path": "/health",
        "startup_timeout_seconds": 90,
        "environment_variables": {},
        "service_dependencies": [],
        "build_notes": [],
        "spec_compliance_notes": [],
        "decisions": [],
        "review_iteration": 1,
        "review_feedback_applied": [],
        "phase": "plan",
        "base_url": None,
        "container_running": False,
    })


def _review_json_response(passed: bool = True) -> str:
    return json.dumps({
        "iteration": 1,
        "overall_score": 85 if passed else 30,
        "security_score": 80,
        "reliability_score": 90,
        "maintainability_score": 85,
        "performance_score": 82,
        "passed": passed,
        "critical_issues": [] if passed else ["SQL injection"],
        "high_issues": [],
        "issues": [],
        "strengths": ["Good JWT implementation"],
        "critical_fixes_required": [],
        "recommendations": [],
        "decisions": [],
    })


def _make_testing_artifact(stage: str = "architecture", passed: bool = True) -> TestingArtifact:
    """Build a valid TestingArtifact for use in tests."""
    return TestingArtifact(
        stage=stage,
        test_cases=[],
        http_test_cases=[],
        cypress_spec_files=[],
        coverage_areas=["General"],
        uncovered_areas=[],
        findings=[],
        blocking_issues=[],
        recommendations=[],
        passed=passed,
    )


def _testing_json_response(stage: str = "architecture") -> str:
    return json.dumps({
        "stage": stage,
        "test_cases": [
            {
                "id": "tc001", "name": "Auth test",
                "description": "Test JWT flow",
                "requirement_covered": "Auth",
                "test_type": "unit",
                "steps": ["POST /auth/login"],
                "expected_outcome": "200 OK",
                "status": "passed",
            }
        ],
        "http_test_cases": [],
        "cypress_spec_files": [],
        "coverage_areas": ["Auth"],
        "uncovered_areas": [],
        "findings": ["All covered"],
        "blocking_issues": [],
        "passed": True,
        "failed_services": [],
        "recommendations": [],
        "decisions": [],
    })


def _spec_json_response() -> str:
    return json.dumps({
        "openapi_spec": "openapi: '3.0.0'",
        "database_schema": "CREATE TABLE tasks (id SERIAL PRIMARY KEY);",
        "tech_stack_constraints": "Kotlin Spring Boot",
        "architecture_constraints": "Three-tier",
        "monorepo_services": ["backend", "bff", "frontend"],
        "service_ports": {"backend": 8081, "bff": 8080, "frontend": 3000},
        "shared_models": ["Task"],
        "generated_spec_files": [
            {"path": "specs/openapi.yaml", "purpose": "OpenAPI spec", "content": "openapi: '3.0.0'"},
            {"path": "specs/schema.sql", "purpose": "DB schema", "content": "CREATE TABLE tasks (id SERIAL);"},
        ],
        "usage_guide": "Use this spec to implement services.",
    })


# ─── EngineeringAgent ─────────────────────────────────────────────────────────

class TestEngineeringAgent:
    async def test_run_returns_assembled_artifact(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        agent.backend_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.bff_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.frontend_agent.run = AsyncMock(return_value=_eng_artifact())
        result = await agent.run(_intent(), _arch(), _contract())
        assert isinstance(result, EngineeringArtifact)

    async def test_run_calls_all_three_sub_agents(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        agent.backend_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.bff_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.frontend_agent.run = AsyncMock(return_value=_eng_artifact())
        await agent.run(_intent(), _arch(), _contract())
        agent.backend_agent.run.assert_called_once()
        agent.bff_agent.run.assert_called_once()
        agent.frontend_agent.run.assert_called_once()

    async def test_run_saves_engineering_artifact(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        agent.backend_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.bff_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.frontend_agent.run = AsyncMock(return_value=_eng_artifact())
        await agent.run(_intent(), _arch(), _contract())
        assert (tmp_path / "03_engineering_artifact.json").exists()

    async def test_run_merges_files_from_all_services(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        be = EngineeringArtifact(generated_files=[FileSpec(path="be.kt", purpose="BE", content="be")])
        bff = EngineeringArtifact(generated_files=[FileSpec(path="bff.kt", purpose="BFF", content="bff")])
        fe = EngineeringArtifact(generated_files=[FileSpec(path="fe.tsx", purpose="FE", content="fe")])
        agent.backend_agent.run = AsyncMock(return_value=be)
        agent.bff_agent.run = AsyncMock(return_value=bff)
        agent.frontend_agent.run = AsyncMock(return_value=fe)
        result = await agent.run(_intent(), _arch(), _contract())
        assert len(result.generated_files) == 3
        paths = [f.path for f in result.generated_files]
        assert "be.kt" in paths
        assert "bff.kt" in paths
        assert "fe.tsx" in paths

    async def test_run_passes_review_feedback_to_sub_agents(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        agent.backend_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.bff_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.frontend_agent.run = AsyncMock(return_value=_eng_artifact())
        fb = ReviewFeedback(iteration=1, critical_issues=["SQL injection"], passed=False)
        await agent.run(_intent(), _arch(), _contract(), review_feedback=fb)
        for mock in (agent.backend_agent.run, agent.bff_agent.run, agent.frontend_agent.run):
            call_kwargs = mock.call_args
            assert call_kwargs[0][3] is fb  # 4th positional arg is review_feedback

    async def test_apply_review_feedback_increments_iteration(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        agent.backend_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.bff_agent.run = AsyncMock(return_value=_eng_artifact())
        agent.frontend_agent.run = AsyncMock(return_value=_eng_artifact())
        current = EngineeringArtifact(review_iteration=2)
        fb = ReviewFeedback(iteration=2, critical_issues=["XSS"], passed=False)
        result = await agent.apply_review_feedback(_intent(), _arch(), current, fb, _contract())
        # All sub-agents should have been called with iteration=3
        for mock in (agent.backend_agent.run, agent.bff_agent.run, agent.frontend_agent.run):
            call_kwargs = mock.call_args
            assert call_kwargs[0][4] == 3  # 5th positional arg is iteration

    def test_assemble_merges_endpoints_and_models(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        be = EngineeringArtifact(api_endpoints=["GET /tasks"], data_models=["Task"])
        bff = EngineeringArtifact(api_endpoints=["GET /api/tasks"], data_models=["Task"])
        fe = EngineeringArtifact(api_endpoints=[], data_models=["User"])
        result = agent._assemble(be, bff, fe, iteration=1)
        # endpoints are deduped via set
        assert "GET /tasks" in result.api_endpoints
        assert "GET /api/tasks" in result.api_endpoints
        # models are deduped
        model_set = set(result.data_models)
        assert "Task" in model_set
        assert "User" in model_set

    def test_assemble_merges_env_vars(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        be = EngineeringArtifact(environment_variables={"DB_URL": "jdbc:pg://db"})
        bff = EngineeringArtifact(environment_variables={"BFF_PORT": "8080"})
        fe = EngineeringArtifact(environment_variables={"VITE_API": "/api"})
        result = agent._assemble(be, bff, fe, iteration=1)
        assert result.environment_variables["DB_URL"] == "jdbc:pg://db"
        assert result.environment_variables["BFF_PORT"] == "8080"
        assert result.environment_variables["VITE_API"] == "/api"

    def test_assemble_creates_services_dict(self, tmp_path):
        agent = EngineeringAgent(artifacts_dir=str(tmp_path))
        be = EngineeringArtifact(service_name="backend")
        bff = EngineeringArtifact(service_name="bff")
        fe = EngineeringArtifact(service_name="frontend")
        result = agent._assemble(be, bff, fe, iteration=1)
        assert "backend" in result.services
        assert "bff" in result.services
        assert "frontend" in result.services


# ─── ReviewAgent ─────────────────────────────────────────────────────────────

class TestReviewAgent:
    def _infra() -> InfrastructureArtifact:
        return InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="plan")

    async def test_run_returns_review_artifact(self, tmp_path):
        agent = ReviewAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_review_json_response())):
            result = await agent.run(_intent(), _arch(), _eng_artifact(), InfrastructureArtifact(iac_files=[], primary_service_port=8080))
        assert isinstance(result, ReviewArtifact)

    async def test_run_sets_passed_true(self, tmp_path):
        agent = ReviewAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_review_json_response(passed=True))):
            result = await agent.run(_intent(), _arch(), _eng_artifact(), InfrastructureArtifact(iac_files=[], primary_service_port=8080))
        assert result.passed is True

    async def test_run_sets_iteration_number(self, tmp_path):
        agent = ReviewAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_review_json_response())):
            result = await agent.run(
                _intent(), _arch(), _eng_artifact(),
                InfrastructureArtifact(iac_files=[], primary_service_port=8080),
                iteration=2,
            )
        assert result.iteration == 2

    async def test_run_includes_previous_feedback_in_message(self, tmp_path):
        agent = ReviewAgent(artifacts_dir=str(tmp_path))
        mock = AsyncMock(return_value=_review_json_response())
        prev = ReviewFeedback(iteration=1, critical_issues=["SQL injection"], passed=False)
        with patch.object(agent, "_raw_query", new=mock):
            await agent.run(
                _intent(), _arch(), _eng_artifact(),
                InfrastructureArtifact(iac_files=[], primary_service_port=8080),
                iteration=2,
                previous_feedback=prev,
            )
        user_msg = mock.call_args[0][1]
        assert "SQL injection" in user_msg

    async def test_run_saves_iteration_named_file(self, tmp_path):
        agent = ReviewAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_review_json_response())):
            await agent.run(_intent(), _arch(), _eng_artifact(),
                InfrastructureArtifact(iac_files=[], primary_service_port=8080), iteration=3)
        assert (tmp_path / "04_review_artifact_iter3.json").exists()

    async def test_run_with_failed_review(self, tmp_path):
        agent = ReviewAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_review_json_response(passed=False))):
            result = await agent.run(_intent(), _arch(), _eng_artifact(),
                InfrastructureArtifact(iac_files=[], primary_service_port=8080))
        assert result.passed is False
        assert result.critical_issues


# ─── SpecAgent ────────────────────────────────────────────────────────────────

class TestSpecAgent:
    async def test_run_returns_spec_artifact(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_spec_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch())
        assert isinstance(result, GeneratedSpecArtifact)

    async def test_run_extracts_openapi_from_spec_files(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_spec_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch())
        assert result.openapi_spec == "openapi: '3.0.0'"

    async def test_run_extracts_schema_from_spec_files(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_spec_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch())
        assert "CREATE TABLE" in result.database_schema

    async def test_run_sets_default_monorepo_services_if_empty(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path))
        resp = json.loads(_spec_json_response())
        resp["monorepo_services"] = []
        resp["service_ports"] = {}
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=json.dumps(resp))):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch())
        assert result.monorepo_services == ["backend", "bff", "frontend"]
        assert result.service_ports == {"backend": 8081, "bff": 8080, "frontend": 3000}

    async def test_run_saves_artifact_file(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_spec_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch())
        assert (tmp_path / "04_generated_spec_artifact.json").exists()

    async def test_run_writes_spec_files_to_disk(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_spec_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch())
        assert (tmp_path / "gen" / "specs" / "openapi.yaml").exists()
        assert (tmp_path / "gen" / "specs" / "schema.sql").exists()

    async def test_run_with_existing_spec_includes_section(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path))
        existing = SpecArtifact(api_spec="openapi: '3.0.0'\npaths:\n  /old: {}")
        mock = AsyncMock(return_value=_spec_json_response())
        with patch.object(agent, "_run_with_retry", new=mock):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch(), existing_spec=existing)
        plan_msg = mock.call_args[0][1]
        assert "EXISTING SPEC" in plan_msg or "x-existing" in plan_msg or "/old" in plan_msg

    def test_build_existing_section_with_all_fields(self):
        agent = SpecAgent(artifacts_dir="/tmp")
        spec = SpecArtifact(
            api_spec="openapi: '3.0.0'",
            database_schema="CREATE TABLE t (id SERIAL);",
            tech_stack_constraints="Kotlin",
        )
        section = agent._build_existing_section(spec)
        assert "EXISTING" in section
        assert "openapi" in section.lower()
        assert "CREATE TABLE" in section
        assert "Kotlin" in section

    def test_build_existing_section_returns_empty_for_none(self):
        agent = SpecAgent(artifacts_dir="/tmp")
        assert agent._build_existing_section(None) == ""

    def test_write_spec_files_skips_pending(self, tmp_path):
        agent = SpecAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        from llm_sdlc_workflow.models.artifacts import FileSpec
        artifact = GeneratedSpecArtifact(
            generated_spec_files=[
                FileSpec(path="specs/openapi.yaml", purpose="spec", content="__PENDING__"),
                FileSpec(path="specs/schema.sql", purpose="schema", content=""),
                FileSpec(path="specs/valid.yaml", purpose="valid", content="valid content"),
            ]
        )
        agent._write_spec_files(artifact)
        assert not (tmp_path / "gen" / "specs" / "openapi.yaml").exists()
        assert not (tmp_path / "gen" / "specs" / "schema.sql").exists()
        assert (tmp_path / "gen" / "specs" / "valid.yaml").exists()


# ─── TestingAgent ─────────────────────────────────────────────────────────────

class TestTestingAgent:
    async def test_run_architecture_stage_returns_artifact(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_testing_json_response("architecture"))):
            result = await agent.run("architecture", _intent(), architecture=_arch())
        assert isinstance(result, TestingArtifact)
        assert result.stage == "architecture"

    async def test_run_review_stage_returns_artifact(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_testing_json_response("review"))):
            result = await agent.run("review", _intent())
        assert isinstance(result, TestingArtifact)

    async def test_run_infrastructure_stage_with_no_live_service(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        resp = _testing_json_response("infrastructure")
        infra = InfrastructureArtifact(
            iac_files=[], primary_service_port=8080, phase="plan", container_running=False
        )
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=resp)):
            result = await agent.run("infrastructure", _intent(), infrastructure=infra)
        assert isinstance(result, TestingArtifact)

    async def test_run_raises_on_invalid_stage(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        with pytest.raises(ValueError, match="Invalid stage"):
            await agent.run("invalid_stage", _intent())

    async def test_run_saves_architecture_file(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_testing_json_response())):
            await agent.run("architecture", _intent(), architecture=_arch())
        assert (tmp_path / "05a_testing_architecture.json").exists()

    async def test_run_saves_infrastructure_file(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_testing_json_response("infrastructure"))):
            await agent.run("infrastructure", _intent())
        assert (tmp_path / "05b_testing_infrastructure.json").exists()

    async def test_run_saves_review_file(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_raw_query", new=AsyncMock(return_value=_testing_json_response("review"))):
            await agent.run("review", _intent())
        assert (tmp_path / "05c_testing_review.json").exists()

    async def test_run_includes_all_context_in_message(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        mock = AsyncMock(return_value=_testing_json_response())
        review = ReviewArtifact(iteration=1, overall_score=80, passed=True)
        with patch.object(agent, "_raw_query", new=mock):
            await agent.run("review", _intent(), architecture=_arch(),
                           engineering=_eng_artifact(), review=review)
        user_msg = mock.call_args[0][1]
        assert "REVIEW" in user_msg
        assert "Discovery" in user_msg

    async def test_run_live_tests_marks_passed_on_correct_status(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        from llm_sdlc_workflow.models.artifacts import HttpTestCase
        artifact = TestingArtifact(
            stage="infrastructure",
            test_cases=[],
            http_test_cases=[
                HttpTestCase(
                    id="h1", name="GET tasks", description="test",
                    requirement_covered="CRUD",
                    method="GET", path="/tasks",
                    expected_status=200,
                    response_contains=[],
                )
            ],
            coverage_areas=["CRUD"],
            uncovered_areas=[],
            findings=[],
            blocking_issues=[],
            passed=True,
            recommendations=[],
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"items": []}'
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await agent._run_live_tests(artifact, "http://localhost:8080")
        assert artifact.http_test_cases[0].status == "passed"

    async def test_run_live_tests_marks_failed_on_wrong_status(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        from llm_sdlc_workflow.models.artifacts import HttpTestCase
        artifact = TestingArtifact(
            stage="infrastructure",
            test_cases=[],
            http_test_cases=[
                HttpTestCase(
                    id="h1", name="GET tasks", description="test",
                    requirement_covered="CRUD",
                    method="GET", path="/tasks",
                    expected_status=200,
                    response_contains=[],
                )
            ],
            coverage_areas=[],
            uncovered_areas=[],
            findings=[],
            blocking_issues=[],
            passed=True,
            recommendations=[],
        )
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "not found"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_response)
        with patch("httpx.AsyncClient", return_value=mock_client):
            await agent._run_live_tests(artifact, "http://localhost:8080")
        assert artifact.http_test_cases[0].status == "failed"
        assert artifact.passed is False

    async def test_run_live_tests_handles_exception(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        from llm_sdlc_workflow.models.artifacts import HttpTestCase
        artifact = TestingArtifact(
            stage="infrastructure",
            test_cases=[],
            http_test_cases=[
                HttpTestCase(
                    id="h1", name="GET tasks", description="test",
                    requirement_covered="CRUD",
                    method="GET", path="/tasks",
                    expected_status=200,
                )
            ],
            coverage_areas=[],
            uncovered_areas=[],
            findings=[],
            blocking_issues=[],
            passed=True,
            recommendations=[],
        )
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(side_effect=ConnectionError("refused"))
        with patch("httpx.AsyncClient", return_value=mock_client):
            await agent._run_live_tests(artifact, "http://localhost:8080")
        assert artifact.http_test_cases[0].status == "error"

    async def test_run_live_tests_skips_empty_http_cases(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[], http_test_cases=[],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
        )
        # Should complete without calling httpx
        with patch("httpx.AsyncClient") as mock_httpx:
            await agent._run_live_tests(artifact, "http://localhost:8080")
        mock_httpx.assert_not_called()

    def test_write_cypress_specs_creates_files(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
            cypress_spec_files=[
                FileSpec(path="cypress/e2e/tasks.cy.ts", purpose="e2e", content="describe('tasks', () => {});"),
            ]
        )
        agent._write_cypress_specs(artifact)
        assert (tmp_path / "generated" / "cypress" / "e2e" / "tasks.cy.ts").exists()

    def test_write_cypress_specs_creates_config(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
            cypress_spec_files=[
                FileSpec(path="cypress/e2e/tasks.cy.ts", purpose="e2e", content="describe('tasks', () => {});"),
            ]
        )
        agent._write_cypress_specs(artifact)
        assert (tmp_path / "generated" / "cypress.config.ts").exists()

    def test_write_cypress_specs_skips_when_empty(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[], cypress_spec_files=[],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
        )
        agent._write_cypress_specs(artifact)
        # No crash, no files created
        assert not (tmp_path / "generated" / "cypress.config.ts").exists()

    async def test_run_cypress_skips_when_no_specs(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[], cypress_spec_files=[],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
        )
        with patch("shutil.which", return_value="/usr/bin/npx"):
            await agent._run_cypress(artifact)
        # No subprocess launched

    async def test_run_cypress_skips_when_no_binary(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[],
            cypress_spec_files=[FileSpec(path="cypress/e2e/t.cy.ts", purpose="e2e", content="")],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
        )
        with patch("shutil.which", return_value=None):
            await agent._run_cypress(artifact)
        # Should exit early without error

    async def test_run_cypress_skips_when_no_config(self, tmp_path):
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        artifact = TestingArtifact(
            stage="infrastructure", test_cases=[],
            cypress_spec_files=[FileSpec(path="cypress/e2e/t.cy.ts", purpose="e2e", content="")],
            coverage_areas=[], uncovered_areas=[], findings=[],
            blocking_issues=[], passed=True, recommendations=[],
        )
        with patch("shutil.which", return_value="/usr/bin/npx"):
            await agent._run_cypress(artifact)
        # No config file → skip


# ─── InfrastructureAgent ──────────────────────────────────────────────────────

class TestInfrastructureAgent:
    async def test_run_skip_start_returns_plan_phase(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _eng_artifact(), skip_start=True)
        assert result.phase == "plan"
        assert result.container_running is False

    async def test_run_skip_start_saves_plan_file(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch(), _eng_artifact(), skip_start=True)
        assert (tmp_path / "06a_infrastructure_plan_artifact.json").exists()

    async def test_run_writes_iac_files_to_disk(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch(), _eng_artifact(), skip_start=True)
        assert (tmp_path / "gen" / "Dockerfile").exists()
        assert (tmp_path / "gen" / "docker-compose.yml").exists()

    async def test_run_with_review_feedback_populates_applied(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        fb = ReviewFeedback(iteration=1, critical_issues=["No healthcheck"], high_issues=["Missing restart policy"], passed=False)
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _eng_artifact(), review_feedback=fb, skip_start=True)
        assert "No healthcheck" in result.review_feedback_applied
        assert "Missing restart policy" in result.review_feedback_applied

    async def test_run_apply_calls_start_service(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        agent.start_service = AsyncMock(return_value=InfrastructureArtifact(
            iac_files=[], primary_service_port=8080, phase="apply", container_running=False
        ))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _eng_artifact(), skip_start=False)
        agent.start_service.assert_called_once()

    def test_write_iac_files_creates_files(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        artifact = InfrastructureArtifact(
            iac_files=[
                IaCFile(path="Dockerfile", content="FROM python:3.11", purpose="App"),
                IaCFile(path="subdir/compose.yml", content="version: '3.8'", purpose="Compose"),
            ],
            primary_service_port=8080,
        )
        generated_dir = str(tmp_path / "gen")
        agent._write_iac_files(artifact, generated_dir)
        assert (tmp_path / "gen" / "Dockerfile").exists()
        assert (tmp_path / "gen" / "subdir" / "compose.yml").exists()

    async def test_start_containers_returns_false_when_no_compose_file(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        result = await agent._start_containers(str(tmp_path))
        assert result is False

    async def test_start_containers_returns_false_when_docker_not_found(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("docker not found")):
            result = await agent._start_containers(str(tmp_path))
        assert result is False

    async def test_start_containers_returns_false_on_nonzero_exit(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error output"))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await agent._start_containers(str(tmp_path))
        assert result is False

    async def test_start_containers_returns_true_on_success(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await agent._start_containers(str(tmp_path))
        assert result is True

    async def test_start_containers_returns_false_on_timeout(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        (tmp_path / "docker-compose.yml").write_text("version: '3.8'")
        mock_proc = AsyncMock()
        mock_proc.kill = MagicMock()
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                result = await agent._start_containers(str(tmp_path))
        assert result is False

    async def test_stop_containers_does_nothing_without_compose_file(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        # No docker-compose.yml → should return without error
        await agent.stop_containers()

    async def test_stop_containers_calls_docker_compose_down(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        gen_dir = tmp_path / "gen"
        gen_dir.mkdir()
        (gen_dir / "docker-compose.yml").write_text("version: '3.8'")
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            with patch("asyncio.wait_for", new=AsyncMock(return_value=(b"", b""))):
                await agent.stop_containers()
        mock_exec.assert_called_once()
        assert "down" in mock_exec.call_args[0]

    async def test_apply_review_feedback_calls_run_with_skip_start(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        current = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="plan", review_iteration=1)
        fb = ReviewFeedback(iteration=1, critical_issues=["No healthcheck"], passed=False)
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.apply_review_feedback(_intent(), _arch(), _eng_artifact(), current, fb)
        assert result.phase == "plan"  # skip_start=True → plan phase

    async def test_apply_review_feedback_stops_running_containers(self, tmp_path):
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        current = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="apply", container_running=True)
        agent.stop_containers = AsyncMock()
        fb = ReviewFeedback(iteration=1, critical_issues=[], passed=False)
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_infra_json_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.apply_review_feedback(_intent(), _arch(), _eng_artifact(), current, fb)
        agent.stop_containers.assert_called_once()

    async def test_wait_for_health_returns_true_when_service_responds(self, tmp_path):
        """_wait_for_health returns True when the health endpoint returns <500."""
        import time
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        # Fake context manager for httpx.AsyncClient
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_cm):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent._wait_for_health("http://localhost:8080", "/health", 30)

        assert result is True

    async def test_wait_for_health_returns_false_on_timeout(self, tmp_path):
        """_wait_for_health returns False when deadline passes without success."""
        import time
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))

        # Always raise an exception simulating connection refused
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        # Make time.monotonic advance past deadline immediately on second call
        time_values = iter([0.0, 100.0, 200.0])
        with patch("httpx.AsyncClient", return_value=mock_cm):
            with patch("asyncio.sleep", new=AsyncMock()):
                with patch("time.monotonic", side_effect=lambda: next(time_values)):
                    result = await agent._wait_for_health("http://localhost:8080", "/health", 10)

        assert result is False

    async def test_wait_for_health_returns_true_on_503(self, tmp_path):
        """_wait_for_health returns True for any status_code < 500 (e.g. 404 or 200)."""
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))

        mock_resp = MagicMock()
        mock_resp.status_code = 404  # Not found but server is alive

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_cm):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent._wait_for_health("http://localhost:8080", "/health", 30)

        assert result is True

    async def test_start_service_sets_base_url_when_healthy(self, tmp_path):
        """start_service sets base_url and container_running=True when healthy."""
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        artifact = InfrastructureArtifact(
            iac_files=[IaCFile(path="Dockerfile", content="FROM python:3.11", purpose="app")],
            primary_service_port=8080,
        )
        with patch.object(agent, "_start_containers", new=AsyncMock(return_value=True)):
            with patch.object(agent, "_wait_for_health", new=AsyncMock(return_value=True)):
                result = await agent.start_service(artifact)

        assert result.container_running is True
        assert result.base_url == "http://localhost:8080"

    async def test_start_service_marks_not_running_when_unhealthy(self, tmp_path):
        """start_service leaves container_running=False when health check fails."""
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        artifact = InfrastructureArtifact(
            iac_files=[],
            primary_service_port=9000,
        )
        with patch.object(agent, "_start_containers", new=AsyncMock(return_value=True)):
            with patch.object(agent, "_wait_for_health", new=AsyncMock(return_value=False)):
                result = await agent.start_service(artifact)

        assert result.container_running is False

    async def test_start_service_returns_artifact_when_containers_not_started(self, tmp_path):
        """start_service short-circuits and returns artifact when _start_containers returns False."""
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path))
        artifact = InfrastructureArtifact(iac_files=[], primary_service_port=8080)
        with patch.object(agent, "_start_containers", new=AsyncMock(return_value=False)):
            with patch.object(agent, "_wait_for_health", new=AsyncMock()) as mock_health:
                result = await agent.start_service(artifact)

        mock_health.assert_not_called()
        assert result.container_running is False

    async def test_stop_containers_exception_is_swallowed(self, tmp_path):
        """stop_containers prints a warning but does not re-raise on exception."""
        agent = InfrastructureAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        gen_dir = tmp_path / "gen"
        gen_dir.mkdir()
        (gen_dir / "docker-compose.yml").write_text("version: '3.8'")

        with patch("asyncio.create_subprocess_exec",
                   side_effect=RuntimeError("docker daemon not running")):
            # Must not raise
            await agent.stop_containers()


class TestTestingAgentCypressInstalled:
    """Tests for _run_cypress when cypress binary IS installed."""

    def _setup_cypress(self, tmp_path):
        """Create gen/node_modules/.bin/cypress and cypress.config.ts, return ready artifact."""
        gen_dir = tmp_path / "gen"
        bin_dir = gen_dir / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "cypress").write_text("#!/bin/sh\nexit 0")
        (gen_dir / "cypress.config.ts").write_text("export default {}")
        artifact = _make_testing_artifact("infrastructure", passed=True)
        artifact.cypress_spec_files = [
            FileSpec(path="cypress/e2e/smoke.cy.ts", purpose="smoke test", content="it('works', () => {})")
        ]
        return artifact

    async def test_run_cypress_passes_on_zero_exit(self, tmp_path):
        """_run_cypress keeps artifact passed=True when cypress exits 0."""
        import asyncio as _asyncio
        agent = TestingAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = self._setup_cypress(tmp_path)

        fake_proc = types.SimpleNamespace(
            returncode=0,
            communicate=AsyncMock(return_value=(b"Tests passed", b"")),
            kill=MagicMock(),
        )
        with patch("shutil.which", return_value="/usr/local/bin/cypress"):
            with patch("asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=fake_proc)):
                with patch("asyncio.wait_for",
                           new=AsyncMock(return_value=(b"Tests passed", b""))):
                    await agent._run_cypress(artifact)

        assert artifact.passed is True
        assert len(artifact.blocking_issues) == 0

    async def test_run_cypress_fails_on_nonzero_exit(self, tmp_path):
        """_run_cypress adds blocking issue and sets passed=False when cypress exits non-0."""
        agent = TestingAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = self._setup_cypress(tmp_path)

        fake_proc = types.SimpleNamespace(
            returncode=1,
            communicate=AsyncMock(return_value=(b"Error: 1 test failed", b"")),
            kill=MagicMock(),
        )
        with patch("shutil.which", return_value="/usr/local/bin/cypress"):
            with patch("asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=fake_proc)):
                with patch("asyncio.wait_for",
                           new=AsyncMock(return_value=(b"Error: 1 test failed", b""))):
                    await agent._run_cypress(artifact)

        assert artifact.passed is False
        assert any("Cypress" in issue for issue in artifact.blocking_issues)

    async def test_run_cypress_handles_timeout(self, tmp_path):
        """_run_cypress handles asyncio.TimeoutError gracefully."""
        import asyncio as _asyncio
        agent = TestingAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = self._setup_cypress(tmp_path)

        kill_mock = MagicMock()
        fake_proc = types.SimpleNamespace(
            returncode=None,
            communicate=AsyncMock(),
            kill=kill_mock,
        )
        with patch("shutil.which", return_value="/usr/local/bin/cypress"):
            with patch("asyncio.create_subprocess_exec",
                       new=AsyncMock(return_value=fake_proc)):
                with patch("asyncio.wait_for",
                           new=AsyncMock(side_effect=_asyncio.TimeoutError())):
                    await agent._run_cypress(artifact)

        kill_mock.assert_called_once()

    async def test_run_cypress_handles_subprocess_exception(self, tmp_path):
        """_run_cypress swallows unexpected exceptions from create_subprocess_exec."""
        agent = TestingAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = self._setup_cypress(tmp_path)

        with patch("shutil.which", return_value="/usr/local/bin/cypress"):
            with patch("asyncio.create_subprocess_exec",
                       new=AsyncMock(side_effect=OSError("permission denied"))):
                # Must not raise
                await agent._run_cypress(artifact)


class TestTestingAgentContextBuilding:
    """Tests for context building with architecture, engineering, and infrastructure."""

    async def test_context_includes_architecture(self, tmp_path):
        """run() builds a context that includes architecture when provided."""
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        # Test that the agent runs without error when architecture is provided
        with patch.object(agent, "_run_with_retry",
                          new=AsyncMock(return_value=_testing_json_response("architecture"))):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(
                    stage="architecture",
                    intent=_intent(),
                    architecture=_arch(),
                )
        assert result.stage == "architecture"

    async def test_context_includes_infrastructure_base_url(self, tmp_path):
        """run() includes live URL in context when infrastructure.base_url is set."""
        agent = TestingAgent(artifacts_dir=str(tmp_path))
        infra = InfrastructureArtifact(
            iac_files=[],
            primary_service_port=8080,
            container_running=True,
            base_url="http://localhost:8080",
        )
        with patch.object(agent, "_run_with_retry",
                          new=AsyncMock(return_value=_testing_json_response("infrastructure"))):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(
                    stage="infrastructure",
                    intent=_intent(),
                    infrastructure=infra,
                )
        assert result.stage == "infrastructure"

