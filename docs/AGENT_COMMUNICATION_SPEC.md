# Agent Communication & Inter-Agent Contract Specification

## Problem Statement

Agents currently operate with **hardcoded assumptions** rather than reading from
a shared contract. This causes silent inconsistencies that surface only at
runtime — for example, `backend_agent.md` hardcodes port 8081 while
`docker-compose.yml` uses 8080 when BFF is disabled.

The root causes are:

| Location | Hardcoded value | Should read from |
|---|---|---|
| `backend_agent.md` | `Internal port: 8081` | topology contract |
| `backend_agent.py` fill template | `port 8081, internal` | topology contract |
| `infrastructure_agent.md` README spec | `BFF (8080) → Backend (8081)` | topology contract |
| `infrastructure_agent.md` primary port | `primary_service_port = 8080` | topology contract |
| `engineering_agent._port_hint()` | `{"backend": "8081", ...}` | topology contract |
| All agent prompts | Assumes full 3-tier stack | `PipelineConfig.components` |

---

## Architecture: Pull-Based Contract Model

Agents **do not call each other** directly. They communicate through **shared
artifact models** that flow down the pipeline as structured inputs. Each agent
must:

1. Read all relevant inputs from its artifact parameters
2. Produce an artifact that later agents depend on
3. Never invent values (ports, service names, URLs) that should come from an
   earlier agent's output

```
PipelineConfig
    │
    ▼
TopologyContract (built by Pipeline before any agent runs)
    │
    ├──► DiscoveryAgent     → DiscoveryArtifact
    │         │
    ├──► ArchitectureAgent  → ArchitectureArtifact
    │         │
    ├──► SpecAgent          → GeneratedSpecArtifact   ← topology baked in here
    │         │                 (service_ports, monorepo_services are authoritative)
    │         ▼
    ├──► BackendAgent   ─┐
    ├──► BffAgent       ├─ all read GeneratedSpecArtifact.service_ports
    ├──► FrontendAgent  ─┘
    │         │
    ├──► InfrastructureAgent  ← reads topology to build docker-compose + diagrams
    │
    └──► ReviewAgent          ← reads engineering + infra output (no topology needed)
```

---

## TopologyContract (new shared model)

The `Pipeline` builds this from `PipelineConfig` **before** any agent runs. It
is the single source of truth for service topology.

```python
@dataclass
class TopologyContract:
    enabled_services: List[str]        # ["backend"] or ["backend", "bff", "frontend"]
    service_ports: Dict[str, int]      # {"backend": 8080} or {"backend": 8081, "bff": 8080, ...}
    primary_service: str               # the externally-exposed service name
    primary_port: int                  # host port clients connect to
    has_bff: bool
    has_frontend: bool
    service_roles: Dict[str, str]      # {"backend": "internal REST API", "bff": "external gateway"}
    architecture_diagram: str          # ASCII string built from actual topology
```

### Port assignment rules

| Topology | backend port | bff port | frontend port | primary |
|---|---|---|---|---|
| backend only | 8080 (external) | — | — | backend:8080 |
| backend + bff | 8081 (internal) | 8080 (external) | — | bff:8080 |
| backend + bff + frontend | 8081 (internal) | 8082 (internal) | 3000 (external) | frontend:3000 |
| backend + frontend (no bff) | 8081 (internal) | — | 3000 (external) | frontend:3000 |

**Rule**: The externally-exposed service gets port 8080 (or their natural port
for frontend). Internal services get sequential ports starting at 8081.

### Architecture diagram

Built deterministically from topology, not invented by the LLM:

```
# backend only
Browser → Backend (8080)

# backend + bff
Browser → BFF (8080) → Backend (8081)

# backend + bff + frontend
Browser → Frontend (3000) → BFF (8080) → Backend (8081) → DB

# backend + frontend  
Browser → Frontend (3000) → Backend (8081)
```

---

## Per-Agent Input/Output Contracts

### 1. DiscoveryAgent

| | Type | Source |
|---|---|---|
| **IN** | raw requirements text | user CLI |
| **IN** | `TopologyContract` | Pipeline |
| **OUT** | `DiscoveryArtifact` | saved as `01_discovery_artifact.json` |

**Contract rules**:
- Must not invent tech stack constraints that contradict `TopologyContract.enabled_services`
- Must reflect the actual service topology in its summary

---

### 2. ArchitectureAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `TopologyContract` | Pipeline |
| **OUT** | `ArchitectureArtifact` | saved as `02_architecture_artifact.json` |

**Contract rules**:
- `components` list must only include services listed in `TopologyContract.enabled_services`
- Port assignments in `data_flow` and `api_design` must match `TopologyContract.service_ports`
- `deployment_strategy` must match the actual topology (not assume 3-tier if backend-only)

**Currently missing**: ArchitectureAgent does not receive `TopologyContract`. It
must be added so the LLM designs the correct architecture from the start.

---

