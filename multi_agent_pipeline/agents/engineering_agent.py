"""
Engineering Agent — selects tech stack and generates implementation files.
Accepts an optional SpecArtifact to constrain technology choices and code.
"""

from __future__ import annotations

import os
from typing import Optional

from models.artifacts import (
    ArchitectureArtifact,
    EngineeringArtifact,
    IntentArtifact,
    SpecArtifact,
)
from .base_agent import BaseAgent, load_prompt

SYSTEM_PROMPT = load_prompt("engineering_agent.md")


class EngineeringAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Engineering Agent", artifacts_dir=artifacts_dir)

    async def run(
        self,
        intent: IntentArtifact,
        architecture: ArchitectureArtifact,
        spec: Optional[SpecArtifact] = None,
    ) -> EngineeringArtifact:
        spec_section = ""
        if spec:
            parts = []
            if spec.tech_stack_constraints:
                parts.append(f"**Tech stack constraints (MUST use):**\n{spec.tech_stack_constraints}")
            if spec.api_spec:
                parts.append(f"**API spec — implement this exactly:**\n```\n{spec.api_spec[:3000]}\n```")
            if spec.database_schema:
                parts.append(f"**Database schema — use this:**\n```\n{spec.database_schema[:2000]}\n```")
            for name, content in spec.additional_specs.items():
                parts.append(f"**{name}:**\n```\n{content[:1000]}\n```")
            if parts:
                spec_section = "\n\n## Technical Specifications (MUST be honoured)\n" + "\n\n".join(parts)

        user_message = f"""Select the technology stack and generate the implementation.

## Intent Summary
{self._compact(intent)}

## Architecture Summary
{self._compact(architecture)}
{spec_section}

Generate REAL, COMPLETE, RUNNABLE code in generated_files.
Respond ONLY with the JSON block."""

        artifact = await self._query_and_parse(
            system=SYSTEM_PROMPT,
            user_message=user_message,
            model_class=EngineeringArtifact,
        )

        self.save_artifact(artifact, "03_engineering_artifact.json")
        self._write_generated_files(artifact)
        self.save_history()
        return artifact

    def _write_generated_files(self, artifact: EngineeringArtifact) -> None:
        generated_dir = os.path.join(self.artifacts_dir, "generated")
        os.makedirs(generated_dir, exist_ok=True)
        from rich.console import Console
        c = Console()
        for file_spec in artifact.generated_files:
            safe_path = os.path.normpath(file_spec.path).lstrip(os.sep)
            full_path = os.path.join(generated_dir, safe_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(file_spec.content)
            c.print(f"[dim]  📄 Generated: {full_path}[/dim]")
