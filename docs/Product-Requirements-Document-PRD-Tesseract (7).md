# Product Requirements Document (PRD): Tesseract

## 1. Executive Summary
Tesseract is an enterprise-grade, agentic knowledge management system designed to transform raw organizational communication (audio and text) into a persistent, evolving "corporate brain." By leveraging a multi-agent orchestration layer, Tesseract extracts entities, relationships, and semantic context, storing them in a hybrid Knowledge Graph and Vector database. The system provides automated briefings, contradiction detection, and explainable decision-making to ensure organizational alignment.

## 2. Problem Statement
Organizations lose critical institutional knowledge in the "noise" of daily meetings and fragmented transcripts. Existing tools provide simple summaries but fail to track how decisions evolve over time, identify contradictions between past and present statements, or provide a structured, queryable memory of organizational logic.

## 3. Goals & Objectives
*   **Persistent Memory:** Create a self-updating knowledge base that tracks entities and their relationships over time.
*   **Automated Synthesis:** Generate high-context briefings that reconcile new information with existing records.
*   **Enterprise Accountability:** Ensure all automated extractions and flags are explainable, auditable, and secure.
*   **Operational Efficiency:** Decouple heavy processing (transcription/extraction) from user interaction via asynchronous workflows.

## 4. Target Users / Stakeholders
*   **Executive Leadership:** For high-level briefings and tracking project evolution.
*   **Project Managers:** To identify contradictions in project requirements or stale action items.
*   **Data Governance Officers:** To ensure compliance with data retention and privacy regulations.
*   **Technical Architects:** To monitor system health and agentic performance.

## 5. Functional Requirements
*   **FR-101: Multi-Modal Ingestion:** Support for raw audio (WAV/MP3/M4A) and text transcripts (JSON/Markdown).
*   **FR-102: Automated Transcription:** Convert raw audio into normalized text transcripts using Gemini 1.5 Pro.
*   **FR-103: Entity & Relationship Extraction:** Identify people, decisions, action items, and projects from transcripts.
*   **FR-104: Knowledge Graph Construction:** Map extracted entities into Neo4j using "owns," "part-of," and "supersedes" relationships.
*   **FR-105: Semantic Memory Storage:** Store high-dimensional vector embeddings of discussion content for meaning-based recall.
*   **FR-106: Hybrid Retrieval:** Combine graph-based traversal with vector-based search to generate context for briefings.
*   **FR-107: Automated Briefing Generation:** Produce synthesized reports on specific topics or timeframes.
*   **FR-108: Interactive Visualization:** Provide a live graph panel (Bloom) for users to explore organizational relationships.
*   **FR-109: Explainability & Confidence:** The Graph Writer Agent and Briefing Agent must output a structured reasoning chain (chain-of-thought) and a numeric confidence score (0.0–1.0) alongside every contradiction flag and stale-item flag generated.

## 6. Non-Functional Requirements
*   **NFR-201: Performance:** Transcription and initial extraction for a 60-minute meeting must complete within 5 minutes.
*   **NFR-202: Scalability:** Support concurrent processing of up to 50 ingestion tasks via asynchronous queuing.
*   **NFR-203: Reliability:** 99.9% uptime for the API Gateway and Data Layer.
*   **NFR-204: Security:** All data in transit must use TLS 1.3; all data at rest must be encrypted via KMS.
*   **NFR-205: Observability:** Full request tracing via Correlation IDs across the 7-layer pipeline using OpenTelemetry and Langfuse.
*   **NFR-206: Data Retention:** Enforce a 30-day retention policy on raw audio files; provide a purge API for GDPR compliance.
*   **NFR-207: Explainability/Auditability:** All automated contradiction/stale-item decisions must be auditable via a stored reasoning trace and confidence score, retrievable via the API for compliance review.

## 7. Requirements Traceability Matrix

