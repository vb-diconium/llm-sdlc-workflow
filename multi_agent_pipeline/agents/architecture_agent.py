"""
Architecture Agent — designs the system architecture from the intent artifact.

Responsibilities:
  - Choose an appropriate architecture style
  - Define all system components and their responsibilities
  - Design API contracts and data flow
  - Plan database schema approach
  - Address security and scalability from day one
  - Document every architectural decision with alternatives and trade-offs
"""

from __future__ import annotations

import json

from models.artifacts import ArchitectureArtifact, IntentArtifact
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a principal software architect with deep expertise in distributed systems,
cloud architecture, security, and scalability.

Given an IntentArtifact, you will design a comprehensive system architecture. Your design must:

1. Choose an architecture style that best fits the requirements (with justification)
2. Define all system components with clear responsibilities and interfaces
3. Design the data flow between components
4. Specify the API design (REST / GraphQL / gRPC, endpoints, auth strategy)
5. Design the database layer (SQL vs NoSQL, schema approach, indexing strategy)
6. Address security from the ground up (authentication, authorisation, data protection, OWASP considerations)
7. Plan for deployment and scalability
8. Identify design patterns being applied and why
9. Be explicit about trade-offs made

You MUST respond with a single JSON object wrapped in a ```json ... ``` block matching this exact schema:

{
  "system_overview": "<paragraph overview>",
  "architecture_style": "<monolith|microservices|serverless|event-driven|layered|etc>",
  "components": [
    {
      "name": "<component name>",
      "responsibility": "<what it does>",
      "interfaces": ["<interface 1>", ...],
      "dependencies": ["<dep 1>", ...],
      "technology_hint": "<suggested tech>"
    }
  ],
  "data_flow": ["<step 1: A → B via X>", ...],
  "api_design": ["<endpoint or contract description>", ...],
  "database_design": "<schema approach and rationale>",
  "security_design": "<auth, authz, encryption, threat model>",
  "deployment_strategy": "<containers/serverless/VMs, CI/CD, environments>",
  "patterns_used": ["<pattern: rationale>", ...],
  "scalability_considerations": ["<consideration>", ...],
  "trade_offs": ["<trade-off>", ...],
  "design_decisions": [
    {
      "decision": "<what was decided>",
      "rationale": "<why>",
      "alternatives_considered": ["<alt>"],
      "trade_offs": ["<trade-off>"],
      "timestamp": "<ISO 8601>"
    }
  ]
}

Every significant architectural decision must be in design_decisions with alternatives considered."""


class ArchitectureAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Architecture Agent", artifacts_dir=artifacts_dir)

    async def run(self, intent: IntentArtifact) -> ArchitectureArtifact:
        """Design the system architecture based on the IntentArtifact."""
        intent_json = intent.model_dump_json(indent=2)

        user_message = f"""Design the system architecture for the following intent artifact.

## Intent Artifact
```json
{intent_json}
```

Produce a comprehensive architecture that satisfies all requirements and success criteria.
Respond ONLY with the JSON block."""

        artifact = await self._query_and_parse(
            system=SYSTEM_PROMPT,
            user_message=user_message,
            model_class=ArchitectureArtifact,
        )

        self.save_artifact(artifact, "02_architecture_artifact.json")
        self.save_history()
        return artifact
