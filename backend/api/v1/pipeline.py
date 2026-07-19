"""
FastAPI route for running the pipeline with SSE progress streaming.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from backend.deps import get_pipeline
from threadline.pipeline import Pipeline
from threadline.models import StageEvent, PipelineStage, StageStatus

logger = logging.getLogger(__name__)

# In-memory store for background job statuses
JOBS: dict[str, dict] = {}

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

@router.get("/status/{meeting_id}")
async def get_pipeline_job_status(meeting_id: str) -> dict:
    """Get the current background status of a pipeline job."""
    if meeting_id not in JOBS:
        raise HTTPException(status_code=404, detail=f"Job {meeting_id!r} not found")
    return JOBS[meeting_id]

@router.post("/run")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_id: Optional[str] = Form(None),
    pipeline: Pipeline = Depends(get_pipeline)
) -> Any:
    """
    Run the processing pipeline for an uploaded transcript (.txt) or audio file.
    For audio files, immediately enqueues the job and returns 202 Accepted.
    For text files, streams progress updates back using Server-Sent Events (SSE).
    """
    from fastapi import BackgroundTasks
    mid = meeting_id or file.filename.rsplit(".", 1)[0]
    content = await file.read()
    
    # Check if the file is audio
    suffix = file.filename.lower()
    is_audio = any(suffix.endswith(ext) for ext in [".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".flac", ".webm"])

    if is_audio:
        # Decouple heavy audio transcription using BackgroundTasks
        logger.info("Audio file uploaded. Enqueuing background transcription/pipeline for %r", mid)
        JOBS[mid] = {
            "status": "IN_PROGRESS",
            "progress": "Audio file enqueued for background transcription and processing",
            "events": []
        }

        def run_pipeline_bg():
            try:
                generator = pipeline.run_streaming(
                    source=file.filename,
                    meeting_id=mid,
                    content=content
                )
                while True:
                    try:
                        event = next(generator)
                        JOBS[mid]["events"].append(event.model_dump())
                        JOBS[mid]["progress"] = event.message
                    except StopIteration as stop:
                        result = stop.value
                        JOBS[mid]["status"] = "COMPLETED"
                        JOBS[mid]["progress"] = "Processing complete"
                        # We can dump the result or clean up
                        break
            except Exception as e:
                logger.exception("Background pipeline execution failed")
                JOBS[mid]["status"] = "FAILED"
                JOBS[mid]["progress"] = f"Pipeline execution failed: {e}"

        background_tasks.add_task(run_pipeline_bg)
        return StreamingResponse(
            iter([json.dumps({
                "status": "IN_PROGRESS",
                "meeting_id": mid,
                "status_url": f"/api/v1/pipeline/status/{mid}"
            })]),
            status_code=202,
            media_type="application/json"
        )

    # Text files run using SSE streaming as before
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
            err_ev = StageEvent(
                stage=PipelineStage.PIPELINE,
                status=StageStatus.error,
                message=f"Pipeline failed: {e}"
            )
            asyncio.run_coroutine_threadsafe(queue.put(err_ev), loop).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_sync_pipeline)

    async def sse_event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream"
    )
