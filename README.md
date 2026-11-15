# ✈️ TripPlanner-AI

**TripPlanner-AI** is an autonomous, multi-agent travel planning system built with **LangGraph**, **FastAPI**, **Groq LLM**, and the **Model Context Protocol (MCP)**. It coordinates specialized agents for live flights, hotel discovery, live weather forecasting, and budget optimization, featuring dynamic supervisor routing, input guardrails, and human-in-the-loop (HITL) itinerary approval.

---

## 🌟 Key Features

- **🧠 Dynamic Supervisor & Orchestration**: Powered by LangGraph to dynamically inspect travel requests, extract constraints (origin, destination, budget, duration, travel style), and delegate tasks only to relevant specialist agents.
- **🛡️ Input Guardrails**: Validates user intent, filtering out off-topic requests and prompt injections before invoking downstream APIs.
- **✈️ Live Flight Intelligence**: Fetches real-time flight routes, departures, arrivals, and delays via AviationStack with intelligent IATA code resolution (configured with default Kolkata `CCU` departures for travelers from Jamshedpur and Eastern India).
- **🏨 Live Hotel Discovery**: Integrates with Tavily Search to gather real-time hotel recommendations, boutique stays, and direct URLs.
- **⛅ Weather & Forecast MCP Server**: Built on FastMCP and OpenWeatherMap to deliver live conditions, temperatures, humidity, wind speeds, and multi-day forecasts.
- **💰 Budget Feasibility Analysis**: Automatically analyzes cost categories, highlights budget risk areas, and suggests money-saving recommendations.
- **👤 Human-in-the-Loop (HITL) Review**: LangGraph pauses execution (`interrupt()`) after drafting an itinerary, allowing users to **Approve & Finalize** or submit feedback to **Request Revisions**.
- **💾 Persistent State Management**: Session checkpointing backed by PostgreSQL via `langgraph-checkpoint-postgres` and `psycopg`.
- **🎨 Minimalist, Professional Web UI**: Clean, light-themed responsive interface (Linear/Vercel aesthetic) with instant Markdown parsing, specialist data inspection drawers, and 1-click PDF download via `html2pdf.js`.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    User([User Request]) --> Guardrail[Input Guardrail Node]
    Guardrail -- Allowed --> Supervisor[Supervisor Agent]
    Guardrail -- Disallowed --> OutputEnd[Explain Filter Reason]

    subgraph Specialists [Collaborating Specialist Agents]
        FlightAgent[✈️ Flight Agent<br/>AviationStack]
        HotelAgent[🏨 Hotel Agent<br/>Tavily Search]
        WeatherAgent[⛅ Weather Agent<br/>OpenWeather MCP]
        BudgetAgent[💰 Budget Agent<br/>Cost & Risk Analysis]
    end

    Supervisor --> FlightAgent
    Supervisor --> HotelAgent
    Supervisor --> WeatherAgent
    Supervisor --> BudgetAgent

    FlightAgent --> ItineraryDraft[🗺️ Itinerary Agent<br/>Draft Itinerary]
    HotelAgent --> ItineraryDraft
    WeatherAgent --> ItineraryDraft
    BudgetAgent --> ItineraryDraft

    ItineraryDraft --> HITL{👤 Human-in-the-Loop<br/>Review & Approval}

    HITL -- Needs Revision --> Supervisor
    HITL -- Approved --> FinalAgent[📋 Final Polished Response Agent]
    FinalAgent --> Complete([Final Travel Plan + PDF])
