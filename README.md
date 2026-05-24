# AI Agent Orchestration Platform

A full-stack platform for creating, configuring, and orchestrating AI agents that communicate with each other and execute real tasks autonomously. Includes a visual workflow builder, Telegram integration, two-tier semantic memory, and a real-time monitoring dashboard.

## Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend (React + Vite + Tailwind)"]
        A1[Agents Page<br/>CRUD + Memory Viewer]
        A2[Workflow Builder<br/>React Flow Canvas]
        A3[Chat UI<br/>+ Memory Panel]
        A4[Monitor Dashboard<br/>Logs + Stats]
    end

    subgraph Backend["Backend (FastAPI + Python)"]
        B1[Agent CRUD API]
        B2[Workflow Engine<br/>BFS + Fan-in]
        B3[Chat Router]
        B4[Telegram Webhook]
        B5[Memory Routes]
        B6[Logs + Stats API]
    end

    subgraph Runtime["Agent Runtime (LangGraph)"]
        R1[Ollama LLM<br/>llama3.1:8b]
        R2[Tool Registry<br/>8 tools]
        R3[Semantic Memory<br/>ChromaDB + MiniLM]
    end

    subgraph Data["Data Layer"]
        D1[(PostgreSQL 16<br/>Agents, Workflows,<br/>Messages, Logs)]
        D2[(ChromaDB<br/>Vector Embeddings)]
    end

    Frontend -->|REST API| Backend
    Backend --> Runtime
    Runtime --> Data
    B4 -->|Webhook| TG[Telegram Bot API]
