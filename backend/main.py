"""
Main FastAPI application entrypoint.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from threadline.config import get_settings
from threadline.extractor import create_extractor
from threadline.graph_store import create_graph_store
from threadline.vector_store import create_vector_store
from threadline.pipeline import Pipeline

from backend.api.v1.pipeline import router as pipeline_router
from backend.api.v1.briefing import router as briefing_router
from backend.api.v1.graph import router as graph_router
from backend.api.v1.search import router as search_router
from backend.api.v1.status import router as status_router

# Setup logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("backend")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Server lifespan context manager.
    Initializes stores and orchestrator pipeline on startup, attaching to app state.
    """
    logger.info("Initializing Threadline core components...")
    
    # 1. Instantiate stateful stores & components
    graph_store = create_graph_store(settings)
    vector_store = create_vector_store(settings)
    extractor = create_extractor(settings)
    
    pipeline = Pipeline(
        extractor=extractor,
        graph_store=graph_store,
        vector_store=vector_store,
        openai_api_key=settings.openai_api_key
    )

    # 2. Attach to app.state so FastAPI dependency functions can inject them
    app.state.graph_store = graph_store
    app.state.vector_store = vector_store
    app.state.extractor = extractor
    app.state.pipeline = pipeline

    logger.info("Threadline initialization complete. Server is ready.")
    yield
    
    # Clean up (if any close functions exist)
    if hasattr(graph_store, "close"):
        try:
            graph_store.close()
        except Exception:
            pass

app = FastAPI(
    title="Threadline API",
    description="Meeting intelligence pipeline backend wrapping knowledge graph, similarity search, and briefings.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend access.
# Using allow_origin_regex so any localhost port works in dev
# (Vite auto-increments the port when 5173 is busy → 5174, 5175 …).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 endpoints
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(briefing_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(status_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "app": "Threadline Meeting Intelligence API",
        "docs_url": "/docs",
        "status_url": "/api/v1/status"
    }
