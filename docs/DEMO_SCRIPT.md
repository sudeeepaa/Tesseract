# Tesseract — 90-second demo script

**One-liner:** *Tesseract is an AI Chief of Staff that reads your meetings, remembers
every decision, and taps you on the shoulder the moment two decisions collide.*

**Before you start:** backend on `:8000`, frontend on `:5173`, Neo4j + Qdrant up.
Reset to the pristine demo state (3 meetings, 1 open conflict) — the Home command
center should show **"1 decision needs you."**

| # | Time | You do / say | What the judge sees |
|---|------|--------------|---------------------|
| 1 | 0:00 | "Every company loses decisions in meeting notes. Tesseract captures them and catches contradictions across meetings." | **Home / Command Center** — stat cards, recent activity, a red **alert bell**. |
| 2 | 0:12 | "Three meetings are already loaded. Tesseract flagged a clash." Click the **alert bell**. | Scrolls to **"Needs your decision"** — the ConflictCard: *Auth0 (Meeting 1)* vs *GDPR concern (Meeting 3)*, with the AI's reasoning + confidence. |
| 3 | 0:30 | "A non-technical exec doesn't read a graph database — they get a plain choice." Read the card: **Keep**, **Switch to Keycloak**, **Flag for review**. Click **Switch to Keycloak**. | Toast: *Resolved*. Bell badge clears. |
| 4 | 0:45 | Open **Decisions**. | Auth0 now shows **Superseded**; Keycloak **Confirmed**. "This persisted — reload and it's still resolved." Refresh to prove it. |
| 5 | 0:58 | Open **Ask**, type *"What did we decide about authentication?"* | Semantic search (Qdrant) returns the right facts with source meetings — natural language, no query syntax. |
| 6 | 1:12 | "And it works on *your* meetings." **Add meeting** → paste a short transcript → run. | Live stages *Reading → Understanding → Saving → Briefing*; real decisions appear (Gemini/Lyzr extraction). |
| 7 | 1:25 | Toggle **light/dark**; point at the sidebar **System status**. | "Powered by Qdrant + Lyzr, Neo4j knowledge graph — all green." |

**Close (10s):** *"Meeting transcripts in, defensible decisions out, and a human in the
loop exactly when it matters. That's Tesseract."*

## Backup / resilience talking points (if asked)
- **Never crashes:** no LLM key → deterministic mock; no Neo4j/Qdrant → in-memory
  stores; no Lyzr → in-process ADK. The demo degrades, it doesn't die.
- **Mandatory stack:** Qdrant powers semantic memory (real MiniLM embeddings, not a
  hash fallback); Lyzr Studio performs extraction for live uploads (`orchestrator: lyzr`
  in the pipeline events) — see `docs/LYZR_SETUP.md`.
- **The signature distinction:** `under_review` (flagged, still open) vs `superseded`
  (a later decision won) — the product tracks decision *lifecycles*, not just a list.
