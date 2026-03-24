"""
Discovery Agent — analyses raw requirements and produces a structured DiscoveryArtifact.

Position in the SDLC: FIRST — before Architecture, Spec, and Engineering.

Responsibilities:
  - Parse and clarify ambiguous requirements
  - Uncover implicit goals the user may not have stated explicitly
  - Identify constraints (technical, business, regulatory, timeline)
  - Define scope boundaries (in-scope / out-of-scope)
  - Surface risks and uncertainties early
  - Record every interpretation decision with rationale
"""

from __future__ import annotations

from llm_sdlc_workflow.models.artifacts import DiscoveryArtifact
from rich.rule import Rule
from .base_agent import BaseAgent, load_prompt, console

SYSTEM_PROMPT = load_prompt("discovery_agent.md")


class DiscoveryAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts", generated_dir_name: str = "generated"):
        super().__init__(name="Discovery Agent", artifacts_dir=artifacts_dir, generated_dir_name=generated_dir_name)

    async def run(self, requirements: str) -> DiscoveryArtifact:
        """
        Analyse raw requirements and return a validated DiscoveryArtifact.

        Two-phase approach for faster perceived progress:
          Phase 1 — Facts: requirements, goals, scope, constraints, risks
          Phase 2 — Decisions: interpretation decisions derived from Phase 1

        Splitting avoids one huge slow response and lets the user see
        intermediate output sooner.
        """
        # ── Phase 1: core facts ──────────────────────────────────────────────
        phase1_message = f"""Please analyse the following requirements and produce the structured intent artifact.

## Requirements
{requirements}

Set the "decisions" field to an empty array []. You will fill decisions in a follow-up step.
Respond ONLY with the JSON block."""

        console.print(Rule("[bold cyan]Discovery Agent — phase 1: requirements & scope[/bold cyan]"))
        self._add_to_history("user", phase1_message)
        raw1 = await self._run_with_retry(SYSTEM_PROMPT, phase1_message)
        self._add_to_history("assistant", raw1 or "")
        console.print(Rule())

        if not raw1:
            raise ValueError("Discovery Agent (phase 1) returned empty response.")

        data = self._extract_json(raw1)
        data.setdefault("decisions", [])

        # ── Phase 2: interpretation decisions ───────────────────────────────
        phase2_message = f"""Based on the requirements analysis you just produced, generate the "decisions" list.

For each ambiguity or interpretation choice you made, record:
  - decision: what you chose
  - rationale: why
  - alternatives_considered: list of other options you rejected
  - trade_offs: what was accepted/sacrificed

Limit to the 8 most important decisions. Respond ONLY with JSON:
{{"decisions": [ ... ]}}"""

        console.print(Rule("[bold cyan]Discovery Agent — phase 2: decisions[/bold cyan]"))
        self._add_to_history("user", phase2_message)
        raw2 = await self._run_with_retry(SYSTEM_PROMPT, phase2_message)
        self._add_to_history("assistant", raw2 or "")
        console.print(Rule())

        if raw2:
            try:
                dec_data = self._extract_json(raw2)
                data["decisions"] = dec_data.get("decisions", [])
            except Exception:
                pass  # decisions are non-critical — proceed without them

        artifact = DiscoveryArtifact(**data)
        self.save_artifact(artifact, "01_discovery_artifact.json")
        self.save_history()
        return artifact
