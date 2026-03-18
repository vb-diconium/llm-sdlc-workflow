"""
Tests for BackendAgent, BffAgent, and FrontendAgent.

All LLM calls are mocked. Tests verify:
  - Happy-path run() returning EngineeringArtifact
  - service_name set correctly
  - _build_contract_section with full/empty contract
  - _build_feedback_section with/without review feedback
  - _write_service_files writing files to disk
  - review_feedback_applied populated
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from llm_sdlc_workflow.agents.backend_agent import BackendAgent
from llm_sdlc_workflow.agents.bff_agent import BffAgent
from llm_sdlc_workflow.agents.frontend_agent import FrontendAgent
from llm_sdlc_workflow.models.artifacts import (
    ArchitectureArtifact,
    ComponentSpec,
    DiscoveryArtifact,
    EngineeringArtifact,
    FileSpec,
    GeneratedSpecArtifact,
    ReviewFeedback,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _intent() -> DiscoveryArtifact:
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


def _contract(**kw) -> GeneratedSpecArtifact:
    defaults = {
        "openapi_spec": "openapi: '3.0.0'\npaths:\n  /tasks: {}",
        "database_schema": "CREATE TABLE tasks (id SERIAL PRIMARY KEY);",
        "tech_stack_constraints": "Kotlin Spring Boot",
        "architecture_constraints": "Three-tier monorepo",
        "monorepo_services": ["backend", "bff", "frontend"],
        "service_ports": {"backend": 8081, "bff": 8080},
    }
    defaults.update(kw)
    return GeneratedSpecArtifact(**defaults)


def _eng_response(service_name: str = "backend") -> str:
    return json.dumps({
        "service_name": service_name,
        "services": {},
        "generated_files": [
            {"path": "src/main.kt", "purpose": "Entry point", "content": "fun main() {}"},
        ],
        "api_endpoints": ["GET /tasks"],
        "data_models": ["Task"],
        "environment_variables": {"DB_URL": "jdbc:postgresql://localhost/db"},
        "implementation_steps": [],
        "spec_compliance_notes": [],
        "decisions": [],
        "review_iteration": 1,
        "review_feedback_applied": [],
    })


def _feedback(iteration: int = 1) -> ReviewFeedback:
    return ReviewFeedback(
        iteration=iteration,
        critical_issues=["SQL injection in task query"],
        high_issues=["Missing input validation"],
        passed=False,
    )


# ─── BackendAgent ─────────────────────────────────────────────────────────────

class TestBackendAgent:
    async def test_run_returns_engineering_artifact(self, tmp_path):
        agent = BackendAgent(artifacts_dir=str(tmp_path))
        # _query_and_parse_chunked calls _raw_query twice (plan + fill)
        mock = AsyncMock(side_effect=[
            _eng_response("backend"),  # plan phase (no __PENDING__ files — skip fill)
        ])
        with patch.object(agent, "_run_with_retry", new=mock):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract())
        assert isinstance(result, EngineeringArtifact)

    async def test_run_sets_service_name_backend(self, tmp_path):
        agent = BackendAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract())
        assert result.service_name == "backend"

    async def test_run_saves_artifact_file(self, tmp_path):
        agent = BackendAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch(), _contract())
        assert (tmp_path / "03a_backend_artifact.json").exists()

    async def test_run_applies_review_feedback(self, tmp_path):
        agent = BackendAgent(artifacts_dir=str(tmp_path))
        fb = _feedback()
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract(), review_feedback=fb)
        assert "SQL injection in task query" in result.review_feedback_applied
        assert "Missing input validation" in result.review_feedback_applied

    async def test_run_sets_review_iteration(self, tmp_path):
        agent = BackendAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract(), iteration=3)
        assert result.review_iteration == 3

    async def test_write_service_files_creates_files(self, tmp_path):
        agent = BackendAgent(artifacts_dir=str(tmp_path), generated_dir_name="gen")
        artifact = EngineeringArtifact(
            generated_files=[
                FileSpec(path="src/main.kt", purpose="Entry", content="fun main() {}"),
                FileSpec(path="src/service/TaskService.kt", purpose="Service", content="class TaskService {}"),
            ]
        )
        agent._write_service_files(artifact)
        assert (tmp_path / "gen" / "src" / "main.kt").exists()
        assert (tmp_path / "gen" / "src" / "service" / "TaskService.kt").exists()

    def test_build_contract_section_with_full_contract(self):
        agent = BackendAgent(artifacts_dir="/tmp")
        section = agent._build_contract_section(_contract())
        assert "openapi" in section.lower()
        assert "CREATE TABLE" in section
        assert "Kotlin Spring Boot" in section
        assert "Three-tier" in section

    def test_build_contract_section_empty_contract(self):
        agent = BackendAgent(artifacts_dir="/tmp")
        section = agent._build_contract_section(GeneratedSpecArtifact())
        assert "Contract" in section

    def test_build_feedback_section_with_feedback(self):
        agent = BackendAgent(artifacts_dir="/tmp")
        fb = _feedback(iteration=2)
        section = agent._build_feedback_section(fb)
        assert "SQL injection" in section
        assert "Missing input validation" in section
        assert "iteration 2" in section

    def test_build_feedback_section_without_feedback_returns_empty(self):
        agent = BackendAgent(artifacts_dir="/tmp")
        assert agent._build_feedback_section(None) == ""


# ─── BffAgent ─────────────────────────────────────────────────────────────────

class TestBffAgent:
    async def test_run_returns_engineering_artifact(self, tmp_path):
        agent = BffAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response("bff"))):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract())
        assert isinstance(result, EngineeringArtifact)

    async def test_run_sets_service_name_bff(self, tmp_path):
        agent = BffAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response("bff"))):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract())
        assert result.service_name == "bff"

    async def test_run_saves_bff_artifact_file(self, tmp_path):
        agent = BffAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response("bff"))):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch(), _contract())
        assert (tmp_path / "03b_bff_artifact.json").exists()

    def test_build_contract_section_includes_openapi(self):
        agent = BffAgent(artifacts_dir="/tmp")
        section = agent._build_contract_section(_contract())
        assert "openapi" in section.lower()

    def test_build_contract_section_skips_missing_fields(self):
        agent = BffAgent(artifacts_dir="/tmp")
        section = agent._build_contract_section(GeneratedSpecArtifact(openapi_spec="openapi: '3.0.0'"))
        assert "openapi" in section.lower()

    def test_build_feedback_section_with_only_high_issues(self):
        agent = BffAgent(artifacts_dir="/tmp")
        fb = ReviewFeedback(iteration=1, critical_issues=[], high_issues=["Rate limiting missing"], passed=False)
        section = agent._build_feedback_section(fb)
        assert "Rate limiting missing" in section

    async def test_run_applies_review_feedback(self, tmp_path):
        agent = BffAgent(artifacts_dir=str(tmp_path))
        fb = _feedback()
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=_eng_response("bff"))):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract(), review_feedback=fb)
        assert result.review_feedback_applied


# ─── FrontendAgent ────────────────────────────────────────────────────────────

class TestFrontendAgent:
    def _fe_response(self) -> str:
        return json.dumps({
            "service_name": "frontend",
            "services": {},
            "generated_files": [
                {"path": "src/App.tsx", "purpose": "Root component", "content": "export default function App() { return <div/>; }"},
            ],
            "api_endpoints": [],
            "data_models": ["Task"],
            "environment_variables": {},
            "implementation_steps": [],
            "spec_compliance_notes": [],
            "decisions": [],
            "review_iteration": 1,
            "review_feedback_applied": [],
        })

    async def test_run_returns_engineering_artifact(self, tmp_path):
        agent = FrontendAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=self._fe_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract())
        assert isinstance(result, EngineeringArtifact)

    async def test_run_sets_service_name_frontend(self, tmp_path):
        agent = FrontendAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=self._fe_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract())
        assert result.service_name == "frontend"

    async def test_run_saves_frontend_artifact_file(self, tmp_path):
        agent = FrontendAgent(artifacts_dir=str(tmp_path))
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=self._fe_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                await agent.run(_intent(), _arch(), _contract())
        assert (tmp_path / "03c_frontend_artifact.json").exists()

    def test_build_contract_section_includes_openapi(self):
        agent = FrontendAgent(artifacts_dir="/tmp")
        section = agent._build_contract_section(_contract())
        assert "openapi" in section.lower()

    def test_build_contract_section_without_spec(self):
        agent = FrontendAgent(artifacts_dir="/tmp")
        section = agent._build_contract_section(GeneratedSpecArtifact())
        assert "Contract" in section

    async def test_run_applies_review_feedback(self, tmp_path):
        agent = FrontendAgent(artifacts_dir=str(tmp_path))
        fb = ReviewFeedback(iteration=1, critical_issues=["XSS vulnerability"], high_issues=[], passed=False)
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value=self._fe_response())):
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await agent.run(_intent(), _arch(), _contract(), review_feedback=fb)
        assert "XSS vulnerability" in result.review_feedback_applied
