"""
Engineering Agent — selects the technology stack and generates concrete implementation files.

Responsibilities:
  - Choose backend and frontend frameworks with rationale
  - Generate actual source code for core components
  - Define project file structure
  - Outline the implementation roadmap
  - Document every technology choice decision
"""

from __future__ import annotations

from models.artifacts import ArchitectureArtifact, EngineeringArtifact, IntentArtifact
from .base_agent import BaseAgent

SYSTEM_PROMPT = """You are a principal full-stack engineer and technical lead with expertise in
modern web frameworks, cloud-native development, DevOps, and software craftsmanship.

Given an IntentArtifact and ArchitectureArtifact, you will:

1. Select the optimal backend technology stack (framework, language, libraries) with full justification
2. Select the optimal frontend technology stack if a UI is needed
3. Define the infrastructure approach
4. Generate ACTUAL working source code for the key files (not pseudocode — real, runnable code)
5. Define the complete file/directory structure
6. Create a step-by-step implementation plan with acceptance criteria per step
7. List all required environment variables
8. List all REST API endpoints or service contracts
9. Document all key data models

For generated_files, include the FULL content of each file — real, production-quality code with:
  - Proper error handling
  - Input validation
  - Security best practices baked in
  - Comments for non-obvious logic
  - No placeholders — actual implementations

You MUST respond with a single JSON object wrapped in a ```json ... ``` block matching this exact schema:

{
  "backend_tech": {
    "framework": "<framework>",
    "language": "<language>",
    "version": "<version>",
    "key_libraries": ["<lib>", ...],
    "rationale": "<why this stack>"
  },
  "frontend_tech": {  // null if no UI needed
    "framework": "<framework>",
    "language": "<language>",
    "version": "<version>",
    "key_libraries": ["<lib>", ...],
    "rationale": "<why>"
  },
  "infrastructure": "<Docker/K8s/serverless/etc description>",
  "generated_files": [
    {
      "path": "<relative file path>",
      "purpose": "<what this file does>",
      "content": "<full file content>"
    }
  ],
  "implementation_steps": [
    {
      "step": 1,
      "description": "<what to do>",
      "files_involved": ["<file>"],
      "acceptance_criteria": ["<criterion>"]
    }
  ],
  "environment_variables": {
    "VAR_NAME": "<description of what it holds>"
  },
  "api_endpoints": ["<METHOD /path — description>", ...],
  "data_models": ["<ModelName: field1: type, field2: type>", ...],
  "decisions": [
    {
      "decision": "<decision>",
      "rationale": "<why>",
      "alternatives_considered": ["<alt>"],
      "trade_offs": ["<trade-off>"],
      "timestamp": "<ISO 8601>"
    }
  ]
}

Generate at minimum 5 real code files (e.g. main app file, models, routes/controllers, config, Dockerfile).
The code must be COMPLETE and RUNNABLE — no placeholder comments like "TODO: implement this"."""


class EngineeringAgent(BaseAgent):
    def __init__(self, artifacts_dir: str = "./artifacts"):
        super().__init__(name="Engineering Agent", artifacts_dir=artifacts_dir)

    async def run(
        self, intent: IntentArtifact, architecture: ArchitectureArtifact
    ) -> EngineeringArtifact:
        """Generate the technology stack selection and implementation code."""
        user_message = f"""Select the technology stack and generate the implementation based on these artifacts.

## Intent Artifact
```json
{intent.model_dump_json(indent=2)}
```

## Architecture Artifact
```json
{architecture.model_dump_json(indent=2)}
```

Generate REAL, COMPLETE, RUNNABLE code. Every file in generated_files must have full content.
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
        """Write the generated code files to the artifacts/generated/ directory."""
        import os

        generated_dir = os.path.join(self.artifacts_dir, "generated")
        os.makedirs(generated_dir, exist_ok=True)

        for file_spec in artifact.generated_files:
            # Sanitise the path to prevent directory traversal
            safe_path = os.path.normpath(file_spec.path).lstrip(os.sep)
            full_path = os.path.join(generated_dir, safe_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w") as f:
                f.write(file_spec.content)

            from rich.console import Console
            Console().print(f"[dim]  📄 Generated: {full_path}[/dim]")
