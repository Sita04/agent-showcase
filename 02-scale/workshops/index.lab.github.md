# Codelab: Scale Agents with CrewAI, LangGraph, A2A, and ADK

## Introduction

In this codelab, you will learn how to build a multi-agent orchestration system using [CrewAI](https://www.crewai.com/), [LangGraph](https://langchain-ai.github.io/langgraph/), [A2A protocol](https://google.github.io/A2A/), and [ADK](https://google.github.io/adk-docs/) (Agent Development Kit). You will create a system where an ADK control room delegates planning to a LangGraph planner, which dispatches tasks to a CrewAI execution crew -- all connected via A2A -- to handle a retail inventory restock scenario.

### What is multi-agent orchestration?

In a **multi-agent system**, multiple specialized AI agents collaborate to accomplish tasks that would be too complex for a single agent. Instead of one monolithic agent doing everything, you decompose the problem into roles -- a planner and an executor -- each with its own tools and expertise.

This mirrors how human organizations work: a manager delegates strategy to analysts and execution to specialists. The benefits include:

- **Separation of concerns**: Each agent focuses on what it does best
- **Framework flexibility**: Use the best framework for each role (LangGraph for planning logic, CrewAI for tool execution)
- **Scalability**: Add specialized agents without changing the entire system

### The scenario

When a user sends a restock request like *"Restock 1 Pixel 7 phone for the Tokyo office"*, the system:

1. The **LangGraph Planner** analyzes the request and extracts the item and quantity
2. The Planner delegates execution to the **CrewAI Execution Crew**
3. A **Sourcing Specialist** agent searches the product catalog using tools
4. A **Procurement Officer** agent validates the budget and places a purchase order using tools
5. The result flows back up to the planner, which generates a final report

```
User Request
    │
    ▼
┌──────────────────────┐
│ ADK Control Room     │  ← Top-level orchestrator, re-plans on failure
│ (BaseAgent)          │
└──────────┬───────────┘
           │ A2A (JSON-RPC)
           ▼
┌──────────────────────┐
│ LangGraph Planner    │  ← Analyzes intent, delegates, reports
│ (State Machine)      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ CrewAI Execution Crew│  ← Runs agents with tools
│  ├─ Sourcing Agent   │  → search_products
│  └─ Procurement Agent│  → check_budget, create_purchase_order
└──────────────────────┘
```

### Tech stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Planning** | LangGraph | State machine that analyzes intent, routes requests, generates reports |
| **Execution** | CrewAI | Role-based agents that call tools sequentially |
| **LLM** | Gemini on Vertex AI | Powers agent reasoning and tool selection |
| **Inter-agent communication** | A2A Protocol | JSON-RPC 2.0 bridge so agents from different frameworks can talk |
| **Top-level orchestrator** | ADK (BaseAgent) | Receives requests, delegates via A2A, re-plans on failure |

> **See it in action:** If available, try the full production system at **https://scale-control-room-761793285222.us-central1.run.app** -- it extends what you'll build here with a real-time dashboard, A2A protocol, and IAM security.

### What you'll do

- Define custom tools for agents to use.
- Build specialized agents with **CrewAI**.
- Create a state machine planner with **LangGraph**.
- Orchestrate the flow between the planner and the execution crew.
- Wrap the planner in an **A2A Protocol** server for cross-framework communication.
- Build a top-level **ADK Control Room** that delegates via A2A and re-plans on failure.

### What you'll need

- A web browser such as [Chrome](https://www.google.com/chrome/)
- A Google Cloud project with billing enabled

This codelab is for **intermediate** developers who are familiar with Python and basic LLM concepts.

Estimated duration: **35 minutes**.

Cost estimate: The resources created in this codelab should cost less than $1.

## Before you begin

Duration: 03:00

#### Create a Google Cloud Project

In the [Google Cloud Console](https://console.cloud.google.com/), on the project selector page, select or create a Google Cloud project.

Make sure that billing is enabled for your Cloud project. [Learn how to check if billing is enabled on a project](https://cloud.google.com/billing/docs/how-to/verify-billing-enabled).

#### Start Cloud Shell

Cloud Shell is a command-line environment running in Google Cloud that comes preloaded with necessary tools.

Click **Activate Cloud Shell** at the top of the Google Cloud console.

Once connected to Cloud Shell, verify your authentication:

```bash
gcloud auth list
```

Confirm your project is configured:

```bash
gcloud config get project
```

If your project is not set as expected, set it:

```bash
export PROJECT_ID=<YOUR_PROJECT_ID>
gcloud config set project $PROJECT_ID
```

#### Enable APIs

Run this command to enable the Vertex AI API:

```bash
gcloud services enable aiplatform.googleapis.com
```

> **Note:** Cloud Shell automatically authenticates with your Google Cloud account. If you are running this codelab outside of Cloud Shell, you will need to run `gcloud auth application-default login` to authenticate with Vertex AI.

#### Set up your environment

In Cloud Shell, create a new directory for your project and navigate into it:

```bash
mkdir scale-agents
cd scale-agents
```

Install `uv` and use it to install the required packages:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv init --no-workspace --no-readme
rm main.py
sed -i 's/requires-python = ">=3.12"/requires-python = ">=3.12,<3.14"/' pyproject.toml
uv add crewai 'litellm[google]' langgraph 'a2a-sdk>=0.3.25,<0.4' httpx uvicorn 'google-adk>=1.0.0' --prerelease=allow
```

Set the environment variables for Vertex AI:

```bash
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

## Define Tools and Agents

Duration: 05:00

In a multi-agent system, agents need tools to interact with the world, and specific roles to know what to do.

Create a file named `scale_agents.py` and add the following code. This sets up the imports, mock tools, and the CrewAI agents.

```python
import os
from typing import Optional
from crewai import Agent, Crew, Process, Task, LLM
from crewai.tools import tool
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

# CrewAI requires this env var even when using Vertex AI
os.environ["OPENAI_API_KEY"] = "NA"

# Set the project ID for Vertex AI
os.environ["VERTEXAI_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT", "")
os.environ["VERTEXAI_LOCATION"] = "us-central1"

# Initialize the LLM to use Vertex AI
llm = LLM(
    model="vertex_ai/gemini-2.5-flash",
    temperature=0.0,
    max_tokens=4096,
)

# --- Step 1: Define Tools ---

@tool("search_products")
def search_products(query: str) -> list:
    """Search for products in the catalog."""
    # Mock product catalog
    products = [
        {"product_id": "pixel-7", "name": "Pixel 7 Phone", "price": 50.0},
        {"product_id": "pixel-8", "name": "Pixel 8 Phone", "price": 80.0},
    ]
    return [p for p in products if query.lower() in p["name"].lower()]

@tool("check_budget")
def check_budget(amount: float) -> dict:
    """Check if a purchase amount is within the budget."""
    limit = 100.0
    if amount <= limit:
        return {"approved": True, "remaining": limit - amount}
    return {"approved": False, "reason": f"Exceeds budget of ${limit}"}

@tool("create_purchase_order")
def create_purchase_order(product_id: str, quantity: int) -> dict:
    """Create a purchase order for a product."""
    return {
        "status": "SUCCESS",
        "po_id": f"PO-{product_id}-{quantity}",
        "message": f"Successfully ordered {quantity} units of {product_id}."
    }

# --- Step 2: Define Agents ---

sourcing_agent = Agent(
    role="Sourcing Specialist",
    goal="Find the best available products that match the intent of the request. You MUST use the search_products tool to look up products -- never make up product data.",
    backstory="You are a veteran procurement specialist with an eye for detail. You always search the catalog before recommending a product.",
    tools=[search_products],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    memory=False,
    reasoning=False,
)

procurement_agent = Agent(
    role="Procurement Officer",
    goal="Validate the purchase against budget constraints and execute the order. You MUST use the check_budget tool before ordering and the create_purchase_order tool to place the order.",
    backstory="You are the gatekeeper of the budget. You always verify budget before placing any order.",
    tools=[check_budget, create_purchase_order],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    memory=False,
    reasoning=False,
)
```

### Key Concepts

- **`@tool` decorator**: CrewAI uses this to turn regular Python functions into tools that LLMs can understand and call. The function's type hints and docstring are used to generate a tool schema that the LLM can understand.
- **Role, Goal, and Backstory**: These define the agent's persona and guide its LLM reasoning. The backstory isn't just flavor text -- "You always search the catalog" encourages the agent to use its tools rather than hallucinating answers.
- **`reasoning=False`**: Disables extended reasoning so the agent follows the standard tool-calling loop instead of trying to answer directly.
- **`allow_delegation=False`**: Keeps each agent focused on its own assigned tools instead of passing work to other agents.

> **Why two agents instead of one?** Each agent has different tools and a different job. The Sourcing Specialist only searches products; the Procurement Officer only handles budgets and orders. This **separation of concerns** means each agent has a focused prompt and a small, relevant tool set -- which leads to more reliable LLM behavior than a single agent juggling everything.

## Define Tasks and the Crew

Duration: 05:00

Now let's define what these agents need to do by creating **Tasks** and wiring them into a **Crew**.

Append the following code at the end of the same `scale_agents.py` file:

```python
# --- Step 3: Define Tasks & Crew ---

sourcing_task = Task(
    description="Use the search_products tool to find products matching: '{item_description}'. Return the product_id and price of the best match from the tool results.",
    expected_output="The product_id and price of the best matching product from the search_products tool.",
    agent=sourcing_agent
)

procurement_task = Task(
    description="First, use the check_budget tool to verify the total cost for {quantity} units. Then use the create_purchase_order tool with the product_id and quantity to place the order.",
    expected_output="The purchase order details returned by the create_purchase_order tool.",
    agent=procurement_agent,
    context=[sourcing_task] # This task depends on the output of sourcing_task
)

def run_crew(item_description: str, quantity: int):
    crew = Crew(
        agents=[sourcing_agent, procurement_agent],
        tasks=[sourcing_task, procurement_task],
        process=Process.sequential, # Run tasks in order
        verbose=True,
        memory=False,
        planning=False,
    )
    
    result = crew.kickoff(inputs={
        "item_description": item_description,
        "quantity": quantity
    })
    return result
```

### Key Concepts

- **Task Context**: `context=[sourcing_task]` tells CrewAI that the procurement task needs the output of the sourcing task to proceed. The Procurement Officer can see what the Sourcing Specialist found before deciding what to order.
- **Process.sequential**: Tasks are executed in the order they are listed. This is important because the procurement task depends on the sourcing task's results -- you can't place an order before you know which product to buy.
- **`memory=False` / `planning=False`**: Disables CrewAI's built-in memory and planning features to keep the execution simple and predictable for this demo.

## Create the LangGraph Planner

Duration: 05:00

The execution crew handles the "how" -- searching products, checking budgets, placing orders. But who decides the "what"? That's the **Planning Agent**, built with **LangGraph**.

LangGraph models workflows as a **state machine** -- a graph of nodes (functions) connected by edges (transitions). State flows through the graph, with each node reading from and writing to the shared state. This is a natural fit for planning workflows where you need clear, deterministic control flow: analyze the request, delegate to the crew, generate a report.

Append the following code at the end of the same `scale_agents.py` file:

```python
# --- Step 4: Define LangGraph Planner ---

class PlanState(TypedDict):
    objective: str
    item_description: Optional[str]
    quantity_needed: Optional[int]
    execution_result: Optional[str]
    final_report: Optional[str]

def analyze_alert(state: PlanState) -> PlanState:
    """Node 1: Extract intent from the raw objective string."""
    print("--- ANALYZING ALERT ---")
    # In a production app, you would use an LLM here to extract details.
    # For simplicity, we simulate extraction here.
    objective = state["objective"]
    
    # Hardcoded extraction for the demo
    if "Pixel 7" in objective:
        return {
            "item_description": "Pixel 7",
            "quantity_needed": 1,
        }
    return {
        "item_description": "unknown",
        "quantity_needed": 0,
    }

def delegate_to_executor(state: PlanState) -> PlanState:
    """Node 2: Call the CrewAI Execution Crew."""
    print("--- DELEGATING TO CREW ---")
    if state["item_description"] == "unknown":
        return {"execution_result": "Failed: Unknown item"}
        
    result = run_crew(
        item_description=state["item_description"],
        quantity=state["quantity_needed"]
    )
    return {"execution_result": str(result)}

def generate_report(state: PlanState) -> PlanState:
    """Node 3: Synthesize the final outcome."""
    print("--- GENERATING REPORT ---")
    return {
        "final_report": f"Objective handled: {state['objective']}. Result: {state['execution_result']}"
    }

# Build the graph
workflow = StateGraph(PlanState)
workflow.add_node("analyze_alert", analyze_alert)
workflow.add_node("delegate", delegate_to_executor)
workflow.add_node("generate_report", generate_report)

workflow.set_entry_point("analyze_alert")
workflow.add_edge("analyze_alert", "delegate")
workflow.add_edge("delegate", "generate_report")
workflow.add_edge("generate_report", END)

app = workflow.compile()

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Multi-Agent System...")
    
    initial_state = {
        "objective": "Restock 1 Pixel 7 phones for the Tokyo office"
    }
    
    final_state = app.invoke(initial_state)
    
    print("\n=== FINAL REPORT ===")
    print(final_state["final_report"])
```

### Key Concepts

- **StateGraph**: Defines the state machine. `PlanState` is the typed state that accumulates as each node processes the request.
- **Nodes**: Functions that take the current state and return updates to it. Each node has a single responsibility -- `analyze_alert` extracts intent, `delegate_to_executor` runs the crew, `generate_report` summarizes the outcome.
- **Edges**: Define the flow between nodes. In this codelab we use a simple linear flow (`analyze → delegate → report`). The full workshop extends this with **conditional routing** -- for example, routing destructive requests to a security path instead of the executor.

> **Why LangGraph for the planner?** CrewAI is great for tool-calling agents, but the planner needs deterministic control flow -- "if destructive, go to security path; otherwise, delegate." LangGraph's state machine model makes this routing explicit and testable, while CrewAI handles the freeform tool execution below.

## Run the Planner and Crew

Duration: 03:00

Now let's test the LangGraph planner and CrewAI crew together.

In your Cloud Shell terminal, run the script:

```bash
uv run python scale_agents.py
```

You should see output indicating the steps being taken:
1.  **Analyzing Alert**: The LangGraph node runs.
2.  **Delegating to Crew**: The LangGraph node calls the CrewAI crew.
3.  **CrewAI Execution**: You will see the Sourcing Specialist searching for the product and the Procurement Officer checking the budget and creating the purchase order.
4.  **Final Report**: The summarized result will be printed at the end.

Example output (abbreviated):
```text
Starting Multi-Agent System...
--- ANALYZING ALERT ---
--- DELEGATING TO CREW ---

  Agent: Sourcing Specialist
  Tool: search_products  Args: {'query': 'Pixel 7'}
  Tool Completed  Output: [{'product_id': 'pixel-7', 'name': 'Pixel 7 Phone', 'price': 50.0}]

  Agent: Procurement Officer
  Tool: check_budget  Args: {'amount': 50}
  Tool: create_purchase_order  Args: {'product_id': 'pixel-7', 'quantity': 1}
  Tool Completed  Output: {'status': 'SUCCESS', 'po_id': 'PO-pixel-7-1', ...}

--- GENERATING REPORT ---

=== FINAL REPORT ===
Objective handled: Restock 1 Pixel 7 phones for the Tokyo office. Result: ...PO-pixel-7-1...SUCCESS...
```

> **Note:** You may see `[CrewAIEventsBus] Warning: Event pairing mismatch` messages in the output. These are cosmetic warnings from CrewAI's internal event tracking and can be safely ignored.

> **Note:** CrewAI may display a message about tracing being disabled. This is informational and can be safely ignored.

> **Note:** The mock OMS has a **$100 budget limit**. Keep quantities small (under ~2 units) for the happy path to succeed. For example, 1 Pixel 7 Phone at $50 passes the budget check, but 3 units at $150 will be rejected as "Over Budget".

## Wrap the Planner in an A2A Server

Duration: 05:00

The LangGraph planner works, but it's trapped inside a Python process. To make it callable by other agents -- potentially written in different frameworks or running on different machines -- we wrap it in an **A2A (Agent-to-Agent)** server.

A2A is a JSON-RPC 2.0 based protocol that standardizes how agents communicate. Key concepts:

| Concept | Purpose |
|---------|---------|
| **Agent Card** | JSON metadata describing the agent's capabilities (served at `/.well-known/agent-card.json`) |
| **`message/send`** | JSON-RPC method to send a task to the agent |
| **Task** | A unit of work with state (submitted → working → completed/failed) |
| **Artifacts** | Intermediate and final outputs attached to a task |

Create a new file `a2a_planner.py`:

```python
import asyncio
import os
import uvicorn

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentSkill,
                       InternalError, Part, TextPart)
from a2a.utils import new_task
from a2a.utils.errors import ServerError

# Import the LangGraph planner from Step 4
from scale_agents import app as planner_app


class PlannerAgentExecutor(AgentExecutor):
    """Wraps the LangGraph planner as an A2A service."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        objective = context.get_user_input()

        # Initialize A2A task tracking
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            # Run the LangGraph planner synchronously in a thread
            initial_state = {"objective": objective}
            result = await asyncio.to_thread(planner_app.invoke, initial_state)
            final_report = result.get("final_report", "No report generated.")
        except Exception as e:
            final_report = f"Execution failed: {e}"

        # Send the result back as an artifact
        await updater.add_artifact(
            [Part(root=TextPart(text=final_report))],
            name="orchestration_report"
        )
        await updater.complete()

    async def cancel(self, context, event_queue):
        raise ServerError(error=InternalError(message="Cancel not supported"))


# Define the Agent Card — this is what other agents see
port = int(os.environ.get("PORT", 8080))
agent_card = AgentCard(
    name="Retail-Planner-A2A",
    description="LangGraph planner that delegates logistics tasks to a CrewAI crew.",
    url=f"http://localhost:{port}/",
    version="1.0.0",
    default_input_modes=PlannerAgentExecutor.SUPPORTED_CONTENT_TYPES,
    default_output_modes=PlannerAgentExecutor.SUPPORTED_CONTENT_TYPES,
    capabilities=AgentCapabilities(streaming=False),
    skills=[
        AgentSkill(
            id="plan_logistics",
            name="Plan Logistics",
            description="Analyzes inventory alerts and orchestrates procurement.",
            tags=["logistics", "planning"],
            examples=["Restock 1 Pixel 7 phones for the Tokyo office"],
        )
    ],
)

if __name__ == "__main__":
    executor = PlannerAgentExecutor()
    handler = DefaultRequestHandler(
        agent_executor=executor, task_store=InMemoryTaskStore()
    )
    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=handler
    )
    print(f"Starting A2A Planner Server on port {port}...")
    uvicorn.run(server.build(), host="0.0.0.0", port=port)
```

### Key Concepts

- **Agent Card**: Served at `/.well-known/agent-card.json` -- any agent can discover what this server does by fetching that URL. It lists the agent's skills, supported content types, and capabilities.
- **`AgentExecutor.execute()`**: The only method you implement. It receives the incoming request, runs your agent logic (here, the LangGraph planner), and sends results back as artifacts.
- **`TaskUpdater`**: Manages the task lifecycle -- `add_artifact()` sends intermediate/final outputs, `complete()` marks the task as done. The A2A library handles all JSON-RPC plumbing.

Test the A2A server by starting it in a terminal:

```bash
uv run python a2a_planner.py
```

Open another Cloud Shell tab (click **+** next to the current tab) and verify the Agent Card is served:

```bash
cd ~/scale-agents
curl http://localhost:8080/.well-known/agent-card.json | python3 -m json.tool
```

You should see the agent card JSON. Keep the A2A server running in the first terminal for the next step.

## Build the ADK Control Room

Duration: 05:00

The top of the stack is the **Control Room**, built with [ADK](https://google.github.io/adk-docs/) (Google's Agent Development Kit). It receives the user's request, delegates to the planner via A2A, evaluates the result, and -- critically -- handles **re-planning on failure** (CUJ 2).

ADK provides agent primitives like `BaseAgent`, `LlmAgent`, and `InMemoryRunner`. We subclass `BaseAgent` to write custom orchestration logic -- A2A calls, report classification, and dynamic re-planning with an `LlmAgent` sub-agent.

Create a new file `control_room.py`:

```python
import asyncio
import uuid
import os
import httpx

from google.adk.agents import BaseAgent, LlmAgent, RunConfig
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types
from typing import AsyncGenerator

A2A_SERVER_URL = os.environ.get("PLANNER_AGENT_URL", "http://127.0.0.1:8080")


def _classify_report(report: str) -> tuple[bool, bool]:
    """Return (is_success, should_retry) for a planner report."""
    normalized = (report or "").replace("*", "").strip().lower()

    success_markers = [
        "status: success", "'status': 'success'",
        "outcome: success", "po_id", "successfully ordered",
    ]
    retryable_markers = ["not found", "discontinued", "no inventory",
                         "unknown item"]
    terminal_markers = [
        "status: failed", "over budget", "not issued",
        "procurement failed",
    ]

    if any(m in normalized for m in terminal_markers):
        return False, False      # Failed, don't retry
    if any(m in normalized for m in retryable_markers):
        return False, True       # Failed, but retryable
    if any(m in normalized for m in success_markers):
        return True, False       # Success!
    return False, False          # Unknown → treat as failure


class ControlRoomAgent(BaseAgent):
    """Top-level orchestrator: delegates via A2A, re-plans on failure."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Extract user input from session events
        user_msg = ""
        if ctx.session and ctx.session.events:
            for evt in reversed(ctx.session.events):
                if evt.content and evt.content.role == "user":
                    user_msg = evt.content.parts[0].text
                    break

        max_attempts = 2
        current_objective = user_msg
        final_report = "No report returned."

        for attempt in range(1, max_attempts + 1):
            print(f"\n--- Attempt {attempt}: Calling A2A Planner ---")
            print(f"    Objective: {current_objective}")

            # Build the A2A JSON-RPC request
            payload = {
                "jsonrpc": "2.0",
                "id": f"req-{attempt}",
                "method": "message/send",
                "params": {
                    "message": {
                        "message_id": str(uuid.uuid4()),
                        "parts": [{"text": current_objective}],
                        "role": "user"
                    }
                }
            }

            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    resp = await client.post(
                        f"{A2A_SERVER_URL}/", json=payload
                    )
                    data = resp.json()
                    if "error" in data:
                        final_report = data["error"].get("message", "Unknown A2A error")
                    elif "result" in data:
                        artifacts = data["result"].get("artifacts", [])
                        if artifacts and "parts" in artifacts[-1]:
                            parts = artifacts[-1]["parts"]
                            if parts and "text" in parts[0]:
                                final_report = parts[0]["text"]
            except Exception as e:
                final_report = f"Connection error: {e}"

            print(f"\n--- Report ---\n{final_report}\n")
            is_success, should_retry = _classify_report(final_report)

            if is_success:
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=final_report)]
                    ),
                )
                return

            # --- Re-planning (CUJ 2) ---
            if should_retry and attempt < max_attempts:
                print("--- Re-planning with LLM ---")
                replanner = LlmAgent(
                    name=f"replanner_{attempt}",
                    model="gemini-2.5-flash",
                    instruction=(
                        "You are a strategic re-planner. The previous request "
                        "failed. Rewrite the objective to be broader or more "
                        "likely to succeed. Output ONLY the new objective text."
                    ),
                )

                # Run the re-planner as a sub-agent
                child_ctx = InvocationContext(
                    invocation_id=f"{ctx.invocation_id}_replan_{attempt}",
                    agent=replanner,
                    session=ctx.session,
                    session_service=ctx.session_service,
                    run_config=ctx.run_config or RunConfig(),
                )
                child_ctx.user_content = types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=(
                        f"Original Objective: {current_objective}\n"
                        f"Failure Reason: {final_report}\n"
                        "Please broaden the search."
                    ))]
                )

                new_objective = ""
                async for event in replanner.run_async(child_ctx):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                new_objective += part.text

                current_objective = new_objective.strip()
                print(f"New objective: {current_objective}")
                continue

            # Terminal failure (not retryable)
            if not should_retry:
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=f"FAILED: {final_report}")]
                    ),
                )
                return

        # Max attempts exhausted
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(
                    text=f"FAILED after {max_attempts} attempts: {final_report}"
                )]
            ),
        )


async def main():
    prompt = "Restock 1 Pixel 7 phones for the Tokyo office"
    print(f"Starting Control Room with: {prompt}\n")

    agent = ControlRoomAgent(name="control_room")
    runner = InMemoryRunner(app_name="control_room", agent=agent)
    session = await runner.session_service.create_session(
        app_name="control_room", user_id="admin"
    )
    content = types.Content(
        role="user", parts=[types.Part.from_text(text=prompt)]
    )

    async for event in runner.run_async(
        user_id="admin", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(f"Result: {part.text}")

    print("\n=== CONTROL ROOM COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
```

### Key Concepts

- **`BaseAgent`**: The ADK primitive for custom agents. You subclass it and override `_run_async_impl` to write arbitrary async orchestration logic -- here, the A2A call + classify + re-plan loop.
- **A2A JSON-RPC call**: The Control Room sends a standard `message/send` request to the planner's A2A server using `httpx` and parses the JSON-RPC response to extract the final report.
- **`_classify_report()`**: Simple keyword-based classification that determines success, retryable failure, or terminal failure from the report text. This drives the re-planning loop.
- **Sub-agent invocation**: To re-plan, the Control Room creates an `LlmAgent` and runs it by constructing a child `InvocationContext` and calling `replanner.run_async(child_ctx)`. This lets you dynamically spin up LLM agents inside custom orchestration logic.
- **`InMemoryRunner`**: Runs the agent locally with an in-memory session store. In production, you would use `adk deploy` to deploy to Vertex AI Agent Engine.

## Run the Full Stack

Duration: 03:00

Now let's test the complete three-layer system: ADK Control Room → A2A → LangGraph Planner → CrewAI Crew.

Use the second Cloud Shell tab you opened earlier (or click **+** for a new one) and run the Control Room. **Important:** Each Cloud Shell tab has its own shell session. You must set the project and environment variables again:

```bash
cd ~/scale-agents
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
uv run python control_room.py
```

You should see the full orchestration flow:
1. The **Control Room** receives the request and sends a `message/send` JSON-RPC call to the A2A server
2. The **A2A server** receives the request and invokes the LangGraph planner
3. The **LangGraph planner** analyzes the request and delegates to the CrewAI crew
4. The **CrewAI crew** runs the Sourcing and Procurement agents
5. The result flows all the way back to the Control Room

### Critical User Journeys (CUJs)

Try modifying the `prompt` string in `control_room.py` to experiment with these scenarios:

| CUJ | Prompt | What Happens |
|-----|--------|--------------|
| **1. Happy Path** | `Restock 1 Pixel 7 phones for the Tokyo office` | Search -> budget check -> purchase order (SUCCESS). Works end-to-end. |
| **2. Re-planning** | `Order 1 unit of the discontinued XR-7000 Quantum Holographic Display` | The planner returns "Failed: Unknown item". The Control Room detects this and invokes an `LlmAgent` re-planner to broaden the search. Both attempts fail (the hardcoded planner only recognizes "Pixel 7"), but you will see the full re-planning **mechanism** in action. |

To test **CUJ 2 (Re-planning)**, change the `prompt` in `control_room.py` to:

```python
prompt = "Order 1 unit of the discontinued XR-7000 Quantum Holographic Display"
```

The hardcoded planner won't recognize this item and will return "Failed: Unknown item". The Control Room will detect the failure, dynamically create an `LlmAgent` re-planner, and retry with a broader objective. Because the planner only recognizes "Pixel 7", the retry will also fail -- but you will see the full re-planning loop in action. The final output will be `FAILED after 2 attempts: ...`.

## Clean up

Duration: 01:00

To avoid ongoing charges to your Google Cloud account, you can delete the resources created during this codelab.
You can simply remove the directory you created:
```bash
cd ..
rm -rf scale-agents
```

## Congratulations

Duration: 01:00

Congratulations! You have successfully built a multi-agent orchestration system using CrewAI, LangGraph, A2A Protocol, and ADK.

#### What you've learned
- How to define tools for agents using CrewAI's `@tool` decorator.
- How to create specialized agents with distinct roles, tools, and goals.
- How to wire agents into a sequential crew with task dependencies.
- How to build a state machine planner with LangGraph that delegates to the crew.
- How to expose the planner as an A2A service with `AgentCard` and `AgentExecutor`.
- How to build a custom ADK `BaseAgent` that delegates via A2A and re-plans on failure by invoking an `LlmAgent` sub-agent.
- Why separating planning, execution, and orchestration across frameworks gives you modularity and resilience.

#### Going further

The full workshop extends this system with:
- **Real-time dashboard** -- SSE streaming to visualize multi-agent progress
- **Identity Shield** -- IAM-based security that blocks destructive actions at the infrastructure level, not the prompt level
- **Vertex AI Agent Engine** -- deploy the ADK agent to managed cloud infrastructure with `adk deploy`

#### Reference docs
- [CrewAI Documentation](https://docs.crewai.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [A2A Protocol](https://github.com/google/a2a-python)
- [ADK Documentation](https://google.github.io/adk-docs/)

