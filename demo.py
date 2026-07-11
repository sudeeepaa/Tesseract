#!/usr/bin/env python3
"""
Threadline Demo Script.
Runs all 4 meeting fixtures in sequence to demonstrate fact extraction,
supersession, and contradiction tracking.
"""
import os
import sys
import time
from pathlib import Path

# Add project root to python path to ensure imports work
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from threadline.pipeline import create_pipeline
from threadline.config import get_settings
from threadline.models import PipelineStage, StageStatus

def run_demo():
    print("==================================================")
    print("         THREADLINE DEMO PIPELINE RUNNER          ")
    print("==================================================")
    
    settings = get_settings()
    # Force in-memory fallback if docker is not running
    print(f"Extractor backend: {settings.effective_extractor_backend.value}")
    print(f"Graph Store:       {settings.graph_backend.value}")
    print(f"Vector Store:      {settings.vector_backend.value}")
    print("--------------------------------------------------")

    pipeline = create_pipeline(settings)
    
    fixtures_dir = Path("tests/fixtures")
    meetings = sorted(fixtures_dir.glob("meeting_*.txt"))
    
    if not meetings:
        print(f"Error: No meeting fixtures found in {fixtures_dir.resolve()}")
        sys.exit(1)

    for i, path in enumerate(meetings, 1):
        print(f"\n[Meeting {i}/{len(meetings)}] Processing: {path.name}")
        print("-" * 50)
        
        generator = pipeline.run_streaming(path, meeting_id=path.stem)
        try:
            while True:
                event = next(generator)
                # Pretty print status transitions
                icon = "✅" if event.status == StageStatus.done else ("❌" if event.status == StageStatus.error else "⏳")
                print(f"  {icon} {event.stage.value:<15} : {event.message}")
        except StopIteration:
            pass
            
        if i < len(meetings):
            print("\nPausing for 3 seconds before next meeting...")
            time.sleep(3)

    print("\n==================================================")
    print(" Demo complete! All fixtures processed successfully.")
    print(" Start FastAPI backend and React frontend to view.")
    print("==================================================")

if __name__ == "__main__":
    run_demo()
