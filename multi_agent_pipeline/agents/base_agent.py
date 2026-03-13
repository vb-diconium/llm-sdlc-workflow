"""
Base agent — Claude Agent SDK with:
  - Compact context formatting (passes summaries, not raw JSON blobs)
  - Retry logic (3 attempts with backoff)
  - CLAUDECODE env-var bypass for nested invocation
  - Prompt loading from prompts/ directory
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

# Prompts directory: <repo_root>/prompts/
_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")


def load_prompt(filename: str) -> str:
    """Load a system prompt from the prompts/ directory.

    Args:
        filename: Name of the .md file inside prompts/, e.g. "intent_agent.md"

    Returns:
        The prompt text, stripped of leading/trailing whitespace.
    """
    path = os.path.normpath(os.path.join(_PROMPTS_DIR, filename))
    with open(path) as f:
        return f.read().strip()

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel
from rich.console import Console
from rich.rule import Rule

T = TypeVar("T", bound=BaseModel)
console = Console()

MAX_RETRIES = 3
RETRY_DELAY = 5   # seconds between retries


class BaseAgent:
    def __init__(self, name: str, artifacts_dir: str = "./artifacts"):
        self.name = name
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        self.history: List[Dict[str, Any]] = []

    # ─── LLM ────────────────────────────────────────────────────────────────

    async def _query_and_parse(
        self,
        system: str,
        user_message: str,
        model_class: Type[T],
    ) -> T:
        console.print(Rule(f"[bold cyan]{self.name}[/bold cyan]"))

        full_prompt = f"{system}\n\n---\n\n{user_message}"
        self._add_to_history("user", full_prompt)

        raw = await self._run_with_retry(full_prompt)
        self._add_to_history("assistant", raw or "")
        console.print(Rule())

        if not raw:
            raise ValueError(f"{self.name} returned an empty response — try again.")

        try:
            data = self._extract_json(raw)
            return model_class(**data)
        except Exception as e:
            console.print(f"[red]JSON parse error in {self.name}:[/red] {e}")
            console.print(f"[dim]Raw (first 1000 chars):\n{raw[:1000]}[/dim]")
            raise

    async def _run_with_retry(self, prompt: str) -> str:
        """Run query with up to MAX_RETRIES attempts."""
        last_err: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._run_query(prompt)
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    console.print(
                        f"[yellow][{self.name}] Attempt {attempt} failed: {e}. "
                        f"Retrying in {RETRY_DELAY}s…[/yellow]"
                    )
                    await asyncio.sleep(RETRY_DELAY)
        raise last_err  # type: ignore

    async def _run_query(self, prompt: str) -> str:
        """
        Spawn a Claude Code subagent.
        Temporarily clears CLAUDECODE so the nested-session guard doesn't fire.
        Safe because our agents use allowed_tools=[] (no file/shell access).
        """
        claudecode_val = os.environ.pop("CLAUDECODE", None)
        try:
            result_text = ""
            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    allowed_tools=[],
                    max_turns=1,   # single-turn: send prompt, get response, done
                ),
            ):
                if isinstance(message, ResultMessage):
                    result_text = message.result or ""
            return result_text
        finally:
            if claudecode_val is not None:
                os.environ["CLAUDECODE"] = claudecode_val

    # ─── Context formatting ──────────────────────────────────────────────────

    def _compact(self, artifact: BaseModel, max_list: int = 8) -> str:
        """
        Produce a compact markdown summary of an artifact for use as agent
        context. Avoids bloating prompts with full JSON dumps.
        Lists are capped at max_list items; long strings are truncated.
        """
        lines: List[str] = [f"### {type(artifact).__name__}"]
        data = artifact.model_dump()

        def _fmt_val(v: Any, depth: int = 0) -> str:
            indent = "  " * depth
            if isinstance(v, list):
                if not v:
                    return "(none)"
                items = v[:max_list]
                rest = len(v) - max_list
                out = "\n".join(f"{indent}  - {_fmt_item(i)}" for i in items)
                if rest > 0:
                    out += f"\n{indent}  - … and {rest} more"
                return "\n" + out
            if isinstance(v, dict):
                if not v:
                    return "(empty)"
                items = list(v.items())[:max_list]
                return "\n" + "\n".join(f"{indent}  {k}: {_fmt_item(val)}" for k, val in items)
            return _fmt_item(v)

        def _fmt_item(v: Any) -> str:
            if isinstance(v, dict):
                # Inline small dicts (e.g. DecisionRecord)
                parts = []
                for k, val in list(v.items())[:4]:
                    if k == "timestamp":
                        continue
                    parts.append(f"{k}: {str(val)[:80]}")
                return "{" + ", ".join(parts) + "}"
            s = str(v)
            return s if len(s) <= 120 else s[:117] + "…"

        for key, val in data.items():
            if key in ("raw_requirements", "decisions", "history"):
                continue  # skip very large or internal fields
            label = key.replace("_", " ").title()
            lines.append(f"\n**{label}:** {_fmt_val(val)}")

        # Include up to 3 decisions for traceability
        decisions = data.get("decisions", [])
        if decisions:
            lines.append("\n**Key Decisions:**")
            for d in decisions[:3]:
                lines.append(f"  - {d.get('decision','')[:100]} (reason: {d.get('rationale','')[:80]})")

        return "\n".join(lines)

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

    # ─── Helpers ─────────────────────────────────────────────────────────────

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
        self.history.append({
            "role": role,
            "content": content,
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
        })
