# Implementation Plan & Tracker — Threadline / Tesseract

_Companion to [`PROJECT_STATUS.md`](./PROJECT_STATUS.md). Check boxes as work lands.
Keep this file honest — an unchecked box the day before the demo is information, not failure._

The codebase is **feature-complete**; this plan is therefore weighted toward
**verification, hardening, and de-risking**, not net-new features. Phases are ordered
by demo impact. Do Phase 0 and Phase 1 no matter what.

---

## Phase 0 — Make it run & prove the ✅s (blocking, ~1–2h)

Goal: turn "code exists" into "observed working." Nothing else matters until this is done.

- [x] `pip install -e ".[dev]"` succeeds — used a **Python 3.13 venv** (`.venv/`);
      the machine default `python3` is 3.14, which lacks wheels for some heavy deps.
- [x] `pytest` → **104 passed, 5 skipped** (skips are opt-in live tests only). 2026-07-21.
- [x] `python3 demo.py` runs all 4 fixtures without error.
- [x] Demo narrative visibly holds: Auth0 conflict raised in m3 (1 conflict, 0 decisions),
      Auth0 `superseded` by Keycloak in m4 (1 supersession). _(Direct `Pipeline`+mock path.)_
- [x] `uvicorn backend.main:app --port 8000` boots (with `THREADLINE_TESTING=1`);
      `/`, `/api/v1/health`, `/api/v1/status` all 200; graceful degradation logged.
- [x] `cd frontend && npm install` (exit 0), `npm run build` (tsc + vite, **no errors**),
      and `npm run dev` serves **HTTP 200 at http://localhost:5173**. Remaining: a human
      browser click-through of the 4 views (backend + live DBs are up behind it).

## Phase 1 — End-to-end demo dress rehearsal (blocking, ~1–2h)

Goal: the exact sequence you'll show judges, executed live once.

- [ ] Upload `meeting_01.txt` via UI → SSE progress animates → Briefing populates.
- [ ] Upload m2 → Graph view shows MongoDB **supersedes** PostgreSQL (dashed/greyed edge).
- [ ] Upload m3 → amber **Contradiction Alert** with confidence score + reasoning trace;
      Auth0 shows `under_review` (NOT superseded).
- [ ] Upload m4 → Auth0 → `superseded` by Keycloak; conflict clears.
- [x] Semantic Search returns sensible hits (verified via API: "authentication provider"
      → Keycloak items top, real `all-MiniLM-L6-v2` embeddings). UI view still to click.
- [x] `DELETE /api/v1/governance/purge/Dev Rao` → verified via API: 1 entity removed,
      6 decisions + 7 action items PII-nulled, all 9 decisions retained.
- [ ] Write the click-by-click script into the demo notes (order + expected UI at each step).

> **Note:** the API-level equivalents of the SSE upload, supersession, conflict, search,
> and purge steps were all verified live on 2026-07-21 (see PROJECT_STATUS §6). What
> remains for Phase 1 is confirming the **React UI** renders them (browser session).

## Phase 2 — Resolve the top correctness risks (high value, ~half day)

Goal: close the gaps most likely to bite under judge scrutiny.

- [ ] **Unify or explicitly document the two pipeline paths** (`Pipeline` vs
      `AgentPipeline`). Minimum: a short note in code + docs stating which ships and why.
      Stretch: route both through the same store-write + sanitization seam.
- [ ] **Extend security to the direct `Pipeline` path**, or assert in tests that the
      shipped (backend) path always sanitizes. Currently only the MCP/agent path does.
- [ ] Confirm audio path works on the shipped backend (Gemini transcription) with one
      real short clip, or disable audio upload in the UI for the demo to avoid a live failure.
- [ ] Add/confirm a test that exercises the **backend `AgentPipeline`** end-to-end in
      fallback mode (not just the direct `Pipeline`).

## Phase 3 — Light up at least one real backing service (medium value, ~half day)

Goal: be able to say "and it's not just in-memory" truthfully.

- [x] `docker-compose up -d` (defaults already select `neo4j`/`qdrant`, no `.env` needed).
- [x] `THREADLINE_INTEGRATION=1 pytest` → **106 passed, 3 skipped**; live graph + vector
      tests green. **Fixed a real bug**: bumped `docker-compose` Qdrant `v1.9.3 → v1.18.0`
      to match `qdrant-client 1.18.0` (old server lacked the `query_points` API → 404).
- [x] Ran all 4 fixtures via the API against live Neo4j + Qdrant; verified persistence by
      direct DB query (Neo4j 57 nodes incl. 2 `SUPERSEDES` + 1 `RESOLVES`; Qdrant 21 points).
      `/status` reports `backend: neo4j` / `backend: qdrant` (would show "connected" in UI).
- [ ] (Optional) Real LLM extraction: set `OPENAI_API_KEY` or `GEMINI_API_KEY`, run one
      fixture, sanity-check extraction quality vs the mock.
- [ ] (Optional) Verify **or de-scope** the Lyzr Studio path. If it can't be made green,
      say so plainly and rely on the ADK in-process fallback (which is the honest default).

## Phase 4 — Polish & credibility (nice-to-have)

