# Wiring Lyzr Studio (the mandatory integration)

Tesseract delegates **fact extraction** for real (non-fixture) meeting uploads to a
Lyzr Studio agent. The structured JSON the agent returns is parsed and persisted to
the local Neo4j + Qdrant stores by the in-process orchestrator, so the *reasoning* is
Lyzr's while persistence stays local (hosted Lyzr cannot reach your local databases).

If Lyzr is not configured, or a call fails, the backend falls back automatically to
in-process Gemini/ADK — and the four demo fixtures always use deterministic mock
output regardless — so a live demo never crashes.

## 1. Create the agent in Lyzr Studio

1. Sign in at <https://studio.lyzr.ai> and create a new **Agent**.
2. **Model:** any capable chat model (e.g. GPT-4o-mini or Gemini-1.5-Flash).
3. **System prompt** — the request already carries Tesseract's full extraction
   instructions in each message, so keep the agent's own prompt minimal:

   ```
   You are Tesseract's meeting-intelligence extraction engine. Each message
   contains complete instructions and a meeting transcript. Follow those
   instructions exactly and return ONLY the single valid JSON object they
   describe — no prose, no markdown, no code fences.
   ```

4. **Response format:** JSON / text (do not force a schema that conflicts with the
   one described in the message). Temperature low (~0.1) for stable JSON.
5. Save and copy the **Agent ID** from the agent's URL / settings.
6. Create an **API key** from your Lyzr account settings.

## 2. Configure Tesseract

Add to your `.env` (see `.env.example`):

```bash
LYZR_API_KEY=lyzr_xxx…
LYZR_AGENT_ID=your_agent_id
# Optional overrides:
# LYZR_USER_ID=threadline@tesseract.ai
# LYZR_BASE_URL=https://agent-prod.studio.lyzr.ai/v3/inference/chat/
```

Restart the backend.

## 3. Verify

```bash
# Both flags true → Tesseract will use Lyzr for real uploads.
curl -s localhost:8000/api/v1/health | jq '.dependencies.lyzr_studio'
# → { "configured": true, "api_key": true, "agent_id": true, "status": "healthy" }
```

Upload a transcript that is **not** one of the four fixtures and watch the backend
log — a successful Lyzr call logs:

```
Delegating extraction to Lyzr Studio agent <id>
Lyzr orchestration complete: N decisions, M conflict(s)
```

and the pipeline's final SSE event carries `"orchestrator": "lyzr"`.

Kill `LYZR_API_KEY` and repeat — the same upload should log the Gemini/ADK fallback
and finish with `"orchestrator": "adk"`, proving graceful degradation.

## Where it lives in code

- `threadline/agents/manager_agent.py` → `_lyzr_extract()` (the real REST call) and
  `_adk_orchestrate()` (routing: fixture→mock, else Lyzr→Gemini/ADK→mock).
- `backend/api/v1/health.py` → the `lyzr_studio` health block.
