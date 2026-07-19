"""
Threadline ADK Agent definitions.

Each module in this package defines a Google ADK Agent that is exposed
as an A2A server with its own Agent Card.

Agents:
    input_agent        — File ingestion + Gemini audio transcription
    extraction_agent   — LLM fact extraction (with LangGraph internals)
    graph_writer_agent — Knowledge graph persistence via MCP tools
    semantic_memory_agent — Vector store indexing via MCP tools
    briefing_agent     — Executive briefing generation
    manager_agent      — A2A client orchestrator (replaces Pipeline)
    agent_registry     — A2A server lifecycle management
"""
