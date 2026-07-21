# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Meeting-intelligence pipeline. Ingests meeting transcripts (or audio), extracts
structured decisions / action items / entities / conflicts with an LLM, persists
them into a Neo4j knowledge graph + Qdrant vector index, tracks decision
lifecycles **across meetings** (supersession, `under_review` → `superseded`,
contradiction-then-resolution), and renders an auto-updating executive briefing +
graph view + semantic search in a React frontend.

The whole system is built to **degrade to a zero-dependency in-process mode** so a
live demo never crashes: no LLM key → `MockExtractor`; no Neo4j → `InMemoryGraphStore`;
no Qdrant → `InMemoryVectorStore`; no Lyzr → in-process ADK orchestration.

> **Naming:** the Python package and CLI are `threadline`; the FastAPI app title,
> `README.md`, and `ARCHITECTURE.md` call the product **"Tesseract"**; the frontend
> navbar says "Threadline". These refer to the same system. Treat `threadline` as
> the canonical code name.

## Commands

Python (backend + core). Note: this machine's interpreter is `python3` (there is no
`python` shim).

```bash
pip install -e ".[dev]"                       # install package + test deps (editable)
uvicorn backend.main:app --reload --port 8000 # run API  → http://localhost:8000/docs
pytest -v                                      # unit tests (in-memory, no creds needed)
pytest tests/test_pipeline.py -v               # one file
pytest tests/test_pipeline.py::test_name -v    # one test
THREADLINE_INTEGRATION=1 pytest -v             # also hit live Neo4j/Qdrant/Lyzr/LLM
python3 demo.py                                # run all 4 fixtures through direct Pipeline
threadline demo | run <file> | status         # CLI (Typer); same pipeline, rich output
docker-compose up -d                           # Neo4j (:7687/:7474) + Qdrant (:6333), optional
```

Frontend (`frontend/`):

```bash
npm install
npm run dev      # Vite dev server → http://localhost:5173
npm run build    # tsc -b && vite build  (this is the real type-check gate)
```

