"""Tests for TopologyContract — port assignment and topology section generation."""
import pytest
from llm_sdlc_workflow.config import (
    PipelineConfig,
    TopologyContract,
    ComponentConfig,
    TechConfig,
)


# ─── Port assignment ──────────────────────────────────────────────────────────

class TestTopologyContractPorts:
    def test_backend_only_gets_external_port_8080(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.service_ports["backend"] == 8080

    def test_backend_with_bff_gets_internal_port_8081(self):
        cfg = PipelineConfig(components=ComponentConfig(frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.service_ports["backend"] == 8081
        assert t.service_ports["bff"] == 8080

    def test_full_stack_port_assignments(self):
        cfg = PipelineConfig()
        t = TopologyContract.from_config(cfg)
        assert t.service_ports["backend"] == 8081
        assert t.service_ports["bff"] == 8080
        assert t.service_ports["frontend"] == 3000

    def test_backend_with_frontend_no_bff(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False))
        t = TopologyContract.from_config(cfg)
        assert t.service_ports["backend"] == 8081
        assert t.service_ports["frontend"] == 3000
        assert "bff" not in t.service_ports

    def test_mobile_platforms_get_zero_port(self):
        cfg = PipelineConfig(
            components=ComponentConfig(bff=False, frontend=False, mobile_platforms=["React Native"])
        )
        t = TopologyContract.from_config(cfg)
        assert t.service_ports.get("mobile_react_native") == 0


# ─── Primary service / port ───────────────────────────────────────────────────

class TestTopologyContractPrimary:
    def test_backend_only_is_primary(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.primary_service == "backend"
        assert t.primary_port == 8080

    def test_bff_is_primary_when_no_frontend(self):
        cfg = PipelineConfig(components=ComponentConfig(frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.primary_service == "bff"
        assert t.primary_port == 8080

    def test_frontend_is_primary_in_full_stack(self):
        cfg = PipelineConfig()
        t = TopologyContract.from_config(cfg)
        assert t.primary_service == "frontend"
        assert t.primary_port == 3000

    def test_frontend_is_primary_when_no_bff(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False))
        t = TopologyContract.from_config(cfg)
        assert t.primary_service == "frontend"
        assert t.primary_port == 3000


# ─── Flags ────────────────────────────────────────────────────────────────────

class TestTopologyContractFlags:
    def test_has_bff_false_when_disabled(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.has_bff is False
        assert t.has_frontend is False

    def test_has_bff_true_when_enabled(self):
        cfg = PipelineConfig(components=ComponentConfig(frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.has_bff is True

    def test_has_frontend_true_when_enabled(self):
        cfg = PipelineConfig()
        t = TopologyContract.from_config(cfg)
        assert t.has_frontend is True

    def test_enabled_services_matches_components(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        assert t.enabled_services == ["backend"]

        cfg2 = PipelineConfig(components=ComponentConfig(frontend=False))
        t2 = TopologyContract.from_config(cfg2)
        assert t2.enabled_services == ["backend", "bff"]

        cfg3 = PipelineConfig()
        t3 = TopologyContract.from_config(cfg3)
        assert t3.enabled_services == ["backend", "bff", "frontend"]


# ─── Architecture diagram ─────────────────────────────────────────────────────

class TestTopologyContractDiagram:
    def test_backend_only_diagram(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        assert "BACKEND (8080)" in t.architecture_diagram
        assert "BFF" not in t.architecture_diagram
        assert "FRONTEND" not in t.architecture_diagram
        assert "DB" in t.architecture_diagram

    def test_full_stack_diagram(self):
        cfg = PipelineConfig()
        t = TopologyContract.from_config(cfg)
        assert "FRONTEND (3000)" in t.architecture_diagram
        assert "BFF (8080)" in t.architecture_diagram
        assert "BACKEND (8081)" in t.architecture_diagram
        assert "DB" in t.architecture_diagram

    def test_diagram_left_to_right_order(self):
        cfg = PipelineConfig()
        t = TopologyContract.from_config(cfg)
        # Frontend must appear before BFF which must appear before Backend
        fe_pos = t.architecture_diagram.index("FRONTEND")
        bff_pos = t.architecture_diagram.index("BFF")
        be_pos = t.architecture_diagram.index("BACKEND")
        assert fe_pos < bff_pos < be_pos


# ─── topology_section() ───────────────────────────────────────────────────────

class TestTopologySection:
    def test_backend_only_topology_section_contains_port_8080(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        section = t.topology_section()
        assert "backend: 8080" in section
        assert "external" in section.lower()

    def test_bff_topology_section_marks_backend_internal(self):
        cfg = PipelineConfig(components=ComponentConfig(frontend=False))
        t = TopologyContract.from_config(cfg)
        section = t.topology_section()
        assert "backend: 8081" in section
        assert "internal" in section.lower()
        assert "bff: 8080" in section

    def test_topology_section_includes_inter_service_url_when_bff_present(self):
        cfg = PipelineConfig(components=ComponentConfig(frontend=False))
        t = TopologyContract.from_config(cfg)
        section = t.topology_section()
        assert "http://backend:8081" in section

    def test_topology_section_no_inter_service_url_when_no_bff(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        section = t.topology_section()
        assert "http://backend" not in section

    def test_topology_section_has_authoritative_header(self):
        cfg = PipelineConfig(components=ComponentConfig(bff=False, frontend=False))
        t = TopologyContract.from_config(cfg)
        section = t.topology_section()
        assert "authoritative" in section.lower()
