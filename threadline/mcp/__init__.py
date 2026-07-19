"""
Threadline MCP tool server wrappers.

Each module wraps an existing store Protocol as an MCP tool server,
exposing domain-specific operations (not generic Cypher/vector queries)
so that ADK agents can access stores through the MCP tool interface.

Modules:
    graph_mcp  — MCP tools wrapping GraphStore operations
    vector_mcp — MCP tools wrapping VectorStore operations
"""
