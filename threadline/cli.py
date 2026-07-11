"""
Threadline CLI — developer tool for testing the pipeline without the frontend.

Commands:
    threadline run <file>        Process one meeting transcript or audio file
    threadline run --watch <dir> Watch a directory for new files
    threadline briefing          Re-generate briefing from stored data
    threadline status            Show backend connectivity
    threadline demo              Run all 4 fixture meetings in sequence (demo mode)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app     = typer.Typer(name="threadline", help="Threadline meeting intelligence CLI")
console = Console()


def _get_pipeline():
    from threadline.pipeline import create_pipeline
    return create_pipeline()


# ─────────────────────────────────────────────────────────────────────────────
# threadline run
# ─────────────────────────────────────────────────────────────────────────────

@app.command()
def run(
    source:     str = typer.Argument(..., help="Path to .txt transcript or audio file"),
    meeting_id: Optional[str] = typer.Option(None, "--meeting-id", "-m",
                                              help="Override meeting ID (defaults to filename stem)"),
) -> None:
    """Process a single meeting file through the full pipeline."""
    from threadline.models import StageStatus, PipelineStage

    p = Path(source)
    if not p.exists():
        console.print(f"[red]File not found:[/red] {source}")
        raise typer.Exit(1)

    pipeline = _get_pipeline()
    mid      = meeting_id or p.stem

    console.print(f"\n[bold cyan]Threadline[/bold cyan] — processing [yellow]{p.name}[/yellow] as [green]{mid}[/green]\n")

    gen = pipeline.run_streaming(p, mid)
    result = None
    try:
        while True:
            event = next(gen)
            icon = {"done": "✅", "error": "❌", "running": "⏳", "skipped": "⏭️", "pending": "⬜"}.get(event.status.value, "•")
            colour = {"done": "green", "error": "red", "running": "yellow", "skipped": "dim"}.get(event.status.value, "white")
            console.print(f"  {icon} [{colour}]{event.stage.value:12}[/{colour}]  {event.message}")
    except StopIteration as stop:
        result = stop.value

    if result and result.errors:
        console.print(f"\n[yellow]Warnings ({len(result.errors)}):[/yellow]")
        for e in result.errors:
            console.print(f"  • {e}")

    status = "[green]✅ Success[/green]" if (result and result.overall_success) else "[red]❌ Errors[/red]"
    console.print(f"\n{status}\n")


# ─────────────────────────────────────────────────────────────────────────────
# threadline status
# ─────────────────────────────────────────────────────────────────────────────

@app.command()
def status() -> None:
    """Show backend connectivity and data counts."""
    from threadline.graph_store  import create_graph_store
    from threadline.vector_store import create_vector_store
    from threadline.config       import get_settings
    from threadline.extractor    import create_extractor

    settings = get_settings()
    gs       = create_graph_store(settings)
    vs       = create_vector_store(settings)

    t = Table(title="Threadline Backend Status", show_header=True, header_style="bold cyan")
    t.add_column("Component", style="bold")
    t.add_column("Backend")
    t.add_column("Status")
    t.add_column("Details")

    gs_status = gs.get_status()
    vs_status = vs.get_status()
    ex_backend = settings.effective_extractor_backend.value

    t.add_row(
        "Graph Store",
        gs_status.get("backend", "?"),
        "[green]connected[/green]" if gs_status.get("connected") else "[red]error[/red]",
        f"{gs_status.get('node_count', 0)} nodes, {gs_status.get('edge_count', 0)} edges",
    )
    t.add_row(
        "Vector Store",
        vs_status.get("backend", "?"),
        "[green]connected[/green]" if vs_status.get("connected") else "[red]error[/red]",
        f"{vs_status.get('vector_count', 0)} vectors",
    )
    t.add_row(
        "Extractor",
        ex_backend,
        "[green]ready[/green]" if ex_backend != "mock" else "[yellow]mock mode[/yellow]",
        "API key configured" if ex_backend != "mock" else "No API key — using MockExtractor",
    )

    console.print()
    console.print(t)
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# threadline demo
# ─────────────────────────────────────────────────────────────────────────────

@app.command()
def demo(
    fixtures_dir: str = typer.Option("tests/fixtures", "--dir", "-d",
                                      help="Directory containing fixture .txt files"),
    delay: float = typer.Option(2.0, "--delay",
                                help="Seconds to pause between meetings"),
) -> None:
    """
    Run all fixture meetings in sequence.
    Demonstrates the supersession and conflict-resolution story end-to-end.
    """
    d = Path(fixtures_dir)
    meetings = sorted(d.glob("meeting_*.txt"))
    if not meetings:
        console.print(f"[red]No meeting_*.txt files found in {d}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Threadline Demo[/bold cyan] — {len(meetings)} meetings\n")
    pipeline = _get_pipeline()

    for i, path in enumerate(meetings, 1):
        console.rule(f"[bold]Meeting {i}/{len(meetings)}: {path.name}[/bold]")
        gen = pipeline.run_streaming(path)
        try:
            while True:
                event = next(gen)
                if event.stage.value == "PIPELINE":
                    continue
                icon = "✅" if event.status.value == "done" else ("❌" if event.status.value == "error" else "⏳")
                console.print(f"  {icon} {event.stage.value:12} {event.message}")
        except StopIteration:
            pass
        if i < len(meetings):
            console.print(f"\n[dim]Waiting {delay}s before next meeting…[/dim]\n")
            time.sleep(delay)

    console.print("\n[bold green]Demo complete.[/bold green]")
    console.print("Open the React frontend or run [cyan]threadline status[/cyan] to see the results.\n")


if __name__ == "__main__":
    app()
