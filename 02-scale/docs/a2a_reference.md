# A2A (Agent-to-Agent) Native Protocol Concepts

Based on the provided reference implementation, the native Agent-to-Agent (A2A) protocol in the Google Agent Development Kit (ADK) revolves around several key architectural components that turn a standard AI agent into a web-accessible service that other agents can interact with.

## 1. The Core Components

### `AgentCard`
This is the identity and "swagger spec" of the agent. Before an agent can be invoked by another system, it defines an `AgentCard` that details:
*   **Identity:** `name`, `version`, `url` (where it can be reached).
*   **I/O:** `default_input_modes` and `default_output_modes` (e.g., `["text", "text/plain"]`).
*   **Capabilities:** `capabilities=AgentCapabilities(streaming=False)` indicating what technical features it supports.
*   **Skills:** A list of `AgentSkill` objects. These are basically the functions/intents this agent exposes to the outside world, complete with descriptions, tags, and examples.

### `AgentExecutor`
This is the bridge between the A2A HTTP layer and the actual agent logic (like an ADK `Agent` or a LangGraph graph).
*   It implements an `execute(self, context: RequestContext, event_queue: EventQueue)` method.
*   **Context:** `RequestContext` contains the incoming message and payload from the calling agent.
*   **Execution:** Inside this method, the developer instantiates their agent (e.g., ADK `Runner`), runs the generation loop, and captures the result.

### `TaskUpdater` and Artifacts
A2A treats agent interactions as asynchronous "Tasks". 
*   When a request comes in, a new `Task` is created (`new_task(context.message)`).
*   The `TaskUpdater` is used to send status updates back to the caller.
*   When the agent finishes its work, the output is packaged as an "Artifact" (`updater.add_artifact`) and the task is marked as `complete()`.

### The Server Application (`A2AStarletteApplication`)
To expose this to the network, the A2A protocol provides a Starlette-based application wrapper.
*   It takes the `AgentCard` and a `DefaultRequestHandler` (which wraps the `AgentExecutor` and a `TaskStore` for tracking state).
*   This builds an ASGI application that can be run using a standard web server like Uvicorn.

## 2. How the Flow Works (The Lifecycle)

1.  **Server Startup:** The app defines its `AgentCard`, wires up the `AgentExecutor` to the `A2AStarletteApplication`, and starts listening on a port (e.g., `0.0.0.0:8080`).
2.  **Incoming Request:** Another agent (or system) sends an A2A-formatted HTTP request to the server's endpoint.
3.  **Task Creation:** The `DefaultRequestHandler` parses the request, creates a task in the `InMemoryTaskStore`, and invokes `AgentExecutor.execute()`.
4.  **Agent Execution:** The `AgentExecutor` extracts the query, initializes the underlying AI logic (e.g., connecting to MCP tools, starting an ADK Runner session), and waits for the AI to generate a response.
5.  **Task Completion:** Once the AI finishes, the `AgentExecutor` bundles the text response into an `Artifact`, attaches it to the task using the `TaskUpdater`, and marks the task as complete.
6.  **Response:** The server sends the completed task details and artifacts back to the calling agent.

## 3. Applying this to `02-scale`

In the context of the `02-scale` "Global Retail IT Orchestrator":
*   Currently, the LangGraph Planning Agent calls the CrewAI Execution Agent directly via an in-memory python import (`crew.run(...)`).
*   To implement true Native A2A based on this reference:
    1.  The CrewAI agent would be wrapped in a custom `AgentExecutor`.
    2.  It would define an `AgentCard` advertising its logistics skills.
    3.  It would be deployed as an independent Cloud Run service running the `A2AStarletteApplication`.
    4.  The LangGraph planner would become an A2A Client, making HTTP requests to the CrewAI A2A server instead of calling the Python function directly.
