# Scale AI Agents: Global Retail IT Orchestrator

**Owners:** Emmanuel Awa, Kaz Sato  
**Track:** Build AI Apps & Agents  
**Session IDs:** GCS109, SHOW134  
**Type:** Live Demo  
**Level:** 200 Technical (Apply/Use)

## Description

Scale multi-agent systems for sophisticated use cases. Use **Google Agent Engine**, **LangGraph**, and **CrewAI** with **MCP** and **A2A** to orchestrate a secure, global retail workflow—all without the infrastructure overhead.

## Setup Instructions

### Prerequisites

* **Python 3.10+**
* **uv** (An extremely fast Python package manager)

### Installation

1. **Install `uv`** (if not already installed):

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. **Sync Dependencies**:
    The project uses a unified virtual environment at the repository root. Navigate to the `02-scale` directory (or root) and sync dependencies:

    ```bash
    uv sync
    ```

3. **Environment Setup**:
    To enable deep tracing of the agents' internal thoughts and tool usage, create a `.env` file in the root directory:

    ```bash
    echo 'CREWAI_TRACING_ENABLED=true' > .env
    echo 'GOOGLE_CLOUD_PROJECT=your-project-id' >> .env
    ```

## Pitch

Ready to coordinate a Multi-Agent System (MAS)? We show how to leverage **Google Agent Platform** to manage a high-performance team where a strategic **Planning Agent** (LangGraph) delegates tasks to tactical **Execution Agents** (CrewAI), enforcing strict security boundaries via **Agent Identity**.

## Demo Leaders & Contributors

* **Emmanuel Awa**
* **Kaz Sato**

## Scenario: Global Retail IT Orchestrator

This demo showcases a **Multi-Agent System (MAS)** designed to handle complex logistics operations.

**The Challenge:** Orchestrating supply chain and inventory management across disparate systems while maintaining strict security controls.

**The Solution:** A "Hub-and-Spoke" delegation model:

1. **Planning Agent (The Brain):** A **LangGraph** state machine that analyzes high-level goals (e.g., "Restock Northeast Region") and delegates tasks. It has **no direct access** to the inventory database. It runs as an A2A-compliant web server.
2. **Execution Agents (The Hands):** Ephemeral **CrewAI** swarms that receive specific tasks (e.g., "Order 500 Vintage Sci-Fi Mugs"). They connect to the **Mercari Product Vector Store** via **MCP**.
3. **Governance:** **Google Agent Platform Agent Identity** ensures "Least Privilege"—only the Execution Agent can touch the database, while the Planning Agent handles strategy.

## Tech Stack

* **Runtime:** Google Agent Engine
* **Planning:** LangGraph (Python)
* **Execution:** CrewAI (Python)
* **Interoperability:** Native A2A (Agent-to-Agent) Protocol via JSON-RPC
* **Data Source:** Mercari Product Vector Store (via REST API)
* **Tooling:** Model Context Protocol (MCP)
* **Security:** Google Agent Platform Agent Identity

## Critical User Journeys (CUJs)

### 1. The "Happy Path" Restock

The **Planning Agent** identifies a stock shortage and delegates a procurement task to a **CrewAI Logistics Agent**. The CrewAI agent uses **Semantic Vector Search** to find the best matching products ("Vintage Sci-Fi Mugs") and places a mock Purchase Order.

### 2. The "Identity Shield" (Security)

A malicious prompt attempts to trick the **Planning Agent** into deleting the vector index. The planner's LLM extracts the destructive intent and routes to a **security path** that attempts the forbidden `delete_index` API call. **Google Agent Engine** blocks it because the Planning Agent's **Identity** lacks `Vector_Store_Write` permissions. The Control Room detects the security block and returns immediately — no re-planning is attempted.

### 3. Cross-Framework Error Handling

The **Planning Agent** requests a discontinued item. The **Execution Agent** fails to find it in the vector store, catches the error, and reports back a structured recommendation ("No inventory found, try broadening search"). The Planning Agent then re-plans automatically.

## Architecture

![architecture](./assets/scale-arch-diagram.png)

