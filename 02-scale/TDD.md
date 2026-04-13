# Technical Design Document: Scale AI Agents - Global Retail IT Orchestrator

**Status:** Draft  
**Date:** March 25, 2026  
**Owners:** Emmanuel Awa, Kaz Sato  
**Track:** Scale (02-scale)

## 1. Overview

This document outlines the technical design for the "Global Retail IT Orchestrator," a multi-agent system designed to demonstrate secure, high-scale interoperability between disparate agent frameworks (LangGraph and CrewAI) using the native Agent-to-Agent (A2A) protocol and Model Context Protocol (MCP).

### 1.1 Objective

To demonstrate a "nervous system" for global retail operations where a high-level "Planning Agent" (Strategy) delegates specific logistical tasks to "Execution Agents" (Tactics) across a secure boundary, enforcing "Least Privilege" access to business data via Agent Identity.

### 1.2 Key Technologies

- **Runtime:** Google Agent Engine
- **Planning Framework:** LangGraph (Python)
- **Execution Framework:** CrewAI (Python)
- **Interoperability:** Native A2A (Agent-to-Agent) Protocol via JSON-RPC
- **Tooling/Data:** Model Context Protocol (MCP)
- **Governance:** Google Agent Platform Agent Identity

---

## 2. System Architecture

The system follows a "Hub-and-Spoke" delegation model where the top-level Hub is an **ADK 2.0 Control Room Agent**, the intermediate Planner is a stateful LangGraph server exposed via A2A, and the Spokes are ephemeral CrewAI worker swarms connecting to MCP servers.

```mermaid
graph TD
    User[ADK Agent / Dashboard] --> CR[ADK 2.0 Control Room Agent]
    
    subgraph "Global Coordination (ADK 2.0)"
        CR -->|A2A JSON-RPC 'message/send'| A2AServer[A2A Web Server (Uvicorn)]
    end

    subgraph "Strategy Layer (High Privilege)"
        A2AServer -->|Extract Intent| PA[Planning Agent (LangGraph)]
    end

    subgraph "Execution Layer (Restricted Scope)"
        PA -->|Delegate Logistics| EA[Execution Agent (CrewAI)]
        EA -->|Query/Action| MCP[MCP Client]
    end

    subgraph "External Systems"
        MCP -->|REST API /api/query| VS_API[Vector Search Service]
        VS_API -->|Semantic Search| VDB[(Vertex AI Vector Search)]
        MCP -->|Internal Mock| OMS[Mock Order Management System]
    end

    style PA fill:#e1f5fe,stroke:#01579b
    style EA fill:#e8f5e9,stroke:#1b5e20
    style MCP fill:#fff3e0,stroke:#e65100
    style A2AServer fill:#f3e5f5,stroke:#4a148c
```

### 2.1 Components

1. **Control Room Agent (The Orchestrator):**
   - **Role:** The primary entry point built with ADK 2.0. It receives user inputs, maintains global session context via `InMemoryRunner`, and dynamically handles A2A delegation and error recovery (re-planning) using `@node(rerun_on_resume=True)`.
   - **Implementation:** `google_adk` (ADK 2.0 Alpha).

2. **Native A2A Server (The API):**
   - **Role:** A Starlette-based asynchronous server that wraps the LangGraph application. It exposes a standardized `/.well-known/agent-card.json` and listens for JSON-RPC 2.0 `message/send` requests from the Control Room.
   - **Implementation:** `a2a-server` SDK.

3. **Planning Agent (The Brain):**
   - **Role:** Analyzes high-level goals ("Restock Northeast Region"), extracts structured schema data, and decomposes the goal into sub-tasks.
   - **Implementation:** LangGraph state machine.

4. **Execution Agent (The Hands):**
   - **Role:** Receives a specific, bounded task ("Order 2 units of Rare Japanese Anime Figure"), validates vendor agreements, and executes the order.
   - **Implementation:** CrewAI Agent swarm.
   - **Identity:** Has access to `Vector_Store_Read` and `Order_Write` via MCP. Cannot access global strategy data.

5. **MCP Server (The Universal Plug):**
   - **Role:** Exposes the **Mercari Product Vector Store** (via REST API) and Order System (Mocked internally) via a standardized MCP interface.
   - **Why MCP?** Decouples the agent from the specific API implementation of the Search Service and OMS.

---

## 3. Critical User Journeys (CUJs)

### CUJ 1: The "Happy Path" Restock (A2A Native)

**Goal:** Successfully restock a low-inventory item across frameworks over HTTP.

1. **Trigger:** An external ADK agent sends a standardized JSON-RPC `message/send` request to the A2A Server.
2. **Plan (LangGraph):**
   - The A2A `AgentExecutor` routes the message to the LangGraph node.
   - Planning Agent extracts structured data (Item, Quantity, Budget).
3. **Execute (CrewAI):**
   - Planning Agent instantiates the CrewAI swarm.
   - CrewAI Agent uses **MCP Tool** `catalog.search_vectors`.
   - CrewAI Agent uses **MCP Tool** `orders.create_po(...)`.
   - Returns success payload.
