"""
Engineering Agent — orchestrates BackendAgent, BffAgent, FrontendAgent, and (optionally)
MobileAgent to generate the full monorepo in parallel.

All enabled sub-agents receive the same GeneratedSpecArtifact (forward contract)
so their code is consistent with each other from the start.

assemble() merges per-service outputs into a single flat EngineeringArtifact
that the rest of the pipeline consumes.
"""

from __future__ import annotations

import asyncio
from typing import Optional, TYPE_CHECKING

from rich.console import Console

from llm_sdlc_workflow.models.artifacts import (
    ArchitectureArtifact,
    DiscoveryArtifact,
    EngineeringArtifact,
    GeneratedSpecArtifact,
    ReviewFeedback,
    ServiceArtifact,
)
from .backend_agent import BackendAgent
from .bff_agent import BffAgent
from .frontend_agent import FrontendAgent
from .mobile_agent import MobileAgent
from .base_agent import BaseAgent

if TYPE_CHECKING:
    from llm_sdlc_workflow.config import PipelineConfig

console = Console()


class EngineeringAgent(BaseAgent):
    def __init__(
        self,
        artifacts_dir: str = "./artifacts",
        generated_dir_name: str = "generated",
        config: Optional["PipelineConfig"] = None,
    ):
        super().__init__(name="Engineering Agent", artifacts_dir=artifacts_dir, generated_dir_name=generated_dir_name)
        # Import here to avoid circular import at module load time
        from llm_sdlc_workflow.config import PipelineConfig, ComponentConfig, TechConfig
        cfg = config or PipelineConfig()
        self._config = cfg

        # Conditionally instantiate sub-agents based on config
        self.backend_agent = (
            BackendAgent(artifacts_dir, generated_dir_name=generated_dir_name,
                         language=cfg.tech.backend_language, framework=cfg.tech.backend_framework)
            if cfg.components.backend else None
        )
        self.bff_agent = (
            BffAgent(artifacts_dir, generated_dir_name=generated_dir_name,
                     language=cfg.tech.bff_language, framework=cfg.tech.bff_framework)
            if cfg.components.bff else None
        )
        self.frontend_agent = (
            FrontendAgent(artifacts_dir, generated_dir_name=generated_dir_name,
                          framework=cfg.tech.frontend_framework, language=cfg.tech.frontend_language)
            if cfg.components.frontend else None
        )
        # One MobileAgent per configured platform — all run in parallel
        self.mobile_agents: list[MobileAgent] = [
            MobileAgent(artifacts_dir, generated_dir_name=generated_dir_name, platform=p)
            for p in cfg.components.mobile_platforms
        ]

    async def run(
        self,
        intent: DiscoveryArtifact,
        architecture: ArchitectureArtifact,
        contract: GeneratedSpecArtifact,
        review_feedback: Optional[ReviewFeedback] = None,
        iteration: int = 1,
    ) -> EngineeringArtifact:
        """Run enabled sub-agents in parallel, then assemble into one artifact."""
        active = {
            name: agent
            for name, agent in [
                ("backend",  self.backend_agent),
                ("bff",      self.bff_agent),
                ("frontend", self.frontend_agent),
            ]
            if agent is not None
        }
        # Add one entry per mobile platform (each has a unique slug key)
        for mobile_agent in self.mobile_agents:
            active[mobile_agent.slug] = mobile_agent
        console.print(
            f"[cyan]⚙  Engineering (iter {iteration}): "
            f"launching {', '.join(active.keys())} in parallel…[/cyan]"
        )
        results = await asyncio.gather(
            *[a.run(intent, architecture, contract, review_feedback, iteration)
              for a in active.values()]
        )
        service_artifacts = dict(zip(active.keys(), results))
        assembled = self._assemble(service_artifacts, iteration)
        self.save_artifact(assembled, "03_engineering_artifact.json")
        return assembled

    async def apply_review_feedback(
        self,
        intent: DiscoveryArtifact,
        architecture: ArchitectureArtifact,
        current: EngineeringArtifact,
        feedback: ReviewFeedback,
        contract: GeneratedSpecArtifact,
    ) -> EngineeringArtifact:
        """Re-run all sub-agents with review feedback. Increments review_iteration."""
        console.print(
            f"[yellow]🔄 Engineering: applying review feedback "
            f"(iter {current.review_iteration} → {current.review_iteration + 1})[/yellow]"
        )
        return await self.run(
            intent=intent,
            architecture=architecture,
            contract=contract,
            review_feedback=feedback,
            iteration=current.review_iteration + 1,
        )

    # ─── Assembly ────────────────────────────────────────────────────────────

    def _assemble(
        self,
        service_artifacts: dict,  # {service_name: EngineeringArtifact}
        iteration: int,
    ) -> EngineeringArtifact:
        """Merge per-service artifacts into one flat EngineeringArtifact."""
        all_files = [f for a in service_artifacts.values() for f in a.generated_files]
        all_endpoints = list({ep for a in service_artifacts.values() for ep in a.api_endpoints})
        all_models = list({m for a in service_artifacts.values() for m in a.data_models})
        all_env = {k: v for a in service_artifacts.values() for k, v in a.environment_variables.items()}
        all_steps = [s for a in service_artifacts.values() for s in a.implementation_steps]
        all_notes = [n for a in service_artifacts.values() for n in a.spec_compliance_notes]
        all_decisions = [d for a in service_artifacts.values() for d in a.decisions]
        all_feedback = [f for a in service_artifacts.values() for f in a.review_feedback_applied]

        be = service_artifacts.get("backend")
        fe = service_artifacts.get("frontend")

        svc_breakdown = ", ".join(
            f"{name} ({len(a.generated_files)} files)"
            for name, a in service_artifacts.items()
        )
        assembled = EngineeringArtifact(
            service_name=None,
            services={name: self._to_service(a) for name, a in service_artifacts.items()},
            backend_tech=be.backend_tech if be else None,
            frontend_tech=fe.frontend_tech if fe else None,
            infrastructure=" + ".join(
                f"{name} ({self._port_hint(name)})" for name in service_artifacts
            ),
            generated_files=all_files,
            implementation_steps=all_steps,
            environment_variables=all_env,
            api_endpoints=all_endpoints,
            data_models=all_models,
            spec_compliance_notes=all_notes,
            decisions=all_decisions,
            review_iteration=iteration,
            review_feedback_applied=all_feedback,
        )
        console.print(
            f"[green]✅ Engineering assembled: {svc_breakdown} = {len(all_files)} total files[/green]"
        )
        return assembled

    def _port_hint(self, service: str) -> str:
        defaults = {"backend": "8081", "bff": "8080", "frontend": "3000"}
        if service in defaults:
            return defaults[service]
        if service.startswith("mobile_"):
            return "BFF_BASE_URL"
        return "?"

    def _to_service(self, artifact: EngineeringArtifact) -> ServiceArtifact:
        return ServiceArtifact(
            service=artifact.service_name or "unknown",
            tech_stack=artifact.backend_tech or artifact.frontend_tech,
            generated_files=artifact.generated_files,
            api_endpoints=artifact.api_endpoints,
            data_models=artifact.data_models,
            environment_variables=artifact.environment_variables,
            implementation_steps=artifact.implementation_steps,
            spec_compliance_notes=artifact.spec_compliance_notes,
            decisions=artifact.decisions,
            review_iteration=artifact.review_iteration,
            review_feedback_applied=artifact.review_feedback_applied,
        )
