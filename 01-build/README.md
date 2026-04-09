# Personalized Shopping Agent - "Shopping Squad"

A premium, persona-driven shopping concierge application powered by Gemini and built with the Retail Agent Development Suite (ADK) and A2UI (Server-Driven UI).

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

### 🛒 Advanced Cart Management
- **Integrated Cart**: A side drawer cart that slides in and out, keeping your shopping flow uninterrupted.
- **Quantity Counter**: Easily see how many items you have selected.
- **Silent Actions**: Adding or removing items from the cart updates the UI smoothly without cluttering the chat history with system messages.
- **Stripe Checkout**: Ready-to-use integration for creating payment sessions via `/api/create-checkout-session`.

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI / Starlette
- **Frontend**: Vanilla JavaScript, CSS3 (with advanced glassmorphism and CSS variables), Semantic HTML5
- **AI Integration**: Google Gen AI SDK (Gemini) via ADK
- **UI Framework**: A2UI (Server-Driven UI) for dynamic card rendering

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Vertex AI Project 
- Stripe Secret Key (set as `STRIPE_SECRET_KEY` environment variable)

### Running the Application

1. Start the backend server:
   ```bash
   python3 app_server.py
   ```

2. Open your browser and navigate to the local address provided by the server (usually `http://localhost:8000` or as configured).

## 📁 Project Structure

- `app_server.py`: Main server handling API requests and agent orchestration.
- `agents/`: Contains the agent definitions (planner, scout, etc.).
  - `views/`: Contains UI rendering logic (like `search.py` for A2UI grids).
- `ui/`: Frontend assets.
  - `index.html`: Main application structure.
  - `style.css`: Premium styling and animations.
  - `app.js`: Core frontend logic and A2UI rendering engine.
