# Development Log: Scale AI Agents

**Owners:** Emmanuel Awa, Kaz Sato  
**Objective:** Build the "Global Retail IT Orchestrator" - a multi-agent system where a LangGraph Planning Agent delegates tasks to a CrewAI Execution Agent via the Agent-to-Agent (A2A) protocol and Model Context Protocol (MCP).

**Date Started:** March 12, 2026

## Status: Implementation

- [x] Reviewed `IDEAS.md`, `README.md`, and `TDD.md`.
- [x] Scaffold project structure (`02-scale/agents/executor`, `02-scale/mcp_server`).
- [x] Flesh out Executor Agents (CrewAI Swarm).
  - [x] Moved prompts to dedicated `prompts.py`
  - [x] Configured `reasoning=True` (gemini-3.1-pro-preview) and Crew `planning=True` (gemini-2.5-flash).
  - [x] Extracted configs to `config/default_config.py`.
- [x] Implement and Test MCP Servers.
  - [x] Tested Vector Search MCP connection in Executor Swarm (verified Sourcing Specialist connects correctly to `search_products`).
  - [x] Decided on Mock Orders (extracted local `@tool` functions into their own FastMCP server `mock_oms_mcp/server.py`).
- [x] Implement Planning Agent (LangGraph).
  - [x] Created `agents/planner/src/state.py`
  - [x] Created `agents/planner/src/prompts.py`
  - [x] Created `agents/planner/src/graph.py`
  - [x] Migrated from deprecated `langchain-google-vertexai` to modern `langchain-google-genai`.
- [x] Integrate and Test "Happy Path" (Restock).
  - [x] Tested the full end-to-end flow: LangGraph -> CrewAI -> MCP -> Success Report.

## Decisions & Notes

- **Architecture:** "Hub-and-Spoke" model.
  - **Planner (Hub):** LangGraph (Strategy).
  - **Executor (Spoke):** CrewAI (Tactics).
  - **Communication:** A2A Protocol (simulated natively via LangGraph Node calling CrewAI object).
  - **Tools:** Two independent MCP Servers:
        1. Vector Search Backend (Cloud Run)
        2. Mock Order Management System (Local FastMCP)
- **Observability:** Enabled CrewAI execution tracing locally (`CREWAI_TRACING_ENABLED=true`) to monitor internal agent thoughts, tool use, and latency without exposing logs to production environments.
- **Project Identity:** Using `genai-blackbelt-fishfooding` for all Vertex AI operations.
- **LLM/Vertex AI Integration:**
  - CrewAI uses `vertex_ai/gemini-3.1-pro-preview`
  - LangGraph uses `gemini-2.5-flash` via `langchain-google-genai`.
  - Required setting `GOOGLE_CLOUD_PROJECT="genai-blackbelt-fishfooding"` in `.env`.
  - Set `OPENAI_API_KEY="NA"` to satisfy internal CrewAI framework requirements.
  - Use `memory=False` in `Crew` initialization as enabling it causes a silent fallback to `OpenAI` through `chromadb`.
  - Resolved `EmbedderConfig` Pydantic typing issues by explicitly casting `VertexAIProviderSpec` dictionary matching `text-embedding-005`.
- **Data Source:** Mercari Product Vector Store (1M+ items).

## Stabilization & Type-Safety Overhaul (April 7, 2026)
- **Status Update:** Fully stabilized the unified test suite. All 58 tests (E2E, Integration, Unit) are passing with 0 `pyright` errors.
- **Key Improvements:**
  - **Import Refactoring:** Converted all internal imports in `agents/planner/` to absolute paths (`from agents.planner.state import ...`) to ensure consistency between runtime execution and `pyright` static analysis.
  - **CrewAI Stability Fix:** Identified and resolved a critical "None or empty response" failure in the Execution Swarm by disabling `reasoning=True` in `agents/executor/src/agents.py`. This appears to be a compatibility issue between the `gemini-3.1-pro-preview` model and CrewAI's internal reasoning loop.
  - **Token Limit Increase:** Bumped `AGENT_MAX_TOKENS` to 4096 in `default_config.py` to prevent truncation during complex multi-step procurement reasoning.
  - **Test Robustness:** 
    - Added explicit null checks and `assert` statements in `_run_node` and E2E tests to satisfy strict type-checkers.
    - Updated `test_identity_shield.py` to use `.get()` and `str()` for `TypedDict` access, resolving `reportOptionalSubscript` and `reportOperatorIssue` errors.
    - Broadened PO ID regex in `test_cuj1_happy_path.py` to support `PO-123` and `PO123` formats.
- **Verification:** Successfully ran `uv run pytest tests -v` with 100% success rate.

## Next Steps
- **ADK Dashboard Integration:** Now that the back-end orchestration is robust and fully tested, begin building the front-end dashboard to visualize the multi-agent flows in real-time.
- **Cloud Run Deployment:** Explore deploying the A2A Server to Cloud Run to test the orchestration in a fully distributed environment.
- [x] Integrate ADK 2.0 (Dispatcher Agent).
  - [x] Installed `google_adk` 2.0 SDK wheel from `sdk/` directly into the `.venv` workspace (using `--no-deps` to bypass resolution issues).
  - [x] Created `DispatcherAgent` at `02-scale/agents/dispatcher/agent.py` acting as the "User [ADK Agent / Dashboard]" entry point.
  - [x] Configured `DispatcherAgent` to intercept messages in ADK Web and forward them via A2A JSON-RPC to the LangGraph A2A Server on port `8000`.
  - [x] Validated ADK Web launches successfully with local framework structure.

## ADK 2.0 Upgrade & Control Room (April 6, 2026)
- **Status Update:** Transitioned from a simplistic A2A client to a full **ADK 2.0 Control Room Agent** using `google-adk>=2.0.0a0`.
- **Architecture Shift:** Implemented the "Top-Level Coordinator (Hub-and-Spoke)" model to act as the primary entry point for the Multi-Agent System.
- **Implementation Details:**
  - Designed `02-scale/docs/adk_2_control_room_plan.md` and synced it to a Google Doc.
  - Updated `pyproject.toml` to install ADK 2.0. Pinned `aiohttp<4.0.0` to avoid a C-extension compilation bug on Python 3.13 during the `--pre` installation, and added `[tool.uv] prerelease = "allow"` to ensure proper syncs across environments.
  - Scaffolded the graph in `agents/control_room/agent.py` utilizing ADK 2.0 dynamic nodes via `@node(rerun_on_resume=True)`.
  - Wired explicit deterministic routing for CUJ 3 (Cross-Framework Error Handling) with `Success`, `ItemNotFound`, and `Error` conditions using `ctx.run_node()` to dynamically spin up a Re-planning LLM mid-workflow.
  - Fixed intermittent JSON truncation bugs in CrewAI by adding explicit Pydantic `expected_output` models (`SourcingOutput` and `ProcurementOutput`) to `agents/executor/src/tasks.py` and disabling the buggy internal CrewAI planner.
  - Implemented `main.py` using `InMemoryRunner` and `session_service` for robust session handling.
- **Verification:** 
  - Verified `tests/e2e/test_cuj1_happy_path.py` (CUJ 1) successfully runs natively and generates valid mock POs.
  - Authored and verified `tests/e2e/test_cuj3_replanning.py` (CUJ 3) successfully triggers the ADK 2.0 fallback routing and rewrites the user objective using LLM dynamic execution. Next up is simulating CUJ 2 (Identity Shield).
