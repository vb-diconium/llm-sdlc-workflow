"""
Testing Agent — verifies the application at each pipeline stage.

IMPORTANT: The Testing Agent ONLY uses IntentArtifact to derive test cases.
It does NOT receive SpecArtifact — specs are an implementation concern for
Architecture and Engineering; testing must validate against user intent only.

Runs at three stages:
  architecture  — does the design satisfy requirements?
  engineering   — does the implementation match the architecture and requirements?
  review        — final check after review findings
"""

from __future__ import annotations

from typing import Optional

from models.artifacts import (
    ArchitectureArtifact,
    EngineeringArtifact,
    IntentArtifact,
    ReviewArtifact,
    TestingArtifact,
)
from .base_agent import BaseAgent, load_prompt

SYSTEM_PROMPT = load_prompt("testing_agent.md")


class TestingAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Testing Agent", artifacts_dir=artifacts_dir)

    async def run(
        self,
        stage: str,
        intent: IntentArtifact,
        architecture: Optional[ArchitectureArtifact] = None,
        engineering: Optional[EngineeringArtifact] = None,
        review: Optional[ReviewArtifact] = None,
    ) -> TestingArtifact:
        if stage not in ("architecture", "engineering", "review"):
            raise ValueError(f"Invalid stage: {stage!r}")

        # Intent is always the source of truth for test cases
        context = f"## Intent (source of truth for all test cases)\n{self._compact(intent)}"

        if architecture:
            context += f"\n\n## Architecture (what was designed)\n{self._compact(architecture)}"
        if engineering:
            context += f"\n\n## Engineering (what was built)\n{self._compact(engineering)}"
        if review:
            context += f"\n\n## Review findings\n{self._compact(review)}"

        stage_instruction = {
            "architecture": (
                "Verify the Architecture satisfies ALL requirements and success criteria "
                "from the Intent. Flag any requirement the architecture ignores or contradicts."
            ),
            "engineering": (
                "Verify the Engineering implementation satisfies ALL requirements from the Intent "
                "and follows the Architecture. Check completeness of the implementation plan."
            ),
            "review": (
                "Final verification: does the full system — intent + architecture + implementation "
                "— deliver what was originally requested? Are review findings addressed?"
            ),
        }[stage]

        user_message = f"""Perform {stage.upper()} stage testing.

{stage_instruction}

{context}

Test cases must be derived from the Intent's requirements and success criteria.
Respond ONLY with the JSON block."""

        artifact = await self._query_and_parse(
            system=SYSTEM_PROMPT,
            user_message=user_message,
            model_class=TestingArtifact,
        )

        filename = {
            "architecture": "05a_testing_architecture.json",
            "engineering": "05b_testing_engineering.json",
            "review": "05c_testing_review.json",
        }[stage]

        self.save_artifact(artifact, filename)
        self.save_history()
        return artifact