```

## Tech Stack & Justification

| Component | Choice | Why |
|-----------|--------|-----|
| **Backend** | Python + FastAPI | Async-native, best AI/ML ecosystem, great DX |
| **Frontend** | React 18 + Vite 5 + Tailwind CSS 3 | Fast builds, modern tooling, React Flow for visual workflows |
| **AI Framework** | LangGraph | Graph-based agent orchestration with conditional edges and cycles — needed for feedback loops. Chosen over CrewAI (too opinionated, limited edge conditions) and AutoGen (heavy, complex setup for simple flows) |
| **LLM** | Ollama (local, llama3.1:8b) | Zero cost, no API keys, reproducible, runs on consumer hardware (Apple Silicon / GPU) |
| **Vector Memory** | ChromaDB + all-MiniLM-L6-v2 | Lightweight local embeddings (~80MB model), no external API needed, cosine similarity search |
| **Database** | PostgreSQL 16 | Robust relational persistence for agents, workflows, messages, logs |
| **Messaging** | Telegram Bot API | 100% free, no business verification, instant bot creation via @BotFather |
| **Workflow UI** | React Flow 11 | Purpose-built for node-based editors, drag-and-drop, handles and edges |

## Features

### Agent Management (15+ configurable dimensions)
- Full CRUD: name, role, system prompt, model selector, tools, channels
- Configurable: schedule (cron), memory toggle, temperature, max tokens, guardrails, skills, interaction rules
- Per-agent memory visualization: view short-term + long-term memories, semantic recall search, add/delete facts

### Semantic Memory (Two-Tier)
- **Short-term**: Every message embedded and stored per-agent in ChromaDB. Semantically similar past messages recalled on each turn
- **Long-term**: Persistent facts stored separately. Agents can self-store via `remember_fact` tool, or users add facts manually in the UI
- Both tiers use cosine similarity with `all-MiniLM-L6-v2` embeddings — fully local, no API calls
- Memory visible and searchable in the UI (Agents page → Memory button, Chat page → Memory panel)

### Tool Registry (8 executable tools)
| Tool | Description |
|------|-------------|
| `web_search` | DuckDuckGo search (top 5 results) |
| `calculator` | Safe math expression evaluator |
| `code_executor` | Python snippet execution (10s timeout, subprocess isolation) |
| `file_reader` | Read local files (CWD-restricted) |
| `weather` | Current weather via wttr.in (free, no API key) |
| `summarizer` | Extractive text summarization |
| `current_datetime` | Returns current date and time |
| `remember_fact` | Stores a fact to agent's long-term memory |

### Visual Workflow Builder
- Drag-and-drop React Flow canvas with node/edge editing
- Add nodes (agents), draw edges (connections), set conditions on edges
- Condition types: `contains`, `not_contains`, `max_iterations` (feedback loops)
- **Fan-in support**: multiple agents can feed into one aggregator node — outputs are merged with labels
- 2 pre-built templates:
  1. **Research & Summarize**: Researcher → Summarizer
  2. **Customer Support Escalation**: Frontline → Specialist → Manager (conditional)
- Expanded output panel with 3 view modes: Formatted (agent cards), JSON (raw), Steps (per-node)

### Telegram Integration
- Webhook-based: receives messages, routes to assigned agent, sends response back
- Full message history persisted and visible in web UI

### Monitoring Dashboard
- **Overview tab**: total agents/messages/tokens, per-agent token usage, channel/role distribution
- **Logs tab**: real-time log viewer with auto-refresh (5s), level coloring
- **Inter-Agent tab**: view all agent-to-agent messages from workflow executions

---

## Quick Start (Local Development)

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| PostgreSQL | 16 | `brew install postgresql@16` |
| Ollama | latest | `brew install ollama` |

### Step 1: Clone and enter the project

```bash
cd agents
```

### Step 2: Start PostgreSQL

```bash
brew services start postgresql@16
```

### Step 3: Create database and user

```bash
psql postgres -c "CREATE USER agents WITH PASSWORD 'agents_dev';"
psql postgres -c "CREATE DATABASE agents_platform OWNER agents;"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE agents_platform TO agents;"
psql agents_platform -c "GRANT ALL ON SCHEMA public TO agents;"
```

### Step 4: Start Ollama and pull the model

```bash
ollama serve &
ollama pull llama3.1:8b
```

> This downloads ~4.7 GB. The model runs on CPU or Apple Silicon GPU automatically.

### Step 5: Install and start the backend

```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` (or copy from root):
```bash
cp ../.env.example .env
```

The defaults work out of the box:
```
DATABASE_URL=postgresql+asyncpg://agents:agents_dev@localhost:5432/agents_platform
REDIS_URL=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_URL=
```

Start the backend:
```bash
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 6: Install and start the frontend

Open a **new terminal**:
```bash
cd frontend
npm install
npm run dev
```

You should see:
```
VITE v5.x.x ready
➜ Local: http://localhost:5173/
```

### Step 7: Open the app

Navigate to **http://localhost:5173** in your browser.

---

## First Steps in the UI

### 1. Create an Agent
- Go to **Agents** → **Create Agent**
- Fill in: name, role, system prompt
- Select tools (e.g., `web_search`, `weather`, `calculator`)
- Enable memory
- Click **Save**

### 2. Chat with an Agent
- Go to **Chat** → select your agent from the sidebar
- Type a message and hit Send
- The agent will use Ollama + tools to respond
- Click the 🧠 brain icon to view/search the agent's memory

### 3. Build a Workflow
- Go to **Workflows** → load a template (e.g., "Research & Summarize")
- Assign agents to each node (click a node → select agent from dropdown)
- Save the workflow
- Enter an input message and click **Run**
- View results in the expanded output panel (Formatted / JSON / Steps)

### 4. Monitor Activity
- Go to **Monitor** → see real-time stats, logs, and inter-agent messages

---

## Telegram Bot Setup

1. Open Telegram, message **@BotFather**, send `/newbot`, follow prompts
2. Copy the bot token
3. Add to `backend/.env`:
   ```
   TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxx
   ```
4. Expose your local server:
   ```bash
   ngrok http 8000
   ```
5. Add the ngrok URL to `backend/.env`:
   ```
   TELEGRAM_WEBHOOK_URL=https://abc123.ngrok-free.app/api/telegram/webhook
   ```