```mermaid
graph TD
    User[ADK Agent / Dashboard] --> CR[ADK 2.0 Control Room Agent]
    
    subgraph "Global Coordination (ADK 2.0)"
        CR -->|A2A JSON-RPC 'message/send'| A2AServer[A2A Web Server (Uvicorn)]
    end
    
    subgraph "Strategy Layer (High Privilege)"
        A2AServer -->|Extract Intent| PA[Planning Agent (LangGraph)]
        PA -->|is_destructive?| Router{Route}
    end
    
    subgraph "Security Path (CUJ 2: Identity Shield)"
        Router -->|YES| FA[Attempt Forbidden Action]
        FA -->|PermissionDenied| SR[Generate Security Report]
    end
    
    subgraph "Execution Layer (Restricted Scope)"
        Router -->|NO| EA[Execution Agent (CrewAI)]
        EA -->|Query/Action| MCP[MCP Client]
    end
    
    subgraph "External Systems"
        MCP -->|REST API /api/query| VS_API[Vector Search Service]
        VS_API -->|Semantic Search| VDB[(Mercari Vector Store)]
        MCP -->|Internal Mock| OMS[Mock Order System]
        FA -.->|Blocked by IAM| VS_API
    end
    
    style PA fill:#e1f5fe,stroke:#01579b
    style EA fill:#e8f5e9,stroke:#1b5e20
    style MCP fill:#fff3e0,stroke:#e65100
    style A2AServer fill:#f3e5f5,stroke:#4a148c
    style FA fill:#ffebee,stroke:#b71c1c
    style SR fill:#ffebee,stroke:#b71c1c
    style Router fill:#fff9c4,stroke:#f57f17
```

## Running the Demo

### Testing the Full System (Native A2A with ADK 2.0)

The demonstration relies on a **Google ADK 2.0 Control Room Agent** orchestrating a LangGraph planner via the A2A protocol, which in turn triggers the CrewAI execution swarm.

To test this flow, open **two** terminal windows:

**Terminal 1: Start the A2A LangGraph Server**
This runs the Uvicorn server, exposing the `.well-known/agent-card.json` and listening for tasks.

```bash
uv run agents/planner/a2a_server.py
```

**Terminal 2: Run the ADK 2.0 Control Room**
This script acts as the main entry point (utilizing ADK `InMemoryRunner` and `LlmAgent`). It sends a natural language prompt via an A2A JSON-RPC request to the server, triggering the entire LangGraph -> CrewAI -> MCP flow and managing fallback routing.

```bash
uv run agents/control_room/main.py
```

### Agent Engine Deployment (CUJ 2: Identity Shield)

Scripts for deploying agents to Agent Engine with scoped IAM service accounts.

```bash
# Step 1: Create service accounts and bind IAM roles
bash scripts/setup_iam.sh

# Step 2: Deploy the Planning Agent to Agent Engine
uv run scripts/deploy_to_agent_engine.py --planning-only

# Step 3: Bind the restricted SA to the deployed engine (done automatically by deploy script)

# List deployed engines
uv run scripts/deploy_to_agent_engine.py --list

# Teardown (delete engines, SAs, and IAM bindings)
bash scripts/teardown.sh
```

### Testing the MCP Server (Standalone)

If you need to verify that the Mock Order Management System (OMS) is working independently of the agents, you can test it directly using the official Model Context Protocol Inspector.

1. Open a new terminal window.
2. Run the Inspector with the `-q` (quiet) flag to prevent `uv` from polluting the JSON stream:

    ```bash
    npx @modelcontextprotocol/inspector uv run -q mock_oms_mcp/server.py
    ```

3. Open the provided `localhost:6274` URL in your browser.
4. On the left sidebar, select tools like `check_budget` or `create_purchase_order`, provide arguments (e.g., `amount: 50`, `category: collectibles`), and click "Run Tool" to see the JSON response.

### Running Unit & Integration Tests

The project includes a pytest test suite (55 tests) that covers all components. Unit and integration tests run **without** GCP credentials (all external dependencies are mocked). The E2E tests run against real services and auto-skip without credentials.

```bash
# Run all tests
uv run pytest tests/ -v

# Run only unit tests (fast, no mocking)
uv run pytest tests/unit/ -v

# Run only integration tests (mocked external services)
uv run pytest tests/integration/ -v

# Run E2E tests (requires GCP credentials and network access)
uv run pytest tests/e2e/ -v
```

