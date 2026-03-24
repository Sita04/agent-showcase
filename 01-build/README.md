# Shopping Squad

A hyper-personalized, multi-agent shopping workflow built on the Google Agent Development Kit (ADK) 2.0.

The Shopping Squad utilizes dynamic ADK workflow graphs and the Model Context Protocol (MCP) to decompose a vague shopping request into a structured plan, continuously interacting with the human user at critical checkpoints.

## Architecture & Workflow

The workflow executes in 3 distinct Human-In-The-Loop (HitL) phases:

### Phase 1: Plan Generation & Budget Approval
- **Planner Agent (`planner.py`)**: Uses `gemini-2.5-flash` with structured output schemas to decompose a general user request into a `ShoppingPlan` with specific `ShoppingComponent` elements and budget allocations.
- **HitL Pause**: The workflow pauses and waits for the user to explicitly approve or reject the budget breakdown. If rejected, the Planner dynamically re-calculates the plan based on user feedback.

### Phase 2: Parallel Scouting & Automated Math Evaluator
- **Scout Agents (`scout.py`)**: Spawned dynamically for each approved category and executed in parallel. Each scout connects to a remote MCP server using vector search to retrieve exactly 3 physical product options strictly under the allocated budget limit.
- **Evaluator Node (`evaluator.py`)**: A standard Python node that parses the JSON output of all scouts, and algebraically confirms that the sum of the cheapest option from all categories is strictly less than or equal to the master budget.

### Phase 3: Final Verification & Cart Formatting
- **HitL Pause**: Once the Evaluator succeeds, the workflow pauses again, presenting all the retrieved options to the user.
- **Selection Agent**: Once the user chooses their preferred items (e.g. "I'll take the Kelty tent and the MOON LENCE bag"), a final LLM maps the natural language to the exact products and generates a gorgeous Markdown order confirmation. 

See [architecture.md](./architecture.md) for a visual diagram of the execution flow and UX patterns.

## Project Structure

```text
shopping_squad/
├── agents/             # ADK Node logic and logic orchestration
│   ├── agent.py        # The root sequential workflow and HitL state machine
│   ├── evaluator.py    # Python evaluation and budget constraint gating
│   ├── planner.py      # LLM Agent generating Pydantic-shaped budgets
│   ├── scout.py        # LLM Agent performing vector search via MCP
│   └── schemas.py      # Pydantic Core Models (CartItem, ShoppingPlan)
├── mcp/                # Tools and Backend Access
│   └── server.py       # Proxy converting local tool calls to Cloud Run REST APIs
├── architecture.md     # Visual workflow map and UX tricks
└── README.md
```

## Setup & Running

1. Ensure your environment has the required dependencies, including ADK's LiteLLM abstractions for complex tool routing:
   ```bash
   pip install "google-adk[extensions]" mcp httpx
   ```
2. Start the ADK Web UI from the squad root:
   ```bash
   adk web
   ```
3. Test your `shopping_workflow` by providing the initial prompt:
   > "I want an ultralight camping kit. My budget is $300."

Follow the instructions in the chat UI to approve the budget and make your final Cartesian selections!
