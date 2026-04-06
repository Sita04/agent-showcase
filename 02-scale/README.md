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

A malicious prompt attempts to trick the **Planning Agent** into deleting the vector index. The **Google Agent Engine** intercepts the call and blocks it because the Planning Agent's **Identity** lacks `Vector_Store_Write` permissions.

### 3. Cross-Framework Error Handling

The **Planning Agent** requests a discontinued item. The **Execution Agent** fails to find it in the vector store, catches the error, and reports back a structured recommendation ("No inventory found, try broadening search"). The Planning Agent then re-plans automatically.

## Architecture

![architecture](./assets/scale-arch-diagram.png)

```mermaid
graph TD
    User[ADK Agent / Dashboard] -->|A2A JSON-RPC 'message/send'| A2AServer[A2A Web Server (Uvicorn)]
    
    subgraph "Strategy Layer (High Privilege)"
        A2AServer -->|Extract Intent| PA[Planning Agent (LangGraph)]
    end
    
    subgraph "Execution Layer (Restricted Scope)"
        PA -->|Delegate Logistics| EA[Execution Agent (CrewAI)]
        EA -->|Query/Action| MCP[MCP Client]
    end
    
    subgraph "External Systems"
        MCP -->|REST API /api/query| VS_API[Vector Search Service]
        VS_API -->|Semantic Search| VDB[(Mercari Vector Store)]
        MCP -->|Internal Mock| OMS[Mock Order System]
    end
    
    style PA fill:#e1f5fe,stroke:#01579b
    style EA fill:#e8f5e9,stroke:#1b5e20
    style MCP fill:#fff3e0,stroke:#e65100
    style A2AServer fill:#f3e5f5,stroke:#4a148c
```

## Running the Demo

### Testing the Full System (Native A2A)

The demonstration relies on a LangGraph planner acting as an A2A server that triggers the CrewAI execution swarm.

To test this flow, open **two** terminal windows:

**Terminal 1: Start the A2A LangGraph Server**
This runs the Uvicorn server, exposing the `.well-known/agent-card.json` and listening for tasks.

```bash
uv run agents/planner/a2a_server.py
```

**Terminal 2: Run the Mock A2A Client**
This script acts as an external ADK agent. It sends a natural language prompt via an A2A JSON-RPC request to the server, triggering the entire LangGraph -> CrewAI -> MCP flow.

```bash
uv run agents/planner/test_a2a_client.py
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
