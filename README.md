# Tesseract (formerly Threadline) — Meeting Intelligence Pipeline

Tesseract is a production-quality meeting intelligence pipeline that processes meeting transcripts, extracts structured decisions/actions/entities, tracks decision lifecycles across multiple meetings (handling updates, review states, and supersession), flags logical contradictions, and renders an auto-updating executive briefing dashboard.

---

> [!IMPORTANT]
> **SCOPE & ARCHITECTURE NOTE: Demo-Safe vs Enterprise Target**
> This repository is configured to prioritize **lightweight, demo-safe reliability** while fully satisfying all **enterprise-grade compliance contracts**. 
> - **Orchestration Layer**: Uses a hybrid approach with **Lyzr Studio** (primary) and an in-process **Google ADK RemoteA2aAgent** runner fallback. In testing or offline environments, it runs entirely in-process to guarantee a crash-free presentation.
> - **Agent Isolation (A2A)**: Rather than running five distinct microservices (each with its own deployment and handshake failures), all agents (Input, Extraction, Graph Writer, Semantic Memory, Briefing, Manager) are deployed as **ASGI sub-apps** mounted directly under the main FastAPI parent process, communicating via A2A protocol semantic paths.
> - **Database Fallbacks**: Automatically degrades to `InMemoryGraphStore` and `InMemoryVectorStore` (utilizing deterministic hash-based mock embeddings) if Neo4j or Qdrant Docker containers are offline.
> - **Explainability & Security**: Employs parameterized Neo4j Cypher query disarming, input validation sanitizers, a cascaded GDPR purge engine, and confidence score reasoning traces for all contradiction and stale-item flags.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Tesseract System                             │
│                                                                          │
│  ┌────────────────────────────────┐                                      │
│  │       React + TypeScript       │  Upload · Briefing · Graph · Search  │
│  │       Frontend (Vite)          │◄──── SSE (pipeline progress) ────┐   │
│  └──────────────┬─────────────────┘                                  │   │
│                 │ REST + SSE                                          │   │
│  ┌──────────────▼─────────────────────────────────────────────┐      │   │
│  │                   FastAPI Backend  (/backend)               │      │   │
│  │  POST /api/v1/pipeline/run  (starts processing)            │──────┘   │
│  │  GET  /api/v1/pipeline/status/{id} (polls audio jobs)       │          │
│  │  GET  /api/v1/briefing                                      │          │
│  │  GET  /api/v1/graph                                         │          │
│  │  POST /api/v1/search                                        │          │
│  │  GET  /api/v1/health                                        │          │
│  │  DELETE /api/v1/governance/purge/{name} (GDPR Purge)        │          │
│  └──────────────┬─────────────────────────────────────────────┘          │
│                 │ dispatches to                                            │
│  ┌──────────────▼─────────────────────────────────────────────┐          │
│  │               tesseract/  (core Python package)            │          │
│  │                                                             │          │
│  │  A2A Sub-mounts:                                            │          │
│  │  - /a2a/input            - /a2a/graph-writer                │          │
│  │  - /a2a/extraction       - /a2a/semantic-memory             │          │
│  │  - /a2a/briefing         - /a2a/manager                     │          │
│  │                                                             │          │
│  │                    ┌──────────┴──────────┐                 │          │
│  │                    ▼                      ▼                 │          │
│  │             GraphStore              VectorStore             │          │
│  │          (Neo4j / InMemory)      (Qdrant / InMemory)       │          │
│  └─────────────────────────────────────────────────────────────┘          │
│                                                                            │
│  ┌──────────────────────────┐  ┌──────────────────────────┐                │
│  │  Neo4j  (Docker :7687)   │  │  Qdrant (Docker :6333)   │                │
│  └──────────────────────────┘  └──────────────────────────┘                │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Framework Setup

