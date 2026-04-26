# LLM SDLC Workflow

**From requirements file to running full-stack application — automated end to end.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Providers](https://img.shields.io/badge/providers-7-green.svg)](#provider-quick-reference)

---

## Overview

Writing software takes time not because code is hard to write, but because the decisions behind it are hard to make consistently. Requirements get misinterpreted. Architecture drifts between services. API contracts break between teams. Security issues surface after the code is already written.

LLM SDLC Workflow addresses each of these failure points with a pipeline of specialised AI agents, each responsible for one phase of the software delivery lifecycle. Agents do not share a context window or pass raw JSON between each other. Each one receives a compact, typed artifact from the previous stage, produces a typed artifact of its own, and hands off to the next. The result is a timestamped directory containing generated source code, OpenAPI contracts, Dockerfiles, docker-compose, Kubernetes manifests, and a complete audit log of every decision made.

The pipeline is **contract-first**. The Spec Agent generates an OpenAPI 3.0 + SQL DDL contract before any code is written. All engineering agents implement against this contract. Subsequent runs can extend it without breaking existing endpoints.

The pipeline is **measurable**. The Review Agent scores output deterministically: start at 100, deduct fixed points per issue severity, weighted across security, reliability, maintainability, and performance. Results are reproducible and comparable across iterations.

The pipeline is **configurable**. Choose which services to generate, override the language and framework per service, and tune everything from a single `pipeline.yaml` — no Python changes required.

**Supported providers:** GitHub Models (default) · Anthropic · OpenAI · xAI · Google Gemini · Mistral · Ollama

---

## Table of Contents

- [Pipeline Flow](#pipeline-flow)
- [Agents](#agents)
- [SDLC Coverage](#sdlc-coverage)
- [Deterministic Review Scoring](#deterministic-review-scoring)
- [Configuring the Pipeline](#configuring-the-pipeline)
- [Human Intelligence Checkpoints](#human-intelligence-checkpoints)
- [Resilience and Reliability](#resilience--reliability)
- [Multi-Project Support](#multi-project-support)
- [Installation](#installation)
- [Usage](#usage)
- [Output Structure](#output-structure)
- [Project Structure](#project-structure)
- [Customising Prompts](#customising-prompts)
- [Roadmap](#roadmap--planned-agents)
- [How It Works](#how-it-works)
- [Requirements](#requirements)

---

## Pipeline Flow

```
  Your Requirements
         │
         ▼
┌──────────────────────┐
│   Discovery Agent    │  Extracts requirements, goals, constraints, risks, scope
└──────────┬───────────┘  → 01_discovery_artifact.json
           │
           ▼
┌──────────────────────┐  ◄── optional: --spec / --config (OpenAPI, SQL, constraints)
│  Architecture Agent  │  Designs components, data flow, API contracts, security model
└──────────┬───────────┘  → 02_architecture_artifact.json
           │
           ▼
  ┌─────────────────────────────────────────────────────────────┐
  │           Testing Agent  [Stage 1 — Architecture]           │
  │  Verifies architecture + spec satisfy all requirements      │
  └─────────────────────────────────────────────────────────────┘
           │  → 05a_testing_architecture.json
           │
           │  ✗ blocking issues found?
           │  ╔═══════════════════════════════════════════════════════╗
           │  ║  Architecture fix loop                                ║
           │  ║  Testing finds gaps → Architecture Agent              ║
           │  ║  redesigns affected components and re-runs Stage 1    ║
           │  ║  until no blockers remain                             ║
           │  ╚═══════════════════╤═════════════════════════════════╝ ║
           │  ✓ all clear         │ (feedback applied, loop back)      ║
           ▼                      └────────────────────────────────────╝
           │
           ▼
┌──────────────────────┐  ◄── optional: --from-run (extends existing contract)
│     Spec Agent       │  Generates forward contract: OpenAPI 3.0 YAML + SQL DDL
└──────────┬───────────┘  → 04_generated_spec_artifact.json + generated/specs/
           │
           ├────────────────────────────────────────────┐
           ▼                                            ▼
┌────────────────────────────────┐     ┌───────────────────────────┐
│      Engineering Agent         │     │   Infrastructure Agent    │
│       (orchestrator)           │     │   (IaC plan — parallel)   │
│                                │     └───────────────────────────┘
│  ┌──────────────────────────┐  │
│  │  Backend Agent           │  │  Language/framework — configurable
│  └──────────────────────────┘  │  → backend/
│  ┌──────────────────────────┐  │
│  │  BFF Agent   [optional]  │  │  Configurable
│  └──────────────────────────┘  │  → bff/
│  ┌──────────────────────────┐  │
│  │  Frontend Agent[optional]│  │  Configurable
│  └──────────────────────────┘  │  → frontend/
│  ┌──────────────────────────┐  │
│  │  Mobile Agent  [opt-in]  │  │  React Native / Flutter / Swift / Kotlin
│  └──────────────────────────┘  │  → mobile_<platform>/
└───────────────┬────────────────┘  → 03_engineering_artifact.json
                │
                ▼
  ╔═════════════════════════════════════════════════════════════════╗
  ║                    Review Loop                                  ║
  ║                                                                 ║
  ║   ┌─────────────────────────────────────────────────────────┐  ║
  ║   │                   Review Agent                           │  ║
  ║   │   Security (OWASP) · Reliability · Code Quality · Perf  │  ║
  ║   │          → 04_review_artifact_iter<N>.json              │  ║
  ║   └────────────────────────┬────────────────────────────────┘  ║
  ║                            │                                    ║
  ║             ┌──────────────┴────────────────┐                  ║
  ║             ▼                               ▼                  ║
  ║   ✓ passed                      ✗ critical or high issues      ║
  ║   (no critical/high)                        │                  ║
  ║             │                               ▼                  ║
  ║             │              ┌────────────────────────────────┐  ║
  ║             │              │  Engineering Agent  (re-gen)   │  ║
  ║             │              │  + Infrastructure Agent (plan) │  ║
  ║             │              │    both run in parallel        │  ║
  ║             │              └───────────────┬────────────────┘  ║
  ║             │                              │ feedback applied   ║
  ║             │                              └──► Review Agent    ║
  ║             │                                  (next iteration) ║
  ╚═════════════╪═════════════════════════════════════════════════╝ ║
                │  ✓ review clean (no critical/high issues left)    ║
                ▼                                                   ║
  ┌─────────────────────────────────────────────────────────────┐  ║
  │   Infrastructure Agent  ┐                                   │  ║
  │   Deployment Agent      ┘   parallel                        │  ║
  │                                                             │  ║
  │  • Infrastructure: docker compose up --build                │  ║
  │  • Deployment: GitHub Actions CI/CD + K8s manifests + Helm  │  ║
  │                canary (10 → 25 → 50 → 100 %)               │  ║
  │                blue-green (atomic kubectl patch switch)     │  ║
  └──────────────────────────┬──────────────────────────────────┘  ║
    → 06b_infrastructure_apply_artifact.json                        ║
    → 07_deployment_artifact.json + generated/deployment/           ║
                             │                                      ║
                             ▼                                      ║
  ╔═════════════════════════════════════════════════════════════════╣
  ║            Testing Loop  [Stage 2 — Infrastructure]            ║
  ║                                                                 ║
  ║   ┌─────────────────────────────────────────────────────────┐  ║
  ║   │                   Testing Agent                          │  ║
  ║   │     Live HTTP tests via httpx (curl-equivalent)         │  ║
  ║   │           → 05b_testing_infrastructure.json             │  ║
  ║   └────────────────────────┬────────────────────────────────┘  ║
  ║                            │                                    ║
  ║             ┌──────────────┴────────────────┐                  ║
  ║             ▼                               ▼                  ║
  ║   ✓ all services pass           ✗ services failing             ║
  ║             │                               │                  ║
  ║             │                               ▼                  ║
  ║             │              ┌────────────────────────────────┐  ║
  ║             │              │  Engineering Agent             │  ║
  ║             │              │  (re-gen failed services only) │  ║
  ║             │              │  + Infrastructure Agent        │  ║
  ║             │              │  (restart containers)          │  ║
  ║             │              └───────────────┬────────────────┘  ║
  ║             │                              │ retry (up to 2×)  ║
  ║             │                              └──► Testing Stage 2 ║
  ╚═════════════╪═════════════════════════════════════════════════╝
                │  ✓ live tests pass
                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │         Testing Agent  [Stage 3 — Final Sign-off]           │
  │   Final verification against original requirements          │
  └─────────────────────────────────────────────────────────────┘
                   → 05c_testing_review.json
```

---

## Agents

| Agent | Role | Output |
|---|---|---|
| **Discovery Agent** | Extracts requirements, goals, constraints, scope, risks, and success criteria from raw text. Two-phase: phase 1 = facts and scope; phase 2 = interpretation decisions | `DiscoveryArtifact` |
| **Architecture Agent** | Designs the system: components, data flow, API contracts, security model. Two-phase: phase 1 = structure; phase 2 = design decisions | `ArchitectureArtifact` |
| **Spec Agent** | Generates the forward contract (OpenAPI 3.0 + SQL DDL) that all engineering implements against | `GeneratedSpecArtifact` |
| **Engineering Agent** | Orchestrates BE + BFF + FE sub-agents in parallel via `asyncio.gather` | `EngineeringArtifact` |
| ↳ **Backend Agent** | Tech-agnostic backend (configurable language/framework) — files under `backend/` | `ServiceArtifact` |
| ↳ **BFF Agent** | Tech-agnostic BFF layer (configurable language/framework) — files under `bff/`. Opt-in: `components.bff: true` | `ServiceArtifact` |
| ↳ **Frontend Agent** | Tech-agnostic frontend (configurable framework/language) — files under `frontend/`. Opt-in: `components.frontend: true` | `ServiceArtifact` |
| ↳ **Mobile Agent** | Tech-agnostic mobile apps (configurable platforms) — files under `mobile/`. Opt-in via `--mobile` or `components.mobile: true` | `ServiceArtifact` |
| **Infrastructure Agent** | Dockerfiles + docker-compose for the full stack; tech-stack-aware | `InfrastructureArtifact` |
| **Deployment Agent** | GitHub Actions CI/CD workflows, Kubernetes manifests, Helm chart, blue-green + canary strategies, rollback scripts | `DeploymentArtifact` |
| **Review Agent** | Security (OWASP), reliability, code quality — feedback loop until no critical or high issues. Score: start 100, deduct 15/8/3/1 per critical/high/medium/low per dimension, weighted average (security×0.35, reliability×0.25, maintainability×0.25, performance×0.15). Pass: no criticals AND overall >= 70 | `ReviewArtifact` |
| **Testing Agent** | 3-stage: architecture plan → live HTTP via httpx → final sign-off. All checks use plain HTTP request/response | `TestingArtifact` |

---

## SDLC Coverage

| SDLC Phase | Agent | Status |
|---|---|---|
| Requirements Discovery | Discovery Agent | ✅ Active |
| System Architecture | Architecture Agent | ✅ Active |
| API Contract and Database Design | Spec Agent | ✅ Active |
| Backend Development | Backend Agent | ✅ Active |
| BFF Development | BFF Agent | ✅ Active |
| Frontend Development | Frontend Agent | ✅ Active |
| Mobile Development (React Native, Flutter, Swift, Kotlin) | Mobile Agent | ✅ Active (opt-in) |
| Infrastructure / IaC | Infrastructure Agent | ✅ Active |
| Code Review and Security Audit | Review Agent | ✅ Active |
| Testing (plan + live HTTP) | Testing Agent | ✅ Active |
| CI/CD Pipelines (GitHub Actions, K8s, Helm, canary + blue-green) | Deployment Agent | ✅ Active |
| API Documentation (Swagger UI, ADRs, runbooks) | Documentation Agent | 🔜 Planned |
| Observability (Prometheus, OpenTelemetry, Grafana) | Observability Agent | 🔜 Planned |
| Database Migrations (Flyway / Liquibase) | Migration Agent | 🔜 Planned |
| Performance and Load Testing (k6 / Gatling) | Performance Agent | 🔜 Planned |
| Compliance Checks (GDPR, SOC2, HIPAA) | Compliance Agent | 🔜 Planned |
| Dependency and Vulnerability Scanning (SAST, CVE) | Security Scan Agent | 🔜 Planned |
| Technical Debt and Refactoring | Maintenance Agent | 🔜 Planned |

---

## Deterministic Review Scoring

- **Per-dimension score:** start at 100 and deduct per-issue penalties: critical (-15), high (-8), medium (-3), low (-1).
- **Overall score:** weighted average across dimensions: security × 0.35, reliability × 0.25, maintainability × 0.25, performance × 0.15.
- **Pass criteria:** no critical issues AND overall_score >= 70.

This deterministic formula replaces free-form model scoring so results are reproducible and comparable across iterations. See `src/llm_sdlc_workflow/prompts/review_agent.md` for the exact prompt text used by the Review Agent.

---

## Configuring the Pipeline

By default the pipeline generates a tech-agnostic backend only (BFF and frontend are disabled). Add BFF and/or frontend with `--bff` / `--frontend` flags or `components.bff: true` in `pipeline.yaml`. Everything is overridable via CLI flags, `pipeline.yaml`, or environment variables — no Python code changes required.

> `pipeline.yaml` is auto-loaded from the current working directory when present — no `--config` flag needed.

### Component Toggles

| Flag | pipeline.yaml | Effect |
|---|---|---|
| _(default)_ | `components.bff: false` | BFF sub-agent disabled |
| `--bff` | `components.bff: true` | BFF enabled |
| _(default)_ | `components.frontend: false` | Frontend sub-agent disabled |
| `--no-frontend` | `components.frontend: false` | Frontend disabled (explicit) |
| `--mobile` | `components.mobile_platforms: ["React Native"]` | Single React Native mobile app |
| `--mobile-platform P` | `components.mobile_platforms: [P]` | Single platform of your choice |
| `--mobile-platform P1 --mobile-platform P2` | `components.mobile_platforms: [P1, P2]` | Multiple platforms in parallel |

### Tech-Stack Preferences

| Flag | pipeline.yaml key | Default |
|---|---|---|
| `--backend-lang LANG` | `tech.backend_language` | Configurable |
| `--backend-framework FW` | `tech.backend_framework` | Configurable |
| `--bff-lang LANG` | `tech.bff_language` | Configurable |
| `--bff-framework FW` | `tech.bff_framework` | Spring WebFlux |
| `--frontend-framework FW` | `tech.frontend_framework` | Configurable |
| `--frontend-lang LANG` | `tech.frontend_language` | TypeScript |
| `--mobile-platform PLAT` | `components.mobile_platforms: [PLAT]` | Configurable |

### Common Configurations

#### Pure API project (default)

```bash
python3.11 main.py --requirements reqs.txt
```

#### Full-stack project (backend + BFF + frontend)

```bash
python3.11 main.py \
  --requirements reqs.txt \
  --bff \
  --frontend
```

#### Go + Gin backend, Vue frontend

```bash
python3.11 main.py \
  --requirements reqs.txt \
  --backend-lang Go \
  --backend-framework Gin \
  --frontend-framework Vue
```

#### Full stack + React Native mobile

```bash
python3.11 main.py \
  --requirements reqs.txt \
  --mobile
```

#### iOS and Android native — generated in parallel

```bash
python3.11 main.py \
  --requirements reqs.txt \
  --mobile-platform "iOS (Swift)" \
  --mobile-platform "Android (Kotlin)"
```

#### All three mobile targets at once

```bash
python3.11 main.py \
  --requirements reqs.txt \
  --mobile-platform "React Native" \
  --mobile-platform "iOS (Swift)" \
  --mobile-platform "Android (Kotlin)"
```

### pipeline.yaml — Full Configuration Reference

```yaml
# pipeline.yaml

# ─── Component Toggles ───────────────────────────────────────────────────────
components:
  backend: true
  bff: false
  frontend: false
  mobile_platforms: []
  # mobile_platforms: ["React Native"]
  # mobile_platforms: ["iOS (Swift)", "Android (Kotlin)"]

# ─── Tech-Stack Preferences ──────────────────────────────────────────────────
tech:
  backend_language: null     # "Kotlin" | "Go" | "Node.js" | "Java" | "Python" | ...
  backend_framework: null    # "Spring Boot" | "Gin" | "Express" | "FastAPI" | ...
  bff_language: null
  bff_framework: null
  frontend_framework: null   # "Vue" | "Angular" | "Next.js" | "Svelte" | "React" | ...
  frontend_language: null    # "TypeScript" | "JavaScript"

# ─── Pipeline Behaviour ──────────────────────────────────────────────────────
pipeline:
  max_review_iterations: 3
  # model: claude-haiku-4-5-20251001

# ─── Spec-Driven Constraints ─────────────────────────────────────────────────
spec:
  tech_constraints: null     # e.g. "PostgreSQL 16, Redis 7, JWT auth"
  arch_constraints: null     # e.g. "12-factor app, stateless, horizontal scaling"
  files: []
```

### Mobile Agent

Multiple platforms run simultaneously as independent `MobileAgent` instances via `asyncio.gather`.

| Platform | Output directory | Default stack |
|---|---|---|
| React Native (default) | `mobile_react_native/` | Expo SDK 51, React Navigation 6, Zustand, Axios |
| Flutter | `mobile_flutter/` | Riverpod 2, Dio, GoRouter, Flutter 3.22 |
| iOS (Swift) | `mobile_ios_swift/` | SwiftUI + Combine, URLSession, async/await |
| Android (Kotlin) | `mobile_android_kotlin/` | Jetpack Compose + ViewModel, Retrofit 2, Coroutines |

---

## Human Intelligence Checkpoints

The pipeline pauses automatically at four checkpoints. At each pause it prints a summary and waits for input before continuing.

```
⏸  Pipeline paused — human review required

  Requirements extracted : 12
  Goals identified       : 5

  Artifact → artifacts/my_run/01_discovery_artifact.json

  ↵ Enter — proceed    s — skip checkpoint    a — abort pipeline
  ▶ _
```

| # | Checkpoint | After Agent | Why It Matters |
|---|---|---|---|
| 1 | Requirements Validated | Discovery Agent | Confirm the agent correctly interpreted ambiguous requirements |
| 2 | Architecture Approved | Architecture Agent + Test | Review technology choices against team expertise and existing systems |
| 3 | **API Contract Approved** | Spec Agent | The OpenAPI + DDL is a public contract — changes after this are expensive |
| 4 | Security and Quality Review | Review Agent | LLMs miss context-specific threat models and organisation-specific compliance requirements |

> **CI/CD mode:** pass `--auto` to skip all checkpoints. Checkpoints are also auto-skipped when stdin is not a TTY.

### Checkpoint 3 — API Contract (most critical)

The pipeline pauses after the Spec Agent. Edit the contract files freely before pressing Enter:

```bash
vim artifacts/my_run/generated/specs/openapi.yaml
vim artifacts/my_run/generated/specs/schema.sql
# Then press Enter — Engineering implements your edited contract exactly
```

### Incremental feature development

```bash
# Sprint 1
python3.11 main.py --requirements sprint1.txt --output-dir ./artifacts/sprint1

# Sprint 2 — extends sprint 1 contract without breaking existing endpoints
python3.11 main.py \
  --requirements sprint2.txt \
  --from-run ./artifacts/sprint1 \
  --output-dir ./artifacts/sprint2
```

---

## Resilience and Reliability

### Self-healing responses

When the LLM returns malformed JSON or an object that fails Pydantic validation, the pipeline performs one self-heal attempt: the raw broken response and exact error message are sent back to the LLM with instructions to return corrected JSON. If the corrected response also fails, the original error is raised and captured in the event log.

### LLM call retry

Every LLM call retries up to 3 times with exponential back-off on transient errors (rate limits, network timeouts, server errors).

### Coercion layer

Field-level coercion validators handle common LLM schema deviations before validation:

| LLM deviation | Coercion applied |
|---|---|
| `List[str]` field contains dict objects | Extracts string value from dict |
| `str` field returned as scoped object | Flattened to readable string |
| `Dict[str, str]` returned as nested objects | Flattened to plain string |
| `List[int]` returned with string entries | Cast to `int` |
| Missing optional list field | Defaults to `[]` |

### Full traceability

Every retry, self-heal attempt, and parse error is recorded as a `PipelineEvent` and written to `DECISIONS_LOG.md` after every completed stage:

```markdown
## Pipeline Events

| Time                | Agent          | Type        | Message                                      |
|---------------------|----------------|-------------|----------------------------------------------|
| 2026-03-24 17:43:12 | Review Agent   | parse_error | JSON/validation error — attempting self-heal |
| 2026-03-24 17:43:15 | Review Agent   | self_heal   | Self-heal succeeded — corrected JSON accepted |
| 2026-03-24 17:41:05 | Architecture   | retry       | Attempt 1/3 failed — retrying in 5s          |
```

---

## Multi-Project Support

### Option 1 — Tech constraints flag

```bash
python3.11 main.py \
  --requirements reqs.txt \
  --tech-constraints "Python FastAPI, PostgreSQL, Next.js frontend"
```

### Option 2 — Dedicated config file per project (recommended for teams)

```yaml
# my_project/pipeline.yaml
components:
  bff: false
  mobile_platforms:
    - "iOS (Swift)"
    - "Android (Kotlin)"

tech:
  backend_language: Go
  backend_framework: Gin
  frontend_framework: Vue
  frontend_language: TypeScript

spec:
  tech_constraints: "PostgreSQL 16, Redis 7, JWT auth"
  arch_constraints: "12-factor app, horizontal scaling"
```

```bash
python3.11 main.py --config my_project/pipeline.yaml
```

### Option 3 — Edit agent prompts per project

Each agent's behaviour is controlled by a Markdown file in `prompts/`. No Python changes required.

---

## Installation

**Prerequisites:** Python 3.11+, Docker, GitHub CLI (`gh`).

```bash
git clone https://github.com/vb-nattamai/llm-sdlc-workflow.git
cd llm-sdlc-workflow

pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

### Authentication

The pipeline calls the GitHub Models API by default — an OpenAI-compatible endpoint included with every GitHub Copilot plan. No separate API account required.

**Option A — GitHub CLI (recommended)**

```bash
gh auth login
python3.11 main.py --requirements my_requirements.txt
```

**Option B — Personal Access Token**

```bash
export GITHUB_TOKEN=github_pat_XXXXXXXXXXXXXXXXXXXX
python3.11 main.py --requirements my_requirements.txt
```

### Bring Your Own API Key

Three environment variables control the provider:

| Variable | Purpose | Default |
|---|---|---|
| `PIPELINE_BASE_URL` | API endpoint (any OpenAI-compatible URL) | `https://models.inference.ai.azure.com` |
| `PIPELINE_API_KEY` | API key (overrides GitHub token) | GitHub token |
| `PIPELINE_MODEL` | Model name | `gpt-4o` |

### Provider Quick Reference

| Provider | `PIPELINE_BASE_URL` | Recommended model |
|---|---|---|
| GitHub Models (default) | `https://models.inference.ai.azure.com` | `gpt-4o` |
| Anthropic | `https://api.anthropic.com/v1` | `claude-haiku-4-5-20251001` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| xAI Grok | `https://api.x.ai/v1` | `grok-3-beta` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` |
| Mistral | `https://api.mistral.ai/v1` | `mistral-large-latest` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.3` |

**Anthropic example:**

```bash
export PIPELINE_BASE_URL="https://api.anthropic.com/v1"
export PIPELINE_API_KEY="$ANTHROPIC_API_KEY"
export PIPELINE_MODEL="claude-haiku-4-5-20251001"
python3.11 main.py --requirements reqs.txt --auto
```

**Ollama (local, no API costs):**

```bash
ollama pull llama3.3
ollama serve

export PIPELINE_API_KEY=ollama
export PIPELINE_BASE_URL=http://localhost:11434/v1
export PIPELINE_MODEL=llama3.3
python3.11 main.py --requirements reqs.txt
```

### GitHub Actions

```yaml
# .github/workflows/pipeline.yml
name: Run LLM SDLC Pipeline

on:
  workflow_dispatch:
    inputs:
      requirements:
        description: "Path to requirements file"
        default: "examples/hello_world_requirements.txt"

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - name: Run pipeline
        env:
          PIPELINE_API_KEY:  ${{ secrets.PIPELINE_API_KEY }}
          PIPELINE_BASE_URL: ${{ vars.PIPELINE_BASE_URL }}
          PIPELINE_MODEL:    ${{ vars.PIPELINE_MODEL }}
        run: python3.11 main.py --requirements ${{ github.event.inputs.requirements }} --auto
      - uses: actions/upload-artifact@v4
        with:
          name: pipeline-artifacts
          path: artifacts/
```

---

## Usage

### New project from scratch

```bash
# Built-in example
python3.11 main.py

# Your own requirements
python3.11 main.py --requirements my_requirements.txt

# With tech-stack constraints
python3.11 main.py \
  --requirements my_requirements.txt \
  --tech-constraints "Kotlin Spring Boot, React 18, PostgreSQL" \
  --output-dir ./artifacts/my_project

# Via config file
python3.11 main.py --config pipeline.yaml
```

### Incremental development — extending an existing contract

```bash
# Run 1
python3.11 main.py \
  --requirements v1_requirements.txt \
  --output-dir ./artifacts/run_v1

# Run 2 — adds new features without breaking the live API
python3.11 main.py \
  --requirements v2_new_feature.txt \
  --from-run ./artifacts/run_v1 \
  --output-dir ./artifacts/run_v2
```

The Spec Agent marks all existing paths `x-existing: true`. Engineering agents must not break them.

### All CLI Flags

```
# Input / output
--requirements FILE       Path to a requirements text file
--interactive             Type requirements at the terminal
--config FILE             Load configuration from pipeline.yaml
--spec FILE               Spec file (OpenAPI YAML, SQL DDL) — repeatable
--output-dir DIR          Artifacts output directory
--project-name NAME       Generated code directory name
--from-run DIR            Extend the existing contract from a previous run

# Constraints
--tech-constraints STR    e.g. "Python FastAPI, PostgreSQL, Redis"
--arch-constraints STR    e.g. "Microservices on Kubernetes"

# Execution
--auto                    Skip all human review checkpoints (CI/CD mode)
--model MODEL             LLM model (default: gpt-4o)
--max-review-iterations N Max review cycles (default: 3)

# Component toggles
--bff                     Enable BFF sub-agent
--frontend                Enable Frontend sub-agent
--mobile                  Enable Mobile sub-agent (React Native by default)

# Tech-stack preferences
--backend-lang LANG       e.g. "Python", "Go", "Node.js"
--backend-framework FW    e.g. "FastAPI", "Gin"
--bff-lang LANG
--bff-framework FW        e.g. "NestJS"
--frontend-framework FW   e.g. "Vue", "Next.js"
--frontend-lang LANG
--mobile-platform PLAT    Repeatable: "React Native", "Flutter", "iOS (Swift)", "Android (Kotlin)"
```

---

## Output Structure

```
artifacts/run_20260318_120000/
├── 00_pipeline_report.json
├── 01_discovery_artifact.json
├── 02_architecture_artifact.json
├── 03_engineering_artifact.json
├── 03a_backend_artifact.json
├── 03b_bff_artifact.json
├── 03c_frontend_artifact.json
├── 03d_mobile_react_native_artifact.json
├── 04_generated_spec_artifact.json
├── 04_review_artifact_iter<N>.json
├── 05a_testing_architecture.json
├── 05b_testing_infrastructure.json
├── 05c_testing_review.json
├── 06a_infrastructure_plan_artifact.json
├── 06b_infrastructure_apply_artifact.json
├── 07_deployment_artifact.json
├── DECISIONS_LOG.md
└── generated/
    ├── backend/
    ├── bff/
    ├── frontend/
    ├── mobile_react_native/
    ├── mobile_ios_swift/
    ├── mobile_android_kotlin/
    ├── specs/
    │   ├── openapi.yaml
    │   └── schema.sql
    ├── deployment/
    │   ├── .github/workflows/
    │   ├── k8s/
    │   ├── helm/
    │   └── scripts/
    └── docker-compose.yml
```

The `generated/specs/` directory is what `--from-run` reads on the next run.

---

## Project Structure

```
llm-sdlc-workflow/
├── main.py
├── pyproject.toml
├── pipeline.yaml
│
├── src/
│   └── llm_sdlc_workflow/
│       ├── pipeline.py
│       ├── config.py
│       ├── agents/
│       │   ├── base_agent.py
│       │   ├── discovery_agent.py
│       │   ├── architecture_agent.py
│       │   ├── spec_agent.py
│       │   ├── engineering_agent.py
│       │   ├── backend_agent.py
│       │   ├── bff_agent.py
│       │   ├── frontend_agent.py
│       │   ├── mobile_agent.py
│       │   ├── infrastructure_agent.py
│       │   ├── deployment_agent.py
│       │   ├── review_agent.py
│       │   └── testing_agent.py
│       ├── models/
│       │   └── artifacts.py
│       └── prompts/
│           ├── discovery_agent.md
│           ├── architecture_agent.md
│           ├── spec_agent.md
│           ├── backend_agent.md
│           ├── bff_agent.md
│           ├── frontend_agent.md
│           ├── mobile_agent.md
│           ├── infrastructure_agent.md
│           ├── deployment_agent.md
│           ├── review_agent.md
│           └── testing_agent.md
│
├── tests/
│   ├── test_artifacts.py
│   └── test_pipeline.py
│
└── examples/
    ├── status_api_requirements.txt
    ├── ping_echo_requirements.txt
    ├── todo_api_requirements.txt
    └── hello_world_requirements.txt
```

---

## Customising Prompts

Every agent's behaviour is defined entirely by a Markdown file in `prompts/`. Edit any `.md` file to change persona, output style, or constraints — no Python changes required.

The JSON schema at the bottom of each prompt file defines the artifact structure the agent must return. Keep those schemas intact or update the matching Pydantic model in `models/artifacts.py`.

---

## Roadmap — Planned Agents

| Agent | SDLC Phase | Description |
|---|---|---|
| DocumentationAgent | Docs | Swagger UI config, Architecture Decision Records, runbooks |
| ObservabilityAgent | Ops | Prometheus metrics, structured logging, OpenTelemetry tracing |
| MigrationAgent | Database | Flyway / Liquibase migration scripts with rollback |
| PerformanceAgent | Testing | k6 / Gatling load test scripts, SLA budgets |
| ComplianceAgent | Governance | GDPR data map, SOC2 controls checklist, HIPAA PHI handling |
| SecurityScanAgent | Security | SAST output triage, dependency CVE report, secrets detection |
| MaintenanceAgent | Maintenance | Dependency update PRs, technical debt scoring |

---

## How It Works

1. **Single HTTP client for all providers** — all LLM calls go through the OpenAI Python SDK used as a generic HTTP client. Swapping providers is purely a matter of changing `PIPELINE_BASE_URL` and `PIPELINE_API_KEY`.

2. **Chunked LLM generation** — each agent generates files in two LLM calls: first a plan with all content marked `__PENDING__`, then one call per file to fill it. Prevents token-limit failures on large codebases.

3. **Contract-first spec** — the Spec Agent generates an OpenAPI + DDL contract before any code is written. All engineering sub-agents implement against this single source of truth.

4. **Parallel sub-agents** — only enabled sub-agents run, via `asyncio.gather`. Infrastructure planning also runs in parallel with Engineering. After the review loop, the Infrastructure Agent and Deployment Agent both run in parallel.

5. **Deterministic review scoring** — start at 100, deduct fixed points per issue severity, weighted across security/reliability/maintainability/performance. Results are reproducible across iterations.

6. **Compact context** — each agent receives a compact summary of upstream artifacts, not raw JSON blobs. Keeps prompts lean and LLM calls fast.

7. **Incremental contracts** — `--from-run` marks existing API paths `x-existing: true` so new runs only add endpoints, never silently break a live API.

8. **Full decision traceability** — every agent records `DecisionRecord` entries in `DECISIONS_LOG.md`, written after every completed stage.

9. **Topology contract** — the pipeline computes canonical port assignments before any agent runs and injects this contract into every agent that generates ports, Dockerfiles, or docker-compose. Prevents port-mismatch bugs across services.

---

## Requirements

- Python 3.11+
- `openai` Python package (installed via `pip install -e .`)
- GitHub CLI (`gh`) authenticated with a GitHub Copilot licence — only required when using the default GitHub Models endpoint
- Docker — for the Infrastructure Agent to build and start containers

---

## License

MIT
