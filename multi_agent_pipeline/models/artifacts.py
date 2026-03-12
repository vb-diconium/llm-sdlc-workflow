"""
Artifact data models for all agents in the multi-agent pipeline.
Each agent produces a typed artifact that is persisted to disk and
passed downstream as context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DecisionRecord(BaseModel):
    """Captures a single architectural or implementation decision with full rationale."""

    decision: str
    rationale: str
    alternatives_considered: List[str]
    trade_offs: List[str] = []
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── Intent Agent ───────────────────────────────────────────────────────────


class IntentArtifact(BaseModel):
    """Output of the Intent Agent — the distilled understanding of what needs to be built."""

    raw_requirements: str
    requirements: List[str]
    user_goals: List[str]
    constraints: List[str]
    success_criteria: List[str]
    key_features: List[str]
    tech_preferences: Optional[List[str]] = None
    domain_context: str
    scope: str  # in-scope vs out-of-scope summary
    risks: List[str] = []
    decisions: List[DecisionRecord] = []


# ─── Architecture Agent ──────────────────────────────────────────────────────


class ComponentSpec(BaseModel):
    """Describes a single system component."""

    name: str
    responsibility: str
    interfaces: List[str]
    dependencies: List[str]
    technology_hint: Optional[str] = None


class ArchitectureArtifact(BaseModel):
    """Output of the Architecture Agent — the system design blueprint."""

    system_overview: str
    architecture_style: str  # e.g. microservices, monolith, serverless
    components: List[ComponentSpec]
    data_flow: List[str]
    api_design: List[str]
    database_design: str
    security_design: str
    deployment_strategy: str
    patterns_used: List[str]
    scalability_considerations: List[str]
    trade_offs: List[str]
    design_decisions: List[DecisionRecord]


# ─── Engineering Agent ───────────────────────────────────────────────────────


class TechStack(BaseModel):
    """Describes a technology choice for a tier."""

    framework: str
    language: str
    version: str
    key_libraries: List[str]
    rationale: str


class FileSpec(BaseModel):
    """Represents a file that should be created."""

    path: str
    purpose: str
    content: str  # actual file content or detailed spec


class ImplementationStep(BaseModel):
    step: int
    description: str
    files_involved: List[str]
    acceptance_criteria: List[str] = []


class EngineeringArtifact(BaseModel):
    """Output of the Engineering Agent — tech stack choices and code generation."""

    backend_tech: TechStack
    frontend_tech: Optional[TechStack] = None
    infrastructure: str
    generated_files: List[FileSpec]
    implementation_steps: List[ImplementationStep]
    environment_variables: Dict[str, str] = {}  # key -> description
    api_endpoints: List[str] = []
    data_models: List[str] = []
    decisions: List[DecisionRecord]


# ─── Review Agent ────────────────────────────────────────────────────────────


class Issue(BaseModel):
    """A specific issue found during code review."""

    severity: str  # critical | high | medium | low
    category: str  # security | reliability | performance | maintainability | correctness
    description: str
    location: str  # file path or component name
    recommendation: str
    cwe_id: Optional[str] = None  # Common Weakness Enumeration ID if applicable


class ReviewArtifact(BaseModel):
    """Output of the Review Agent — quality assessment of the engineering output."""

    overall_score: int = Field(ge=0, le=100)
    security_score: int = Field(ge=0, le=100)
    reliability_score: int = Field(ge=0, le=100)
    maintainability_score: int = Field(ge=0, le=100)
    performance_score: int = Field(ge=0, le=100)
    issues: List[Issue]
    strengths: List[str]
    critical_fixes_required: List[str]
    recommendations: List[str]
    passed: bool  # True if no critical issues
    decisions: List[DecisionRecord]


# ─── Testing Agent ───────────────────────────────────────────────────────────


class TestCase(BaseModel):
    """A single test case verifying a requirement or behaviour."""

    id: str
    name: str
    description: str
    requirement_covered: str
    test_type: str  # unit | integration | e2e | security | performance
    steps: List[str]
    expected_outcome: str
    actual_outcome: Optional[str] = None
    status: Optional[str] = None  # passed | failed | skipped | pending


class TestingArtifact(BaseModel):
    """Output of the Testing Agent at a given pipeline stage."""

    stage: str  # architecture | engineering | review
    test_cases: List[TestCase]
    coverage_areas: List[str]  # which requirements are covered
    uncovered_areas: List[str]  # requirements NOT covered by tests
    findings: List[str]
    blocking_issues: List[str]  # issues that must be fixed before proceeding
    passed: bool
    recommendations: List[str]
    decisions: List[DecisionRecord]