Tesseract is built using real agent abstractions:
- **Input Handling Agent** ([input_agent.py](file:///c:/SattyGithub/ThreadLine/threadline/agents/input_agent.py)): Handles transcript reading and multimodal Gemini-based audio transcription.
- **Extraction Agent** ([extraction_agent.py](file:///c:/SattyGithub/ThreadLine/threadline/agents/extraction_agent.py)): Leverages a minimal LangGraph state graph with a 3× retry loop to extract entities, decisions, and conflicts.
- **Graph Writer Agent** ([graph_writer_agent.py](file:///c:/SattyGithub/ThreadLine/threadline/agents/graph_writer_agent.py)): Saves extracted structured data into the Neo4j Graph Store using custom MCP tool wrappers.
- **Semantic Memory Agent** ([semantic_memory_agent.py](file:///c:/SattyGithub/ThreadLine/threadline/agents/semantic_memory_agent.py)): Embeds and indexes claims in the Qdrant Vector Store.
- **Briefing Agent** ([briefing_agent.py](file:///c:/SattyGithub/ThreadLine/threadline/agents/briefing_agent.py)): Compiles the historical state into a comprehensive Markdown briefing.
- **Manager Agent** ([manager_agent.py](file:///c:/SattyGithub/ThreadLine/threadline/agents/manager_agent.py)): A hybrid client coordinator that uses **Lyzr Studio** (primary) for orchestration and falls back to **Google ADK RemoteA2aAgent** running locally when Lyzr is unreachable.

---

## 3. Quickstart Guide

### Prerequisites
- Python 3.9+ installed
- Node.js (v18+) & npm installed
- Docker & Docker Compose (optional; fallback in-memory stores are used automatically if Docker is offline)

### Step 1: Environment Setup
Copy the environment variables template and configure your API keys:
```bash
cp .env.example .env
```
Open `.env` and fill in the values. See below for detailed instructions on obtaining key credentials.

### Step 2: Spin up Databases (Optional)
If Docker is installed and running:
```bash
docker-compose up -d
```
This spins up **Neo4j** (Bolt: port 7687, Browser UI: port 7474) and **Qdrant** (API: port 6333) with persistent volumes.

### Step 3: Run FastAPI Backend
Install python dependencies and start the local FastAPI web server:
```bash
pip install -e ".[dev]"
uvicorn backend.main:app --reload --port 8000
```
The API documentation is accessible at `http://localhost:8000/docs`.

### Step 4: Run React Frontend
Navigate to the `frontend` directory, install dependencies, and start Vite development server:
```bash
cd frontend
npm install
npm run dev
```
Open your browser and navigate to `http://localhost:5173`.

---

## 4. How to Obtain Environment Variables

### A. LLM & Extraction Keys
*   `EXTRACTOR_BACKEND`: `openai` to use GPT models, `gemini` to use Google models, or `mock` to run offline without spending credentials.
*   `OPENAI_API_KEY`: 
    1. Log in to the [OpenAI Platform](https://platform.openai.com/).
    2. Go to **API Keys** -> **Create new secret key**.
*   `GEMINI_API_KEY`:
    1. Log in to [Google AI Studio](https://aistudio.google.com/).
    2. Click **Get API Key** -> **Create API Key**.

### B. Neo4j Graph Store Credentials
*   `GRAPH_BACKEND`: Set to `neo4j` (or `memory` for offline mock mode).
*   `NEO4J_URI`: Binds to `bolt://localhost:7687` for local Docker setups. For Neo4j Aura (cloud), paste your instance's `neo4j+s://...` URI.
*   `NEO4J_USER` / `NEO4J_PASSWORD`: Local defaults are `neo4j` and `threadline_dev`. For Aura, use the credentials provided upon database creation.

### C. Qdrant Vector Store Credentials
*   `VECTOR_BACKEND`: Set to `qdrant` (or `memory` for offline mock mode).
*   `QDRANT_URL`: Set to `http://localhost:6333` locally. For Qdrant Cloud, copy your cluster endpoint URL.
*   `QDRANT_API_KEY`: Leave blank for local Docker. For Qdrant Cloud, create a key under **API Keys**.

### D. Lyzr Studio Credentials (Manager Agent)
*   `LYZR_API_KEY`: 
    1. Go to [Lyzr Studio Console](https://studio.lyzr.ai/).
    2. Generate an API Key under Account Settings.
*   `LYZR_AGENT_ID`:
    1. Create an orchestrator agent in the Lyzr Studio UI.
    2. Copy the **Agent ID** string from the dashboard.

---

## 5. Running Automated Tests

Tesseract includes a thorough suite of unit and integration tests.

### Running Unit Tests (In-memory, zero credentials needed)
To run the lightweight offline tests:
```bash
pytest -v
```

### Running Live Integration Tests (Requires active credentials/Docker services)
To trigger testing against your live Neo4j, Qdrant, Lyzr Studio, and Gemini API endpoints:
```bash
# Windows PowerShell
$env:THREADLINE_INTEGRATION="1"
pytest -v

# Linux/macOS
THREADLINE_INTEGRATION=1 pytest -v
```

---

## 6. Live Demo Script (Panel Presentation)

During your presentation, you can demonstrate Tesseract's unique ability to track decision lifecycles across meetings:

1. **Upload meeting_01.txt (Project Kickoff)**
   - Configures stack: React, FastAPI, Postgres, and Auth0.
   - Statuses are set to `confirmed`.
2. **Upload meeting_02.txt (Sprint review)**
   - Databases switch: Postgres is replaced by MongoDB Atlas.
   - The graph shows `MongoDB` **superseding** `PostgreSQL`.
3. **Upload meeting_03.txt (Security Review)**
   - Auth0 is flagged for GDPR concerns.
   - The Auth0 decision status changes to `under_review` (not superseded).
   - An amber **Contradiction Alert** pops up on the dashboard showing a confidence score and a detailed reasoning trace explaining the conflict.
4. **Upload meeting_04.txt (Resolution Call)**
   - Keycloak is confirmed as the new auth provider.
   - Auth0 status transitions to `superseded` by `Keycloak`.
   - The **Contradiction is resolved** and flags clear on the dashboard.
5. **GDPR Cascade Purge**
   - Execute a `DELETE /api/v1/governance/purge/Dev Rao`.
   - Show that Dev Rao's metadata speaker references are wiped from vector chunks and graph nodes, while decisions themselves remain intact with owner fields set to null.
