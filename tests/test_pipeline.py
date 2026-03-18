"""
Smoke tests for the Pipeline orchestrator.
"""

import pytest
from llm_sdlc_workflow.pipeline import Pipeline, PipelineResult


class TestPipelineResult:
    def test_passed_is_false_when_no_tests_run(self):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        assert result.passed is False

    def test_review_returns_none_when_no_iterations(self):
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        assert result.review is None

    def test_infrastructure_prefers_apply_over_plan(self):
        from llm_sdlc_workflow.models.artifacts import InfrastructureArtifact, IaCFile
        plan = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="plan")
        apply = InfrastructureArtifact(iac_files=[], primary_service_port=8080, phase="apply")
        result = PipelineResult(requirements="x", started_at="2026-01-01T00:00:00")
        result.infra_plan = plan
        result.infra_apply = apply
        assert result.infrastructure is apply


class TestPipelineInit:
    def test_pipeline_creates_agents(self, tmp_path):
        p = Pipeline(artifacts_dir=str(tmp_path))
        assert p.discovery_agent is not None
        assert p.engineering_agent is not None
        assert p.review_agent is not None