## Implementation & Test Status

| Component | Source | Tests | Status |
| --------- | ------ | ----- | ------ |
| **DefaultConfig** | `agents/config/default_config.py` | `tests/unit/test_default_config.py` | Tested |
| **Mock OMS MCP Server** (`check_budget`, `create_purchase_order`) | `mock_oms_mcp/server.py` | `tests/unit/test_mock_oms.py` | Tested |
| **Planner State** (`PlanState`) | `agents/planner/state.py` | `tests/integration/test_planner_graph.py` | Tested |
| **Planner Prompts** (`AlertExtraction`, templates) | `agents/planner/prompts.py` | `tests/unit/test_planner_prompts.py` | Tested |
| **Planner Graph** (`PlannerNodes`, `build_planner_graph`) | `agents/planner/graph.py` | `tests/integration/test_planner_graph.py` | Tested |
| **A2A Server** (`PlannerAgentExecutor`, agent card, JSON-RPC) | `agents/planner/a2a_server.py` | `tests/integration/test_a2a_server.py` | Tested |
| **Executor Prompts** (`AGENT_PROMPTS`, `TASK_PROMPTS`) | `agents/executor/src/prompts.py` | `tests/unit/test_executor_prompts.py` | Tested |
| **Executor Tasks** (`ExecutorTasks`) | `agents/executor/src/tasks.py` | `tests/unit/test_executor_tasks.py` | Tested |
| **Executor Agents** (`ExecutorAgents`) | `agents/executor/src/agents.py` | `tests/integration/test_executor_crew.py` | Tested |
| **Executor Crew** (`LogisticsExecutionCrew`) | `agents/executor/src/crew.py` | `tests/integration/test_executor_crew.py` | Tested |
| **MCP Tool Adapters** (`get_mcp_server`, `get_mock_oms_mcp`) | `agents/executor/src/tools.py` | `tests/integration/test_executor_crew.py` | Tested |
| **Control Room Agent** (`LlmAgent`, `delegate_to_planner`) | `agents/control_room/agent.py` | `tests/integration/test_control_room.py` | Tested |
| **CUJ 1: Happy Path Restock** (E2E) | Full stack | `tests/e2e/test_cuj1_happy_path.py` | Tested |
| **Cross-Framework Error Handling / Re-planning** (CUJ 3) | `agents/control_room/agent.py` | `tests/e2e/test_cuj3_replanning.py` | Tested |
| **Identity Shield Graph** (CUJ 2 — routing + IAM check) | `agents/planner/graph.py` | `tests/integration/test_identity_shield.py` | Tested (IAM mocked in CI) |
| **Identity Shield Control Room** (CUJ 2 — security block handling) | `agents/control_room/agent.py` | `tests/e2e/test_cuj2_identity_shield.py` | Tested |
| **Agent Engine Deployment** (Planning Agent) | `scripts/deploy_to_agent_engine.py` | — | Deployed (`reasoningEngines/7579541130434314240`) |
| **Agent Engine Deployment** (Control Room Agent) | `scripts/deploy_to_agent_engine.py` | — | Deployed (`reasoningEngines/2125119031735222272`) |
| **Agent Engine IAM** (service accounts + role binding) | `scripts/setup_iam.sh` | — | Done (`planning-agent-sa`, `execution-agent-sa`) |
| **ADK Agent / Dashboard Frontend** | — | — | TODO |

## CUJ 2 Implementation Plan: Agent Identity via Agent Engine

**Status:** All phases complete. Both agents deployed to Agent Engine with scoped IAM.

Agent Engine is active on `gcp-samples-ic0` (project `761793285222`, `us-central1`).

### Goal

Demonstrate the "Identity Shield": a malicious prompt attempts to trick the Planning Agent into deleting the vector index. Agent Engine intercepts the call and blocks it because the Planning Agent's service account lacks `Vector_Store_Write` permissions.

### Phase 1: Deploy Agents to Agent Engine (DONE)

1. **Created two service accounts** with distinct IAM roles (`scripts/setup_iam.sh`):
   * `planning-agent-sa@gcp-samples-ic0.iam.gserviceaccount.com` — `roles/aiplatform.user` (read-only, no vector store write)
   * `execution-agent-sa@gcp-samples-ic0.iam.gserviceaccount.com` — `roles/aiplatform.user` + `roles/aiplatform.editor` (full access)
