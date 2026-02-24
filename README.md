# SecondBrain AgenticRAG

A modernized Second Brain system that keeps conversational memory, routes queries through an agentic workflow, and stores searchable knowledge across text and images.

## Highlights

- **Agentic RAG** — LangGraph-powered workflow that routes, retrieves, and refines
- **Cross-Session Memory** — Remembers past conversations across all sessions via PostgreSQL
- **Triple-Source Retrieval** — Combines vector search, user memories, and session history
- **Multi-LLM Parallel Calls** — Queries OpenAI, Gemini, and Grok simultaneously with context
- **Smart Summarization** — Gemini-primary with automatic OpenAI fallback on quota limits
- **Notion Push** — Export conversation summaries directly to your Notion database

---

## Architecture

![System Architecture](docs/architecture.svg)

### Services Overview

| Service | Port | Description |
|---------|------|-------------|
| **Frontend** | 8000 | Web UI for chat interface |
| **API** | 8001 | FastAPI + LangGraph agentic pipeline |
| **Vector** | 8002 | Embedding generation and semantic search |
| **Qdrant** | 6333 | Vector database for knowledge storage |
| **PostgreSQL** | 5432 | Sessions, messages, and cross-session memories |

---

## Agentic Workflow

![Workflow Diagram](docs/workflow.svg)

The agentic RAG pipeline follows these stages:

1. **Classify Session** (`classify_session`) — **[NEW]** LLM categorizes the session as "RAG" (History Search) or "NO_RAG" (General).
2. **Route** (`route_query`) — LLM decides whether retrieval is needed (only for RAG mode).
3. **Retrieve** (`retrieve_context`) — Gathers context from 3 sources (no LLM).
4. **Call LLMs** (`call_llms`) — Parallel calls to OpenAI/Gemini/Grok with injected context (skipped if NO_RAG).
5. **Answer** (`generate_answer`) — Synthesizes final response from all LLM outputs.

---

## Agent Flow

![Agent Flow](docs/agent-flow.svg)

### Memory Sources

| Source | Storage | Scope | Purpose |
|--------|---------|-------|---------|
| `semantic_search` | Qdrant | Global | Vector similarity search on stored knowledge |
| `user_memories` | PostgreSQL | Cross-session | Retrieve past Q&A from `prompt_logs` table |
| `session_history` | PostgreSQL | Current session | Recent messages for immediate context |

### LLM Providers

All LLMs receive the **full retrieved context** injected into their prompts:

- **OpenAI** (`gpt-4o` for agent reasoning; `OPENAI_MODEL` for parallel calls, default `gpt-5-mini`) — Primary reasoning model
- **Gemini** (`GEMINI_MODEL`, default `gemini-2.0-flash-exp`) — Fast responses, used for summarization
- **Grok** (`grok-2-vision-1212`) — Alternative perspective

---

## AgenticRAG Mechanism

This project implements a sophisticated **Agentic RAG** (Retrieval-Augmented Generation) system powered by **LangGraph**, featuring intelligent routing, multi-source retrieval, parallel LLM calls, and context-aware synthesis.

### How It Works

The agentic workflow operates as a state machine with the following stages:

#### 1. **Classify Session** (`classify_session_node`)
- **Purpose**: Determines the intent of a new session based on the first query.
- **LLM**: GPT-4o
- **Modes**:
  - `RAG`: History Search / Context Dependent (triggers full pipeline)
  - `NO_RAG`: New Knowledge / General Assistance (bypasses retrieval for speed)
- **Persistence**: Remembers classification for the duration of the session.

#### 2. **Route Query** (`route_query_node`)
- **Purpose**: Intelligently decides whether the query requires context retrieval
- **LLM**: GPT-4o at temperature 0.1 (for consistent reasoning)
- **Logic**: 
  - Analyzes the user's query to determine if it needs historical context
  - Automatically forces retrieval for multi-turn conversations to maintain context
  - Outputs: `should_retrieve` decision flag