| Requirement ID | Description | Architectural Component | Verification Method |
| :--- | :--- | :--- | :--- |
| **FR-101** | Multi-Modal Ingestion | Input Handling Agent | Integration Test |
| **FR-102** | Automated Transcription | Input Handling Agent | Manual Review |
| **FR-103** | Entity Extraction | Extraction Agent | Unit Test |
| **FR-104** | Graph Construction | Graph Writer Agent / Neo4j | Integration Test |
| **FR-105** | Semantic Memory | Semantic Memory Agent / Qdrant | Integration Test |
| **FR-106** | Hybrid Retrieval | Briefing Agent | Manual Review |
| **FR-107** | Briefing Generation | Briefing Agent | Manual Review |
| **FR-108** | Graph Visualization | React Web App / Neo4j Bloom | Manual Review |
| **FR-109** | Explainability Output | Graph Writer / Briefing Agent | Manual Review |
| **NFR-201** | Latency | Task Queue / Lyzr Manager | Load Test |
| **NFR-202** | Scalability | AWS SQS / ECS | Load Test |
| **NFR-203** | Reliability | API Gateway / AWS Infrastructure | Load Test |
| **NFR-204** | Security | API Gateway / Secrets Manager | Security Audit |
| **NFR-205** | Observability | Observability Layer (Langfuse) | Integration Test |
| **NFR-206** | Data Retention | Data Governance Service | Security Audit |
| **NFR-207** | Auditability | Data Governance Service | Manual Review |

## 8. System Architecture Overview
Tesseract is organized into seven functional layers:
1.  **Input Sources:** Raw audio and text transcripts.
2.  **API Edge Layer:** API Gateway managing authentication and rate limiting.
3.  **Async Ingestion Layer:** Input Handling Agent and Task Queue (SQS) for decoupling.
4.  **Agent Orchestration Layer:** Lyzr Manager Agent coordinating Extraction, Graph Writer, Semantic Memory, and Briefing Agents.
5.  **Enterprise Data Layer:** Neo4j (Knowledge Graph) and Qdrant (Vector Memory).
6.  **Presentation Layer:** React Web App for visualization and briefings.
7.  **Enterprise Support Layer:**
    *   **Observability Layer:** Traces latency and token usage via OpenTelemetry/Langfuse.
    *   **Data Governance Service:** Manages GDPR compliance, retention, and purge APIs.
    *   **Secrets Manager:** Centralized encryption and credential management (AWS Secrets Manager).
    *   **API Gateway:** Routes requests and enforces OAuth2/JWT.
    *   **Task Queue:** Decouples ingestion from orchestration to prevent pipeline blocking.

## 9. Tech Stack
*   **LLM/AI:** Gemini 1.5 Pro, Google ADK, Lyzr SDK, LangGraph.
*   **Backend:** Python, A2A Protocol, MCP Protocol.
*   **Databases:** Neo4j AuraDB (Cypher, Bloom), Qdrant (HNSW Vector Search).
*   **Infrastructure:** AWS SQS, AWS Secrets Manager, Docker, OpenTelemetry, Langfuse.
*   **Frontend:** React, Tailwind CSS, Vite.

## 10. Data Requirements
*   **Graph Model:** Nodes (Person, Decision, Project, ActionItem) and Edges (OWNS, PART_OF, SUPERSEDES).
*   **Vector Model:** 1536-dimensional embeddings of transcript segments with metadata (timestamp, speaker, meeting_id).
*   **Retention:** Raw audio purged after 30 days; structured graph data persisted indefinitely unless a purge request is received.

## 11. API Specifications
*   `POST /v1/ingest`: Upload audio/text; returns a `correlation_id`.
*   `GET /v1/briefing/{topic}`: Retrieve synthesized briefing with reasoning traces.
*   `GET /v1/audit/decisions`: Retrieve log of contradiction flags and confidence scores.
*   `DELETE /v1/governance/purge/{user_id}`: GDPR-compliant erasure across Neo4j and Qdrant.

## 12. Prompt Engineering Specification

### 12.1 Input Handling Agent
*   **Capacity:** An expert transcriptionist and data normalizer specializing in multi-modal meeting data.
*   **Role:** Receives raw audio or text; produces a cleaned, speaker-diarized, and timestamped JSON transcript.
*   **Insight:** Knowledge of common corporate jargon and the specific audio quality constraints of the Tesseract pipeline.
*   **Statement:** Transcribe the input audio or normalize the input text into a standardized schema, ensuring speaker labels are consistent.
*   **Personality:** Precise and literal—do not summarize or omit "filler" words that might contain sentiment.
*   **Experiment:** If audio confidence is low, flag specific segments for human review rather than guessing the transcript.

### 12.2 Extraction Agent
*   **Capacity:** A meticulous business analyst trained in identifying organizational entities and commitments.
*   **Role:** Receives a normalized transcript; produces a structured list of people, projects, decisions, and action items.
*   **Insight:** Context of existing project names and organizational hierarchy to ensure entity resolution.
*   **Statement:** Extract all unique entities and explicit decisions from the transcript, mapping them to the standard Tesseract schema.
*   **Personality:** Analytical and objective—only extract what is explicitly stated, avoiding inference.
*   **Experiment:** Run a secondary pass to check for "implied" action items and label them with a "suggested" status.

