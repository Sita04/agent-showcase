# Planning Agent (LangGraph)

This directory contains the "Brain" of the Global Retail IT Orchestrator. The Planning Agent is responsible for analyzing high-level inventory alerts, formulating a strategy, delegating tasks to execution swarms, and reporting on the outcome.

It is built using **LangGraph** to maintain state and control the flow of execution, and it exposes itself to the outside world via the **Native A2A (Agent-to-Agent) Protocol** over HTTP.

## Architecture & Responsibilities

The Planning Agent operates strictly at the *Strategy Layer*. It has high privileges regarding business logic but enforces "Least Privilege" regarding data access—it cannot touch the inventory database or place orders directly. It must rely on delegation.

### LangGraph Workflow (`graph.py`)

The internal state machine follows a strict three-node sequence:

1.  **`analyze_alert`**: Uses `gemini-2.5-flash` with structured outputs (Pydantic) to parse a vague natural language alert into a concrete `AlertExtraction` schema (extracting item descriptions, budgets, and required quantities).
2.  **`delegate_to_executor`**: The internal handoff. It instantiates the **CrewAI** execution swarm (`LogisticsExecutionCrew`), passes the extracted constraints, and waits synchronously for the swarm to complete its tactical work via MCP.
3.  **`generate_report`**: After CrewAI returns (either with a success or failure), the Planner synthesizes the raw execution results back into a clean, human-readable Markdown report summarizing the outcome of the logistics operation.

### A2A Web Server (`a2a_server.py`)

To make this LangGraph state machine accessible to other agents across the network (such as the Google Agent Development Kit or a dashboard), it is wrapped in an A2A Server.

*   **`PlannerAgentExecutor`**: Acts as the bridge. It receives a JSON-RPC request, maps it into the `PlanState['objective']`, asynchronously invokes the LangGraph `build_planner_graph()`, and packages the resulting `final_report` into an A2A `TaskArtifact`.
*   **`AgentCard`**: The server hosts a `/.well-known/agent-card.json` endpoint that advertises this agent's capability (`orchestrate_logistics`) to external discovery systems.

## Setup & Execution

*Ensure you have completed the unified workspace setup (`uv sync`) from the repository root.*

### 1. Running as an A2A Service (Recommended)

To run the Planner as a standalone HTTP microservice that listens for Agent-to-Agent requests:

```bash
# From the 02-scale root directory
uv run agents/planner/a2a_server.py
```

This will start a Uvicorn server on `http://0.0.0.0:8080`.

You can test it by running the mock client in another terminal:

```bash
uv run agents/planner/test_a2a_client.py
```

### 2. Running Locally (Direct Python Execution)

If you want to debug the LangGraph workflow directly without the A2A HTTP overhead, you can execute the graph script directly:

```bash
# From the 02-scale root directory
uv run agents/planner/graph.py
```

This will run the predefined example objective through the graph and print the state transitions and final report directly to your terminal.

## File Structure

```text
planner/
├── a2a_server.py      # The Uvicorn Starlette app and A2A AgentExecutor wrapper
├── graph.py           # The LangGraph nodes and edge definitions
├── prompts.py         # System instructions and Pydantic schemas for the LLM
├── state.py           # The TypedDict defining the LangGraph state object
├── test_a2a_client.py # A mock script to send A2A JSON-RPC requests to the server
└── README.md          # This file
```