Scripts are `dev`/`build`/`preview` only — there is **no** `npm run lint` (an
`.oxlintrc.json` exists but oxlint isn't a dependency; `npx oxlint src` if you want it).
Likewise there's no configured Python linter target despite `[tool.ruff]` in
`pyproject.toml` — run `ruff check .` manually if needed.

### Test environment flags

- Tests set `THREADLINE_TESTING=1`, which makes `agent_registry.build_a2a_mounts()`
  skip ADK/A2A ASGI mounts (avoids GCP auth timeouts). See `tests/conftest.py`.
- `THREADLINE_INTEGRATION=1` opts into live-service tests (otherwise skipped).
- Pytest markers: `integration`, `llm`. `asyncio_mode = "auto"`.

## Architecture — the big picture

Data contracts live in exactly one place: **`threadline/models.py`** (Pydantic).
Every other module speaks in these types. Read this file first — the
`DecisionStatus` state machine (`proposed → confirmed → under_review → superseded/reversed`)
and `StageEvent`/`PipelineStage` are the backbone of both the domain logic and the
SSE streaming protocol.

**Everything is a `Protocol` + factory with graceful fallback.** `Extractor`,
`GraphStore`, `VectorStore` are each a `Protocol` with a real backend, an in-memory
backend, and a `create_*(settings)` factory that auto-selects and falls back on
missing key / unreachable service. `config.py`'s `effective_extractor_backend`
encodes the mock-fallback rule; store fallback lives in the store factories.

### There are TWO orchestration paths — do not confuse them

1. **`Pipeline`** (`pipeline.py`) — plain dependency-injected orchestrator. Calls
   `graph_store` / `vector_store` **directly**. Used by the **CLI, `demo.py`, and
   all tests**. Audio → **OpenAI Whisper**. `create_pipeline(settings)` builds it.

2. **`AgentPipeline`** (`pipeline.py`) → **`ManagerAgentRunner`** (`agents/manager_agent.py`)
   — used by the **FastAPI backend** (wired in `backend/main.py` lifespan). Tries
   **Lyzr Studio** first (if `LYZR_API_KEY`+`LYZR_AGENT_ID`), else falls back to
   **in-process ADK** orchestration that drives the per-stage agent runners
   (`input → extraction → graph_writer → semantic_memory → briefing`). These runners
   call the stores **through MCP tool wrappers** (`threadline/mcp/*`). Audio → **Gemini**.

Both expose the identical `run_streaming()`/`run_sync()` contract, yielding one
`StageEvent` per stage so the SSE endpoint forwards them verbatim. Consequences to
keep in mind:

- The **security/sanitization layer (`security.py`) only runs on path #2**, because
  `validate_extraction_result` / `validate_meeting_transcript` are invoked inside the
  MCP wrappers (`mcp/graph_mcp.py`, `mcp/vector_mcp.py`). The direct `Pipeline` writes
  to stores without sanitizing. Tests of injection protection exercise the MCP layer.
- Agents reach the stores via **module-level singleton stores** set by
  `agent_registry.wire_stores(graph, vector)`, called in `AgentPipeline.__init__`.
  If you invoke MCP tools outside that wiring, they have no store.

### Request flow (backend)

`POST /api/v1/pipeline/run` (`backend/api/v1/pipeline.py`): text files stream
progress as **SSE** (`text/event-stream`), running the sync generator in a thread
executor and bridging events through an `asyncio.Queue`. **Audio files** instead
return `202` immediately and process in a `BackgroundTasks` job whose status is
polled at `GET /api/v1/pipeline/status/{meeting_id}` (job state in the in-memory
`JOBS` dict). Other endpoints: `briefing`, `graph`, `search`, `status`, `health`,
`governance` (GDPR purge: `DELETE /api/v1/governance/purge/{name}`),
`conflicts` (`GET /api/v1/conflicts`; `POST /api/v1/conflicts/{id}/resolve` — the
human-in-the-loop resolution loop, backed by `GraphStore.resolve_conflict` in both
InMemory and Neo4j), and `demo` (`POST /api/v1/demo/seed` loads sample meetings 1–3,
leaving the Auth0 conflict open for a live resolution demo).
Stores/extractor/pipeline are created once in the lifespan and injected via
`backend/deps.py` reading `request.app.state`.

### A2A mounts

`agent_registry.build_a2a_mounts()` wraps each ADK agent as an ASGI sub-app mounted
under `/a2a/<agent>` on the parent FastAPI app (single-process "A2A"). Returns `{}`
if `google-adk[a2a]` is absent or `THREADLINE_TESTING=1` — so the system runs fine
without it.

### Frontend

Vite + React Router, redesigned as a Notion-style **"AI Chief of Staff" command
center** for non-technical users (light-first, theme-aware; `src/index.css` holds the
whole design-token + component-class system). Shell = left sidebar + top bar with an
alert bell (`components/Shell.tsx`). Global state (theme, toasts, and polled
status+conflicts shared by the bell and Home) lives in `src/state/app.tsx`
(`AppProviders` / `useAppData` / `useToast` / `useTheme`). Views: `Home` (Command
Center — the default), `Decisions`, `ActionItems`, `Ask` (search), `Map`
(relationships graph), `AddMeeting`, `Settings`. The signature element is
`components/ConflictCard.tsx` — the plain-language "Needs your decision" card (Keep /
Switch / Flag-for-review) that calls the resolve endpoint. All API access + the audio
202-polling fix are in `src/api/client.ts`. Plain business language throughout; raw
Neo4j/Qdrant/LLM detail is demoted to `SystemStatus` (sidebar) and the Settings page.

## Conventions & gotchas

- **The 4 fixtures (`tests/fixtures/meeting_01..04.txt`) drive the demo narrative**
  and `MockExtractor` has **hardcoded, ID-stable responses** for exactly these
  meeting IDs (`dec_m1_04` Auth0 → `under_review` in m3 → `superseded` by Keycloak
  `dec_m4_01` in m4). If you change a fixture's story, update `_MOCK_RESPONSES` in
  `extractor.py` in lockstep, or the cross-meeting supersession/conflict tests break.
- `under_review` vs `superseded` is the product's signature distinction — preserve it.
  The extractor prompt (`_build_prompt`) spends most of its length enforcing this.
- New inter-component data must be added to `models.py`, not ad hoc dicts.
- Docs (`ARCHITECTURE.md`, `README.md`) describe an aspirational Lyzr/ADK/MCP mapping;
  the running default is the in-process fallback. Verify against code before relying
  on a doc claim.

## Project tracking

Living status + roadmap are in `docs/PROJECT_STATUS.md` and
`docs/IMPLEMENTATION_PLAN.md`. Update them as sections land.