6. Register the webhook:
   ```bash
   curl -X POST http://localhost:8000/api/telegram/setup-webhook
   ```
7. In the web UI, create an agent with `telegram` in its channels
8. Message your bot on Telegram — the agent responds!

---

## Docker Compose (Alternative)

### Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Docker Compose v2 | Included with Docker Desktop |

### Step 1: Create the backend `.env` file

```bash
cp .env.example backend/.env
```

Edit `backend/.env` if you need Telegram (otherwise the defaults work):
```
DATABASE_URL=postgresql+asyncpg://agents:agents_dev@localhost:5432/agents_platform
REDIS_URL=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
TELEGRAM_BOT_TOKEN=          # optional — see Telegram section below
TELEGRAM_WEBHOOK_URL=        # optional
```

> When running inside Docker, the backend reads `DATABASE_URL` and `OLLAMA_BASE_URL` from docker-compose.yml environment overrides, so the `.env` values for those are only used in local development.

### Step 2: Build and start all services

```bash
docker compose up --build
```

This starts 5 services:

| Service | Port | Description |
|---------|------|-------------|
| **postgres** | 5432 | PostgreSQL 16 — auto-creates `agents_platform` database |
| **redis** | 6379 | Redis 7 (caching layer) |
| **ollama** | 11434 | Ollama LLM server |
| **backend** | 8000 | FastAPI with hot-reload |
| **frontend** | 5173 | Vite dev server |

### Step 3: Pull the LLM model (first run only)

In a separate terminal, pull the model into the Ollama container:

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

> This downloads ~4.7 GB. Progress is shown in the terminal. The model is persisted in a Docker volume (`ollama_data`), so you only need to do this once.

### Step 4: Open the app

Navigate to **http://localhost:5173** in your browser. The backend API is at **http://localhost:8000/docs**.

### Stopping

```bash
docker compose down
```

To also wipe database and model data (full reset):
```bash
docker compose down -v
```

---

## Running Tests

```bash
cd backend
source ../venv/bin/activate
python -m pytest tests/ -v
```

16 tests covering:
- Agent CRUD (create, list, get, update, delete, validation, not-found)
- Workflow CRUD (create, list, execution)
- Chat message delivery + message history
- Monitoring stats endpoint
- Health check

---

## Project Structure

```
agents/
├── docker-compose.yml              # Full stack orchestration (5 services)
├── .env.example                    # Environment template
├── README.md
├── backend/
│   ├── Dockerfile                  # Python 3.12-slim
│   ├── requirements.txt            # 20 packages
│   ├── .env                        # Local config (gitignored)
│   ├── pyproject.toml              # pytest config
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan, CORS, 7 routers
│   │   ├── config.py               # Pydantic Settings (env-based)
│   │   ├── database.py             # Async SQLAlchemy engine + session
│   │   ├── models.py               # Agent, Workflow, WorkflowExecution, Message, AgentLog
│   │   ├── schemas.py              # Pydantic request/response schemas
│   │   ├── runtime.py              # LangGraph agent execution (Ollama + tools + memory)
│   │   ├── memory.py               # Two-tier semantic memory (ChromaDB)
│   │   ├── tools.py                # Tool registry (8 real tools)
│   │   ├── workflow_engine.py      # Workflow BFS executor with fan-in
│   │   └── routers/
│   │       ├── agents.py           # CRUD
│   │       ├── workflows.py        # CRUD + execute
│   │       ├── chat.py             # Chat + inter-agent messaging
│   │       ├── messages.py         # Message history
│   │       ├── logs.py             # Logs + stats + monitoring
│   │       ├── memory_routes.py    # Memory CRUD + recall
│   │       └── telegram.py         # Telegram webhook
│   └── tests/
│       ├── conftest.py             # Heavy dependency mocking
│       └── test_critical_paths.py  # 16 tests
├── frontend/
│   ├── Dockerfile                  # Multi-stage: Node build → nginx serve
│   ├── nginx.conf                  # SPA routing + API proxy
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx                 # Router + sidebar layout
│       ├── api.ts                  # Type-safe API client (7 modules)
│       ├── pages/
│       │   ├── AgentsPage.tsx      # Agent cards + memory viewer modal
│       │   ├── WorkflowsPage.tsx   # React Flow builder + output panel
│       │   ├── ChatPage.tsx        # Chat UI + memory panel
│       │   └── MonitorPage.tsx     # 3-tab monitoring dashboard
│       └── components/
│           └── AgentForm.tsx       # Agent create/edit form (15+ fields)
└── venv/                           # Python virtual environment (local)
```