4. **Completion:** LangGraph generates a final Markdown report, which the A2A Server wraps into a `TaskArtifact` and sends back over HTTP to the calling agent.

### CUJ 2: The "Identity Shield" Block (Security) - Local Simulation

**Goal:** Prevent a compromised or confused Planning Agent from destroying data.

1. **Trigger:** Malicious prompt injection or hallucination causes the ADK Control Room to relay a dangerous instruction to the LangGraph Planning Agent, attempting to _directly_ delete the inventory database.
2. **Execute:** The CrewAI Sourcing Specialist attempts to call `MCP_Vector_Store_Delete_Index` (Mocked destructive tool).
3. **Enforcement:**
   - The MCP Server intercepts the call and checks the simulated **Agent Identity** of the executor.
   - **Deny:** The Execution Agent's simulated identity lacks `Vector_Store_Write` scope.
4. **Result:** Operation fails with `403 Forbidden`. The incident bubbles up and is safely caught by the ADK Control Room without crashing the system.

### CUJ 3: Cross-Framework Error Handling & ADK 2.0 Re-planning

**Goal:** Gracefully handle failure when the Execution Agent fails and dynamically re-plan.

1. **Trigger:** External ADK 2.0 Control Room Agent sends a request for a discontinued or impossible item.
2. **Execute:** LangGraph Planner delegates to CrewAI. CrewAI Agent fails to find the item via the Vector Search MCP.
3. **Failure:**
   - CrewAI Agent catches the error.
   - Returns failed result to LangGraph.
   - LangGraph generates a graceful failure report (Status: FAILED).
   - A2A Server returns the formatted failure report back to the ADK Control Room.
4. **Recovery:**
   - The ADK 2.0 Control Room parses the failure.
   - Using dynamic code routing (`ctx.run_node()`), the Control Room spawns a `replanner_agent` (LLM) to intelligently broaden the original objective based on the failure reason.
   - The Control Room re-delegates the new, broader objective to the A2A server in a retry loop.

---

## 4. Detailed Component Design

### 4.1 A2A Protocol (Native JSON-RPC)

The standardized message format for agents talking to our Orchestrator.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "id": "req-cr-1",
  "method": "message/send",
  "params": {
    "message": {
      "message_id": "uuid-1234",
      "parts": [{ "text": "Order 2 Figures" }],
      "role": "user"
    }
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "req-cr-1",
  "result": {
    "artifacts": [
      {
        "name": "orchestration_report",
        "parts": [{ "kind": "text", "text": "**Success:** PO-123 created." }]
      }
    ]
  }
}
```

### 4.2 LangGraph Planner (State Schema)

```python
class PlanState(TypedDict):
    objective: str
    region: str
    item_description: str
    quantity_needed: int
    max_budget: float
    current_step: str
    delegation_status: str # 'pending', 'success', 'failed'
    execution_result: str
    final_report: str
```

### 4.3 MCP Server Tools

The Server connects to the Vector Search Backend (`https://ac-web2-761793285222.us-central1.run.app`) and exposes these tools:

- `catalog.search_vectors(query: str, dataset_id: str = "mercari3m_text_128")`: Semantic search against the Mercari product vector store via `POST /api/query`.

- `orders.create_purchase_order(product_id: str, quantity: int, vendor_id: str)`: (Mocked internally) Creates a purchase order.

- `orders.check_budget(amount: float, category: str)`: Validates financial limits.

---

## 5. Development Plan

1. **Scaffold**: Create `02-scale/agents/planner` and `02-scale/agents/executor`.
2. **MCP Server**: Build a simple Python MCP server (`02-scale/mock_oms_mcp/`) mocking the ERP.
3. **CrewAI Impl**: Implement the Execution Agent that connects to the MCP server.
4. **LangGraph Impl**: Implement the Planning Agent state machine.
5. **Integration (Phase 1)**: Python-level function call handoff from LangGraph to CrewAI.
6. **Integration (Phase 2)**: Implement a native A2A Server (`a2a_server.py`) exposing the LangGraph system via JSON-RPC over HTTP.
7. **Control Room (Phase 3 - Current)**: Implement the ADK 2.0 Control Room (`agents/control_room/agent.py`) utilizing `google_adk` dynamic nodes to orchestrate the A2A server, manage sessions, and handle CUJ 3 re-planning loops.
8. **Identity Shield (Phase 4 - DONE)**: 
   - Implemented local simulation of CUJ 2 by adding mock destructive tools and `PermissionDenied` interceptors.
   - Fully verified via `tests/integration/test_identity_shield.py` and `tests/e2e/test_cuj2_identity_shield.py`.
9. **Full Stack Verification (April 7, 2026)**:
   - All 58 tests in the unified suite are passing.
   - Fixed `gemini-3.1-flash-lite-preview` truncation and reasoning errors by increasing tokens and disabling `reasoning=True` in CrewAI.
   - Refactored all imports to absolute paths for `pyright` compliance.
