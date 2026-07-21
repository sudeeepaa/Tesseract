# Project Status — Threadline / Tesseract

_Last evaluated: 2026-07-21 · Branch: `refactor` · Evaluator: engineering review of the working tree._

This is the single source of truth for **what actually exists and works** versus
what the marketing docs (`README.md`, `ARCHITECTURE.md`) aspire to. It is written
to be blunt so the team can triage before a demo. Companion roadmap:
[`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

---

## 1. One-paragraph summary

Threadline is a **meeting-intelligence pipeline** that turns raw meeting transcripts
(or audio) into a living, cross-meeting knowledge base: it extracts decisions, action
items, entities and contradictions with an LLM, writes them to a **Neo4j graph** and
**Qdrant vector index**, tracks each decision's lifecycle across meetings (including
the subtle `under_review` → `superseded` transition and contradiction-then-resolution),
and surfaces it as an **auto-updating executive briefing, an interactive graph, and
semantic search** in a React UI. Its defining engineering choice is **graceful
degradation everywhere** — it runs end-to-end with zero external services or API keys,
which makes it demo-proof.

## 2. Progress at a glance

| Layer | Status | Confidence |
| :--- | :--- | :--- |
| Data model (`models.py`) | ✅ Complete | High |
| Config + fallback logic (`config.py`) | ✅ Complete | High |
| Extractor (LLM + Mock) | ✅ Complete | High |
| Graph store (InMemory + Neo4j) | ✅ Complete; **Neo4j verified live** (2026-07-21) | High |
| Vector store (InMemory + Qdrant) | ✅ Complete; **Qdrant verified live** after image bump | High |
| Direct `Pipeline` orchestrator | ✅ Complete | High |
| Agent layer + `AgentPipeline` (Manager/ADK/MCP) | ✅ **Verified live** in ADK fallback (2026-07-21) | Medium-High |
| Lyzr Studio orchestration | ⚠️ Coded, unverified live | Low |
| FastAPI backend + SSE + GDPR purge | ✅ **Smoke-tested live** (2026-07-21) | High |
| **Conflict resolution (human-in-the-loop)** | ✅ **New — full-stack, verified live** (2026-07-21) | High |
| React frontend | ✅ **Rebuilt as Notion-style "Chief of Staff" command center** (2026-07-21) | Medium-High (build + module transforms clean; browser click-through still human) |
| Security / injection sanitization | ✅ Built + tested | Medium (only on agent/MCP path) |
| Test suite (15 files) | ✅ **104 passed, 5 skipped** (verified 2026-07-21) | High |
| Docs vs. reality alignment | ⚠️ Aspirational | — |

**Overall: this is a genuinely substantial, near-complete build (~7.9k LOC across
Python + TS), not a skeleton.** The main risks are integration-level, not missing
features: two divergent pipeline paths, unverified live third-party integrations,
and docs that over-claim relative to the default runtime.

## 3. Section-by-section breakdown

### 3.1 Domain model — `threadline/models.py` ✅
All inter-component types (Pydantic) in one file: `Decision`, `ActionItem`, `Entity`,
`Topic`, `ExtractedFact`, `ConflictRecord`, `SupersessionRecord`, `ExtractionResult`,
`StageEvent`, `PipelineResult`, graph/search/briefing outputs. The `DecisionStatus`
state machine and `PipelineStage`/`StageStatus` enums anchor the whole system.
Clean, well-documented, no business logic. **Nothing outstanding.**

### 3.2 Configuration — `threadline/config.py` ✅
`pydantic-settings` reading `.env`. Three backends each switchable
(`openai|gemini|mock`, `neo4j|memory`, `qdrant|memory`). `effective_extractor_backend`
implements auto-degrade-to-mock. Singleton with a test override hook. **Complete.**

### 3.3 Extraction — `threadline/extractor.py` ✅
- `LLMExtractor`: OpenAI (`gpt-4o-mini`) or Gemini Flash, JSON-mode prompt, Pydantic
  validation, **3× retry w/ exponential backoff**, returns partial result rather than
  raising. The prompt is carefully engineered around the `under_review` vs `superseded`
  distinction.
- `MockExtractor`: deterministic, **ID-stable hardcoded responses for meeting_01–04**
  that encode the full supersession + conflict-resolution demo story; generic plausible
  output for any other ID.
**Complete.** Coupling to fixtures is intentional but fragile (see Risks).

### 3.4 Graph store — `graph_store.py` (InMemory) + `graph_store_neo4j.py` ✅
`GraphStore` Protocol with `upsert_result`, decision/action/conflict/topic getters,
`get_graph_snapshot`, `get_status`, and `purge_person` (GDPR). InMemory backend is the
tested fallback; Neo4j backend (572 LOC) implements the same contract with Cypher.
**InMemory: high confidence. Neo4j: needs a live smoke test** (`THREADLINE_INTEGRATION=1`).

### 3.5 Vector store — `vector_store.py` (InMemory) + `vector_store_qdrant.py` ✅
InMemory uses deterministic hash-based mock embeddings (no model download needed);
Qdrant backend uses `sentence-transformers` (`all-MiniLM-L6-v2`, dim 384). Semantic
search + upsert + status. **Same posture as graph store.**

### 3.6 Orchestration — `pipeline.py` ✅ (two paths) ⚠️
- **`Pipeline`** (direct DI): 6 stages (INGEST → TRANSCRIBE → EXTRACT → GRAPH_WRITE →
  VECTOR_WRITE → BRIEFING), per-stage error isolation, streams `StageEvent`s. Audio via
  OpenAI Whisper. Used by CLI/`demo.py`/tests. **Solid.**
- **`AgentPipeline`** → `ManagerAgentRunner`: same stage contract, but delegates to the
  agent layer; Lyzr primary → in-process ADK fallback. Audio via Gemini. Used by the
  backend. **Built and works in fallback mode; the Lyzr path is unverified.**
> ⚠️ **These two paths can drift.** Bug fixes to one (e.g. the Whisper-vs-Gemini audio
> difference, or security sanitization) do not automatically apply to the other.

### 3.7 Agent layer — `threadline/agents/*` + `threadline/mcp/*` ✅ built
Six agent runners (input, extraction, graph_writer, semantic_memory, briefing, manager)
plus MCP tool wrappers around the stores and an `agent_registry` that wires singleton
stores and builds optional `/a2a/<agent>` ASGI sub-mounts. The extraction agent uses a
minimal LangGraph state graph. **Runs in-process reliably; the "5 agents as A2A
microservices" framing is architectural aspiration — real transport is in-process.**

### 3.8 Backend API — `backend/**` ✅
FastAPI app with lifespan-initialized stores, CORS regex for any localhost port, and
routers: `pipeline` (SSE for text / 202+polling for audio), `briefing`, `graph`,
`search`, `status`, `governance` (GDPR cascade purge), `health`. Dependency injection
via `app.state`. **Complete and coherent.** Note the background `JOBS` dict is
in-memory (fine for demo, not multi-worker).

### 3.9 Frontend — `frontend/src/**` ✅
React + TS + Vite, React Router, four views (Upload with live SSE progress, Briefing,
Graph viz, Search), shared components (`StageProgress`, `ConflictAlert`, `StatusDot`,
`SourceBadge`), typed API client, oxlint configured. **Feature-complete; needs a live
end-to-end click-through against the running backend to confirm wiring.**

### 3.10 Security — `threadline/security.py` ✅ built / ⚠️ partial coverage
`sanitize_name` (strips quotes/backticks/semicolons/braces, disarms Cypher keywords,
caps length), `validate_extraction_result`, `validate_meeting_transcript` (1MB cap).
Invoked **inside the MCP wrappers** → only protects the **agent/backend path**, not the
direct `Pipeline`. 4 injection-protection tests exist. **Good, but asymmetric.**

### 3.11 Tests — `tests/**` ✅ broad
~109 test functions across 15 files: models, extractor, pipeline, MCP tools, graph &
vector stores, API, health, injection, purge, observability, async decoupling, plus
opt-in Gemini/Lyzr integration tests. `conftest.py` sets `THREADLINE_TESTING=1`.
**Verified 2026-07-21: `104 passed, 5 skipped` in ~0.2s** (Python 3.13 venv). The 5
skips are all opt-in live tests (OpenAI key / `THREADLINE_INTEGRATION=1` for
Gemini/Neo4j/Qdrant/Lyzr) — not failures. `python3 demo.py` also runs all 4 fixtures
clean with the full supersession + conflict narrative intact. One non-fatal Starlette
TestClient/httpx deprecation warning. Deps resolved **far newer** than the `>=` floors
(pydantic 2.13, fastapi 0.139, neo4j 6.2, google-adk 2.5, langgraph 1.2) and still pass
— but the build is unpinned, so a future `pip install` could drift.

## 4. Key risks & gaps (ranked)

1. **Two pipeline paths that can silently diverge** (§3.6). Backend and CLI/tests
   exercise *different* orchestrators, transcription providers, and security coverage.
   → **Partially retired 2026-07-21**: both paths were run over all 4 fixtures and
   produced identical decision/conflict/supersession counts (§6). Residual risk is
   narrow — the *audio/transcription* branch (Whisper vs Gemini) is still untested on
   both, and nothing structurally prevents future drift. Keep an eye on it; consider a
   test that pins the backend path's output.
2. **Security only on the MCP/agent path** (§3.10). Direct `Pipeline` writes unsanitized.
3. **Live third-party integrations**: local **Neo4j + Qdrant now verified green**
   (2026-07-21, §7). Still unverified: Lyzr Studio, Neo4j Aura / Qdrant Cloud, and real
   OpenAI/Gemini extraction (all need credentials).
4. **Docs over-claim** (`ARCHITECTURE.md`/`README.md` present Lyzr+ADK+MCP+A2A as the
   operating reality; default runtime is in-process fallback). Judges may probe this.
5. **Branding inconsistency**: `threadline` (package/CLI) vs "Tesseract" (API title,
   docs) vs "Threadline" (frontend). Pick one before the demo.
6. **Mock/fixture coupling** (§3.3): editing a fixture without updating `_MOCK_RESPONSES`
   breaks the cross-meeting narrative tests.
7. **Unpinned dependencies already bit once.** `qdrant-client` resolved to 1.18.0 vs a
   pinned 1.9.3 server → a 404 in `search()` (fixed by bumping the image, §7). The
   `>=`-only deps mean a fresh `pip install` can pull versions the code/infra weren't
   tested against. **Pin a lockfile before the demo.** _(Test suite itself: verified —
   106 passed / 3 skipped with live DBs.)_

## 5. What "done for the demo" requires

The build is feature-complete; closing the demo means **verifying**, not writing:
- [x] `pip install -e ".[dev]"` then `pytest` → **104 passed, 5 skipped** (2026-07-21, py3.13 venv).
- [x] `python3 demo.py` → 4 fixtures produce the Auth0→Keycloak supersession + conflict
      resolution story (m3: 1 conflict / m4: 1 supersession).
- [x] **Backend up + all endpoints smoke-tested live** (see §6). Frontend click-through
      still pending (requires a browser session).
- [x] GDPR purge (`DELETE /api/v1/governance/purge/Dev Rao`) verified: 1 entity removed,
      6 decisions + 7 action items PII-nulled, **all 9 decisions retained**.
- [ ] Decide branding; make one live-service path (at least Neo4j+Qdrant via Docker) green.

See [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for the sequenced checklist.

## 6. Live backend smoke test — 2026-07-21

Booted `uvicorn backend.main:app` (with `THREADLINE_TESTING=1` to skip A2A GCP-auth
mounts). No external services running, so it degraded to InMemory graph + InMemory
vector + MockExtractor — **exactly as designed**. Then drove every endpoint:

- **Startup**: clean; logged each fallback; "Application startup complete."
- **`GET /`, `/api/v1/health`, `/api/v1/status`**: all 200, report `backend: memory` +
  `llm: mock`. Health distinguishes connected/degraded per dependency.
- **`POST /api/v1/pipeline/run`** (SSE) for all 4 fixtures via the **`AgentPipeline` →
  `ManagerAgentRunner` ADK-fallback path** (the shipped path, *not* the one `demo.py`
  uses): every stage streamed `done`, tagged `(ADK)` with a correlation id. Results
  matched the direct path — m1: 7 decisions; m2: 1 supersession; m3: 1 conflict/0
  decisions; m4: 1 supersession + conflict resolved. **This closes the biggest risk in
  §4 (the two paths agree in practice.)**
- **`GET /api/v1/briefing`**: 4 meetings, 9 decisions (`confirmed` + `superseded`), 1
  conflict with `resolved: true`, 12 action items.
- **`GET /api/v1/graph`**: 54 nodes / 25 edges; edge types `SUPERSEDES`, `CONTRADICTS`,
  `RESOLVES`, `MENTIONED_IN`; 2 superseded edges (PG→Mongo, Auth0→Keycloak).
- **`POST /api/v1/search`**: **real sentence-transformers embeddings** (`all-MiniLM-L6-v2`,
  `using_hash_fallback: false`) — "authentication provider" surfaced Keycloak items top.
- **`DELETE /api/v1/governance/purge/Dev Rao`**: cascade worked (see checklist above).

Not yet verified at that point: frontend browser click-through; live external services.

## 7. Live database integration — 2026-07-21

Brought up `docker-compose` (Neo4j 5.20 + Qdrant) and ran against real stores:

- **`THREADLINE_INTEGRATION=1 pytest` → 106 passed, 3 skipped** (the 2 store-integration
  tests now execute and pass; 3 remaining skips all need API keys: OpenAI/Gemini/Lyzr).
- **Found + fixed a real dependency-drift bug** (this is risk §4.7 materializing): the
  resolved `qdrant-client 1.18.0` calls the `query_points` API introduced in Qdrant
  **1.10**, but `docker-compose.yml` pinned the server to **`v1.9.3`** → `search()`
  returned **404**. Fix applied: bumped the image to **`qdrant/qdrant:v1.18.0`** (and
  wiped the stale volume, whose v1.9.3 segment format v1.18 can't read). After that,
  all vector integration tests pass.
- **Backend booted against live stores** (`Neo4jGraphStore` / `QdrantVectorStore`), ran
  all 4 fixtures via the API. Persistence confirmed by querying the DBs directly:
  - Neo4j: `/status` reported 57 nodes / 54 edges; `cypher-shell MATCH (n) RETURN count(n)`
    → **57** (match). Relationship types: `MENTIONED_IN`×51, **`SUPERSEDES`×2**,
    **`RESOLVES`×1**. The two SUPERSEDES edges are the actual demo story
    (MongoDB→PostgreSQL, Keycloak→Auth0).
  - Qdrant: `/status` reported 21 vectors; `GET /collections/threadline_facts` →
    **21 points, status green** (match).

Net: the full stack works end-to-end on real infrastructure, not just in-memory.
