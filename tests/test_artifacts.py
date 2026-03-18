"""
Unit tests for artifact data models.
"""

import pytest
from llm_sdlc_workflow.models.artifacts import (
    DiscoveryArtifact,
    ArchitectureArtifact,
    GeneratedSpecArtifact,
)


class TestDiscoveryArtifact:
    def test_coerces_str_list_fields(self):
        """LLM sometimes returns dicts instead of strings — coercion must handle it."""
        artifact = DiscoveryArtifact(
            raw_requirements="Build a task API",
            requirements=[{"description": "User auth"}, "CRUD tasks"],
            user_goals=["Fast delivery"],
            constraints=["Must use PostgreSQL"],
            success_criteria=["All endpoints return < 200ms"],
            key_features=["JWT auth"],
            domain_context="Task management",
            scope="REST API only",
        )
        assert artifact.requirements == ["User auth", "CRUD tasks"]

    def test_optional_tech_preferences_defaults_to_none(self):
        artifact = DiscoveryArtifact(
            raw_requirements="x",
            requirements=["r"],
            user_goals=["g"],
            constraints=[],
            success_criteria=[],
            key_features=[],
            domain_context="x",
            scope="x",
        )
        assert artifact.tech_preferences is None


class TestGeneratedSpecArtifact:
    def test_defaults_are_empty(self):
        spec = GeneratedSpecArtifact()
        assert spec.openapi_spec == ""
        assert spec.monorepo_services == []
        assert spec.service_ports == {}
