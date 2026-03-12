"""
Entry point for the Multi-Agent Pipeline.

Usage:
    python main.py                          # runs the built-in example
    python main.py --requirements path.txt  # load requirements from a file
    python main.py --interactive            # type/paste requirements interactively

Each run creates a timestamped artifacts directory so runs never overwrite each other.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import anyio
from rich.console import Console
from rich.panel import Panel

from pipeline import Pipeline

console = Console()

# ─── Built-in example requirements ──────────────────────────────────────────

EXAMPLE_REQUIREMENTS = """
Build a task management REST API with the following features:

1. User authentication (register, login, logout) using JWT tokens
2. Users can create, read, update, and delete their own tasks
3. Tasks have: title, description, status (todo/in_progress/done), priority (low/medium/high),
   due date, and tags
4. Tasks can be filtered by status, priority, and tags
5. Pagination support for task listings (max 50 per page)
6. Users can share tasks with other users (read-only or edit access)
7. Email notifications when a shared task is updated (async, non-blocking)
8. Rate limiting: 100 requests/minute per user
9. Full audit log of all task changes (who changed what and when)
10. API must be production-ready: proper error handling, input validation, logging

Non-functional requirements:
- The API should handle 1000 concurrent users
- Response time < 200ms for 95th percentile
- 99.9% uptime target
- All sensitive data encrypted at rest and in transit
- GDPR compliant (data export and deletion endpoints)

Technology preferences: Python backend preferred, PostgreSQL for storage.
"""


# ─── Main ────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-Agent Software Development Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # run built-in task-manager example
  python main.py --requirements reqs.txt      # load from file
  python main.py --interactive                # type requirements interactively
  python main.py --output-dir ./my_artifacts  # custom artifacts directory
        """,
    )
    parser.add_argument(
        "--requirements",
        type=str,
        help="Path to a text file containing requirements",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enter requirements interactively (type, then Ctrl+D or Ctrl+Z to finish)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save artifacts (default: ./artifacts/run_<timestamp>)",
    )
    return parser.parse_args()


def get_requirements(args: argparse.Namespace) -> str:
    if args.requirements:
        with open(args.requirements) as f:
            requirements = f.read().strip()
        console.print(f"[dim]Loaded requirements from {args.requirements}[/dim]")
        return requirements

    if args.interactive:
        console.print(
            Panel(
                "Enter your requirements below.\n"
                "Press [bold]Ctrl+D[/bold] (Unix) or [bold]Ctrl+Z[/bold] (Windows) when done.",
                title="Interactive Mode",
            )
        )
        try:
            lines = sys.stdin.read()
            return lines.strip()
        except EOFError:
            pass

    # Default: use the built-in example
    console.print(
        Panel(
            "No requirements provided — using built-in Task Management API example.\n\n"
            "Run with [bold]--requirements path.txt[/bold] or [bold]--interactive[/bold] "
            "to use your own requirements.",
            title="[yellow]Using Example Requirements[/yellow]",
        )
    )
    return EXAMPLE_REQUIREMENTS.strip()


async def async_main(args: argparse.Namespace, requirements: str) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifacts_dir = args.output_dir or os.path.join("artifacts", f"run_{timestamp}")

    console.print(
        Panel(
            f"[bold]Requirements preview:[/bold]\n{requirements[:300]}{'...' if len(requirements) > 300 else ''}\n\n"
            f"[dim]Artifacts will be saved to: {artifacts_dir}[/dim]",
            title="Starting Pipeline",
        )
    )

    pipeline = Pipeline(artifacts_dir=artifacts_dir)
    result = await pipeline.run(requirements)
    pipeline.print_summary(result)
    return 0 if result.passed else 1


def main() -> int:
    args = parse_args()
    requirements = get_requirements(args)

    if not requirements:
        console.print("[red]Error: No requirements provided.[/red]")
        return 1

    try:
        return anyio.run(async_main, args, requirements)
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user.[/yellow]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
