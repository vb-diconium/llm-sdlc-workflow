"""
Pipeline Orchestrator — coordinates all agents in sequence.

Flow:
  1. IntentAgent          → IntentArtifact
  2. ArchitectureAgent    → ArchitectureArtifact
  3. TestingAgent         → TestingArtifact (stage: architecture)
  4. EngineeringAgent     → EngineeringArtifact
  5. TestingAgent         → TestingArtifact (stage: engineering)
  6. ReviewAgent          → ReviewArtifact
  7. TestingAgent         → TestingArtifact (stage: review)
  8. PipelineReport       → saved to disk

Each agent's artifact is persisted to ./artifacts/ after every step so the
pipeline can be inspected or resumed at any point.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents import (
    ArchitectureAgent,
    EngineeringAgent,
    IntentAgent,
    ReviewAgent,
    TestingAgent,
)
from models.artifacts import (
    ArchitectureArtifact,
    EngineeringArtifact,
    IntentArtifact,
    ReviewArtifact,
    TestingArtifact,
)

console = Console()


@dataclass
class PipelineResult:
    """Collects all artifacts and metadata from a full pipeline run."""

    requirements: str
    started_at: str
    completed_at: Optional[str] = None
    artifacts_dir: str = "./artifacts"

    intent: Optional[IntentArtifact] = None
    architecture: Optional[ArchitectureArtifact] = None
    engineering: Optional[EngineeringArtifact] = None
    review: Optional[ReviewArtifact] = None

    test_architecture: Optional[TestingArtifact] = None
    test_engineering: Optional[TestingArtifact] = None
    test_review: Optional[TestingArtifact] = None

    errors: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if all testing stages passed and review found no critical issues."""
        checks = [
            self.test_architecture and self.test_architecture.passed,
            self.test_engineering and self.test_engineering.passed,
            self.test_review and self.test_review.passed,
            self.review and self.review.passed,
        ]
        return all(checks)


