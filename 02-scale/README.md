# Scale AI Agents: Global Retail IT Orchestrator

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

2. **Initialize the Project**:
    Navigate to the `02-scale` directory and initialize the project:

    ```bash
    cd 02-scale
    uv init
    ```

3. **Install Dependencies**:
    Add the required packages for the Executor Agents (CrewAI) and Planning Agents (LangGraph):

    ```bash
    uv add crewai crewai-tools langchain-google-vertexai python-dotenv requests mcp
    ```

4. **Running the Agents**:
    To run the Executor Crew directly:

    ```bash
    uv run python agents/executor/src/crew.py
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

> (Coming Soon: Instructions for scaffolding agents and running the MCP server)
