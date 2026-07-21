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
2. **Model:** any capable chat model (e.g. GPT-4o-mini or a current Gemini Flash
   like `gemini-flash-lite-latest`).
3. **System prompt** — the request already carries Tesseract's full extraction
   instructions in each message, so keep the agent's own prompt minimal:

   ```
   You are Tesseract's meeting-intelligence extraction engine. Each message
   contains complete instructions and a meeting transcript. Follow those
   instructions exactly and return ONLY the single valid JSON object they
   describe — no prose, no markdown, no code fences.
   ```

4. **Response format:** leave the output **unstructured / plain text** — do NOT
   attach a Structured Output module. The schema is already in every message; a
   forced structured output overrides it and the agent returns the wrong keys
   (e.g. a template returning `{"tweet": "...", "title": "..."}`), which parses to
   zero decisions. Temperature low (~0.1) for stable JSON.
5. Save and copy the **Agent ID** from the agent's URL / settings.
6. Create an **API key** from your Lyzr account settings.

> ⚠️ **Most common mistake:** a template/structured-output agent that returns its
> own JSON shape. If uploads come back with 0 decisions, this is why — see the
> schema below and remove any forced output schema.

## 1a. Output schema (what the agent must return)

Tesseract sends the schema in the message, so you normally don't configure it in
Lyzr at all. But if Lyzr *requires* a response schema, use **exactly this** one — do
not invent a new shape. The parser (`LLMExtractor._parse`) reads these six top-level
keys; each is an array (`[]` if empty — never omit a key):

```json
{
  "decisions": [
    { "text": "string", "status": "proposed|confirmed|under_review|superseded|reversed",
      "rationale": "string|null", "owner": "string|null",
      "supersedes_decision_id": "existing-id|null" }
  ],
  "prior_decision_updates": [
    { "decision_id": "existing-id", "decision_text": "string",
      "new_status": "under_review|superseded|reversed",
      "reason": "string", "new_decision_id": "id|null" }
  ],
  "action_items": [
    { "text": "string", "assignee": "string|null",
      "due_date": "YYYY-MM-DD or string|null",
      "status": "open|in_progress|completed|cancelled" }
  ],
  "entities": [
    { "name": "string",
      "entity_type": "person|organization|project|date|location|technology" }
  ],
  "topics": ["string"],
  "conflicts_detected": [
    { "old_decision_id": "existing-id", "conflict_description": "string",
      "confidence": 0.85, "reasoning": "string" }
  ]
}
```

Notes:
- Parsing is lenient — missing keys default to `[]`, so a wrong-schema reply doesn't
  crash; it just extracts nothing. The agent must produce **these** keys.
- The signature of the product is the `status` distinction — `under_review` (a prior
  decision is questioned, no replacement yet) vs `superseded` (explicitly replaced by
  a confirmed new decision) — plus `conflicts_detected`. The full rules are in the
  system prompt that ships inside each message, so the model already sees them.

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
