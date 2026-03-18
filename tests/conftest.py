"""
Shared pytest fixtures used across all test modules.
"""

from __future__ import annotations

import pytest

from llm_sdlc_workflow.models.artifacts import (
    ArchitectureArtifact,
    ComponentSpec,
    DecisionRecord,
    DiscoveryArtifact,
    EngineeringArtifact,
    GeneratedSpecArtifact,
    HttpTestCase,
    IaCFile,
    InfrastructureArtifact,
    Issue,
    ReviewArtifact,
    ServiceArtifact,
    SpecArtifact,
    TestCase,
    TestingArtifact,
    TechStack,
)


# ─── Discovery ───────────────────────────────────────────────────────────────


@pytest.fixture
def discovery_artifact() -> DiscoveryArtifact:
    return DiscoveryArtifact(
        raw_requirements="Build a task management REST API",
        requirements=["User authentication via JWT", "CRUD operations for tasks"],
        user_goals=["Fast delivery", "Secure API"],
        constraints=["Must use PostgreSQL", "Python only"],
        success_criteria=["All endpoints return < 200ms", "100% auth coverage"],
        key_features=["JWT auth", "Task CRUD", "User management"],
        tech_preferences=["Python", "FastAPI"],
        domain_context="Task management SaaS",
        scope="REST API backend only",
        risks=["Scope creep", "Auth complexity"],
    )


# ─── Architecture ─────────────────────────────────────────────────────────────


@pytest.fixture
def architecture_artifact() -> ArchitectureArtifact:
    return ArchitectureArtifact(
        system_overview="Three-tier REST API with JWT authentication",
        architecture_style="Monolith",
        components=[
            ComponentSpec(
                name="API Server",
                responsibility="Handle HTTP requests and business logic",
                interfaces=["REST/HTTP"],
                dependencies=["Database"],
                technology_hint="FastAPI",
            ),
            ComponentSpec(
                name="Database",
                responsibility="Persist task and user data",
                interfaces=["SQL"],
                dependencies=[],
                technology_hint="PostgreSQL",
            ),
        ],
        data_flow=["Client → API Server → Database"],
        api_design=["GET /tasks", "POST /tasks", "PUT /tasks/{id}", "DELETE /tasks/{id}"],
        database_design="PostgreSQL with tasks and users tables",
        security_design="JWT Bearer tokens, bcrypt password hashing",
        deployment_strategy="Docker Compose single-host",
        patterns_used=["Repository pattern", "Dependency injection"],
        scalability_considerations=["Horizontal scaling behind load balancer"],
        trade_offs=["Monolith is simpler but harder to scale independently"],
    )


# ─── Spec ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def generated_spec_artifact() -> GeneratedSpecArtifact:
    return GeneratedSpecArtifact(
        openapi_spec="openapi: '3.0.0'\ninfo:\n  title: Task API\n  version: '1.0.0'\n",
        database_schema="CREATE TABLE tasks (id SERIAL PRIMARY KEY, title TEXT NOT NULL);",
        tech_stack_constraints="Python 3.11, FastAPI, PostgreSQL",
        monorepo_services=["backend"],
        service_ports={"backend": 8080},
        shared_models=["Task", "User"],
    )


# ─── Engineering ──────────────────────────────────────────────────────────────


@pytest.fixture
def engineering_artifact() -> EngineeringArtifact:
    return EngineeringArtifact(
        services={},
        generated_files=[],
        review_iteration=1,
        api_endpoints=["GET /tasks", "POST /tasks"],
        data_models=["Task", "User"],
    )


# ─── Infrastructure ───────────────────────────────────────────────────────────


@pytest.fixture
def infra_plan_artifact() -> InfrastructureArtifact:
    return InfrastructureArtifact(
        iac_files=[
            IaCFile(
                path="Dockerfile",
                content="FROM python:3.11-slim\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\"]",
                purpose="Application container image",
            ),
            IaCFile(
                path="docker-compose.yml",
                content="version: '3.8'\nservices:\n  api:\n    build: .\n",
                purpose="Multi-service orchestration",
            ),
        ],
        primary_service_port=8080,
        health_check_path="/health",
        phase="plan",
        container_running=False,
    )