#### 3. **Retrieve Context** (`retrieve_context_node`)
- **Purpose**: Gathers relevant information from three parallel sources
- **No LLM used** — Pure data retrieval for speed and cost efficiency
- **Sources**:
  1. **Semantic Search** (Qdrant) — Vector similarity search on stored knowledge
  2. **User Memories** (PostgreSQL) — Past Q&A from `prompt_logs` table across all sessions
  3. **Session History** (PostgreSQL) — Recent messages from the current conversation
- **Smart Filtering**: 
  - Removes low-value responses ("I don't have information about...")
  - Deduplicates context to avoid redundancy
  - Limits to top results per source

#### 4. **Refine Query** (`refine_query_node`) — Optional
- **Purpose**: Improves the query if initial retrieval returns insufficient context
- **Trigger**: Activated when `retrieved_context` is empty but iterations remain
- **LLM**: GPT-4o refines the query phrasing
- **Iteration**: Can retry retrieval with refined query (max iterations configurable)

#### 5. **Call LLMs** (`call_llms_node`)
- **Purpose**: Parallel fan-out to multiple LLM providers with injected context
- **Models**: OpenAI (`OPENAI_MODEL`, default `gpt-5-mini`), Gemini (`GEMINI_MODEL`, default `gemini-2.0-flash-exp`), Grok (`grok-2-vision-1212`)
- **Context Injection**: 
  - Retrieved context formatted into a structured prompt
  - Session history included for conversational coherence
  - Each model receives **identical context** for consistent comparison
- **Execution**: All models called simultaneously via `asyncio.gather()`

#### 6. **Generate Answer** (`generate_answer_node`)
- **Purpose**: Synthesizes a final answer from all model responses
- **LLM**: GPT-4o as the synthesis engine
- **Input**:
  - Retrieved context (vector search + memories + history)
  - Individual answers from all LLMs (OpenAI, Gemini, Grok)
  - Full conversation history
- **Output**: Coherent, context-aware final answer.

### State Management

The workflow uses **LangGraph's StateGraph** with typed state (`ConversationState`):

```python
{
  "session_id": str,           # Current conversation session
  "user_id": str,              # User identifier
  "session_mode": str,         # "RAG" or "NO_RAG" classification
  "current_query": str,        # User's question (can be refined)
  "messages": List[dict],      # Full conversation history
  "should_retrieve": bool,     # Routing decision
  "retrieved_context": List,   # Context from 3 sources
  "selected_models": List,     # Which LLMs to call
  "llm_answers": Dict,         # Individual model responses
  "llm_errors": Dict,          # Error tracking per model
  "final_answer": str,         # Synthesized response
  "agent_thoughts": List,      # Debugging/transparency log
  "iteration_count": int,      # Current iteration
  "max_iterations": int        # Iteration limit (default: 3)
}
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Session Classification** | Distinguishes between historical search vs general requests on first query |
| **Conditional Routing** | Not all queries need retrieval—simple questions go straight to answer generation |
| **Triple-Source Retrieval** | Combines semantic search, cross-session memories, and session history |
| **Parallel LLM Calls** | Calls OpenAI, Gemini, and Grok simultaneously for diverse perspectives |
| **Transparent Logging** | `agent_thoughts` array tracks decision process for debugging |

### Flow Control

The workflow uses **conditional edges** for dynamic routing:

```
START → route_query
         ↓
     [should_retrieve?]
         ↓
    Yes: retrieve_context → [has context?]
                              ↓
                         No: refine_query → retrieve_context (retry)
                         Yes: call_llms
    No: call_llms (direct answer)
         ↓
    generate_answer → END
