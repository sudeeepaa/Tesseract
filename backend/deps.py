"""
FastAPI dependency injection module.
"""
from __future__ import annotations

from fastapi import Request

from threadline.config import Settings, get_settings
from threadline.graph_store import GraphStore
from threadline.vector_store import VectorStore
from threadline.pipeline import Pipeline

def get_config_settings() -> Settings:
    return get_settings()

def get_graph_store(request: Request) -> GraphStore:
    return request.app.state.graph_store

def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store

def get_pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline
