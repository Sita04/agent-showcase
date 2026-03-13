# Executor Swarm Design (CrewAI)

**Role:** The "Hands" of the system.
**Responsibility:** Execute specific, bounded logistical tasks delegated by the Planner.
**Architecture:** A CrewAI Swarm consisting of specialized agents.

## Agents

### 1. Sourcing Specialist (`sourcing_agent`)

* **Role:** Expert Buyer / Inventory Scout.
* **Goal:** Find the best available products that match the semantic intent of the request.
* **Backstory:** "You are a veteran procurement specialist with an eye for detail. You don't just match keywords; you understand the 'vibe'. You are tenacious and will try multiple search strategies if the first one fails."
* **Tools:** `MCP_Vector_Search`
* **Behavior:**
    1. Receives a vague description (e.g., "Vintage Sci-Fi Mugs").
    2. Formulates a search query.
    3. Analyzes the returned vector results.
    4. **Critical:** If results are poor (low similarity score), it refines the query and tries again *before* giving up.
    5. Outputs a list of `Candidate Products` with ID, Name, Price, and "Match Reason".

### 2. Procurement Officer (`purchasing_agent`)

* **Role:** Financial Controller / Order Manager.
* **Goal:** Validate the purchase against budget constraints and execute the order.
* **Backstory:** "You are the gatekeeper of the budget. You ensure we never overpay and that every Purchase Order (PO) is accurate. You trust the Sourcing Specialist's recommendations but verify the math."
* **Tools:** `MCP_Order_Management` (Create PO, Check Budget)
* **Behavior:**
    1. Receives `Candidate Products` from the Sourcing Specialist.
    2. Checks against the `Task Budget` and `Quantity` requirements.
    3. Selects the best fit (e.g., lowest price that meets quality, or highest quality within budget).
    4. Executes `create_po`.
    5. Reports the final `PO_ID` and status.

## Workflow (Crew)

The `LogisticsExecutionCrew` manages the sequential process:

1. **Task 1 (Sourcing):** "Find [Quantity] of [Description]. Strict requirement: [Constraints]." -> Assigned to `Sourcing Specialist`.
2. **Task 2 (Procurement):** "Review the candidates. If a valid item is found within [Budget], place the order." -> Assigned to `Procurement Officer`.

## Error Handling (Self-Correction)

* **Scenario: No Items Found.**
  * *Sourcing Specialist* returns: "Status: FAILED. Reason: No items above 0.8 similarity. Recommendation: Broaden search to 'Sci-Fi Cups'."
  * *Crew Manager* (Process): Halts execution (or reports back to Planner via A2A).
* **Scenario: Over Budget.**
  * *Procurement Officer* returns: "Status: BLOCKED. Reason: Best item is $50, Budget is $30."

## File Structure

```bash
02-scale/agents/
├── config/
│   └── default_config.py   # Global project constants and configs
└── executor/
    └── src/
        ├── agents.py       # Defines the CrewAI Agents (with Reasoning enabled)
        ├── tasks.py        # Defines the Tasks
        ├── tools.py        # MCP Tool Wrappers
        ├── prompts.py      # Centralized prompts (roles, goals, instructions)
        └── crew.py         # Main entry point (The Crew with Planning enabled)
```
