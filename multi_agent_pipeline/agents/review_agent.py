"""
Review Agent — audits engineering output for quality, security, reliability.
"""

from __future__ import annotations

from models.artifacts import (
    ArchitectureArtifact,
    EngineeringArtifact,
    IntentArtifact,
    ReviewArtifact,
)
from .base_agent import BaseAgent, load_prompt

SYSTEM_PROMPT = load_prompt("review_agent.md")


class ReviewAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Review Agent", artifacts_dir=artifacts_dir)

    async def run(
        self,
        intent: IntentArtifact,
        architecture: ArchitectureArtifact,
        engineering: EngineeringArtifact,
    ) -> ReviewArtifact:
        user_message = f"""Review these pipeline artifacts for quality, security, and reliability.

## Intent Summary
{self._compact(intent)}

## Architecture Summary
{self._compact(architecture)}

## Engineering Summary
{self._compact(engineering)}

Be specific about every issue found. Respond ONLY with the JSON block."""

        artifact = await self._query_and_parse(
            system=SYSTEM_PROMPT,
            user_message=user_message,
            model_class=ReviewArtifact,
        )

        self.save_artifact(artifact, "04_review_artifact.json")
        self.save_history()
        return artifact
