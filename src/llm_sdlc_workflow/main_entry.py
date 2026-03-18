"""
Package main entry point.

Provides the ``main()`` function used by:
  - python -m llm_sdlc_workflow
  - the ``llm-sdlc`` console script (pyproject.toml [project.scripts])

The actual CLI logic lives in ``main.py`` at the repository root.  This
module dynamically loads it so the package can be run in both development
(run from repo root) and installed-package modes.
"""

from __future__ import annotations

import importlib.util
import os
import sys


def main() -> int:
    """Run the LLM SDLC pipeline CLI."""
    # Locate main.py relative to this file:
    # src/llm_sdlc_workflow/main_entry.py → ../../.. = repo root
    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.normpath(os.path.join(_pkg_dir, "..", "..", ".."))
    _main_py = os.path.join(_root, "main.py")

    if os.path.exists(_main_py):
        spec = importlib.util.spec_from_file_location("_llm_sdlc_cli", _main_py)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules.setdefault("_llm_sdlc_cli", mod)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.main()

    print(
        "Error: main.py not found. Please run `python main.py` from the repository root.",
        file=sys.stderr,
    )
    return 1