### 12.3 Graph Writer Agent
*   **Capacity:** A senior database architect and logic specialist expert in Cypher and graph theory.
*   **Role:** Receives extracted entities; produces Cypher queries to update the Knowledge Graph.
*   **Insight:** Access to the current graph schema and existing node relationships to identify potential conflicts.
*   **Statement:** Generate Cypher commands to upsert nodes and edges, specifically looking for "supersedes" relationships where new info replaces old.
*   **Personality:** Conservative—flag uncertain relationships or potential contradictions rather than overwriting data.
*   **Experiment:** When flagging a contradiction, attach a 2-3 sentence reasoning trace explaining the conflict and a confidence score; escalate if score < 0.6.

### 12.4 Semantic Memory Agent
*   **Capacity:** A retrieval-augmented generation (RAG) specialist focused on high-dimensional semantic indexing.
*   **Role:** Receives transcript segments; produces vector embeddings and metadata for storage in Qdrant.
*   **Insight:** Understanding of the MCP protocol and vector injection protection standards.
*   **Statement:** Convert transcript chunks into vectors, ensuring metadata includes meeting IDs and temporal markers for accurate recall.
*   **Personality:** Deterministic—ensure consistent embedding generation with no creative embellishment of the source text.
*   **Experiment:** Compare current embeddings against the most recent 5 meetings to identify semantic drift in project discussions.

### 12.5 Briefing Agent
*   **Capacity:** A high-level executive assistant and strategic synthesizer.
*   **Role:** Receives hybrid data from Neo4j and Qdrant; produces a synthesized briefing for the end-user.
*   **Insight:** Prior meeting history and the current state of the Knowledge Graph to provide longitudinal context.
*   **Statement:** Synthesize a briefing that highlights new decisions, updates project statuses, and flags any stale or contradictory information.
*   **Personality:** Professional and concise—prioritize actionable insights over exhaustive detail.
*   **Experiment:** When flagging stale items, attach a 2-3 sentence reasoning trace and confidence score; escalate if score < 0.6.

## 13. Security Requirements
*   **Authentication:** API Gateway enforcing OAuth2/JWT authentication and strict rate limiting.
*   **Injection Protection:** Cypher injection protection on the Graph Writer Agent's input validation; Vector injection protection for Semantic Memory.
*   **Compliance:** GDPR Article 13/14 compliance via the Data Governance Service (retention policy + purge API).
*   **Secrets Management:** All credentials managed via AWS Secrets Manager/Vault; no hardcoded keys in the codebase.

## 14. Deployment & Infrastructure
*   **Methodology:** Adherence to 12-Factor App principles:
    *   **Config:** All environment-specific configuration must be injected via environment variables sourced from AWS Secrets Manager.
    *   **Stateless Processes:** All agent containers must be stateless; all state persists in Neo4j, Qdrant, or SQS.
    *   **Dependencies:** Explicitly declared via `pyproject.toml` with no reliance on system-wide packages.
    *   **Disposability:** Support fast startup and graceful shutdown; tasks are re-queued via SQS on failure.
    *   **Dev/Prod Parity:** Docker Compose used locally to mirror the production ECS/EKS environment.
*   **Orchestration:** Containerized services deployed via AWS ECS or EKS.
*   **CI/CD:** Automated pipeline for unit testing, integration testing, and security scanning.

## 15. Success Metrics
*   **Extraction Accuracy:** >90% accuracy in entity and relationship extraction (verified by manual review).
*   **System Latency:** End-to-end processing under 5 minutes for standard meeting lengths.
*   **User Adoption:** Number of briefings generated and graph queries executed per week.
*   **Explainability Trust:** <5% escalation rate for automated contradiction flags.

## 16. Timeline & Milestones
*   **Phase 1 (MVP):** Ingestion, Transcription, and basic Graph Writing.
*   **Phase 2:** Semantic Memory integration and Hybrid Retrieval.
*   **Phase 3:** Enterprise Support Layer (Observability, Governance, Secrets).
*   **Phase 4:** Explainability features and 12-Factor App optimization.

## 17. Open Questions & Risks
*   **Risk:** High token usage costs for Gemini 1.5 Pro during heavy ingestion.
*   **Question:** Should the purge API support "soft deletes" for a recovery window before permanent erasure?
*   **Risk:** Complexity of resolving entities across different speakers who use different terminology for the same project.