2. **Deployed the Planning Agent** (LangGraph) to Agent Engine via `adk deploy agent_engine` (`scripts/deploy_to_agent_engine.py`)
   * Resource: `projects/761793285222/locations/us-central1/reasoningEngines/7579541130434314240`
   * Bound to `planning-agent-sa` via `client.agent_engines.update()`
3. **Deployed the Control Room Agent** to Agent Engine via `adk deploy agent_engine`
   * Resource: `projects/761793285222/locations/us-central1/reasoningEngines/2125119031735222272`
   * Bound to `execution-agent-sa` via `client.agent_engines.update()`
   * Refactored from ADK `Workflow` to `LlmAgent` with `delegate_to_planner` tool (Workflow is alpha-only and not supported by Agent Engine)

### Phase 2: Enforce IAM Boundaries (DONE)

4. **IAM role separation**: `planning-agent-sa` has only `aiplatform.user`, which excludes `aiplatform.indexes.delete`. The execution SA has `aiplatform.editor` with full write access.
5. **Optional IAM deny policy** (`deny-planning-agent-index-delete`): Requires `iam.denypolicies.create` permission. Belt-and-suspenders — not strictly needed since `aiplatform.user` already blocks index operations.

### Phase 3: Implement & Test CUJ 2 (DONE)

7. **Planner graph conditional routing** (`agents/planner/graph.py`):
   * `AlertExtraction` now includes `is_destructive` flag — LLM classifies destructive vs. legitimate intent
   * `route_after_analysis` routes destructive requests to security path, normal requests to delegation
   * `attempt_forbidden_action` node calls `IndexServiceClient.delete_index()` — blocked by IAM (`PermissionDenied`)
   * `generate_security_report` node produces an incident report
8. **Control Room security block handling** (`agents/control_room/agent.py`):
   * Detects security violation keywords ("permission denied", "security violation", "blocked by iam", "identity shield")
   * Returns immediately with `SECURITY BLOCK` status — no re-planning attempted
9. **Integration tests** (`tests/integration/test_identity_shield.py`, 5 tests):
   * Conditional routing (destructive vs. normal)
   * `PermissionDenied` capture in state
   * Security report generation
   * Full graph security path end-to-end
10. **E2E test** (`tests/e2e/test_cuj2_identity_shield.py`):
    * Control Room with mocked A2A security response
    * Asserts single A2A call (no retry) and `SECURITY BLOCK` outcome

### Prerequisites

* [x] GCP project with Agent Engine enabled (`gcp-samples-ic0`)
* [x] Vertex AI API enabled
* [x] Authenticated (`kazunori279@gmail.com`)
* [x] Planner graph security path implemented and tested
* [x] Control Room security block handling implemented and tested
* [x] Service accounts created (`planning-agent-sa`, `execution-agent-sa`)
* [x] IAM roles bound (`aiplatform.user` for planning, `aiplatform.editor` for execution)
* [x] Planning Agent deployed to Agent Engine (`reasoningEngines/7579541130434314240`)
* [x] Planning Agent SA bound (`planning-agent-sa` — read-only, no index delete)
* [x] Control Room deployed to Agent Engine (`reasoningEngines/2125119031735222272`)
* [x] Control Room SA bound (`execution-agent-sa` — full access)
* [ ] IAM deny policy (optional — requires `iam.denypolicies.create` permission)

## Architecture Gap Analysis

Comparing the [architecture diagram](./assets/scale-arch-diagram.png) to the current implementation.

| Area | What's in the Diagram | Current State | Gap |
| ---- | --------------------- | ------------- | --- |
| **Execution Agents** | Supply Chain, Customer Support, Inventory agents | One generic logistics agent | Missing specialized agent swarm |
| **External Systems** | ERP, CRM integrations on both sides | None | No ERP/CRM connectors |
| **Agent Identity** | Centralized access control, instance-level permissions (ISTIO) | Both agents deployed to Agent Engine with scoped SAs; graph routes destructive requests to IAM-blocked path; Control Room handles security blocks | — |
| **Session Management** | Enhanced session management | Partially addressed via ADK 2.0 `InMemoryRunner` & `Session` | Need persistent remote session DB |
| **Agent Engine** | Core Runtime hosting both layers | Both Planning Agent and Control Room deployed to Agent Engine | — |
| **Multi-cloud** | Multi-cloud interoperability | Single environment only | Not started |
| **Multiple MCP connections** | MCP on both planning and execution sides | MCP only on execution side | Planning Agent has no MCP tools |