### 3. SpecAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `ArchitectureArtifact` | step 2 |
| **IN** | `TopologyContract` | Pipeline |
| **OUT** | `GeneratedSpecArtifact` | saved as `04_generated_spec_artifact.json` |

**Contract rules** (most critical):
- `GeneratedSpecArtifact.service_ports` **MUST** be set from `TopologyContract.service_ports`, not invented
- `GeneratedSpecArtifact.monorepo_services` **MUST** match `TopologyContract.enabled_services`
- `tech_stack_constraints` must include port assignments from topology
- `architecture_constraints` must include the correct architecture diagram string

**This is the checkpoint**: once the spec is set, all downstream agents must
only read ports from `contract.service_ports[service_name]`, never from hardcoded values.

---

### 4. BackendAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `ArchitectureArtifact` | step 2 |
| **IN** | `GeneratedSpecArtifact` | step 3 |
| **OUT** | `EngineeringArtifact` (service_name="backend") | merged into step 4 |

**Contract rules**:
- Port in `EXPOSE`, `HEALTHCHECK`, `CMD -Dserver.port`, and application.yml **MUST** come from `contract.service_ports["backend"]`
- Health check URL must use the backend's own port, not the primary service port
- `infrastructure` field in response JSON must say `"internal service, port {backend_port}"` or `"external service, port {backend_port}"` based on topology role

**Required code change**: `BackendAgent.run()` must extract `backend_port = contract.service_ports.get("backend", 8080)` and inject it into both the plan message and the `fill_message_tmpl`.

---

### 5. BffAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `ArchitectureArtifact` | step 2 |
| **IN** | `GeneratedSpecArtifact` | step 3 |
| **OUT** | `EngineeringArtifact` (service_name="bff") | merged into step 4 |

**Contract rules**:
- BFF port from `contract.service_ports.get("bff", 8080)`
- Backend base URL in BFF config → `http://backend:{contract.service_ports["backend"]}`
- Never hardcode the backend port — read it from the contract

---

### 6. FrontendAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `ArchitectureArtifact` | step 2 |
| **IN** | `GeneratedSpecArtifact` | step 3 |
| **OUT** | `EngineeringArtifact` (service_name="frontend") | merged into step 4 |

**Contract rules**:
- API base URL in frontend env → `http://localhost:{contract.service_ports.get("bff") or contract.service_ports.get("backend")}`
- Port 3000 for development server is a frontend convention (not inter-service), OK to hardcode

---

### 7. InfrastructureAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `ArchitectureArtifact` | step 2 |
| **IN** | `EngineeringArtifact` | step 4 (full assembled) |
| **IN** | `TopologyContract` | Pipeline |
| **OUT** | `InfrastructureArtifact` | saved as `06a_infrastructure_plan_artifact.json` |

**Contract rules**:
- `docker-compose.yml` port mappings **MUST** match `TopologyContract.service_ports`
- `Dockerfile.backend` `EXPOSE` and `CMD -Dserver.port` **MUST** match `contract.service_ports["backend"]`
- `primary_service_port` in artifact **MUST** equal `TopologyContract.primary_port`
- `health_check_path` for health polling **MUST** target the `TopologyContract.primary_service`
- README architecture diagram **MUST** use `TopologyContract.architecture_diagram`

**Required code change**: `InfrastructureAgent.run()` must receive and inject
`TopologyContract` into both the plan message and `fill_message_tmpl`.

---

### 8. ReviewAgent

| | Type | Source |
|---|---|---|
| **IN** | `DiscoveryArtifact` | step 1 |
| **IN** | `ArchitectureArtifact` | step 2 |
| **IN** | `EngineeringArtifact` | step 4 |
| **IN** | `InfrastructureArtifact` | step 6 |
| **OUT** | `ReviewArtifact` | saved as `04_review_artifact_iter{N}.json` |

**Contract rules**:
- Must judge files ONLY against the code actually present in the context
- Must NOT re-report issues from previous iterations (no `prev_section` anchoring)
- Score must be based only on what is verifiably present in the shown file content

---

### 9. TestingAgent

| | Type | Source |
|---|---|---|
| **IN** | `InfrastructureArtifact` (base_url, container_running) | step 6 |
| **IN** | `GeneratedSpecArtifact` (openapi_spec for test generation) | step 3 |
| **OUT** | `TestingArtifact` | saved as `05a/b/c_testing_*.json` |

**Contract rules**:
- `base_url` is always `http://localhost:{primary_port}` — comes from `InfrastructureArtifact.base_url`, never hardcoded
- Test paths must be derived from `GeneratedSpecArtifact.openapi_spec`, not guessed

---

## What Needs to Change (Implementation Tasks)

### Step 1 — Add `TopologyContract` to `config.py` or `models/artifacts.py`

