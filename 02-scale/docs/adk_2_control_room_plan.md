# ADK 2.0 Control Room Agent Architecture

## Background & Motivation

To scale our multi-agent system effectively and showcase the full power of the Google Agent Engine Platform at Next '26, we need a "Main Control Room". This agent will act as the top-level orchestrator, receiving user inputs and alerts, maintaining global session context, and securely delegating complex work down to our framework-specific sub-agents (LangGraph Planner -> CrewAI Executor).

We will leverage the new **ADK 2.0 Alpha** SDK, utilizing its `Runtime`, `MemoryBank`, `Context`, and `Graph` paradigms to implement a true Multi-Agent System (MAS).

## Scope & Impact

* **Replace A2A Client:** The current simplistic `test_a2a_client.py` will be replaced by a robust, stateful `ControlRoomAgent` built with `google_adk`.
* **Achieve CUJ 2 (Agent Identity / Least Privilege):** By deploying the Control Room as the primary entry point via `google_adk.Runtime`, we can enforce a rigid identity boundary. The Control Room handles high-level strategy but is explicitly denied `Vector_Store_Write` permissions. It *must* delegate to the specialized Execution Agents to perform database actions, thereby demonstrating the Identity Shield.
* **Achieve CUJ 3 (Cross-Framework Error Handling / Re-planning):** We will replace LLM-driven "hopeful" routing with deterministic, graph-based error handling. If the LangGraph/CrewAI stack fails (e.g., an item is discontinued), the error bubbles up to the ADK 2.0 Control Room. The `google_adk.Graph` will contain an explicit error edge that routes execution to a `RePlanNode`, adjusting the global context (e.g., widening the search) before retrying.

## Proposed Solution: Top-Level Coordinator (Hub-and-Spoke)

The system will adopt a "Coordinator/Sub-agent" architecture:

1. **User/System Alert** -> Triggers ADK 2.0 Control Room.
2. **Control Room (Coordinator):**
    * **Context:** Manages the global `Session` and `MemoryBank` to track state (budget, target items, previous failures).
    * **Graph:** Orchestrates the workflow. It delegates a sub-task to LangGraph via the A2A protocol.
    * **Runtime:** Hosts the agent securely, applying Agent Engine Platform Identity policies.
3. **LangGraph Planner (Sub-agent):** Receives the scoped task, breaks it down, and delegates to CrewAI.
4. **CrewAI Executor (Sub-agent):** Uses MCP to query the mock Vector Store.

### Graph Architecture (Control Room)

The `ControlRoomAgent` graph will consist of the following nodes and edges:

* `ReceiveAlertNode`: Parses the incoming request and updates the `Context`.
* `DelegateNode`: Triggers the LangGraph A2A Server.
* `EvaluateResultNode`: Parses the LangGraph response.
  * *Edge -> Success:* Workflow completes successfully.
  * *Edge -> ItemNotFound:* Routes deterministically to `RePlanNode`.
* `RePlanNode`: Analyzes the `MemoryBank` history, modifies the `Context` (e.g., changing "Rare Japanese Anime Figure" to a broader category like "Anime Collectibles"), and routes back to `DelegateNode`.

## Alternatives Considered

* **Peer-to-Peer Event Bus:** We considered connecting the ADK Control Room, LangGraph, and CrewAI as equal peers subscribing to a central event bus.
  * *Trade-off:* While decoupled, this makes tracking the global state and enforcing strict "Least Privilege" delegation harder to trace and debug. The Hub-and-Spoke model provides better observability for the demo.

## Implementation Plan

1. **Phase 1: SDK Installation & Setup**
    * Install the `google_adk-2.0.0+20260316` wheel file locally via `uv pip install`.
2. **Phase 2: Control Room Scaffold**
    * Create `02-scale/agents/control_room/agent.py`.
    * Initialize the `google_adk.Graph`, `google_adk.Context`, and `google_adk.MemoryBank`.
3. **Phase 3: Sub-Agent Integration**
    * Implement the A2A connection inside `DelegateNode` to communicate with the existing LangGraph server.
4. **Phase 4: Implement Re-planning (CUJ 3)**
    * Wire up the `EvaluateResultNode` to catch `ItemNotFound` errors.
    * Implement the `RePlanNode` to mutate the `Context` and retry the delegation.
5. **Phase 5: Runtime Deployment & Identity (CUJ 2)**
    * Wrap the agent execution in `google_adk.Runtime` to enforce the mock identity boundaries.

## Verification & Testing

* **Unit Tests:** Verify the ADK Graph edges route correctly based on mocked A2A responses.
* **E2E Validation:** Create `tests/e2e/test_cuj3_replanning.py` to trigger the Control Room with a known discontinued item and assert that the `RePlanNode` executes and successfully completes the procurement with a substitute item.

## Migration & Rollback

* The existing `test_a2a_client.py` will remain untouched as a debugging tool for the LangGraph server. If the ADK 2.0 agent fails to integrate, we can revert to invoking the A2A server directly for the demo.