## Agent Engine Platform Features (GA at Next '26)

Features available on the Google Agent Engine platform and their usage in this demo.

Priority is based on **impact** (how much it improves the demo), **ease** (effort to integrate), and **importance** (relevance to the core multi-agent orchestration story). Scale: P0 = critical, P1 = high, P2 = medium, P3 = low.

### Runtime Enhancements

| Priority | Feature | Availability | Used in Demo | Use Case in This Scenario |
| -------- | ------- | ------------ | ------------ | ------------------------- |
| **P0** | Resource level IAM binding | GA | Yes — `planning-agent-sa` (read-only) vs `execution-agent-sa` (full) | CUJ 2: restrict the Planning Agent's identity so it cannot access the vector store directly |
| **P1** | Bring Your Own Container (BYOC) | GA | Not yet | Package LangGraph + CrewAI + MCP dependencies into a custom container for consistent deployment |
| **P1** | Performance: fast cold starts and provisioning | GA | Not yet | Reduce latency when spinning up the Planning Agent on incoming inventory alerts |
| **P2** | Bi-directional streaming | GA | Not yet | Stream real-time progress updates (sourcing status, budget checks) back to the dashboard |
| **P2** | Versioning & traffic control | GA | Not yet | Canary-deploy updated planner prompts or executor logic, roll back if PO accuracy drops |
| **P2** | Expanded language support: Python, Java, TS, Go | GA | Python | Both LangGraph planner and CrewAI executor are Python-based |
| **P3** | LRO agents up to 7 days | GA | Not yet | Handle large-scale restocking jobs that span multiple vendor negotiations over days |
| **P3** | Accelerated onboarding | GA | Not yet | Faster initial setup when deploying the multi-agent system to new GCP projects |
| **P3** | 5k agents per project | GA | Not yet | Scale to thousands of regional planner/executor agent pairs for global retail operations |

### Context Enhancements

| Priority | Feature | Availability | Used in Demo | Use Case in This Scenario |
| -------- | ------- | ------------ | ------------ | ------------------------- |
| **P1** | Framework-agnostic session support | Q2 | Not yet | Share session state between LangGraph (planner) and CrewAI (executor) seamlessly |
| **P1** | Custom Session IDs | Preview at Next '26 | Not yet | Correlate a restock alert to its session across Planning Agent and Execution Agents |
| **P2** | Configurable session fields | Q2 | Not yet | Store region, budget, and delegation status as structured session metadata |
| **P2** | Branching — time-travel for advanced debugging | Q2 | Not yet | CUJ 3: branch at the delegation step to compare re-planning strategies side by side |
| **P2** | Context compaction to reduce tokens | Q2 | Not yet | Reduce token usage in multi-turn planning sessions with long execution results |
| **P3** | IngestEvents API for enhanced DevEx | Preview at Next '26 | Not yet | Replay past procurement workflows to debug why a specific PO failed |
| **P3** | Multi-region endpoint support (US and Europe) | Q2 | Not yet | Serve regional planner agents close to each retail region (Northeast, Europe) |

### Sandbox Enhancements

| Priority | Feature | Availability | Used in Demo | Use Case in This Scenario |
| -------- | ------- | ------------ | ------------ | ------------------------- |
| **P2** | Code Execution | GA at Next '26 | Not yet | Let the planner dynamically compute optimal order quantities or budget splits |
| **P2** | Snapshot API long-running workflows | Preview at Next '26 | Not yet | Checkpoint a multi-step procurement workflow so it can resume after interruption |
| **P3** | BYOC custom browser tools / containers | GA at Next '26 | Not yet | Run the MCP vector search adapter in an isolated container with network controls |
| **P3** | Computer Use Sandbox | GA at Next '26 | Not yet | Automate interactions with vendor web portals that lack APIs |