```python
@dataclass
class TopologyContract:
    enabled_services: List[str]
    service_ports: Dict[str, int]
    primary_service: str
    primary_port: int
    has_bff: bool
    has_frontend: bool
    architecture_diagram: str

    @classmethod
    def from_config(cls, cfg: "PipelineConfig") -> "TopologyContract":
        services = cfg.enabled_services()
        has_bff = cfg.components.bff
        has_frontend = cfg.components.frontend

        # Assign ports based on topology
        ports: Dict[str, int] = {}
        if "backend" in services:
            ports["backend"] = 8080 if (not has_bff and not has_frontend) else 8081
        if "bff" in services:
            ports["bff"] = 8080
        if "frontend" in services:
            ports["frontend"] = 3000
        for svc in services:
            if svc.startswith("mobile_"):
                ports[svc] = 0  # no port (connects via BFF URL)

        # Determine primary (externally-reachable) service
        if has_frontend:
            primary = "frontend"
            primary_port = 3000
        elif has_bff:
            primary = "bff"
            primary_port = 8080
        else:
            primary = "backend"
            primary_port = 8080

        # Build ASCII diagram
        diagram = cls._build_diagram(services, ports, primary)

        return cls(
            enabled_services=services,
            service_ports=ports,
            primary_service=primary,
            primary_port=primary_port,
            has_bff=has_bff,
            has_frontend=has_frontend,
            architecture_diagram=diagram,
        )

    @staticmethod
    def _build_diagram(services, ports, primary):
        parts = []
        if "frontend" in services:
            parts.append(f"Browser → Frontend ({ports.get('frontend', 3000)})")
        if "bff" in services:
            parts.append(f"BFF ({ports.get('bff', 8080)})")
        if "backend" in services:
            parts.append(f"Backend ({ports.get('backend', 8081)})")
        parts.append("DB")
        return " → ".join(parts)
```

---

### Step 2 — Pipeline builds `TopologyContract` before first agent

```python
# In Pipeline.run(), before step 1:
topology = TopologyContract.from_config(self._config)
```

---

### Step 3 — SpecAgent writes topology into `GeneratedSpecArtifact`

After `SpecAgent.run()` returns, the pipeline must enforce:

```python
spec.monorepo_services = topology.enabled_services
spec.service_ports = topology.service_ports
```

This ensures the spec is always authoritative regardless of what the LLM generated.

---

### Step 4 — BackendAgent injects port from contract

In `BackendAgent.run()`:

```python
backend_port = contract.service_ports.get("backend", 8080)
is_external = topology is None or not topology.has_bff

fill_tmpl = (
    f"Write COMPLETE, RUNNABLE {self.tech_hint} content for: {{path}}\n"
    f"Service: backend\n"
    f"Container port: {backend_port} ({"external — directly exposed" if is_external else "internal — sits behind BFF"})\n"
    f"EXPOSE {backend_port}\n"
    f"HEALTHCHECK uses port {backend_port}\n"
    f"CMD -Dserver.port={backend_port}\n"
    ...
)
```

The `contract.service_ports["backend"]` replaces all hardcoded `8081` occurrences.

---

### Step 5 — InfrastructureAgent injects topology into prompts

In `InfrastructureAgent.run()` plan message:

```python
topology_section = f"""
## Deployment topology
Enabled services: {', '.join(topology.enabled_services)}
Port assignments:
{chr(10).join(f"  {svc}: {port}" for svc, port in topology.service_ports.items())}
Primary service (externally exposed): {topology.primary_service}:{topology.primary_port}
Architecture: {topology.architecture_diagram}
"""
```

This replaces the hardcoded BFF-centric diagram and port 8080/8081 assumptions
in `infrastructure_agent.md`.

---

### Step 6 — Fix `engineering_agent._port_hint()` to use contract

```python
def _port_hint(self, service: str, contract: Optional[GeneratedSpecArtifact] = None) -> str:
    if contract and contract.service_ports:
        return str(contract.service_ports.get(service, "?"))
    defaults = {"backend": "8080", "bff": "8080", "frontend": "3000"}
    return defaults.get(service, "?")
```

---

### Step 7 — Update `backend_agent.md` and `infrastructure_agent.md` prompts

Remove all hardcoded port values from both prompts. Replace with placeholders
that will be filled by the Python code before the LLM call:

```
# backend_agent.md — remove this line:
- Docker Compose service name: `backend`. Internal port: **8081**.

# Replace with instruction to use whatever port is in the context:
- Docker Compose service name: `backend`.
- Port, Dockerfile EXPOSE, HEALTHCHECK, and CMD flags are specified in the context below.
- Use EXACTLY the port given in "## Deployment topology" — do not substitute another value.
```

---

## Contract Violation Detection (Future Enhancement)

The `ReviewAgent` and `TestingAgent` should cross-check:

1. `Dockerfile.backend EXPOSE` == `spec.service_ports["backend"]`
2. `docker-compose.yml backend.ports[0].split(":")[1]` == `spec.service_ports["backend"]`
3. `docker-compose.yml primary_service.ports[0].split(":")[0]` == `topology.primary_port`
4. All inter-service URLs use Docker Compose service names, not `localhost`

These checks should be **deterministic** (Python code, not LLM), added to the
`InfrastructureAgent` after file generation.
