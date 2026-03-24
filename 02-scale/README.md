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

4. **Running the Full System (LangGraph Planner + CrewAI Executor)**:
    To run the complete end-to-end multi-agent system:

    ```bash
    uv run -q agents/planner/src/graph.py
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

1. **Planning Agent (The Brain):** A **LangGraph** state machine that analyzes high-level goals (e.g., "Restock Northeast Region") and delegates tasks. It has **no direct access** to the inventory database.
2. **Execution Agents (The Hands):** Ephemeral **CrewAI** swarms that receive specific tasks (e.g., "Order 500 Vintage Sci-Fi Mugs"). They connect to the **Mercari Product Vector Store** via **MCP**.
3. **Governance:** **Google Agent Platform Agent Identity** ensures "Least Privilege"—only the Execution Agent can touch the database, while the Planning Agent handles strategy.

## Tech Stack

* **Runtime:** Google Agent Engine
* **Planning:** LangGraph (Python)
* **Execution:** CrewAI (Python)
* **Interoperability:** Agent-to-Agent (A2A) Protocol
* **Data Source:** Mercari Product Vector Store (via REST API)
* **Tooling:** Model Context Protocol (MCP)
* **Security:** Google Agent Platform Agent Identity

## Critical User Journeys (CUJs)

### 1. The "Happy Path" Restock

The **Planning Agent** identifies a stock shortage and delegates a procurement task to a **CrewAI Logistics Agent**. The CrewAI agent uses **Semantic Vector Search** to find the best matching products ("Vintage Sci-Fi Mugs") and places a mock Purchase Order.

### 2. The "Identity Shield" (Security)

A malicious prompt attempts to trick the **Planning Agent** into deleting the vector index. The **Google Agent Engine** intercepts the call and blocks it because the Planning Agent's **Identity** lacks `Vector_Store_Write` permissions.

### 3. Cross-Framework Error Handling

The **Planning Agent** requests a discontinued item. The **Execution Agent** fails to find it in the vector store, catches the error, and reports back a structured recommendation ("No inventory found, try broadening search"). The Planning Agent then re-plans automatically.

## Architecture

![architecture](./assets/scale-arch-diagram.png)

```mermaid
graph TD
    User[User / Dashboard] -->|Trigger Restock| PA[Planning Agent (LangGraph)]
    
    subgraph "Strategy Layer (High Privilege)"
        PA -->|Plan & Delegate| A2A[A2A Protocol Interface]
    end
    
    subgraph "Execution Layer (Restricted Scope)"
        A2A -->|Task Packet| EA[Execution Agent (CrewAI)]
        EA -->|Query/Action| MCP[MCP Client]
    end
    
    subgraph "External Systems"
        MCP -->|REST API| VS_API[Vector Search Service]
        VS_API -->|Semantic Search| VDB[(Mercari Vector Store)]
        MCP -->|Internal Mock| OMS[Mock Order System]
    end
```

## Running the Demo

### Testing the MCP Server (Standalone)

Before running the full agent workflow, you can test the **Mock Order Management System (OMS)** MCP server directly using the official Model Context Protocol Inspector.

1. Open a new terminal window.
2. Run the Inspector with the required environment variables and the `-q` (quiet) flag to prevent `uv` from polluting the JSON stream:

    ```bash
    GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID> npx @modelcontextprotocol/inspector uv run -q mock_oms_mcp/server.py
    ```

3. Open the provided `localhost:6274` URL in your browser.
4. On the left sidebar, select tools like `check_budget` or `create_purchase_order`, provide arguments (e.g., `amount: 50`, `category: collectibles`), and click "Run Tool" to see the JSON response.

### Running the Agent Execution Swarm

Once you've verified the tools work, you can run the CrewAI worker agents. They will seamlessly connect to the MCP servers in the background and execute the logistics tasks autonomously.

```bash
uv run -q agents/executor/src/crew.py
```