@pytest.fixture
def infra_apply_artifact() -> InfrastructureArtifact:
    return InfrastructureArtifact(
        iac_files=[
            IaCFile(
                path="Dockerfile",
                content="FROM python:3.11-slim",
                purpose="Application container image",
            ),
        ],
        primary_service_port=8080,
        health_check_path="/health",
        phase="apply",
        container_running=False,
        base_url=None,
    )


# ─── Review ───────────────────────────────────────────────────────────────────


@pytest.fixture
def review_passed() -> ReviewArtifact:
    return ReviewArtifact(
        iteration=1,
        overall_score=85,
        security_score=80,
        reliability_score=90,
        maintainability_score=85,
        performance_score=82,
        passed=True,
        critical_issues=[],
        high_issues=["Consider adding rate limiting"],
        issues=[
            Issue(
                severity="high",
                category="performance",
                description="No rate limiting on auth endpoint",
                location="POST /auth/login",
                recommendation="Add rate limiting middleware",
            )
        ],
        strengths=["Good JWT implementation", "Clear code structure"],
        recommendations=["Add OpenAPI docs", "Improve error messages"],
    )


@pytest.fixture
def review_failed() -> ReviewArtifact:
    return ReviewArtifact(
        iteration=1,
        overall_score=35,
        security_score=20,
        reliability_score=50,
        maintainability_score=60,
        performance_score=40,
        passed=False,
        critical_issues=["SQL injection vulnerability in task query", "Plaintext password storage"],
        high_issues=["No input validation", "Missing HTTPS enforcement"],
        issues=[
            Issue(
                severity="critical",
                category="security",
                description="SQL injection via unsanitised task title",
                location="GET /tasks?filter=",
                recommendation="Use parameterised queries",
                cwe_id="CWE-89",
            )
        ],
    )


# ─── Testing ──────────────────────────────────────────────────────────────────


@pytest.fixture
def testing_passed() -> TestingArtifact:
    return TestingArtifact(
        stage="architecture",
        test_cases=[
            TestCase(
                id="tc001",
                name="JWT auth flow",
                description="Verify JWT issuance and validation",
                requirement_covered="User authentication via JWT",
                test_type="unit",
                steps=["POST /auth/login with valid creds", "Extract JWT", "Call protected endpoint"],
                expected_outcome="200 OK with valid JWT",
                status="passed",
            ),
            TestCase(
                id="tc002",
                name="Task CRUD",
                description="Verify full task lifecycle",
                requirement_covered="CRUD operations for tasks",
                test_type="integration",
                steps=["POST /tasks", "GET /tasks/{id}", "PUT /tasks/{id}", "DELETE /tasks/{id}"],
                expected_outcome="All operations return expected status codes",
                status="passed",
            ),
        ],
        coverage_areas=["Authentication", "Task management"],
        uncovered_areas=[],
        findings=["All core requirements covered"],
        blocking_issues=[],
        passed=True,
        recommendations=["Add load tests"],
    )


@pytest.fixture
def testing_failed() -> TestingArtifact:
    return TestingArtifact(
        stage="infrastructure",
        test_cases=[
            TestCase(
                id="tc003",
                name="Service health check",
                description="Verify /health endpoint",
                requirement_covered="Service availability",
                test_type="integration",
                steps=["GET /health"],
                expected_outcome="200 OK",
                status="failed",
            ),
        ],
        coverage_areas=["Service availability"],
        uncovered_areas=["Auth", "Task management"],
        findings=["Service not reachable on port 8080"],
        blocking_issues=["Cannot connect to backend service on port 8080"],
        passed=False,
        failed_services=["backend"],
        recommendations=["Check Dockerfile CMD and port binding"],
    )


# ─── Spec (user-provided) ─────────────────────────────────────────────────────


@pytest.fixture
def user_spec() -> SpecArtifact:
    return SpecArtifact(
        architecture_constraints="Must use three-tier architecture",
        tech_stack_constraints="Python 3.11, FastAPI, PostgreSQL, React 18",
        api_spec="openapi: '3.0.0'\ninfo:\n  title: MyAPI\n",
        database_schema="CREATE TABLE tasks (id SERIAL PRIMARY KEY);",
    )