```

### Why Agentic?

Traditional RAG systems follow a fixed pipeline: retrieve → generate. This **agentic** approach adds:

1. **Intelligence**: Decides when retrieval is necessary
2. **Adaptability**: Refines queries if initial retrieval fails
3. **Redundancy**: Calls multiple LLMs for robustness
4. **Context-Awareness**: Full conversation memory across sessions
5. **Observability**: Explicit state tracking and decision logging

This architecture ensures that answers are not just generated from context, but intelligently orchestrated through a reasoning process that adapts to each query's needs.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- API keys for: OpenAI, Gemini (optional), Grok (optional)
- Notion token (optional, for Notion push feature)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/SecondBrian_AgenticRAG.git
   cd SecondBrian_AgenticRAG
   ```

2. Create `.env` file with your credentials (see `.env.example`).

3. Start all services:
   ```bash
   docker compose up -d
   ```

4. Access the UI at [http://localhost:8000](http://localhost:8000)

### Reset & Debug Mode

Use the provided reset script to perform a clean deployment.
**Note**: This script automatically enables `DEBUG` logging for all containers.

```bash
./reset_and_run.sh
```

---

## API Endpoints

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Create new conversation session |
| `GET` | `/sessions` | List user sessions |
| `POST` | `/sessions/{id}/messages` | Send message (triggers agentic RAG) |
| `GET` | `/sessions/{id}/messages` | Get session message history |
| `DELETE` | `/sessions/{id}` | Delete a session |

### Vector Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/vector/concepts/upsert` | Add/update knowledge entries |
| `POST` | `/vector/concepts/search` | Semantic search |
| `GET` | `/vector/knowledge-graph` | Query knowledge graph |

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/summarize` | Generate smart summary |
| `POST` | `/notion/push` | Push to Notion database |
| `POST` | `/combo` | Summarize + Notion push |
| `POST` | `/analyze-image` | Multi-model vision analysis |

---

## Tools Reference

| Tool | Description |
|------|-------------|
| `semantic_search_tool` | Queries Qdrant for semantically similar content |
| `session_history_tool` | Retrieves messages from current session |
| `user_memories_tool` | Fetches past Q&A from PostgreSQL across all sessions |
| `knowledge_graph_tool` | Explores related concepts via graph traversal |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `LOG_LEVEL` | `INFO` | Global log level (`DEBUG`, `INFO`, etc.) |
| `OPENAI_MODEL` | `gpt-5-mini` | OpenAI model for parallel LLM calls |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp` | Gemini model for parallel LLM calls |
| `GROK_MODEL` | `grok-beta` | Grok model setting (agentic graph currently uses `grok-2-vision-1212`) |
| `AGENTIC_MAX_ITERATIONS` | `2` | Max RAG retrieval retry limit |

---

## Project Structure

```
SecondBrian_AgenticRAG/
├── docker-compose.yml           # Service orchestration
├── reset_and_run.sh             # Clean start + Debug mode
├── docs/
│   ├── architecture.svg         # System architecture diagram
│   ├── workflow.svg             # RAG workflow (incl. Classification)
│   ├── agent-flow.svg           # Detailed agent flow (incl. Classifier)
│   └── agentic-graph.svg        # LangGraph state diagram
└── services/
    ├── init.sql                 # Database schema
    ├── api-service/             # FastAPI + LangGraph
    │   ├── main.py              # API endpoints
    │   ├── agentic/
    │   │   ├── graph.py         # Workflow & Routing logic
    │   │   ├── state.py         # Conversation state
    │   │   ├── tools.py         # RAG tools
    │   │   └── prompts.py       # Session Classification prompts
    │   ├── db/                  # Database operations
    │   ├── tools/               # Summarizer, Notion push
    │   └── auth/                # Authentication middleware
    ├── frontend-service/        # Web UI (Gradio + static)
    └── vector-service/          # Embeddings + Qdrant proxy
```

---

## Roadmap & TODO

### Core Improvements
- [ ] **Image Session Integration**: Apply the session classifier logic to `/analyze-image` queries to maintain context consistency when sessions start with an image.
- [ ] **Advanced Graph Traversal**: Enhance `knowledge_graph_tool` to explore deeper relationships in vector space.

---

## License

MIT
