"""
FastAPI route for running the pipeline with SSE progress streaming.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from backend.deps import get_pipeline
from threadline.pipeline import Pipeline
from threadline.models import StageEvent, PipelineStage, StageStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

@router.post("/run")
async def run_pipeline(
    file: UploadFile = File(...),
    meeting_id: Optional[str] = Form(None),
    pipeline: Pipeline = Depends(get_pipeline)
) -> StreamingResponse:
    """
    Run the processing pipeline for an uploaded transcript (.txt) or audio file.
    Streams progress updates back to the client in real-time using Server-Sent Events (SSE).
    """
    mid = meeting_id or file.filename.rsplit(".", 1)[0]
    content = await file.read()
    
    # We will run the synchronous pipeline.run_streaming in a background thread
    # and use an asyncio.Queue to bridge the events to our async SSE generator.
    queue: asyncio.Queue[Optional[StageEvent]] = asyncio.Queue()

    def run_sync_pipeline():
        try:
            generator = pipeline.run_streaming(
                source=file.filename,
                meeting_id=mid,
                content=content
            )
            while True:
                try:
                    event = next(generator)
                    # Enqueue event in the main loop thread-safely
                    asyncio.run_coroutine_threadsafe(queue.put(event), loop).result()
                except StopIteration:
                    break
        except Exception as e:
            logger.exception("Pipeline execution failed in background thread")
            # Enqueue error stage event
            err_ev = StageEvent(
                stage=PipelineStage.PIPELINE,
                status=StageStatus.error,
                message=f"Pipeline failed: {e}"
            )
            asyncio.run_coroutine_threadsafe(queue.put(err_ev), loop).result()
        finally:
            # Sentinel value to signal completion
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    loop = asyncio.get_running_loop()
    # Start thread in executor
    loop.run_in_executor(None, run_sync_pipeline)

    async def sse_event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            
            # Format according to SSE spec
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream"
    )
