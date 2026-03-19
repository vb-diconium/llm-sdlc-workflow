"""
PipelineConfig — controls which agents run and what tech stack they target.

All fields have sensible defaults so existing code continues to work unchanged.
Pass an instance to Pipeline(..., config=PipelineConfig(...)) to customise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Component toggles ────────────────────────────────────────────────────────

@dataclass
class ComponentConfig:
    """Which service sub-agents are enabled.

    ``mobile_platforms`` is a list of platform names to generate simultaneously.
    Each entry spawns an independent MobileAgent running in parallel.

    Examples::

        ComponentConfig(mobile_platforms=["React Native"])          # single
        ComponentConfig(mobile_platforms=["iOS (Swift)", "Android (Kotlin)"])  # both native
        ComponentConfig(mobile_platforms=["Flutter"])               # cross-platform
    """
    backend: bool = True
    bff: bool = True
    frontend: bool = True
    mobile_platforms: List[str] = field(default_factory=list)
    # ^ empty list = mobile disabled; one or more entries = that many parallel agents

    @property
    def mobile(self) -> bool:
        """True when at least one mobile platform is configured."""
        return bool(self.mobile_platforms)


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


def platform_slug(platform: str) -> str:
    """Convert a platform name to a safe directory / dict key.

    Examples::

        platform_slug("React Native")      → "mobile_react_native"
        platform_slug("iOS (Swift)")        → "mobile_ios_swift"
        platform_slug("Android (Kotlin)")   → "mobile_android_kotlin"
        platform_slug("Flutter")            → "mobile_flutter"
    """
    slug = re.sub(r"[^a-z0-9]+", "_", platform.lower()).strip("_")
    return f"mobile_{slug}"


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

    # Single React Native mobile app
    Pipeline(config=PipelineConfig(
        components=ComponentConfig(mobile_platforms=["React Native"]),
    ))

    # Dual native: iOS + Android generated in parallel
    Pipeline(config=PipelineConfig(
        components=ComponentConfig(
            mobile_platforms=["iOS (Swift)", "Android (Kotlin)"],
        ),
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
        """Build from a plain dict (e.g. loaded from pipeline.yaml).

        Supports both the new list form and the old scalar for backward compat::

            # new
            components:
              mobile_platforms: ["iOS (Swift)", "Android (Kotlin)"]

            # old (still works)
            components:
              mobile: true
            tech:
              mobile_platform: "Flutter"
        """
        comp = d.get("components", {})
        tech = d.get("tech", {})

        # Resolve mobile_platforms — new list form takes precedence
        mobile_platforms: List[str] = comp.get("mobile_platforms") or []
        if not mobile_platforms:
            # Backward compat: components.mobile: true + (optional) tech.mobile_platform
            if comp.get("mobile"):
                plat = tech.get("mobile_platform") or "React Native"
                mobile_platforms = [plat]

        return cls(
            components=ComponentConfig(
                backend=comp.get("backend", True),
                bff=comp.get("bff", True),
                frontend=comp.get("frontend", True),
                mobile_platforms=mobile_platforms,
            ),
            tech=TechConfig(
                backend_language=tech.get("backend_language"),
                backend_framework=tech.get("backend_framework"),
                bff_language=tech.get("bff_language"),
                bff_framework=tech.get("bff_framework"),
                frontend_framework=tech.get("frontend_framework"),
                frontend_language=tech.get("frontend_language"),
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
        for p in self.components.mobile_platforms:
            svcs.append(platform_slug(p))
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
        for p in self.components.mobile_platforms:
            tech_parts.append(f"Mobile:{p}")
        tech_str = f"  [{', '.join(tech_parts)}]" if tech_parts else ""
        return f"Services: {', '.join(svcs)}{tech_str}"
