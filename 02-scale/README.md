# Scale AI Agents

**Track:** Build AI Apps & Agents  
**Session IDs:** GCS109, SHOW134  
**Type:** Live Demo  
**Level:** 200 Technical (Apply/Use).

## Description

Scale multi-agent systems for sophisticated use cases. Use Agent Engine, LangGraph, and CrewAI with MCP/A2A to orchestrate global retail workflows and optimize performance—all without the infrastructure overhead.

## Pitch

Ready to coordinate a Multi-Agent System (MAS) using Vertex AI, LangGraph, and CrewAI? Leverage the Agent Development Kit and MCP to manage real-time scale, going from just bots to a high-performance team that actually delivers.

## Demo Leaders & Contributors

- **Emmanuel Awa**
- **Kaz Sato**

## Scenario: Global Retail Workflow

This demo showcases a **Multi-Agent System (MAS)** designed to handle complex, global retail operations.

**The Challenge:** Orchestrating supply chain, inventory management, and customer support across multiple regions without massive infrastructure overhead.

**The Solution:** A team of specialized agents:

- **Planning Agent:** Uses LangGraph to decompose high-level goals into actionable tasks.
- **Execution Agents:** CrewAI agents that interface with specific systems (ERP, CRM) via **MCP**.
- **Governance:** Vertex AI Agent Identity ensures each agent has only the permissions it needs.
- **Interconnectivity:** LangGraph and CrewAI agents interact seamlessly with Vertex AI ADK agents via **A2A (Agent to Agent)** to demonstrate true cross-framework interoperability.

## Tech Stack

- Agent Engine
- Vector Search 2.0
- Agent Development Kit (ADK)
- A2A (Agent to Agent)
- Agent Identity
- LangGraph
- CrewAI
- Model Context Protocol (MCP)

## Architecture & Runtime Configuration

"Scale Agents" answers the question: **"What am I running and how is it configured?"**

This demo leverages the following key components to manage the lifecycle and state of AI agents:

- **Agent Engine:** The core runtime environment that executes agent logic, manages tool calls, and handles orchestration between multiple agents.
- **Memory:** Persistent context storage allowing agents to recall past interactions, user preferences, and intermediate reasoning steps across different sessions.
- **Sessions:** State management for ongoing user-agent or agent-agent interactions, ensuring continuity and context preservation.
- **Batch Inference Jobs:** High-throughput processing for offline tasks, enabling agents to process large datasets (e.g., nightly inventory analysis) efficiently in bulk.

## Agent Identity & Security

Leveraging **Vertex AI Agent Identity** for secure, scalable agent operations:

- **Centralized Access Control (GA Next):** Unified permission management for agents.
- **Enhanced Developer Experience (Preview Next):** Simplified authentication to MCP servers and auto-refreshing OAuth tokens.
- **Instance-Level Identity:** Granular security with unique identities per Agent Engine instance.
- **Multi-Cloud Interoperability:** Flexible and secure access to resources across cloud providers.