Goal: remove the small things that read as "unfinished" to a judge.

- [ ] **Pick one product name** and make it consistent (package/API title/frontend/docs).
- [ ] Reconcile `ARCHITECTURE.md` / `README.md` claims with the default in-process runtime
      (add a one-line "what actually runs by default" callout so nothing reads as overclaim).
- [ ] Run `ruff check .` and `npm run lint`; fix or silence findings.
- [ ] Screenshot/GIF the 4-step story for the README and pitch deck.
- [ ] Confirm `.env.example` matches every var actually read by `config.py` + agents
      (e.g. `LYZR_API_KEY`, `LYZR_AGENT_ID` are read but not in `.env.example`).
- [x] **Pin the Python dependency set** — `requirements.lock` written via
      `pip freeze --exclude-editable` (131 exact pins, the known-good set verified this
      session: fastapi 0.139.2, pydantic 2.13.4, neo4j 6.2.0, qdrant-client 1.18.0,
      google-adk 2.5.0, langgraph 1.2.9, torch 2.13.0, …). Install reproducibly with
      `pip install -r requirements.lock && pip install -e . --no-deps`. Frontend is
      already pinned via the committed `package-lock.json` (`npm ci` for reproducible installs).

## Phase 5 — Post-hackathon / stretch (only if ahead)

- [ ] Real distributed A2A (separate ADK services) instead of ASGI sub-mounts.
- [ ] Persist background `JOBS` (Redis) so audio jobs survive multi-worker/restart.
- [ ] Migrate `Extractor`/stores to true Google ADK Agents + MCP servers per `ARCHITECTURE.md`.
- [ ] Auth on the API; multi-tenant meeting workspaces.
- [ ] Streaming/partial extraction for very long transcripts.

---

## Definition of done (demo)

The demo is ready when **Phase 0 + Phase 1 are fully checked** and at least the
correctness items in **Phase 2** are addressed or consciously accepted as risks with a
fallback. Phase 3+ strengthen the story but are not blocking if the in-memory demo is
crisp — which is exactly what the architecture was designed to guarantee.

## Changelog

- 2026-07-21 — **Frontend rehaul + conflict-resolution loop** (plan
  `~/.claude/plans/mossy-wiggling-glade.md`). Backend: new `ConflictRecord` resolution
  fields, `GraphStore.resolve_conflict`/`get_conflict` (InMemory + Neo4j), `sanitize_text`,
  `/api/v1/conflicts` (list + `POST /{id}/resolve`), `/api/v1/demo/seed`; 8 new tests
  (unit + API + live-Neo4j). Frontend: full Notion-style redesign — design system
  (`index.css`), app shell (sidebar + alert bell), global state (`state/app.tsx`), views
  (Home/Decisions/ActionItems/Ask/Map/AddMeeting/Settings), signature `ConflictCard`,
  audio 202-polling fix, plain-language copy, tech demoted to a health area. Verified:
  111 unit / 114 with live integration; `npm run build` type-checks clean; full conflict
  loop confirmed end-to-end via API against live Neo4j+Qdrant (seed → 1 open conflict →
  resolve "switch" → Auth0 superseded, count → 0). Old views (Upload/Briefing/Graph/
  Search) + `ConflictAlert`/`StatusDot` removed; `index.html` title fixed.
- 2026-07-21 — Pinned the Python deps (`requirements.lock`, 131 pins) locking the
  known-good set. Started the Vite dev server (200 at :5173) + backend against live DBs
  for browser click-through. **New file: `requirements.lock`.**
- 2026-07-21 — Live DB integration: `docker-compose up` (Neo4j+Qdrant),
  `THREADLINE_INTEGRATION=1 pytest` → 106 passed / 3 skipped. Fixed Qdrant client/server
  version mismatch by bumping the compose image to v1.18.0. Backend run against live
  stores confirmed data (incl. supersession edges) persists in Neo4j + Qdrant. Frontend
  `npm run build` passes (tsc + vite, no errors). **Code change: `docker-compose.yml`
  Qdrant image v1.9.3 → v1.18.0.**
- 2026-07-21 — Backend smoke test: booted uvicorn, drove every endpoint incl. all 4
  fixtures through the `AgentPipeline` (ADK) path via SSE — results match the direct
  path; briefing/graph/search/GDPR-purge all correct. Top correctness risk (two paths
  diverging) partially retired. Remaining Phase 0/1: frontend browser click-through.
- 2026-07-21 — Phase 0 largely verified: deps installed in a Python 3.13 venv,
  `pytest` → 104 passed / 5 skipped, `demo.py` narrative confirmed. Remaining Phase 0:
  live backend/frontend boot.
- 2026-07-21 — Initial plan created from full-repo review (branch `refactor`).

## Environment notes

- Install into `.venv/` built with **`python3.13`** (`python3.13 -m venv .venv`), not the
  system `python3` (3.14) — some deps (torch, sentence-transformers, google-adk) lack
  3.14 wheels. Run everything via `.venv/bin/python` / `.venv/bin/pytest`.
- Dependencies are declared with `>=` floors only; the resolved versions are much newer
  than what the code was written against. Consider pinning a known-good lockfile before
  the demo so a fresh install can't drift.
