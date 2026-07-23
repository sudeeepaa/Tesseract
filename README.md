<div align="center">

# 💎 Tesseract (ThreadLine)
### *Enterprise Multi-Agent Meeting Intelligence & Executive Chief of Staff*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.20-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.18-DC2626?style=for-the-badge&logo=qdrant&logoColor=white)](https://qdrant.tech)
[![Lyzr Studio](https://img.shields.io/badge/Lyzr_Studio-Primary_Orchestrator-7C3AED?style=for-the-badge)](https://lyzr.ai)
[![Google ADK](https://img.shields.io/badge/Google_ADK-A2A_Protocol-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://google.ai)

<p align="center">
  <b>Tesseract is an enterprise-grade AI Chief of Staff platform that does not just transcribe meetings into dead text — it UNDERSTANDS decision lifecycles, TRACKS cross-meeting supersession chains, and REMEMBERS organizational context.</b>
</p>

[Explore Overview](#-key-features) • [System Architecture](#-system-architecture) • [Getting Started](#-getting-started) • [API Reference](#-api-reference)

---

</div>

## 📌 Executive Summary

Existing AI tools like Otter.ai, Fireflies, or Zoom AI transcribe meetings into isolated walls of text. They treat every meeting as an island, failing to answer critical questions:
* *What was actually decided?*
* *Did today's decision contradict a decision made 3 weeks ago?*
* *Is that architectural choice still valid, or was it superseded?*

**Tesseract solves this by building a persistent, multi-agent organizational memory.** It combines **Neo4j Knowledge Graphs** (for tracking decision evolution) with **Qdrant Vector Storage** (for natural language semantic memory), coordinated by a **Lyzr Studio & Google ADK multi-agent fleet**.

---

## ✨ Key Features

### 🔄 1. Cross-Meeting Decision Lifecycle Tracking
Decisions are modeled as stateful entities with a formal lifecycle:
`proposed → confirmed → under_review → superseded`
* Automatically creates `SUPERSEDES` links when a new meeting replaces a previous decision.
* Maintains a full lineage audit trail so no historical rationale is lost.

### ⚔️ 2. Contradiction & Conflict Resolution Engine
* Automatically cross-references newly extracted claims against prior decisions.
* Detects logical conflicts (e.g., Auth0 vs. EU Data Residency regulations) with confidence scores and reasoning traces.
* Provides a human-in-the-loop **"Keep / Switch / Flag"** resolution dashboard.

### 🧠 3. Dual Graph & Vector Memory
* **Neo4j Knowledge Graph:** Maps entities, decisions, action items, and topic relationships as connected graph nodes.
* **Qdrant Vector Index:** Embeds extracted facts into 384-dimensional space via `all-MiniLM-L6-v2` or `Gemini Embeddings` for fast similarity search.

### 🛡️ 4. GDPR Article 17 Cascading Purge
* Implements a compliance engine (`DELETE /api/v1/governance/purge/{name}`) to scrub speaker identity metadata across Qdrant vector points and Neo4j graph nodes without corrupting decision records.

### ⚡ 5. Zero-Dependency Graceful Degradation
* Automatically falls back to `InMemoryGraphStore` and `InMemoryVectorStore` (with deterministic hash embeddings) if Neo4j or Qdrant cloud services are unreachable, ensuring 100% demo availability.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Frontend ["Frontend (Vite / React 18 / TypeScript)"]
        UI["Notion-Style Command Center UI"]
        D3["D3-Force Relationship Graph"]
        SSE_Client["SSE Live Stream Listener"]
    end

    subgraph Backend ["FastAPI Parent Application"]
        API["REST & SSE Endpoints (/api/v1/*)"]
        
        subgraph Agents ["6 Specialized AI Agents (A2A Protocol /a2a/*)"]
            Manager["Manager Agent (Lyzr Primary / ADK Fallback)"]
            Input["Input Agent (Gemini Audio / Whisper)"]
            Extract["Extraction Agent (LangGraph + Gemini / GPT-4o-mini)"]
            GraphWriter["Graph Writer Agent (MCP Tools)"]
            Memory["Semantic Memory Agent (MCP Tools)"]
            Briefing["Briefing Agent (Template Engine)"]
        end

        subgraph MCP ["MCP Tool Layer (JSON-RPC Boundaries)"]
            GraphMCP["Graph MCP Tools"]
            VectorMCP["Vector MCP Tools"]
        end
    end

    subgraph Storage ["Persistent Dual-Storage Layer"]
        Neo4j[("Neo4j 5.20 Graph Database")]
        Qdrant[("Qdrant v1.18 Vector Index")]
        InMem[("In-Memory Fallback Stores")]
    end

    UI -->|REST / SSE| API
    API --> Manager
    Manager --> Input
    Input --> Extract
    Extract --> GraphWriter
    Extract --> Memory
    Manager --> Briefing

    GraphWriter -->|Cypher Queries| GraphMCP
    Memory -->|Embeddings| VectorMCP
    
    GraphMCP --> Neo4j
    GraphMCP -.-> InMem
    VectorMCP --> Qdrant
    VectorMCP -.-> InMem
```

---

## 🤖 AI Agent Workflow

| Agent | Core Responsibility | Primary Engine | Fallback Engine |
|---|---|---|---|
| 👑 **Manager Agent** | Orchestrates full meeting processing pipeline | Lyzr Studio API | Google ADK `RemoteA2aAgent` |
| 📥 **Input Agent** | Ingests text files & transcribes audio files | Gemini Flash Multimodal Audio | OpenAI Whisper API (`whisper-1`) |
| 🧠 **Extraction Agent** | Structured JSON fact & conflict extraction | LangGraph + Gemini Flash Lite | OpenAI `gpt-4o-mini` |
| ✍️ **Graph Writer Agent** | Persists decisions, entities & supersessions to Neo4j | Graph MCP Tools | InMemoryGraphStore |
| 🔍 **Semantic Memory Agent**| Vector-indexes facts & claims for search | Qdrant Vector MCP | InMemoryVectorStore (Hash) |
| 📄 **Briefing Agent** | Generates executive summaries & conflict alerts | Jinja2 / Markdown Template | Static Executive Summarizer |

---

## 🛠 Technology Stack

* **Frontend:** React 18, TypeScript, Vite, React Router v6, D3-Force Graph (`react-force-graph-2d`), Lucide Icons, `react-dropzone`.
* **Backend:** FastAPI, Uvicorn, Pydantic v2 (`pydantic-settings`), Python 3.11, `python-multipart`, SSE Streaming.
* **AI & Agent Frameworks:** Lyzr Studio API, Google ADK (`google-adk[a2a]`), LangGraph, OpenAI SDK, Google Generative AI SDK.
* **Databases:** Neo4j 5.20 (Knowledge Graph), Qdrant v1.18 (Vector DB), In-Memory Stubs.
* **Embeddings:** `models/gemini-embedding-001` (768-dim), Hash-based fallback.
* **Deployment:** Vercel (Frontend), Render (FastAPI Backend), Docker Compose (Local Dev DBs).

---

## ⚖️ License & Acknowledgments

Built for hackathon demonstration with production-grade architecture patterns.
