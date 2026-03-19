"""
PipelineConfig — controls which agents run and what tech stack they target.

All fields have sensible defaults so existing code continues to work unchanged.
Pass an instance to Pipeline(..., config=PipelineConfig(...)) to customise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ─── Component toggles ────────────────────────────────────────────────────────

@dataclass
class ComponentConfig:
    """Which service sub-agents are enabled."""
    backend: bool = True
    bff: bool = True
    frontend: bool = True
    mobile: bool = False          # React Native (iOS + Android) — opt-in


# ─── Tech-stack preferences ───────────────────────────────────────────────────

@dataclass
class TechConfig:
    """
    Language / framework preferences forwarded to each sub-agent via the
    system prompt.  Leave None to keep each agent's built-in default.
    """

    # Backend
    backend_language: Optional[str] = None       # e.g. "Python", "Kotlin", "Go", "Node.js"
    backend_framework: Optional[str] = None      # e.g. "FastAPI", "Spring Boot", "Gin", "Express"

    # BFF
    bff_language: Optional[str] = None           # e.g. "Kotlin", "Node.js"
    bff_framework: Optional[str] = None          # e.g. "Spring WebFlux", "NestJS"

    # Frontend
    frontend_framework: Optional[str] = None     # e.g. "React", "Vue", "Angular", "Next.js"
    frontend_language: Optional[str] = None      # e.g. "TypeScript", "JavaScript"

    # Mobile
    mobile_platform: Optional[str] = None        # e.g. "React Native", "Flutter", "iOS (Swift)", "Android (Kotlin)"

    def backend_hint(self) -> str:
        """Short human-readable hint, e.g. 'Python / FastAPI'."""
        parts = [p for p in [self.backend_language, self.backend_framework] if p]
        return " / ".join(parts) if parts else ""

    def bff_hint(self) -> str:
        parts = [p for p in [self.bff_language, self.bff_framework] if p]
        return " / ".join(parts) if parts else ""

    def frontend_hint(self) -> str:
        parts = [p for p in [self.frontend_framework, self.frontend_language] if p]
        return " / ".join(parts) if parts else ""

    def mobile_hint(self) -> str:
        return self.mobile_platform or "React Native"


# ─── Top-level config ─────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """
    Full pipeline configuration.

    Usage
    -----
    # Default (Kotlin BE + BFF + React FE — same as before)
    Pipeline(config=PipelineConfig())

    # Python/FastAPI backend only, no BFF, no frontend
    Pipeline(config=PipelineConfig(
        components=ComponentConfig(bff=False, frontend=False),
        tech=TechConfig(backend_language="Python", backend_framework="FastAPI"),
    ))

    # Add a React Native mobile app
    Pipeline(config=PipelineConfig(
        components=ComponentConfig(mobile=True),
        tech=TechConfig(mobile_platform="React Native"),
    ))

    # Full custom stack
    Pipeline(config=PipelineConfig(
        components=ComponentConfig(bff=False),
        tech=TechConfig(
            backend_language="Go", backend_framework="Gin",
            frontend_framework="Vue", frontend_language="TypeScript",
        ),
    ))
    """
    components: ComponentConfig = field(default_factory=ComponentConfig)
    tech: TechConfig = field(default_factory=TechConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineConfig":
        """Build from a plain dict (e.g. loaded from pipeline.yaml)."""
        comp = d.get("components", {})
        tech = d.get("tech", {})
        return cls(
            components=ComponentConfig(
                backend=comp.get("backend", True),
                bff=comp.get("bff", True),
                frontend=comp.get("frontend", True),
                mobile=comp.get("mobile", False),
            ),
            tech=TechConfig(
                backend_language=tech.get("backend_language"),
                backend_framework=tech.get("backend_framework"),
                bff_language=tech.get("bff_language"),
                bff_framework=tech.get("bff_framework"),
                frontend_framework=tech.get("frontend_framework"),
                frontend_language=tech.get("frontend_language"),
                mobile_platform=tech.get("mobile_platform"),
            ),
        )

    def enabled_services(self) -> List[str]:
        """Return list of enabled service names, in order."""
        svcs = []
        if self.components.backend:
            svcs.append("backend")
        if self.components.bff:
            svcs.append("bff")
        if self.components.frontend:
            svcs.append("frontend")
        if self.components.mobile:
            svcs.append("mobile")
        return svcs

    def summary(self) -> str:
        """One-line human-readable summary for console output."""
        svcs = self.enabled_services()
        tech_parts = []
        if self.components.backend and self.tech.backend_hint():
            tech_parts.append(f"BE:{self.tech.backend_hint()}")
        if self.components.bff and self.tech.bff_hint():
            tech_parts.append(f"BFF:{self.tech.bff_hint()}")
        if self.components.frontend and self.tech.frontend_hint():
            tech_parts.append(f"FE:{self.tech.frontend_hint()}")
        if self.components.mobile and self.tech.mobile_hint():
            tech_parts.append(f"Mobile:{self.tech.mobile_hint()}")
        tech_str = f"  [{', '.join(tech_parts)}]" if tech_parts else ""
        return f"Services: {', '.join(svcs)}{tech_str}"
