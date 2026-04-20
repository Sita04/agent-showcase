# Personalized Shopping Agent - "Shopping Squad"

A premium, persona-driven shopping concierge application powered by Gemini and built with the  Agent Development Suite (ADK 2.0)

## 🌟 Features

### 🎭 Persona-Driven Experience
- **Tailored Scenarios**: Choose between different personas (Adam, Lucy, Elena), each with their own set of curated shopping scenarios.
- **Dynamic Routing**: The agent adapts its search and planning based on the active persona's preferences and budget.
- **Session Management**: Smooth transition between personas with a custom confirmation modal that protects your active session.

### 💎 Premium UI/UX
- **Glassmorphic Design**: A stunning, modern interface with rich gradients, glassmorphism (blur effects), and smooth transitions.
- **Intelligent Chat**: A clean conversational interface with smart follow-up actions.
- **Contextual Action Cards**: Product results are displayed in beautiful, actionable cards with direct "Add to Cart" capabilities.
- **Full-Width Follow-Up Menus**: At the end of a search, a full-width card presents natural follow-up options based on your persona.

### 🛒 Cart Management
- **A2UI Rendered Cart**: The cart is rendered dynamically as rich action cards directly in the chat interface, showing product images, names, and prices.
- **Real-time Budget Warnings**: The agent actively monitors the cart total against the persona's budget and issues warnings if exceeded.
- **Stripe Checkout**: Ready-to-use integration for creating payment sessions via `/api/create-checkout-session`.

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI / Starlette
- **Frontend**: Vanilla JavaScript, CSS3 (with advanced glassmorphism and CSS variables), Semantic HTML5
- **AI Integration**: Agent Framework - ADK 2.0
- **UI Framework**: A2UI (Server-Driven UI) for dynamic card rendering

## 🚀 Getting Started

### 📋 Setup & Installation

1. **Install Dependencies**:
   This project uses `uv` for dependency management. Install all required packages with:
   ```bash
   uv sync
   ```

2. **Configure Environment**:
   Create a `.env` file in the `agents/` directory and populate it with your configuration:
   ```bash
   # In agents/.env
   GOOGLE_CLOUD_PROJECT="your_project_id"
   GOOGLE_CLOUD_LOCATION="your_location"
   GCS_BUCKET="your_staging_bucket"
   GOOGLE_GENAI_USE_VERTEXAI=1
   STRIPE_SECRET_KEY="your_stripe_secret_key"
   MCP_SERVER_URL="https://ac-web2-761793285222.us-central1.run.app/mcp"
   MCP_DATASET_ID="mercari1m_mm2"
   GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true
   OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
   REMOTE_AGENT_ID="fill_this_after_you deploy your_agent_in_agent_engine"
   USE_REMOTE_AGENT=true
   AUTH_USERNAME=""
   AUTH_PASSWORD=""
   ```

### 🚀 Running the Application

1. **Start the Backend Server**:
   ```bash
   uv run python app_server.py
   ```
   This will start the FastAPI server handling the UI and agent interaction.

2. **Access the UI**:
   Open your browser and navigate to `http://localhost:8080` (or the port displayed in the terminal).

### ☁️ Deployment

#### 1. Deploy Agent to Vertex AI Agent Engine
To deploy the Reasoning Engine (the agent logic) to Vertex AI, run:
```bash
uv run deploy.py
```
This script packages the code and deploys it to your configured Google Cloud project.

> [!NOTE]
> You can enter the remote agent ID in your configuration only after successfully deploying the agent, as the ID is generated during the deployment process.

#### 2. Deploy UI to Google Cloud Run
To deploy the frontend and API server to Cloud Run, use the following command:
```bash
gcloud run deploy shopping-squad-ui --source . --project your-project-id --region your-region --allow-unauthenticated

```

## 📁 Project Structure

- `app_server.py`: Main server handling API requests and agent orchestration.
- `agents/`: Contains the agent definitions and schemas.
  - `agent.py`: Core agent logic.
  - `planner.py`: Planning agent definition.
  - `scout.py`: Scout agent for product search.
  - `evaluator.py`: Evaluator agent for proposals.
  - `schemas.py`: Pydantic schemas for structured data.
  - `views/`: Contains UI rendering logic (A2UI cards).
- `ui/`: Frontend assets.
  - `index.html`: Main application structure.
  - `style.css`: Premium styling and animations.
  - `app.js`: Core frontend logic and A2UI rendering engine.
- `Dockerfile`: Container definition for deployment.
- `pyproject.toml`: Dependency management configuration.
- `architecture.png`: High-level architecture documentation.

## 🏗️ Core Architectural Patterns

The Shopping Squad leverages several advanced patterns to deliver a premium experience:

### 1. Multi-Agent Orchestration (ADK)
The system uses the Retail Agent Development Suite (ADK) to coordinate multiple specialized agents:
- **Planner Agent**: Decomposes vague user requests into a structured, multi-component shopping plan with budget allocations.
- **Scout Agents**: Run in parallel to search for real products matching the plan components using Model Context Protocol (MCP) tools.
- **Evaluator Agent**: Acts as a gatekeeper, verifying that the combined cost of the found items fits within the user's master budget.

### 2. A2UI (Server-Driven UI)
Instead of returning plain text, the backend generates JSON payloads that follow the A2UI schema. The frontend (`ui/app.js`) interprets these payloads to render rich interactive cards, carousels, and action buttons. This keeps the UI perfectly synchronized with the agent's state.

### 3. System Speaker Pattern
To bypass ADK's default behavior of rendering internal node traces in the UI, the system uses a "System Speaker" pattern. Critical user-facing messages are piped through a minimal presentation agent, forcing the frontend to render them as clean chat bubbles.

### 4. Structured Data Transfer via Hidden Comments
To pass complex structured data (like product options or cart states) from the agent to the backend/frontend without cluttering the chat transcript, the system uses hidden HTML comments:
- `<!--[JSON_PAYLOAD] ... [/JSON_PAYLOAD]-->` for passing search results.
- `<!--[CART_PAYLOAD] ... [/CART_PAYLOAD]-->` for passing cart state during checkout.

## 🔄 Application Flow

Here is how the application processes a user request:

1. **User Input**: The user sends a prompt (and optionally an image) via the Web UI.
2. **Server Entry**: The request hits `app_server.py` at `/api/chat`.
3. **Planning**: The workflow invokes the **Planner Agent** to create a structured plan.
4. **Human-in-the-Loop (HITL)**: The plan is presented to the user via A2UI cards for approval.
5. **Parallel Search**: Upon approval, parallel **Scout Agents** search for items using MCP tools.
6. **Evaluation**: The **Evaluator** checks if the items fit the budget.
7. **Selection**: Results are rendered as A2UI cards. The user selects items to add to the cart.
8. **Checkout**: The user triggers checkout, and the system generates a Stripe payment link.
