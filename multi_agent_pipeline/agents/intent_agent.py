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
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are an expert requirements analyst and senior product manager with 15+ years of experience
building complex software systems.

Your job is to deeply analyse the provided requirements and extract the core intent. You must:

1. Identify ALL distinct functional requirements
2. Uncover implicit goals the user may not have stated explicitly
3. Identify constraints (technical, business, regulatory, timeline)
4. Define clear, measurable success criteria
5. List the key features that must be implemented
6. Note technical preferences if mentioned
7. Describe the domain context
8. Define what is IN scope and what is OUT of scope
9. Surface risks and uncertainties early
10. Document every interpretation decision you make — what you understood, why, and what alternatives you rejected

You MUST respond with a single JSON object wrapped in a ```json ... ``` block matching this exact schema:

{
  "raw_requirements": "<the original requirements text>",
  "requirements": ["<requirement 1>", ...],
  "user_goals": ["<goal 1>", ...],
  "constraints": ["<constraint 1>", ...],
  "success_criteria": ["<criterion 1>", ...],
  "key_features": ["<feature 1>", ...],
  "tech_preferences": ["<preference 1>", ...],  // null if none stated
  "domain_context": "<paragraph describing the domain>",
  "scope": "<what is in-scope and what is explicitly out-of-scope>",
  "risks": ["<risk 1>", ...],
  "decisions": [
    {
      "decision": "<what you decided>",
      "rationale": "<why>",
      "alternatives_considered": ["<alt 1>", "<alt 2>"],
      "trade_offs": ["<trade-off 1>"],
      "timestamp": "<ISO 8601 datetime>"
    }
  ]
}

Be thorough. Every decision you make must appear in the decisions array with full rationale."""


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
