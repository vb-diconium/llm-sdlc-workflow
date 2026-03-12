"""
Base agent class using the Claude Agent SDK.

Uses claude_agent_sdk.query() which runs through Claude Code's authentication
(Claude Pro subscription) — no separate API credits required.

Each concrete agent:
  1. Calls `_query_and_parse()` with its system prompt + user context.
  2. Gets back a fully validated Pydantic artifact.
  3. Saves it to disk via `save_artifact()`.

All agent methods are async — use anyio.run(pipeline.run(...)) at the top level.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel
from rich.console import Console
from rich.rule import Rule

T = TypeVar("T", bound=BaseModel)

console = Console()


class BaseAgent:
    """
    Foundation for every pipeline agent — backed by the Claude Agent SDK.
    """

    def __init__(self, name: str, artifacts_dir: str = "./artifacts"):
        self.name = name
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        self.history: List[Dict[str, Any]] = []

    # ─── LLM helpers ────────────────────────────────────────────────────────

    async def _query_and_parse(
        self,
        system: str,
        user_message: str,
        model_class: Type[T],
    ) -> T:
        """
        Run a query via the Agent SDK and parse the result into a Pydantic model.
        The system prompt instructs the agent to output a single ```json ... ``` block.
        """
        console.print(Rule(f"[bold cyan]{self.name}[/bold cyan]"))

        full_prompt = f"""{system}

---

{user_message}"""

        self._add_to_history("user", full_prompt)
        raw = await self._run_query(full_prompt)
        self._add_to_history("assistant", raw)

        console.print(Rule())

        try:
            data = self._extract_json(raw)
            return model_class(**data)
        except Exception as e:
            console.print(f"[red]JSON parse error in {self.name}:[/red] {e}")
            console.print(f"[dim]Raw output (first 800 chars):\n{raw[:800]}[/dim]")
            raise

    async def _run_query(self, prompt: str) -> str:
        """Run the Agent SDK query and return the final result text."""
        result_text = ""
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],  # pure reasoning — no file/shell tools needed
            ),
        ):
            if isinstance(message, ResultMessage):
                result_text = message.result
        return result_text

    # ─── Artifact I/O ────────────────────────────────────────────────────────

    def save_artifact(self, artifact: Any, filename: str) -> str:
        path = os.path.join(self.artifacts_dir, filename)
        with open(path, "w") as f:
            if isinstance(artifact, BaseModel):
                f.write(artifact.model_dump_json(indent=2))
            else:
                json.dump(artifact, f, indent=2)
        console.print(f"[dim]✅ Artifact saved → {path}[/dim]")
        return path

    def load_artifact(self, filename: str) -> Optional[Dict]:
        path = os.path.join(self.artifacts_dir, filename)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def save_history(self) -> str:
        filename = f"{self.name.lower().replace(' ', '_')}_history.json"
        path = os.path.join(self.artifacts_dir, filename)
        with open(path, "w") as f:
            json.dump(self.history, f, indent=2)
        return path

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> Dict:
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        m = re.search(r"```\s*([\[{].*?)\s*```", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}") + 1
        if 0 <= start < end:
            return json.loads(text[start:end])
        raise ValueError("No JSON object found in agent response.")

    def _add_to_history(self, role: str, content: str) -> None:
        self.history.append(
            {
                "role": role,
                "content": content,
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
            }
        )