class Pipeline:
    """
    Orchestrates the full multi-agent pipeline.

    Usage:
        pipeline = Pipeline(artifacts_dir="./artifacts/my_run")
        result = pipeline.run(requirements_text)
        pipeline.print_summary(result)
    """

    def __init__(self, artifacts_dir: str = "./artifacts"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)

        # Initialise all agents pointing at the same artifacts directory
        self.intent_agent = IntentAgent(artifacts_dir)
        self.architecture_agent = ArchitectureAgent(artifacts_dir)
        self.engineering_agent = EngineeringAgent(artifacts_dir)
        self.review_agent = ReviewAgent(artifacts_dir)
        self.testing_agent = TestingAgent(artifacts_dir)

    async def run(self, requirements: str) -> PipelineResult:
        """Execute the full pipeline and return a PipelineResult."""
        result = PipelineResult(
            requirements=requirements,
            started_at=datetime.now().isoformat(),
            artifacts_dir=self.artifacts_dir,
        )

        console.print(
            Panel(
                "[bold]🚀 Multi-Agent Pipeline Starting[/bold]\n\n"
                "Agents: Intent → Architecture → Engineering → Review\n"
                "Testing runs after Architecture, Engineering, and Review.",
                title="Pipeline",
                style="bold blue",
            )
        )

        try:
            # ── Step 1: Intent ───────────────────────────────────────────
            self._step_header("Step 1/7", "Intent Agent", "Analysing requirements")
            result.intent = await self.intent_agent.run(requirements)
            self._step_done("Intent", len(result.intent.requirements), "requirements extracted")

            # ── Step 2: Architecture ─────────────────────────────────────
            self._step_header("Step 2/7", "Architecture Agent", "Designing system architecture")
            result.architecture = await self.architecture_agent.run(result.intent)
            self._step_done("Architecture", len(result.architecture.components), "components designed")

            # ── Step 3: Testing — architecture stage ─────────────────────
            self._step_header("Step 3/7", "Testing Agent", "Verifying architecture vs requirements")
            result.test_architecture = await self.testing_agent.run(
                stage="architecture",
                intent=result.intent,
                architecture=result.architecture,
            )
            self._testing_status("Architecture", result.test_architecture)

            # ── Step 4: Engineering ──────────────────────────────────────
            self._step_header("Step 4/7", "Engineering Agent", "Selecting stack and generating code")
            result.engineering = await self.engineering_agent.run(result.intent, result.architecture)
            self._step_done("Engineering", len(result.engineering.generated_files), "files generated")

            # ── Step 5: Testing — engineering stage ──────────────────────
            self._step_header("Step 5/7", "Testing Agent", "Verifying implementation vs requirements")
            result.test_engineering = await self.testing_agent.run(
                stage="engineering",
                intent=result.intent,
                architecture=result.architecture,
                engineering=result.engineering,
            )
            self._testing_status("Engineering", result.test_engineering)

            # ── Step 6: Review ───────────────────────────────────────────
            self._step_header("Step 6/7", "Review Agent", "Reviewing code quality, security, reliability")
            result.review = await self.review_agent.run(
                result.intent, result.architecture, result.engineering
            )
            self._review_status(result.review)

            # ── Step 7: Testing — review stage ───────────────────────────
            self._step_header("Step 7/7", "Testing Agent", "Final verification")
            result.test_review = await self.testing_agent.run(
                stage="review",
                intent=result.intent,
                architecture=result.architecture,
                engineering=result.engineering,
                review=result.review,
            )
            self._testing_status("Final", result.test_review)

        except Exception as e:
            result.errors.append(str(e))
            console.print_exception()

        result.completed_at = datetime.now().isoformat()
        self._save_report(result)
        return result

    # ─── Private helpers ─────────────────────────────────────────────────────

    def _step_header(self, step: str, agent: str, description: str) -> None:
        console.print(
            Panel(
                f"[bold]{agent}[/bold]\n{description}",
                title=f"[cyan]{step}[/cyan]",
                style="cyan",
            )
        )

    def _step_done(self, name: str, count: int, label: str) -> None:
        console.print(f"[green]✅ {name} complete — {count} {label}[/green]\n")

    def _testing_status(self, stage: str, artifact: TestingArtifact) -> None:
        icon = "✅" if artifact.passed else "❌"
        color = "green" if artifact.passed else "red"
        total = len(artifact.test_cases)
        passed = sum(1 for tc in artifact.test_cases if tc.status == "passed")
        failed = sum(1 for tc in artifact.test_cases if tc.status == "failed")
        blocking = len(artifact.blocking_issues)

        console.print(
            f"[{color}]{icon} Testing ({stage}): {passed}/{total} passed, "
            f"{failed} failed, {blocking} blocking issues[/{color}]\n"
        )

    def _review_status(self, artifact: ReviewArtifact) -> None:
        icon = "✅" if artifact.passed else "❌"
        color = "green" if artifact.passed else "red"
        critical = sum(1 for i in artifact.issues if i.severity == "critical")
        high = sum(1 for i in artifact.issues if i.severity == "high")

        console.print(
            f"[{color}]{icon} Review: score={artifact.overall_score}/100, "
            f"security={artifact.security_score}, reliability={artifact.reliability_score}, "
            f"critical={critical}, high={high}[/{color}]\n"
        )

    def _save_report(self, result: PipelineResult) -> None:
        """Save a human-readable pipeline summary report."""
        report = {
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "passed": result.passed,
            "errors": result.errors,
            "summary": {
                "requirements_count": len(result.intent.requirements) if result.intent else 0,
                "components_count": len(result.architecture.components) if result.architecture else 0,
                "files_generated": len(result.engineering.generated_files) if result.engineering else 0,
                "review_score": result.review.overall_score if result.review else None,
                "review_passed": result.review.passed if result.review else None,
                "test_architecture_passed": result.test_architecture.passed if result.test_architecture else None,
                "test_engineering_passed": result.test_engineering.passed if result.test_engineering else None,
                "test_review_passed": result.test_review.passed if result.test_review else None,
            },
        }

        path = os.path.join(self.artifacts_dir, "00_pipeline_report.json")
        with open(path, "w") as f:
            json.dump(report, f, indent=2)

        console.print(f"\n[dim]📊 Pipeline report saved → {path}[/dim]")

    def print_summary(self, result: PipelineResult) -> None:
        """Print a rich summary table of the pipeline run."""
        table = Table(title="Pipeline Run Summary", show_header=True, header_style="bold magenta")
        table.add_column("Stage", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Key Metrics")

        def status(ok: Optional[bool]) -> str:
            if ok is None:
                return "[dim]SKIPPED[/dim]"
            return "[green]PASSED[/green]" if ok else "[red]FAILED[/red]"

        if result.intent:
            table.add_row(
                "Intent",
                "[green]DONE[/green]",
                f"{len(result.intent.requirements)} reqs, {len(result.intent.key_features)} features",
            )

        if result.architecture:
            table.add_row(
                "Architecture",
                "[green]DONE[/green]",
                f"{len(result.architecture.components)} components, "
                f"style: {result.architecture.architecture_style}",
            )

        if result.test_architecture:
            tc = result.test_architecture
            passed = sum(1 for t in tc.test_cases if t.status == "passed")
            table.add_row(
                "Testing (architecture)",
                status(tc.passed),
                f"{passed}/{len(tc.test_cases)} test cases passed, "
                f"{len(tc.blocking_issues)} blocking",
            )

        if result.engineering:
            eng = result.engineering
            table.add_row(
                "Engineering",
                "[green]DONE[/green]",
                f"{len(eng.generated_files)} files, backend: {eng.backend_tech.framework}",
            )

        if result.test_engineering:
            tc = result.test_engineering
            passed = sum(1 for t in tc.test_cases if t.status == "passed")
            table.add_row(
                "Testing (engineering)",
                status(tc.passed),
                f"{passed}/{len(tc.test_cases)} test cases passed, "
                f"{len(tc.blocking_issues)} blocking",
            )

        if result.review:
            rv = result.review
            critical = sum(1 for i in rv.issues if i.severity == "critical")
            table.add_row(
                "Review",
                status(rv.passed),
                f"score={rv.overall_score}/100, security={rv.security_score}, "
                f"critical={critical}, total issues={len(rv.issues)}",
            )

        if result.test_review:
            tc = result.test_review
            passed = sum(1 for t in tc.test_cases if t.status == "passed")
            table.add_row(
                "Testing (final)",
                status(tc.passed),
                f"{passed}/{len(tc.test_cases)} test cases passed, "
                f"{len(tc.blocking_issues)} blocking",
            )

        console.print("\n")
        console.print(table)

        overall_style = "bold green" if result.passed else "bold red"
        overall_text = "✅ PIPELINE PASSED" if result.passed else "❌ PIPELINE FAILED"
        console.print(
            Panel(
                f"[{overall_style}]{overall_text}[/{overall_style}]\n\n"
                f"Artifacts saved to: {result.artifacts_dir}\n"
                f"Duration: {result.started_at} → {result.completed_at}",
                title="Result",
            )
        )

        if result.errors:
            console.print(Panel("\n".join(result.errors), title="[red]Errors[/red]"))
