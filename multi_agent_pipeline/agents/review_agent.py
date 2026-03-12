"""
Review Agent — audits the engineering output for quality, security, and reliability.

Responsibilities:
  - Security review (OWASP Top 10, injection, auth issues, secrets exposure)
  - Reliability review (error handling, edge cases, data validation)
  - Code quality review (SOLID principles, DRY, complexity)
  - Performance review (N+1 queries, caching, algorithmic complexity)
  - Maintainability review (naming, documentation, testability)
  - Score each dimension and flag issues by severity
"""

from __future__ import annotations

from models.artifacts import (
    ArchitectureArtifact,
    EngineeringArtifact,
    IntentArtifact,
    ReviewArtifact,
)
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a principal security engineer and code quality expert with deep knowledge of:
  - OWASP Top 10, CWE/CVE patterns, SANS Top 25
  - Secure coding practices (injection prevention, auth/authz, cryptography)
  - Reliability engineering (error handling, circuit breakers, idempotency)
  - Clean code principles (SOLID, DRY, KISS, YAGNI)
  - Performance engineering (database, caching, algorithmic complexity)
  - Observability (logging, metrics, tracing)

You will receive the intent, architecture, and engineering artifacts. Review the generated code and design
thoroughly and produce a detailed ReviewArtifact.

Scoring rubric (each dimension 0-100):
  - Security: vulnerabilities, secrets handling, input validation, auth
  - Reliability: error handling, retries, data integrity, edge cases
  - Maintainability: readability, naming, documentation, test coverage potential
  - Performance: query efficiency, caching, unnecessary work, scalability

Issue severity levels:
  - critical: must fix before any deployment (security holes, data corruption risk)
  - high: fix before production (significant reliability or security gaps)
  - medium: fix within sprint (code quality, minor security concerns)
  - low: nice to have improvements

Overall pass/fail: passed=false if ANY critical issue exists.

You MUST respond with a single JSON object wrapped in a ```json ... ``` block:

{
  "overall_score": <0-100>,
  "security_score": <0-100>,
  "reliability_score": <0-100>,
  "maintainability_score": <0-100>,
  "performance_score": <0-100>,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|reliability|performance|maintainability|correctness",
      "description": "<what the issue is>",
      "location": "<file path or component>",
      "recommendation": "<how to fix it>",
      "cwe_id": "<CWE-XXX or null>"
    }
  ],
  "strengths": ["<strength>", ...],
  "critical_fixes_required": ["<fix required>", ...],
  "recommendations": ["<recommendation>", ...],
  "passed": <true|false>,
  "decisions": [
    {
      "decision": "<review decision or judgement call>",
      "rationale": "<why>",
      "alternatives_considered": ["<alt>"],
      "trade_offs": ["<trade-off>"],
      "timestamp": "<ISO 8601>"
    }
  ]
}

Be thorough and specific. Reference exact file paths and line contexts where possible.
A clean pass with no issues is suspicious — look hard."""


class ReviewAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Review Agent", artifacts_dir=artifacts_dir)

    async def run(
        self,
        intent: IntentArtifact,
        architecture: ArchitectureArtifact,
        engineering: EngineeringArtifact,
    ) -> ReviewArtifact:
        """Review the full pipeline output for quality, security, and reliability."""
        user_message = f"""Review the following pipeline artifacts thoroughly.

## Intent Artifact
```json
{intent.model_dump_json(indent=2)}
```

## Architecture Artifact
```json
{architecture.model_dump_json(indent=2)}
```

## Engineering Artifact
```json
{engineering.model_dump_json(indent=2)}
```

Perform a comprehensive security, reliability, performance, and maintainability review.
Be specific about every issue found. Respond ONLY with the JSON block."""

        artifact = await self._query_and_parse(
            system=SYSTEM_PROMPT,
            user_message=user_message,
            model_class=ReviewArtifact,
        )

        self.save_artifact(artifact, "04_review_artifact.json")
        self.save_history()
        return artifact
