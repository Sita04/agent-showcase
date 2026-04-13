# Executor Crew Source Code

This directory contains the core logic for the Execution Agents.

## File Structure

* `agents.py`: Defines the `SourcingSpecialist` and `ProcurementOfficer` using CrewAI (Note: Reasoning is disabled for stability with `gemini-3.1-flash-lite-preview`).
* `tasks.py`: Defines the specific tasks (`sourcing_task`, `procurement_task`) with strict Pydantic schemas to prevent output truncation.
* `tools.py`: Wrappers for the MCP Client (currently using mock implementations).
* `prompts.py`: Centralized dictionaries containing role, goal, backstory, and task instruction prompts.
* `crew.py`: The main orchestration class that ties agents and tasks together (Note: Planning mode is disabled for stability).

## Running the Crew

To test the execution layer independently:

```bash
# Ensure you are at the 02-scale/agents/executor directory
python src/crew.py
```
