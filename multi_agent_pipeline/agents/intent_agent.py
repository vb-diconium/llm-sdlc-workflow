"""
Intent Agent — understands raw requirements and produces a structured IntentArtifact.

Responsibilities:
  - Parse and clarify ambiguous requirements
  - Identify user goals, constraints, and success criteria
  - Document what is in/out of scope
  - Record every interpretation decision with rationale
"""

from __future__ import annotations

from models.artifacts import IntentArtifact
from .base_agent import BaseAgent, load_prompt

SYSTEM_PROMPT = load_prompt("intent_agent.md")


class IntentAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Intent Agent", artifacts_dir=artifacts_dir)

    async def run(self, requirements: str) -> IntentArtifact:
        """
        Analyse raw requirements and return a validated IntentArtifact.
        Also saves the artifact and conversation history to disk.
        """
        user_message = f"""Please analyse the following requirements and produce the structured intent artifact.

## Requirements
{requirements}

Remember: respond ONLY with the JSON block. Document every interpretation decision."""

        artifact = await self._query_and_parse(
            system=SYSTEM_PROMPT,
            user_message=user_message,
            model_class=IntentArtifact,
        )

        self.save_artifact(artifact, "01_intent_artifact.json")
        self.save_history()
        return artifact
