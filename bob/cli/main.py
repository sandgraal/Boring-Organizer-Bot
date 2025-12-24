"""Main CLI entrypoint for B.O.B.

Provides commands for indexing, querying, and managing the knowledge base.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from bob import __version__
from bob.config import get_config

console = Console()


def setup_logging() -> None:
    """Configure logging with rich output."""
    config = get_config()

    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format=config.logging.format,
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.version_option(version=__version__, prog_name="bob")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """B.O.B – Boring Organizer Bot.

    A local-first personal knowledge assistant.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    if verbose:
        get_config().logging.level = "DEBUG"

    setup_logging()


@cli.command()
def init() -> None:
    """Initialize the database and configuration."""
    from bob.db import get_database

    console.print("[bold blue]Initializing B.O.B...[/]")

    try:
        db = get_database()
        db.migrate()
        console.print(f"[green]✓[/] Database initialized at [cyan]{db.db_path}[/]")

        if db.has_vec:
            console.print("[green]✓[/] sqlite-vec extension loaded")
        else:
            console.print("[yellow]![/] sqlite-vec not available, using fallback vector search")

        console.print("\n[bold green]B.O.B is ready![/]")
    except Exception as e:
        console.print(f"[red]Error initializing database:[/] {e}")
        sys.exit(1)


@cli.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--project",
    "-p",
    default=None,
    help="Project name (default: from config)",
)
@click.option(
    "--language",
    "-l",
    default=None,
    help="Document language (default: from config)",
)
def index(paths: tuple[str, ...], project: str | None, language: str | None) -> None:
    """Index documents from the specified paths.

    PATHS: One or more file or directory paths to index.
    """
    from bob.index import index_paths

    config = get_config()
    project = project or config.defaults.project
    language = language or config.defaults.language

    console.print("[bold blue]Indexing documents...[/]")
    console.print(f"  Project: [cyan]{project}[/]")
    console.print(f"  Language: [cyan]{language}[/]")
    console.print(f"  Paths: {', '.join(paths)}")
    console.print()

    try:
        stats = index_paths(
            paths=[Path(p) for p in paths],
            project=project,
            language=language,
        )

        console.print("\n[bold green]Indexing complete![/]")
        console.print(f"  Documents processed: [cyan]{stats['documents']}[/]")
        console.print(f"  Chunks created: [cyan]{stats['chunks']}[/]")
        console.print(f"  Skipped (unchanged): [cyan]{stats['skipped']}[/]")
        console.print(f"  Errors: [{'red' if stats['errors'] else 'green'}]{stats['errors']}[/]")
    except Exception as e:
        console.print(f"[red]Error during indexing:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("question")
@click.option(
    "--project",
    "-p",
    default=None,
    help="Filter by project",
)
@click.option(
    "--top-k",
    "-k",
    default=None,
    type=int,
    help="Number of results to retrieve",
)
def ask(question: str, project: str | None, top_k: int | None) -> None:
    """Ask a question and get answers with citations.

    QUESTION: The question to ask.
    """
    from bob.answer import format_answer
    from bob.retrieval import search

    config = get_config()
    top_k = top_k or config.defaults.top_k

    console.print("[bold blue]Searching...[/]\n")

    try:
        results = search(
            query=question,
            project=project,
            top_k=top_k,
        )

        if not results:
            console.print("[yellow]No relevant documents found.[/]")
            console.print("\nTry:")
            console.print("  • Using different keywords")
            console.print("  • Indexing more documents")
            if project:
                console.print("  • Removing the --project filter")
            return

        # Format and display the answer
        formatted = format_answer(question, results)
        console.print(formatted)

    except Exception as e:
        console.print(f"[red]Error during search:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command("extract-decisions")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--project",
    "-p",
    default=None,
    help="Filter by project",
)
def extract_decisions(paths: tuple[str, ...], project: str | None) -> None:
    """Extract decisions from documents.

    PATHS: Optional file paths to extract from. If not specified, extracts from all indexed documents.
    """
    # TODO: Implement decision extraction
    # Next file to edit: bob/extract/decisions.py
    if paths:
        console.print(f"[dim]Paths:[/] {', '.join(paths)}")
    if project:
        console.print(f"[dim]Project filter:[/] {project}")
    console.print("[yellow]Decision extraction is not yet implemented.[/]")
    console.print("\nThis feature will:")
    console.print("  • Scan documents for decision-like statements")
    console.print("  • Extract decision text and context")
    console.print("  • Store in the decisions table")
    console.print("  • Track superseded decisions")
    console.print("\nSee: bob/extract/decisions.py (TODO)")


@cli.command()
@click.option(
    "--project",
    "-p",
    default=None,
    help="Filter by project",
)
def status(project: str | None) -> None:
    """Show the status of the knowledge base."""
    from rich.table import Table

    from bob.db import get_database

    try:
        db = get_database()
        stats = db.get_stats(project)

        console.print("[bold blue]B.O.B Status[/]\n")

        if project:
            console.print(f"Project: [cyan]{project}[/]\n")

        console.print(f"Database: [cyan]{db.db_path}[/]")
        console.print(
            f"Vector Search: [{'green' if stats['has_vec'] else 'yellow'}]"
            f"{'sqlite-vec' if stats['has_vec'] else 'fallback (slower)'}[/]"
        )
        console.print()

        # Statistics table
        table = Table(title="Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Documents", str(stats["document_count"]))
        table.add_row("Chunks", str(stats["chunk_count"]))

        console.print(table)

        # Source types
        if stats["source_types"]:
            console.print("\n[bold]Documents by Type:[/]")
            for source_type, count in stats["source_types"].items():
                console.print(f"  {source_type}: {count}")

        # Projects
        if stats["projects"]:
            console.print("\n[bold]Projects:[/]")
            for proj in stats["projects"]:
                marker = "→ " if proj == project else "  "
                console.print(f"{marker}{proj}")

    except Exception as e:
        console.print(f"[red]Error getting status:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
