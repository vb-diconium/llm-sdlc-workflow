"""
Unit tests for BaseAgent and module-level helper functions in base_agent.

These tests cover pure logic that does NOT require a live LLM connection:
  - _get_github_token()        — env var + subprocess fallback
  - _get_api_key()             — PIPELINE_API_KEY priority chain
  - BaseAgent._extract_json() — JSON extraction from LLM text
  - BaseAgent._add_to_history()
  - BaseAgent.save_artifact() / load_artifact()
  - BaseAgent._run_with_retry() — retry / backoff logic (LLM call mocked)
  - BaseAgent._compact()       — context summarisation
  - BaseAgent._query_and_parse_chunked() — two-phase plan+fill generation
  - main_entry.main()          — package entry point
  - __main__ module            — python -m llm_sdlc_workflow
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import llm_sdlc_workflow.agents.base_agent as base_module
from llm_sdlc_workflow.agents.base_agent import (
    MAX_RETRIES,
    BaseAgent,
    _get_api_key,
    _get_github_token,
)
from llm_sdlc_workflow.models.artifacts import DiscoveryArtifact


# ─── _get_github_token ────────────────────────────────────────────────────────


class TestGetGithubToken:
    def test_returns_github_token_env_var(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_abc123")
        monkeypatch.delenv("PIPELINE_API_KEY", raising=False)
        assert _get_github_token() == "ghp_test_abc123"

    def test_falls_back_to_gh_cli_when_no_env_var(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("PIPELINE_API_KEY", raising=False)
        with patch("subprocess.check_output", return_value=b"cli-token-xyz\n") as mock_sub:
            result = _get_github_token()
        assert result == "cli-token-xyz"
        mock_sub.assert_called_once()

    def test_raises_environment_error_when_gh_cli_not_found(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("subprocess.check_output", side_effect=FileNotFoundError("gh not found")):
            with pytest.raises(EnvironmentError, match="No GitHub token found"):
                _get_github_token()

    def test_raises_environment_error_when_gh_cli_fails(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "gh"),
        ):
            with pytest.raises(EnvironmentError, match="No GitHub token found"):
                _get_github_token()

    def test_raises_when_gh_cli_returns_empty_string(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("subprocess.check_output", return_value=b""):
            with pytest.raises(EnvironmentError, match="No GitHub token found"):
                _get_github_token()

    def test_strips_whitespace_from_cli_output(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("subprocess.check_output", return_value=b"  tok123  \n"):
            result = _get_github_token()
        assert result == "tok123"


# ─── _get_api_key ─────────────────────────────────────────────────────────────


class TestGetApiKey:
    def test_prefers_pipeline_api_key_over_github_token(self, monkeypatch):
        monkeypatch.setenv("PIPELINE_API_KEY", "sk-openai-key")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_not_be_used")
        assert _get_api_key() == "sk-openai-key"

    def test_falls_back_to_github_token_when_no_pipeline_key(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_API_KEY", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fallback")
        assert _get_api_key() == "ghp_fallback"

    def test_falls_back_to_gh_cli_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_API_KEY", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("subprocess.check_output", return_value=b"cli-token\n"):
            assert _get_api_key() == "cli-token"

    def test_raises_when_no_key_available(self, monkeypatch):
        monkeypatch.delenv("PIPELINE_API_KEY", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("subprocess.check_output", side_effect=FileNotFoundError()):
            with pytest.raises(EnvironmentError):
                _get_api_key()


# ─── BaseAgent._extract_json ──────────────────────────────────────────────────


class TestExtractJson:
    """_extract_json must handle every format the LLM might return."""

    def setup_method(self):
        self.agent = BaseAgent(name="test", artifacts_dir="/tmp/_test_extract")

    def test_parses_plain_json_object(self):
        result = self.agent._extract_json('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_parses_fenced_json_code_block(self):
        text = '```json\n{"hello": "world"}\n```'
        assert self.agent._extract_json(text) == {"hello": "world"}

    def test_parses_generic_fenced_code_block(self):
        text = '```\n{"generic": true}\n```'
        assert self.agent._extract_json(text) == {"generic": True}

    def test_extracts_json_embedded_in_prose(self):
        text = 'Sure, here it is: {"answer": 42} — let me know if you need more.'
        assert self.agent._extract_json(text) == {"answer": 42}

    def test_parses_nested_structures(self):
        data = {"a": {"b": [1, 2, 3]}, "c": None, "d": [{"x": 1}]}
        assert self.agent._extract_json(json.dumps(data)) == data

    def test_parses_json_with_leading_and_trailing_whitespace(self):
        result = self.agent._extract_json('  \n  {"spaced": true}  \n  ')
        assert result == {"spaced": True}

    def test_raises_value_error_when_no_json_present(self):
        with pytest.raises(ValueError, match="No JSON object found"):
            self.agent._extract_json("This is plain text with absolutely no JSON at all.")

    def test_raises_value_error_on_empty_string(self):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            self.agent._extract_json("")

    def test_raises_on_invalid_json_in_fence(self):
        text = "```json\n{this is not valid JSON at all!\n```"
        with pytest.raises((ValueError, json.JSONDecodeError)):
            self.agent._extract_json(text)

    def test_fenced_block_preferred_over_embedded(self):
        """When both a fenced block and bare JSON exist, fenced block wins."""
        text = 'Ignore this: {"wrong": 1}\n```json\n{"correct": 2}\n```'
        assert self.agent._extract_json(text) == {"correct": 2}


# ─── BaseAgent._add_to_history ────────────────────────────────────────────────


class TestAddToHistory:
    def setup_method(self):
        self.agent = BaseAgent(name="HistoryAgent", artifacts_dir="/tmp/_test_history")

    def test_history_starts_empty(self):
        assert self.agent.history == []

    def test_appends_entry_with_all_required_fields(self):
        self.agent._add_to_history("user", "Hello LLM")
        assert len(self.agent.history) == 1
        entry = self.agent.history[0]
        assert entry["role"] == "user"
        assert entry["content"] == "Hello LLM"
        assert entry["agent"] == "HistoryAgent"
        assert "timestamp" in entry

    def test_timestamp_is_valid_iso_8601(self):
        self.agent._add_to_history("assistant", "response")
        ts = self.agent.history[0]["timestamp"]
        # Should parse without raising
        datetime.fromisoformat(ts)

    def test_multiple_calls_grow_history_in_order(self):
        self.agent._add_to_history("user", "first")
        self.agent._add_to_history("assistant", "second")
        self.agent._add_to_history("user", "third")
        assert len(self.agent.history) == 3
        assert self.agent.history[0]["content"] == "first"
        assert self.agent.history[1]["content"] == "second"
        assert self.agent.history[2]["content"] == "third"

    def test_different_roles_stored_correctly(self):
        self.agent._add_to_history("user", "question")
        self.agent._add_to_history("assistant", "answer")
        assert self.agent.history[0]["role"] == "user"
        assert self.agent.history[1]["role"] == "assistant"


# ─── BaseAgent.save_artifact / load_artifact ─────────────────────────────────


class TestArtifactIO:
    def test_save_pydantic_model_writes_valid_json(self, tmp_path):
        agent = BaseAgent(name="io-test", artifacts_dir=str(tmp_path))
        artifact = DiscoveryArtifact(
            raw_requirements="Build API",
            requirements=["User auth", "CRUD tasks"],
            user_goals=["Fast delivery"],
            constraints=["PostgreSQL only"],
            success_criteria=["< 200ms latency"],
            key_features=["JWT", "REST"],
            domain_context="task management",
            scope="backend API",
        )
        path = agent.save_artifact(artifact, "01_discovery.json")
        data = json.loads((tmp_path / "01_discovery.json").read_text())
        assert data["raw_requirements"] == "Build API"
        assert data["requirements"] == ["User auth", "CRUD tasks"]

    def test_save_plain_dict_writes_valid_json(self, tmp_path):
        agent = BaseAgent(name="io-test", artifacts_dir=str(tmp_path))
        payload = {"key": "value", "items": [1, 2, 3], "nested": {"a": "b"}}
        agent.save_artifact(payload, "dict.json")
        assert json.loads((tmp_path / "dict.json").read_text()) == payload

    def test_save_returns_absolute_path(self, tmp_path):
        agent = BaseAgent(name="io-test", artifacts_dir=str(tmp_path))
        path = agent.save_artifact({"x": 1}, "out.json")
        assert path == str(tmp_path / "out.json")

    def test_load_returns_dict_for_existing_file(self, tmp_path):
        agent = BaseAgent(name="io-test", artifacts_dir=str(tmp_path))
        data = {"foo": "bar", "count": 99}
        (tmp_path / "existing.json").write_text(json.dumps(data))
        result = agent.load_artifact("existing.json")
        assert result == data

    def test_load_returns_none_for_missing_file(self, tmp_path):
        agent = BaseAgent(name="io-test", artifacts_dir=str(tmp_path))
        assert agent.load_artifact("ghost.json") is None

    def test_save_history_writes_history_file(self, tmp_path):
        agent = BaseAgent(name="My Agent", artifacts_dir=str(tmp_path))
        agent._add_to_history("user", "hello")
        agent._add_to_history("assistant", "world")
        path = agent.save_history()
        data = json.loads((tmp_path / "my_agent_history.json").read_text())
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"


# ─── BaseAgent._run_with_retry ────────────────────────────────────────────────


class TestRunWithRetry:
    async def test_succeeds_on_first_attempt(self, tmp_path):
        agent = BaseAgent(name="retry-test", artifacts_dir=str(tmp_path))
        agent._raw_query = AsyncMock(return_value='{"ok": true}')
        result = await agent._run_with_retry("sys", "user")
        assert result == '{"ok": true}'
        agent._raw_query.assert_called_once()

    async def test_retries_on_transient_error_and_eventually_succeeds(self, tmp_path):
        agent = BaseAgent(name="retry-test", artifacts_dir=str(tmp_path))
        agent._raw_query = AsyncMock(
            side_effect=[RuntimeError("rate limited"), RuntimeError("timeout"), '{"ok": true}']
        )
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await agent._run_with_retry("sys", "user")
        assert result == '{"ok": true}'
        assert agent._raw_query.call_count == 3

    async def test_raises_last_exception_after_max_retries(self, tmp_path):
        agent = BaseAgent(name="retry-test", artifacts_dir=str(tmp_path))
        agent._raw_query = AsyncMock(side_effect=RuntimeError("always fails"))
        with patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(RuntimeError, match="always fails"):
                await agent._run_with_retry("sys", "user")
        assert agent._raw_query.call_count == MAX_RETRIES

    async def test_no_sleep_on_immediate_success(self, tmp_path):
        agent = BaseAgent(name="retry-test", artifacts_dir=str(tmp_path))
        agent._raw_query = AsyncMock(return_value="ok")
        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await agent._run_with_retry("sys", "user")
        mock_sleep.assert_not_called()

    async def test_sleeps_between_retries(self, tmp_path):
        agent = BaseAgent(name="retry-test", artifacts_dir=str(tmp_path))
        agent._raw_query = AsyncMock(
            side_effect=[RuntimeError("fail"), '{"ok": true}']
        )
        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await agent._run_with_retry("sys", "user")
        assert mock_sleep.call_count == 1  # slept once between attempt 1 and 2

    async def test_each_retry_uses_same_arguments(self, tmp_path):
        agent = BaseAgent(name="retry-test", artifacts_dir=str(tmp_path))
        agent._raw_query = AsyncMock(
            side_effect=[RuntimeError("fail"), '{"ok": true}']
        )
        with patch("asyncio.sleep", new=AsyncMock()):
            await agent._run_with_retry("system-prompt", "user-message")
        for call in agent._raw_query.call_args_list:
            assert call.args == ("system-prompt", "user-message")


# ─── BaseAgent._compact ───────────────────────────────────────────────────────


class TestCompact:
    def setup_method(self):
        self.agent = BaseAgent(name="compact-test", artifacts_dir="/tmp/_test_compact")

    def _make_artifact(self, **kwargs) -> DiscoveryArtifact:
        defaults = dict(
            raw_requirements="Build API",
            requirements=["Auth"],
            user_goals=["Speed"],
            constraints=[],
            success_criteria=[],
            key_features=["JWT"],
            domain_context="API",
            scope="backend",
        )
        defaults.update(kwargs)
        return DiscoveryArtifact(**defaults)

    def test_includes_artifact_class_name_as_header(self):
        result = self.agent._compact(self._make_artifact())
        assert "DiscoveryArtifact" in result

    def test_excludes_raw_requirements_key(self):
        """raw_requirements is noisy — should be stripped from compact output."""
        artifact = self._make_artifact(
            raw_requirements="UNIQUE_SENTINEL_VALUE_XYZ_12345"
        )
        result = self.agent._compact(artifact)
        assert "UNIQUE_SENTINEL_VALUE_XYZ_12345" not in result

    def test_empty_list_shown_as_none(self):
        artifact = self._make_artifact(constraints=[], risks=[])
        result = self.agent._compact(artifact)
        assert "(none)" in result

    def test_long_list_is_truncated_with_more_note(self):
        artifact = self._make_artifact(requirements=[f"req_{i}" for i in range(20)])
        result = self.agent._compact(artifact)
        assert "more" in result

    def test_returns_non_empty_string(self):
        result = self.agent._compact(self._make_artifact())
        assert isinstance(result, str)
        assert len(result) > 20

    def test_bold_labels_for_fields(self):
        result = self.agent._compact(self._make_artifact())
        # Should have markdown bold labels
        assert "**" in result


# ─── BaseAgent._query_and_parse_chunked ───────────────────────────────────────


class TestQueryAndParseChunked:
    """Two-phase plan+fill chunked generation."""

    def _make_plan_response(self, with_pending: bool = True) -> str:
        """Minimal valid EngineeringArtifact JSON — files optionally PENDING."""
        content = "__PENDING__" if with_pending else "fun main() {}"
        return json.dumps({
            "service_name": "backend",
            "services": {},
            "generated_files": [
                {"path": "src/main.kt", "purpose": "Entry point", "content": content},
            ],
            "api_endpoints": [],
            "data_models": [],
            "environment_variables": {},
            "implementation_steps": [],
            "spec_compliance_notes": [],
            "decisions": [],
            "review_iteration": 1,
            "review_feedback_applied": [],
        })

    def _make_fill_response(self) -> str:
        return json.dumps({"content": "fun main() { println(\"Hello\") }"})

    async def test_no_pending_files_skips_fill_phase(self, tmp_path):
        from llm_sdlc_workflow.models.artifacts import EngineeringArtifact
        agent = BaseAgent(name="chunked-test", artifacts_dir=str(tmp_path))
        plan_mock = AsyncMock(return_value=self._make_plan_response(with_pending=False))
        agent._run_with_retry = plan_mock
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await agent._query_and_parse_chunked(
                system="sys",
                plan_message="plan",
                file_keys=["generated_files"],
                model_class=EngineeringArtifact,
            )
        assert isinstance(result, EngineeringArtifact)
        # _run_with_retry called exactly once (plan phase only)
        assert plan_mock.call_count == 1

    async def test_pending_file_triggers_fill_phase(self, tmp_path):
        from llm_sdlc_workflow.models.artifacts import EngineeringArtifact
        agent = BaseAgent(name="chunked-test", artifacts_dir=str(tmp_path))
        plan_mock = AsyncMock(return_value=self._make_plan_response(with_pending=True))
        fill_mock = AsyncMock(return_value=self._make_fill_response())
        agent._run_with_retry = plan_mock
        agent._raw_query = fill_mock
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await agent._query_and_parse_chunked(
                system="sys",
                plan_message="plan",
                file_keys=["generated_files"],
                model_class=EngineeringArtifact,
            )
        assert fill_mock.call_count == 1
        assert result.generated_files[0].content == "fun main() { println(\"Hello\") }"

    async def test_fill_with_template_uses_template_vars(self, tmp_path):
        from llm_sdlc_workflow.models.artifacts import EngineeringArtifact
        agent = BaseAgent(name="chunked-test", artifacts_dir=str(tmp_path))
        agent._run_with_retry = AsyncMock(return_value=self._make_plan_response(with_pending=True))
        fill_mock = AsyncMock(return_value=self._make_fill_response())
        agent._raw_query = fill_mock
        tmpl = "Generate {path} for purpose: {purpose}. arch={arch_style}"
        with patch("asyncio.sleep", new=AsyncMock()):
            await agent._query_and_parse_chunked(
                system="sys",
                plan_message="plan",
                file_keys=["generated_files"],
                model_class=EngineeringArtifact,
                fill_message_tmpl=tmpl,
                fill_context={"arch_style": "monolith"},
            )
        fill_call_msg = fill_mock.call_args[0][1]
        assert "src/main.kt" in fill_call_msg
        assert "monolith" in fill_call_msg

    async def test_raises_on_empty_plan_response(self, tmp_path):
        from llm_sdlc_workflow.models.artifacts import EngineeringArtifact
        agent = BaseAgent(name="chunked-test", artifacts_dir=str(tmp_path))
        agent._run_with_retry = AsyncMock(return_value="")
        with pytest.raises(ValueError, match="empty response"):
            await agent._query_and_parse_chunked(
                system="sys",
                plan_message="plan",
                file_keys=["generated_files"],
                model_class=EngineeringArtifact,
            )

    async def test_fill_failure_falls_back_to_todo_comment(self, tmp_path):
        from llm_sdlc_workflow.models.artifacts import EngineeringArtifact
        agent = BaseAgent(name="chunked-test", artifacts_dir=str(tmp_path))
        agent._run_with_retry = AsyncMock(return_value=self._make_plan_response(with_pending=True))
        agent._raw_query = AsyncMock(side_effect=RuntimeError("fill error"))
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await agent._query_and_parse_chunked(
                system="sys",
                plan_message="plan",
                file_keys=["generated_files"],
                model_class=EngineeringArtifact,
            )
        # Should fall back to a TODO comment rather than raising
        assert "TODO" in result.generated_files[0].content


# ─── main_entry and __main__ ──────────────────────────────────────────────────


class TestMainEntry:
    def test_main_entry_exists(self):
        from llm_sdlc_workflow import main_entry
        assert hasattr(main_entry, "main")
        assert callable(main_entry.main)

    def test_main_returns_int_when_main_py_missing(self, tmp_path, monkeypatch):
        """main() returns 1 and prints error when main.py cannot be found."""
        from llm_sdlc_workflow import main_entry
        # Patch os.path.exists inside main_entry to force the "not found" branch
        with patch("llm_sdlc_workflow.main_entry.os.path.exists", return_value=False):
            result = main_entry.main()
        assert result == 1

    def test_dunder_main_module_importable(self):
        import llm_sdlc_workflow.__main__ as m
        assert hasattr(m, "main")

    def test_main_returns_result_when_main_py_found(self, tmp_path):
        """main() loads main.py and calls its main() when file exists."""
        import importlib.util
        from llm_sdlc_workflow import main_entry

        # Build a fake module with a main() that returns 42
        fake_spec = MagicMock()
        fake_mod = MagicMock()
        fake_mod.main = MagicMock(return_value=42)

        with patch("llm_sdlc_workflow.main_entry.os.path.exists", return_value=True):
            with patch("llm_sdlc_workflow.main_entry.importlib.util.spec_from_file_location",
                       return_value=fake_spec):
                with patch("llm_sdlc_workflow.main_entry.importlib.util.module_from_spec",
                           return_value=fake_mod):
                    result = main_entry.main()

        assert result == 42


# ─── _raw_query, _make_client, _get_semaphore ─────────────────────────────────


class TestRawQueryAndSemaphore:
    async def test_raw_query_calls_openai_client(self, tmp_path, monkeypatch):
        """_raw_query builds a client and calls chat.completions.create."""
        monkeypatch.setenv("PIPELINE_API_KEY", "test-key")
        import llm_sdlc_workflow.agents.base_agent as bm

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"ok": true}'

        mock_client = AsyncMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(bm, "_make_client", return_value=mock_client):
            with patch.object(bm, "_get_semaphore", return_value=AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=False))):
                agent = BaseAgent(name="raw-test", artifacts_dir=str(tmp_path))
                result = await agent._raw_query("system prompt", "user message")

        assert result == '{"ok": true}'

    async def test_raw_query_returns_empty_string_when_content_is_none(self, tmp_path, monkeypatch):
        """_raw_query returns '' when message.content is None."""
        monkeypatch.setenv("PIPELINE_API_KEY", "test-key")
        import llm_sdlc_workflow.agents.base_agent as bm

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(bm, "_make_client", return_value=mock_client):
            with patch.object(bm, "_get_semaphore", return_value=AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=False))):
                agent = BaseAgent(name="raw-test", artifacts_dir=str(tmp_path))
                result = await agent._raw_query("system prompt", "user message")

        assert result == ""

    def test_make_client_returns_async_openai(self, monkeypatch):
        """_make_client() instantiates AsyncOpenAI with configured base_url/api_key."""
        monkeypatch.setenv("PIPELINE_API_KEY", "sk-test-key")
        import llm_sdlc_workflow.agents.base_agent as bm
        from openai import AsyncOpenAI

        with patch("llm_sdlc_workflow.agents.base_agent.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            bm._make_client()

        mock_cls.assert_called_once()

    def test_get_semaphore_creates_semaphore_when_none(self):
        """_get_semaphore() creates a new Semaphore when _LLM_SEMAPHORE is None."""
        import asyncio
        import llm_sdlc_workflow.agents.base_agent as bm

        original = bm._LLM_SEMAPHORE
        try:
            bm._LLM_SEMAPHORE = None
            s = bm._get_semaphore()
            assert isinstance(s, asyncio.Semaphore)
            # Second call returns same object
            s2 = bm._get_semaphore()
            assert s is s2
        finally:
            bm._LLM_SEMAPHORE = original


# ─── _query_and_parse and _query_and_parse_chunked error paths ────────────────


class TestQueryAndParseErrorPaths:
    async def test_query_and_parse_reraises_on_bad_json(self, tmp_path):
        """_query_and_parse raises when model construction fails."""
        from llm_sdlc_workflow.models.artifacts import DiscoveryArtifact
        agent = BaseAgent(name="err", artifacts_dir=str(tmp_path))
        # Return JSON that is technically valid but missing required fields
        with patch.object(agent, "_run_with_retry", new=AsyncMock(return_value='{"garbage": true}')):
            with pytest.raises(Exception):
                await agent._query_and_parse("sys", "user", DiscoveryArtifact)

    async def test_query_and_parse_chunked_reraises_when_model_init_fails(self, tmp_path):
        """_query_and_parse_chunked except block fires when model(**data) raises."""
        from llm_sdlc_workflow.models.artifacts import EngineeringArtifact
        agent = BaseAgent(name="err", artifacts_dir=str(tmp_path))

        # Plan response has enough to parse JSON but model(**data) fails because
        # we patch model_class to raise
        good_plan_json = '{"generated_files": [], "backend_tech": null, "frontend_tech": null, "review_iteration": 1}'
        agent._run_with_retry = AsyncMock(return_value=good_plan_json)

        with patch("asyncio.sleep", new=AsyncMock()):
            # Patch EngineeringArtifact to raise on construction
            with patch.object(EngineeringArtifact, "__init__", side_effect=ValueError("bad")):
                with pytest.raises(Exception):
                    await agent._query_and_parse_chunked(
                        system="sys",
                        plan_message="plan",
                        file_keys=["generated_files"],
                        model_class=EngineeringArtifact,
                    )


# ─── _compact edge cases ──────────────────────────────────────────────────────


class TestCompactEdgeCases:
    def test_compact_with_dict_field(self):
        """_compact handles dict-valued fields (environment_variables)."""
        from llm_sdlc_workflow.models.artifacts import InfrastructureArtifact, IaCFile
        agent = BaseAgent(name="cmp", artifacts_dir="/tmp")
        artifact = InfrastructureArtifact(
            iac_files=[IaCFile(path="Dockerfile", content="FROM python:3.11", purpose="app")],
            primary_service_port=8080,
            environment_variables={"DB_URL": "postgres://db/app", "SECRET": "abc"},
        )
        result = agent._compact(artifact)
        assert "InfrastructureArtifact" in result
        assert "DB_URL" in result

    def test_compact_with_empty_dict_shows_empty(self):
        """_compact shows '(empty)' for an empty dict field."""
        from llm_sdlc_workflow.models.artifacts import InfrastructureArtifact
        agent = BaseAgent(name="cmp", artifacts_dir="/tmp")
        artifact = InfrastructureArtifact(
            iac_files=[],
            primary_service_port=8080,
            environment_variables={},
        )
        result = agent._compact(artifact)
        assert "(empty)" in result

    def test_compact_with_iac_files_shows_paths(self):
        """_compact lists iac_files paths without full content."""
        from llm_sdlc_workflow.models.artifacts import InfrastructureArtifact, IaCFile
        agent = BaseAgent(name="cmp", artifacts_dir="/tmp")
        artifact = InfrastructureArtifact(
            iac_files=[
                IaCFile(path="Dockerfile", content="FROM python:3.11\nRUN pip install flask", purpose="App container"),
                IaCFile(path="docker-compose.yml", content="version: '3.8'", purpose="Compose"),
            ],
            primary_service_port=8080,
        )
        result = agent._compact(artifact)
        assert "Dockerfile" in result

    def test_compact_with_decisions_shows_key_decisions(self):
        """_compact shows 'Key Decisions' section when decisions list is populated."""
        from llm_sdlc_workflow.models.artifacts import DiscoveryArtifact, DecisionRecord
        agent = BaseAgent(name="cmp", artifacts_dir="/tmp")
        artifact = DiscoveryArtifact(
            raw_requirements="Build API",
            requirements=["Auth"],
            user_goals=["Speed"],
            constraints=["PostgreSQL"],
            success_criteria=["200ms"],
            key_features=["JWT"],
            domain_context="API",
            scope="backend",
            decisions=[
                DecisionRecord(decision="Use JWT", rationale="Stateless"),
                DecisionRecord(decision="Use PostgreSQL", rationale="ACID"),
            ],
        )
        result = agent._compact(artifact)
        assert "Key Decisions" in result
        assert "Use JWT" in result
