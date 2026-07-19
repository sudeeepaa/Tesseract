# Tesseract (formerly Threadline) — Conceptual Agent Architecture

This document provides a technical mapping of Tesseract's Clean Architecture design onto modern agent framework architectures (specifically Google ADK, Lyzr, Model Context Protocol (MCP), and Agent-to-Agent (A2A) communication).

---

> [!IMPORTANT]
> **SCOPE & ARCHITECTURE NOTE: Demo-Safe vs Enterprise Target**
> Tesseract maps its production-grade design constructs directly onto in-process execution contexts to avoid dependency/network failures during a live demonstration:
> 1. **Zero-Trust Network Boundary (A2A Sub-mounts)**: Agents run as distinct ASGI sub-applications mounted directly under the FastAPI parent process. This satisfies the Agent-to-Agent (A2A) network contract and routing layer while running reliably inside a single operating system process.
> 2. **Orchestrator Hybrid Strategy**: The Manager Agent leverages **Lyzr Studio** (primary) for enterprise workflow execution and falls back gracefully to a localized **Google ADK RemoteA2aAgent** runner if API connectivity is unavailable.
> 3. **Explainability & Security Boundaries**:
>    - **Contradiction/Stale Reasoning**: Employs the CRISPE "Experiment" clause. All contradiction/conflict records and stale action items include a confidence score (float) and a 2-3 sentence reasoning trace.
>    - **Injection Protection**: Sanitizes name fields against Cypher injection syntax and disarms unsafe Cypher keywords before any write transaction in the Graph and Vector stores.
>    - **GDPR Article 17 Purge API**: Implements `DELETE /api/v1/governance/purge/{name}`, executing a cascading delete of the person's entity node and relationships in Neo4j, while clearing their assignee/owner status from all Decisions, Action Items, and semantic vector points.

---

## 1. Architectural Concept Mapping

Although built on native Python Protocol definitions to maximize runtime safety and eliminate latency during a live judging presentation, Threadline was designed from first principles around modular agent patterns. The mapping is direct:

```
                  ┌────────────────────────────────────────────────────────┐
                  │                      Lyzr Flow                         │
                  │             (Pipeline Orchestration Class)             │
                  └───────────┬────────────────────────────────┬───────────┘
                              │ calls                          │ calls
                              ▼                                ▼
                  ┌──────────────────────┐         ┌──────────────────────┐
                  │      ADK Agent       │         │      ADK Agent       │
                  │  (Extractor Protocol)│         │ (Briefing Generator) │
                  └───────────┬──────────┘         └───────────┬──────────┘
                              │ uses                           │ query
                              ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Model Context Protocol (MCP)                   │
├─────────────────────────────┬───────────────────────────────────────────┤
│    MCP Tool: Graph Store    │         MCP Tool: Vector Store            │
│  (Neo4jGraphStore class)    │       (QdrantVectorStore class)           │
└─────────────────────────────┴───────────────────────────────────────────┘
```

| Threadline Component | Agent Framework Equivalent | Description |
| :--- | :--- | :--- |
| **`Extractor` Protocol** | **Google ADK Agent** | A specialized LLM agent configured with a strict system prompt (system instructions) and output schemas to parse meeting structure. |
| **`Pipeline` Orchestrator** | **Lyzr Workflow Engine** | A sequencing engine that coordinates stage-by-stage execution, handles state passing, and controls execution flow. |
| **`GraphStore` Protocol** | **MCP Tool (Database)** | A tool interface enabling an agent to store relational structured claims, link nodes, and traverse relationships (supersession chains). |
| **`VectorStore` Protocol** | **MCP Tool (Semantic Index)** | A tool interface enabling an agent to project claims into semantic vector space and execute similarity searches. |
| **`BriefingGenerator`** | **Briefing Agent** | An agent that receives current factual state and compiles a human-readable executive summary. |

---

## 2. Deep Dive: Google ADK Agent Mapping

In **Google ADK (Agent Development Kit)**, an agent is defined by its:
1. **System Instructions** (Role & Persona)
2. **Input/Output Schemas** (JSON/Pydantic validation)
3. **Registered Tools** (MCP tools or local functions)

Here is how our native `threadline/extractor.py` matches the ADK agent schema:

```python
# Threadline Native Implementation
class Extractor(Protocol):
    def extract(self, transcript: MeetingTranscript, existing_decisions: list[Decision]) -> ExtractionResult:
        ...
```

To migrate this directly to a Google ADK Agent post-hackathon, the wrapping code is a direct mapping:

```python
from google_adk import Agent, ModelType

# Extractor wraps cleanly as an ADK Agent
extractor_agent = Agent(
    name="Meeting Fact Extractor",
    model=ModelType.GEMINI_1_5_FLASH,
    system_instructions="You are an expert meeting analyst...",
    input_schema=MeetingTranscript,
    output_schema=ExtractionResult,
    tools=[read_prior_decisions_tool] # mapped from GraphStore.get_all_decisions
)
```

---

## 3. Deep Dive: Model Context Protocol (MCP) Tool Integration

The **Model Context Protocol** defines a client-server boundary allowing LLMs to safely query data stores. 
In Threadline, the **`GraphStore`** and **`VectorStore`** interfaces sit exactly at this boundary. 

If this application were deployed as a distributed agent fleet, the `GraphStore` and `VectorStore` would run as **MCP Servers**. The `Extractor` Agent (MCP Client) would call them through standardized JSON-RPC schemas:

```json
// Example MCP Tool Schema for GraphStore.detect_contradictions
{
  "name": "detect_contradictions",
  "description": "Query the Neo4j knowledge graph for facts contradicting the newly extracted claims",
  "input_schema": {
    "type": "object",
    "properties": {
      "result": { "$ref": "#/definitions/ExtractionResult" }
    },
    "required": ["result"]
  }
}
```

---

## 4. Agent-to-Agent (A2A) Communication Model

In a production deployment, the transition from **Extraction** to **Briefing** represents an asynchronous Agent-to-Agent (A2A) message passing loop.

1. **Extractor Agent** completes fact extraction.
2. **Extractor Agent** publishes a structured message (`ExtractionResult`) to the event bus.
3. **Briefing Agent** subscribes to this message, queries the **MCP Database Tool** for historical context, and updates the briefing.

Threadline implements this passing flow synchronously inside `threadline/pipeline.py` using Pydantic schemas, guaranteeing type-safety and structural compatibility for direct A2A event migration.

---

## 5. Architectural Trade-offs for the Demo

| Decision | Production Target | Demo Choice (July 18) | Rationale |
| :--- | :--- | :--- | :--- |
| **Frameworks** | Lyzr + Google ADK | Protocol-based DI | Eliminates framework bootstrapping overhead, guarantees sub-second startup, and ensures zero runtime exceptions due to framework wrapper issues during live presentation. |
| **Network API** | Distributed MCP Server | In-Process Factory | Single-process runtime means zero port conflicts or localhost handshake issues on the demo machine. |
| **Databases** | Neo4j Aura + Qdrant Cloud | Local Docker + Memory Fallback | In-memory storage fallback ensures the web app runs perfectly and generates briefings even if local Docker daemon fails. |
