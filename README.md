# Agent Showcase

Build, Scale and Govern demos for Google Cloud NeXT'26.

This repository contains multiple multi-agent system demonstrations showcasing different aspects of the Google Agent Platform, Model Context Protocol (MCP), and advanced orchestration frameworks.

## Demos & Components

*   **[01-build (Shopping Squad)](./01-build/)**: A hyper-personalized, multi-agent shopping workflow built on the Google Agent Development Kit (ADK) 2.0. It utilizes dynamic ADK workflow graphs and MCP to decompose a vague shopping request into a structured plan, featuring Human-in-the-Loop (HitL) checkpoints for budget approval and final cart selection.
*   **[02-scale (Global Retail IT Orchestrator)](./02-scale/)**: A demonstration of scaling multi-agent systems for sophisticated use cases. It leverages Google Agent Engine, LangGraph, and CrewAI with MCP and the Agent-to-Agent (A2A) protocol to orchestrate a secure, global retail workflow. This demo highlights "Hub-and-Spoke" delegation and strict security boundaries using Google Agent Platform Agent Identity.
*   **[03-govern](./03-govern/)**: *(Coming soon)* Demonstrations focusing on the governance, security, and auditing of multi-agent systems.
*   **[Vector Search Backend](./vector-search-backend/)**: A Flask-based search backend API powered by Google Cloud Vertex AI Vector Search 2.0. It provides semantic, text, and hybrid search capabilities over product datasets (e.g., Mercari items) and includes an MCP server for seamless AI agent integration.

## Getting Started

### Unified Workspace Setup

This repository uses [`uv`](https://github.com/astral-sh/uv) to manage a unified Python workspace across all sub-projects. You can easily set up the master virtual environment from the root directory:

1. **Install `uv`** (if you haven't already):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Sync Dependencies**:
   Sync dependencies for all projects from the repository root:
   ```bash
   uv sync
   ```

### Running the Demos

Each directory contains its own `README.md` and configuration files (`pyproject.toml`, `requirements.txt`) with specific execution instructions. Please navigate to the individual project folders for detailed documentation on running the agents and their respective services.
