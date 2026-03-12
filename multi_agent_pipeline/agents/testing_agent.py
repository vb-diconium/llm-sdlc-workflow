"""
Testing Agent — verifies the application at each pipeline stage against the original intent.

It runs three times:
  Stage 1 (architecture):  Does the architecture actually satisfy the requirements?
  Stage 2 (engineering):   Does the generated code implement the architecture and requirements?
  Stage 3 (review):        After review fixes, does the system still meet all requirements?

Responsibilities:
  - Generate test cases that map directly to each success criterion
  - Identify gaps (requirements with no test coverage)
  - Flag blocking issues that must be resolved before the pipeline proceeds
  - Track test case status and provide actionable recommendations
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
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a principal QA engineer and test architect specialising in requirements-based testing,
security testing, and continuous quality assurance.

You will be given a pipeline stage and the artifacts produced up to that stage. Your job is to:

1. Map EVERY success criterion from the IntentArtifact to one or more test cases
2. Generate specific, actionable test cases (unit, integration, e2e, security, performance)
3. Analyse each artifact against the test cases and determine pass/fail status
4. Identify which requirements have NO test coverage (uncovered_areas)
5. Flag blocking issues that must be resolved before the pipeline continues
6. Provide clear recommendations for improving testability and quality

Test case status rules:
  - "passed"  — the artifact clearly satisfies this test case
  - "failed"  — the artifact clearly violates or ignores this requirement
  - "pending" — cannot determine without running the code (generate the test anyway)
  - "skipped" — not applicable at this pipeline stage

You MUST respond with a single JSON object wrapped in a ```json ... ``` block:

{
  "stage": "<architecture|engineering|review>",
  "test_cases": [
    {
      "id": "TC-001",
      "name": "<short test name>",
      "description": "<what is being tested>",
      "requirement_covered": "<which requirement/success criterion>",
      "test_type": "unit|integration|e2e|security|performance",
      "steps": ["<step 1>", "<step 2>", ...],
      "expected_outcome": "<what should happen>",
      "actual_outcome": "<what the artifact shows — or null if pending>",
      "status": "passed|failed|pending|skipped"
    }
  ],
  "coverage_areas": ["<requirement covered>", ...],
  "uncovered_areas": ["<requirement NOT covered>", ...],
  "findings": ["<notable finding>", ...],
  "blocking_issues": ["<must-fix before proceeding>", ...],
  "passed": <true if no blocking issues and no failed critical test cases>,
  "recommendations": ["<recommendation>", ...],
  "decisions": [
    {
      "decision": "<testing decision>",
      "rationale": "<why>",
      "alternatives_considered": ["<alt>"],
      "trade_offs": ["<trade-off>"],
      "timestamp": "<ISO 8601>"
    }
  ]
}

Generate at minimum one test case per success criterion. Be critical — it is better to flag a
potential issue than to give a false green light."""


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
        """
        Run testing verification for the given pipeline stage.

        stage must be one of: "architecture", "engineering", "review"
        """
        if stage not in ("architecture", "engineering", "review"):
            raise ValueError(f"Invalid stage: {stage!r}")

        context_blocks = [
            f"## Intent Artifact\n```json\n{intent.model_dump_json(indent=2)}\n```"
        ]

        if architecture:
            context_blocks.append(
                f"## Architecture Artifact\n```json\n{architecture.model_dump_json(indent=2)}\n```"
            )
        if engineering:
            context_blocks.append(
                f"## Engineering Artifact\n```json\n{engineering.model_dump_json(indent=2)}\n```"
            )
        if review:
            context_blocks.append(
                f"## Review Artifact\n```json\n{review.model_dump_json(indent=2)}\n```"
            )

        stage_instructions = {
            "architecture": (
                "Verify that the Architecture Artifact correctly addresses ALL requirements and "
                "success criteria from the Intent Artifact. Flag any requirement that the architecture "
                "ignores, underspecifies, or contradicts."
            ),
            "engineering": (
                "Verify that the Engineering Artifact implements the Architecture and satisfies all "
                "requirements. Check that the generated code is complete, follows the architecture, "
                "and that the implementation plan covers all features."
            ),
            "review": (
                "Perform final verification. Confirm that the review issues have been acknowledged, "
                "that critical fixes are actionable, and that the overall system — intent + architecture "
                "+ implementation + review — will deliver what was originally requested."
            ),
        }[stage]

        user_message = f"""Perform {stage.upper()} stage testing.

{stage_instructions}

{chr(10).join(context_blocks)}

Generate comprehensive test cases for this stage. Respond ONLY with the JSON block."""

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