```

---

## 📁 Project Structure

```text
TripPlanner-AI/
├── app.py                         # FastAPI web server and REST API endpoints
├── backend.py                     # LangGraph state machine, supervisor, guardrail & agents
├── mcp_client.py                  # Multi-Server MCP client & formatting adapters
├── custom_weather_mcp_server.py   # FastMCP server wrapping OpenWeatherMap API
├── test.py                        # Terminal-based test script for CLI runs
├── requirements.txt               # Python package dependencies
├── .env                           # Environment variables & API keys
├── tools/
│   ├── flight_tool.py             # AviationStack flight search & airport resolution
│   └── tavily_tool.py             # Tavily search wrapper
├── templates/
│   └── index.html                 # Modern, responsive Jinja2 HTML template
└── static/
    ├── style.css                  # Minimalist design system & responsive styling
    └── script.js                  # Frontend state, HITL approvals & PDF generation
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10 to 3.12**
- **Git**
- Active API keys for:
  - [Groq](https://console.groq.com/) (LLM inference)
  - [Tavily](https://tavily.com/) (Web search)
  - [OpenWeatherMap](https://openweathermap.org/api) (Weather & Forecasts)
  - [AviationStack](https://aviationstack.com/) (Live flight data)
  - [PostgreSQL](https://www.postgresql.org/) (Local or hosted, e.g., Render, Neon, Supabase, Prisma)

---

### 2. Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/TripPlanner-AI.git
   cd TripPlanner-AI
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   # Windows PowerShell
   python -m venv travel
   .\travel\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

### 3. Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# Groq LLM API
GROQ_API_KEY="gsk_your_groq_api_key"
GROQ_MODEL="openai/gpt-oss-120b"

# Search & Flight APIs
TAVILY_API_KEY="tvly-your_tavily_api_key"
AVIATIONSTACK_API_KEY="your_aviationstack_key"

# Weather API
OPENWEATHER_API_KEY="your_openweather_key"

# Default Departure Airport (IATA)
DEFAULT_ORIGIN_IATA="CCU"

# PostgreSQL Checkpoint Database
DATABASE_URL="postgres://username:password@host:5432/dbname?sslmode=require"

# Optional: LangSmith Observability
LANGSMITH_TRACING="false"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY=""
LANGSMITH_PROJECT="TripPlanner-AI"
```

---

## 💻 Running the Application

### Option 1: Web Interface (FastAPI)

Start the Uvicorn web server:

```powershell
python app.py
```

Open your browser and navigate to:
```text
http://127.0.0.1:8000
```

#### How it works in the UI:
1. Enter your query (e.g., *"Plan a 7 days Japan trip departing from Kolkata under 2 lakhs"*).
2. The system executes the supervisor, guardrails, and specialist agents.
3. A **Draft Itinerary** appears with an interactive **Human-in-the-Loop Review Box**.
4. Click **Approve & Finalize Plan** to generate the final itinerary, or type custom feedback and click **Request Revision**.
5. Inspect raw agent findings in the collapsible drawer or download a clean **PDF**.

---

### Option 2: CLI Test Script

To run a fast command-line test of the pipeline:

```powershell
python test.py
```

---

## 🔌 API Reference

### 1. `POST /api/travel`
Initiates a new travel planning graph execution.

**Request Body:**
```json
{
  "message": "Plan a 5 days Dubai trip departing from Kolkata",
  "thread_id": "optional_session_thread_id"
}
```

**Response:**
```json
{
  "success": true,
  "thread_id": "user_abc123",
  "answer": "Draft itinerary markdown...",
  "requires_approval": true,
  "approval_request": "Please review the generated draft itinerary...",
  "selected_agents": ["flight_agent", "hotel_agent", "weather_agent", "budget_agent", "itinerary_agent"],
  "trip_constraints": {
    "destination": "Dubai",
    "origin": "Kolkata",
    "duration": "5 days",
    "budget": "N/A"
  },
  "flight_results": "...",
  "hotel_results": "...",
  "weather_results": "...",
  "budget_results": "..."
}
```

---

### 2. `POST /api/travel/approve`
Resumes a paused LangGraph thread with human approval or feedback.

**Request Body:**
```json
{
  "thread_id": "user_abc123",
  "approved": true,
  "feedback": ""
}
```

**Response:**
```json
{
  "success": true,
  "thread_id": "user_abc123",
  "answer": "# Final Polished Travel Plan...",
  "requires_approval": false,
  "approved": true
}
```

---

### 3. `GET /health`
Returns API status and enabled multi-agent features.

---

## 🛠️ Built With

- **[LangGraph](https://github.com/langchain-ai/langgraph)** — Multi-agent graph orchestrator with cyclic execution & state checkpointing.
- **[FastAPI](https://fastapi.tiangolo.com/)** — Modern, high-performance web framework.
- **[Groq](https://groq.com/)** — Ultra-fast LPU inference engine.
- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** — Open standard for connecting AI models to tools and data sources.
- **[OpenWeatherMap](https://openweathermap.org/)** — Global live weather and 5-day forecasting.
- **[AviationStack](https://aviationstack.com/)** — Real-time commercial flight tracking and status.
- **[Tavily](https://tavily.com/)** — High-precision search API optimized for LLMs.
- **[html2pdf.js](https://ekoopmans.github.io/html2pdf.js/)** — Client-side HTML-to-PDF generation.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