---

## Adding New Workflow Templates

Add a new entry to the `TEMPLATES` object in `frontend/src/pages/WorkflowsPage.tsx`:

```typescript
const TEMPLATES = {
  my_template: {
    name: 'My Template',
    description: 'Description of what this workflow does',
    graph: {
      nodes: [
        { id: 'n1', type: 'default', position: { x: 100, y: 100 }, data: { label: 'Agent 1', agent_id: '', role: 'role1' } },
      ],
      edges: [
        { id: 'e1', source: 'n1', target: 'n2', markerEnd: { type: MarkerType.ArrowClosed }, label: 'always' },
      ],
    },
  },
};
```

## Adding New Messaging Channels

1. Create a new router in `backend/app/routers/` (e.g., `slack.py`)
2. Implement a webhook endpoint that:
   - Receives messages from the channel
   - Finds the agent assigned to that channel
   - Calls `run_agent()` from `app.runtime`
   - Saves messages with the channel name
   - Sends response back to the channel
3. Register the router in `backend/app/main.py`:
   ```python
   from app.routers import slack
   app.include_router(slack.router, prefix="/api")
   ```
4. Add the channel name to `AVAILABLE_CHANNELS` in `frontend/src/components/AgentForm.tsx`

## Adding New Tools

1. Add a function in `backend/app/tools.py` with the `@tool` decorator:
   ```python
   @tool
   def my_tool(param: str) -> str:
       """Description of what this tool does."""
       return "result"
   ```
2. Register it in `TOOL_REGISTRY` at the bottom of the same file
3. Add the tool name to `AVAILABLE_TOOLS` in `frontend/src/components/AgentForm.tsx`

---

## Resource Requirements

| Service | RAM |
|---------|-----|
| Ollama + Llama 3.1 8B (Q4) | ~6 GB |
| PostgreSQL | ~0.5 GB |
| ChromaDB + Embeddings Model | ~0.5 GB |
| FastAPI backend | ~0.5 GB |
| React dev server | ~0.3 GB |
| **Total** | **~7.8 GB** |

Runs comfortably on 20 GB RAM with headroom for OS and dev tools.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents` | Create agent |
| GET | `/api/agents/{id}` | Get agent |
| PUT | `/api/agents/{id}` | Update agent |
| DELETE | `/api/agents/{id}` | Delete agent |
| GET | `/api/workflows` | List workflows |
| POST | `/api/workflows` | Create workflow |
| POST | `/api/workflows/{id}/execute` | Execute workflow |
| POST | `/api/chat/{agent_id}` | Chat with agent |
| POST | `/api/chat/inter-agent` | Inter-agent message |
| GET | `/api/messages/agent/{id}` | Message history |
| GET | `/api/memory/{id}/long-term` | List facts |
| POST | `/api/memory/{id}/long-term` | Add fact |
| POST | `/api/memory/{id}/recall` | Semantic recall |
| DELETE | `/api/memory/{id}/clear` | Clear memory |
| GET | `/api/logs/stats` | Platform stats |
| GET | `/api/logs/recent` | Recent logs |
| POST | `/api/telegram/webhook` | Telegram webhook |
| POST | `/api/telegram/setup-webhook` | Register webhook |
