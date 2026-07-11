# Threadline — Meeting Intelligence Pipeline

Threadline is a production-quality meeting intelligence pipeline that processes meeting transcripts, extracts structured decisions/actions/entities, tracks decision lifecycles across multiple meetings (handling updates, review states, and supersession), flags logical contradictions, and renders an auto-updating executive briefing dashboard.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Threadline System                             │
│                                                                          │
│  ┌────────────────────────────────┐                                      │
│  │       React + TypeScript       │  Upload · Briefing · Graph · Search  │
│  │       Frontend (Vite)          │◄──── SSE (pipeline progress) ────┐   │
│  └──────────────┬─────────────────┘                                  │   │
│                 │ REST + SSE                                          │   │
│  ┌──────────────▼─────────────────────────────────────────────┐      │   │
│  │                   FastAPI Backend  (/backend)               │      │   │
│  │  POST /api/v1/pipeline/run  (SSE stream, stage-by-stage)   │──────┘   │
│  │  GET  /api/v1/briefing                                      │          │
│  │  GET  /api/v1/graph                                         │          │
│  │  POST /api/v1/search                                        │          │
│  │  GET  /api/v1/status                                        │          │
│  └──────────────┬─────────────────────────────────────────────┘          │
│                 │ calls                                                    │
│  ┌──────────────▼─────────────────────────────────────────────┐          │
│  │               threadline/  (core Python package)            │          │
│  │                                                             │          │
│  │  Ingestor ──► Extractor ──► Pipeline ──► BriefingGenerator │          │
│  │                               │                             │          │
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

## 2. Agent Framework Conception

Threadline was designed with modern agent abstractions in mind:
- **Extractor Protocol** serves as a **Google ADK Agent** utilizing structural schemas.
- **Pipeline Orchestrator** plays the role of a **Lyzr Workflow Engine** defining the execution flow.
- **GraphStore** and **VectorStore** act as **Model Context Protocol (MCP)** tool boundaries.
- **BriefingGenerator** serves as a specialized report rendering agent.

For a detailed conceptual mapping and migration paths, see [ARCHITECTURE.md](file:///f:/CHRIST%20UNIVERSITY%20MCA/IV%20Trimester%20/Hackathon/Threadline/ARCHITECTURE.md).

---

## 3. Quickstart Guide

### Prerequisites
- Python 3.9+ installed
- Node.js (v18+) & npm installed
- Docker & Docker Compose (optional, fallback in-memory stores are used automatically if Docker is offline)

### Step 1: Environment Setup
Copy the environment variables template and configure your API keys:
```bash
cp .env.example .env
```
Open `.env` and fill in `OPENAI_API_KEY` (required for Whisper audio transcription and LLM extraction). If no API key is provided, the system falls back to **Mock Mode**, generating realistic mock responses for testing.

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

## 4. Run tests
To run the automated test suite (in-memory mode, zero infrastructure required):
```bash
pytest
```
To run tests including Docker integration tests:
```bash
$env:THREADLINE_INTEGRATION="1"
pytest
```

---

## 5. Live Demo Script (Panel Presentation)

During your presentation, you can demonstrate Threadline's unique ability to track decision lifecycles across meetings:

1. **Upload meeting_01.txt (Project Kickoff)**
   - Configures stack: React, FastAPI, Postgres, and Auth0.
   - Statuses are set to `confirmed`.
2. **Upload meeting_02.txt (Sprint review)**
   - Databases switch: Postgres is replaced by MongoDB Atlas.
   - The graph shows `MongoDB` **superseding** `PostgreSQL`.
3. **Upload meeting_03.txt (Security Review)**
   - Auth0 is flagged for GDPR concerns.
   - The Auth0 decision status changes to `under_review` (not superseded).
   - An amber **Contradiction Alert** pops up on the dashboard.
4. **Upload meeting_04.txt (Resolution Call)**
   - Keycloak is confirmed as the new auth provider.
   - Auth0 status transitions to `superseded` by `Keycloak`.
   - The **Contradiction is resolved** and flags clear on the dashboard.
5. **Run Semantic Search**
   - Query *"GDPR compliance"* or *"authentication switch"* to see similarity scoring and source-attributed fact cards from Qdrant.

---

## 6. Graceful Degradation (Demo Insurance)

Threadline degrades gracefully rather than crashing during a live presentation:
- **No Neo4j?** The backend automatically switches to `InMemoryGraphStore`.
- **No Qdrant?** The backend automatically switches to `InMemoryVectorStore` using local sentence-transformers cosine similarity (or hash fallback).
- **No API keys?** The pipeline switches to `MockExtractor`, providing deterministic mock data for the 4 meetings to keep the visual flow intact.
- **Audio failed?** The frontend marks audio uploads as best-effort; transcript `.txt` files remain fully supported offline.
