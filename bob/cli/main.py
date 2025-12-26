"""Main CLI entrypoint for B.O.B.

Provides commands for indexing, querying, and managing the knowledge base.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from bob import __version__
from bob.config import get_config
from bob.watchlist import (
    WatchlistEntry,
    add_watchlist_entry,
    get_watchlist_path,
    load_watchlist,
    remove_watchlist_entry,
)

console = Console()

_DURATION_PATTERN = re.compile(r"^(?P<value>\d+)\s*(?P<unit>[dwmy])?$", re.IGNORECASE)


def parse_duration_to_days(raw: str) -> int:
    """Parse a duration string into days (e.g., 90d, 6w, 6m, 1y)."""
    match = _DURATION_PATTERN.match(raw.strip())
    if not match:
        raise click.UsageError(
            "Invalid duration. Use formats like 90d, 6w, 6m, or 1y."
        )
    value = int(match.group("value"))
    unit = (match.group("unit") or "d").lower()
    if value <= 0:
        raise click.UsageError("Duration must be greater than zero.")
    multipliers = {"d": 1, "w": 7, "m": 30, "y": 365}
    return value * multipliers[unit]


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
@click.option(
    "--watchlist",
    "use_watchlist",
    is_flag=True,
    help="Index all paths saved in the watchlist (`bob watchlist list`).",
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
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
def index(
    paths: tuple[str, ...],
    project: str | None,
    language: str | None,
    use_watchlist: bool,
) -> None:
    """Index documents from the specified paths.

    PATHS: One or more file or directory paths to index.
    """
    from bob.index import index_paths

    config = get_config()
    project = project or config.defaults.project
    language = language or config.defaults.language

    if use_watchlist and paths:
        raise click.UsageError("Cannot specify paths when using --watchlist.")
    if not use_watchlist and not paths:
        raise click.UsageError("Provide at least one path to index or use --watchlist.")

    console.print("[bold blue]Indexing documents...[/]")
    if use_watchlist:
        console.print("[dim]Using watchlist entries[/]")
        console.print(f"  Watchlist: [cyan]{get_watchlist_path()}[/]")
        console.print(f"  Default project: [cyan]{project}[/]")
        console.print(f"  Default language: [cyan]{language}[/]")
    else:
        console.print(f"  Project: [cyan]{project}[/]")
        console.print(f"  Language: [cyan]{language}[/]")
        console.print(f"  Paths: {', '.join(paths)}")
    console.print()

    try:
        if use_watchlist:
            entries = load_watchlist()
            if not entries:
                console.print(
                    "[yellow]Watchlist is empty. Add targets with `bob watchlist add`.[/]"
                )
                return

            stats: dict[str, int] = {"documents": 0, "chunks": 0, "skipped": 0, "errors": 0}
            for entry in entries:
                target_path = Path(entry.path)
                target_project = entry.project or project
                target_language = entry.language or language

                if not target_path.exists():
                    console.print(f"[yellow]Skipping missing path:[/] {target_path}")
                    stats["errors"] += 1
                    continue

                result = index_paths(
                    paths=[target_path],
                    project=target_project,
                    language=target_language,
                )
                for key in stats:
                    stats[key] = stats.get(key, 0) + result.get(key, 0)
        else:
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


@cli.group("watchlist")
def watchlist_group() -> None:
    """Manage saved index targets for easy onboarding."""


@watchlist_group.command("add")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--project",
    "-p",
    default=None,
    help="Project name for the target (falls back to global default).",
)
@click.option(
    "--language",
    "-l",
    default=None,
    help="Language for the target (falls back to global default).",
)
def watchlist_add(path: str, project: str | None, language: str | None) -> None:
    """Add a path to the watchlist."""
    entry = WatchlistEntry(path=path, project=project, language=language)
    if add_watchlist_entry(entry):
        console.print(f"[green]✓[/] Added [cyan]{path}[/] to the watchlist.")
    else:
        console.print(f"[yellow]↺[/] {path} is already in the watchlist.")


@watchlist_group.command("list")
def watchlist_list() -> None:
    """List all watchlist targets."""
    entries = load_watchlist()
    watchlist_path = get_watchlist_path()

    if not entries:
        console.print("[yellow]Watchlist is empty. Add targets with `bob watchlist add <path>`.[/]")
        return

    from rich.table import Table

    table = Table(title=f"Watchlist ({watchlist_path})")
    table.add_column("Path", style="cyan")
    table.add_column("Project", style="green")
    table.add_column("Language", style="green")

    for entry in entries:
        table.add_row(
            entry.path,
            entry.project or "-",
            entry.language or "-",
        )

    console.print(table)


@watchlist_group.command("remove")
@click.argument("path", type=click.Path())
def watchlist_remove(path: str) -> None:
    """Remove a path from the watchlist."""
    if remove_watchlist_entry(path):
        console.print(f"[green]✓[/] Removed [cyan]{path}[/] from the watchlist.")
    else:
        console.print(f"[red]✗[/] Path [cyan]{path}[/] was not found in the watchlist.")


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
@click.option(
    "--max-age",
    default=None,
    type=int,
    help="Maximum document age in days (filters out older content)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON for machine consumption",
)
def ask(
    question: str, project: str | None, top_k: int | None, max_age: int | None, output_json: bool
) -> None:
    """Ask a question and get answers with citations.

    QUESTION: The question to ask.
    """
    import json
    from datetime import datetime, timedelta

    from bob.answer import format_answer
    from bob.answer.constants import NOT_FOUND_MESSAGE
    from bob.retrieval import search

    config = get_config()
    top_k = top_k or config.defaults.top_k

    if not output_json:
        console.print("[bold blue]Searching...[/]\n")

    try:
        results = search(
            query=question,
            project=project,
            top_k=top_k,
        )

        # Apply max-age filter if specified
        if max_age is not None and results:
            cutoff = datetime.now() - timedelta(days=max_age)
            original_count = len(results)
            results = [r for r in results if r.source_date is None or r.source_date >= cutoff]
            filtered_count = original_count - len(results)
            if not output_json and filtered_count > 0:
                console.print(
                    f"[dim]Filtered out {filtered_count} results older than {max_age} days[/]\n"
                )

        if output_json:
            # Machine-readable JSON output
            from bob.answer.formatter import get_date_confidence, is_outdated

            json_results = {
                "question": question,
                "project": project,
                "top_k": top_k,
                "max_age_days": max_age,
                "results_count": len(results),
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "content": r.content,
                        "score": r.score,
                        "source": {
                            "path": r.source_path,
                            "type": r.source_type,
                            "locator_type": r.locator_type,
                            "locator_value": r.locator_value,
                        },
                        "metadata": {
                            "project": r.project,
                            "source_date": r.source_date.isoformat() if r.source_date else None,
                            "date_confidence": get_date_confidence(r.source_date),
                            "may_be_outdated": is_outdated(r.source_date),
                            "git_repo": r.git_repo,
                            "git_commit": r.git_commit,
                        },
                    }
                    for r in results
                ],
            }
            console.print(json.dumps(json_results, indent=2))
        elif not results:
            console.print(f"[yellow]{NOT_FOUND_MESSAGE}[/]")
            console.print("\nTry:")
            console.print("  • Using different keywords")
            console.print("  • Indexing more documents")
            if project:
                console.print("  • Removing the --project filter")
        else:
            # Human-readable output with Rich formatting
            formatted = format_answer(question, results)
            console.print(formatted)

    except Exception as e:
        if output_json:
            import json

            console.print(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        console.print(f"[red]Error during search:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("query")
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
@click.option(
    "--max-age",
    default=None,
    type=int,
    help="Maximum document age in days (filters out older content)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON for machine consumption",
)
def search(
    query: str, project: str | None, top_k: int | None, max_age: int | None, output_json: bool
) -> None:
    """Search for relevant documents (retrieval only, no answer synthesis).

    QUERY: The search query. Supports advanced syntax:

    \b
    Exact phrases:    "exact phrase"
    Exclude terms:    -unwanted
    Project filter:   project:name

    \b
    Examples:
        bob search "API configuration"
        bob search "error handling" -deprecated
        bob search deployment project:devops
    """
    import json
    from datetime import datetime, timedelta

    from bob.answer.formatter import get_date_confidence, is_outdated
    from bob.retrieval import search as do_search
    from bob.retrieval.search import enrich_with_decisions, has_superseded_decisions

    config = get_config()
    top_k = top_k or config.defaults.top_k

    if not output_json:
        console.print("[bold blue]Searching...[/]\n")

    try:
        results = do_search(
            query=query,
            project=project,
            top_k=top_k,
        )

        # Enrich with decision info
        results = enrich_with_decisions(results)

        # Apply max-age filter if specified
        if max_age is not None and results:
            cutoff = datetime.now() - timedelta(days=max_age)
            original_count = len(results)
            results = [r for r in results if r.source_date is None or r.source_date >= cutoff]
            filtered_count = original_count - len(results)
            if not output_json and filtered_count > 0:
                console.print(
                    f"[dim]Filtered out {filtered_count} results older than {max_age} days[/]\n"
                )

        if output_json:
            # Machine-readable JSON output
            json_results = {
                "query": query,
                "project": project,
                "top_k": top_k,
                "max_age_days": max_age,
                "results_count": len(results),
                "has_superseded_decisions": has_superseded_decisions(results),
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "content": r.content,
                        "score": r.score,
                        "source": {
                            "path": r.source_path,
                            "type": r.source_type,
                            "locator_type": r.locator_type,
                            "locator_value": r.locator_value,
                        },
                        "metadata": {
                            "project": r.project,
                            "source_date": r.source_date.isoformat() if r.source_date else None,
                            "date_confidence": get_date_confidence(r.source_date),
                            "may_be_outdated": is_outdated(r.source_date),
                            "git_repo": r.git_repo,
                            "git_commit": r.git_commit,
                        },
                        "decisions": [
                            {
                                "id": d.decision_id,
                                "status": d.status,
                                "superseded_by": d.superseded_by,
                                "text": d.decision_text[:100],
                            }
                            for d in r.decisions
                        ]
                        if r.decisions
                        else [],
                    }
                    for r in results
                ],
            }
            console.print(json.dumps(json_results, indent=2))
        elif not results:
            console.print("[yellow]No relevant documents found.[/]")
            console.print("\nTry:")
            console.print("  • Using different keywords")
            console.print('  • Using exact phrases: "exact text"')
            console.print("  • Indexing more documents")
            if project:
                console.print("  • Removing the --project filter")
            if max_age:
                console.print("  • Increasing or removing the --max-age filter")
        else:
            # Human-readable output - show raw search results
            from bob.answer.formatter import (
                format_decision_badge,
                format_superseded_warning,
                highlight_terms,
            )

            console.print(f"Found [cyan]{len(results)}[/] results\n")

            # Show superseded decision warning if applicable
            warning = format_superseded_warning(results)
            if warning:
                console.print(warning)

            for i, r in enumerate(results, 1):
                # Result header
                date_str = r.source_date.strftime("%Y-%m-%d") if r.source_date else "unknown"
                confidence = get_date_confidence(r.source_date)
                outdated = is_outdated(r.source_date)

                # Build header line with decision badge
                header = f"[bold cyan]{i}.[/] [green]{r.source_path}[/]"
                console.print(header, end="")

                # Add decision badge if applicable
                badge = format_decision_badge(r)
                if badge:
                    console.print(" ", end="")
                    console.print(badge, end="")
                console.print()  # Newline

                console.print(f"   Score: {r.score:.3f} | Date: {date_str} | {confidence}")
                if outdated:
                    console.print("   [yellow]⚠️  May be outdated[/]")

                # Locator
                locator_parts = []
                if r.locator_value.get("heading"):
                    locator_parts.append(f'heading: "{r.locator_value["heading"]}"')
                if r.locator_value.get("start_line"):
                    end = r.locator_value.get("end_line", r.locator_value["start_line"])
                    locator_parts.append(f"lines {r.locator_value['start_line']}-{end}")
                if r.locator_value.get("page"):
                    locator_parts.append(f"page {r.locator_value['page']}")
                if locator_parts:
                    console.print(f"   [dim]{' | '.join(locator_parts)}[/]")

                # Content snippet with highlighted terms
                snippet = r.content[:250].replace("\n", " ")
                if len(r.content) > 250:
                    snippet += "..."
                highlighted = highlight_terms(snippet, query)
                console.print("   ", end="")
                console.print(highlighted)
                console.print()

    except Exception as e:
        if output_json:
            import json

            console.print(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        console.print(f"[red]Error during search:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command("extract-decisions")
@click.option(
    "--project",
    "-p",
    default=None,
    help="Filter by project",
)
@click.option(
    "--min-confidence",
    default=0.6,
    type=float,
    help="Minimum confidence threshold (default: 0.6)",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear existing decisions before extracting",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
def extract_decisions(
    project: str | None,
    min_confidence: float,
    clear: bool,
    output_json: bool,
) -> None:
    """Extract decisions from indexed documents.

    Scans indexed documents for decision-like statements (ADRs, "we decided to...",
    explicit decision markers) and stores them in the decisions table.
    """
    import json

    from bob.extract.decisions import (
        clear_decisions,
        extract_decisions_from_project,
        save_decisions,
    )

    if clear:
        count = clear_decisions(project)
        if not output_json:
            console.print(f"[dim]Cleared {count} existing decisions[/]")

    if not output_json:
        console.print("[bold blue]Extracting decisions...[/]\n")
        if project:
            console.print(f"[dim]Project:[/] {project}")
        console.print(f"[dim]Min confidence:[/] {min_confidence}")

    try:
        decisions = extract_decisions_from_project(
            project=project,
            min_confidence=min_confidence,
        )

        if output_json:
            output = {
                "count": len(decisions),
                "decisions": [
                    {
                        "chunk_id": d.chunk_id,
                        "decision_text": d.decision_text,
                        "context": d.context,
                        "decision_type": d.decision_type,
                        "confidence": d.confidence,
                        "rejected_alternatives": d.rejected_alternatives,
                    }
                    for d in decisions
                ],
            }
            console.print(json.dumps(output, indent=2))
        else:
            if not decisions:
                console.print("[yellow]No decisions found.[/]")
            else:
                console.print(f"\n[green]Found {len(decisions)} decisions:[/]\n")

                for _i, d in enumerate(decisions[:20], 1):  # Show first 20
                    confidence_color = (
                        "green"
                        if d.confidence >= 0.9
                        else "yellow"
                        if d.confidence >= 0.7
                        else "dim"
                    )
                    console.print(
                        f"[{confidence_color}]●[/] [{confidence_color}]{d.confidence:.0%}[/] "
                        f"[dim]{d.decision_type or 'unknown'}[/]"
                    )
                    # Truncate long decisions
                    text = (
                        d.decision_text[:200] + "..."
                        if len(d.decision_text) > 200
                        else d.decision_text
                    )
                    console.print(f"  {text}\n")

                if len(decisions) > 20:
                    console.print(f"[dim]... and {len(decisions) - 20} more[/]")

                # Prompt to save
                if click.confirm("\nSave these decisions to the database?", default=True):
                    saved = save_decisions(decisions)
                    console.print(f"[green]✓[/] Saved {saved} decisions")
                else:
                    console.print("[dim]Decisions not saved[/]")

    except Exception as e:
        console.print(f"[red]Error extracting decisions:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command("decisions")
@click.option(
    "--project",
    "-p",
    default=None,
    help="Filter by project",
)
@click.option(
    "--status",
    type=click.Choice(["active", "superseded", "deprecated"]),
    default=None,
    help="Filter by status",
)
@click.option(
    "--older-than",
    default=None,
    help="Filter decisions older than a duration (e.g., 90d, 6w, 6m, 1y).",
)
@click.option(
    "--limit",
    default=50,
    type=int,
    help="Maximum results (default: 50)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
def list_decisions(
    project: str | None,
    status: str | None,
    older_than: str | None,
    limit: int,
    output_json: bool,
) -> None:
    """List extracted decisions.

    Shows decisions stored in the database with their confidence scores,
    types, and source information.
    """
    import json

    from rich.table import Table

    from bob.extract.decisions import get_decisions

    try:
        older_than_days = parse_duration_to_days(older_than) if older_than else None
        decisions = get_decisions(
            project=project,
            status=status,
            older_than_days=older_than_days,
            limit=limit,
        )

        if output_json:
            output = {
                "count": len(decisions),
                "decisions": [
                    {
                        "id": d.id,
                        "decision_text": d.decision_text,
                        "decision_type": d.decision_type,
                        "status": d.status,
                        "confidence": d.confidence,
                        "source_path": d.source_path,
                        "project": d.project,
                        "decision_date": d.decision_date.isoformat() if d.decision_date else None,
                        "extracted_at": d.extracted_at.isoformat(),
                    }
                    for d in decisions
                ],
            }
            console.print(json.dumps(output, indent=2))
        else:
            if not decisions:
                console.print("[yellow]No decisions found.[/]")
                console.print(
                    "\nRun [cyan]bob extract-decisions[/] to extract decisions from documents."
                )
            else:
                console.print(f"[bold blue]Decisions ({len(decisions)})[/]\n")

                table = Table(show_header=True, header_style="bold")
                table.add_column("ID", style="dim", width=4)
                table.add_column("Type", width=12)
                table.add_column("Decision", width=50)
                table.add_column("Conf", width=5)
                table.add_column("Status", width=10)
                table.add_column("Source", width=25)

                for d in decisions:
                    # Truncate long decisions
                    text = (
                        d.decision_text[:47] + "..."
                        if len(d.decision_text) > 50
                        else d.decision_text
                    )
                    text = text.replace("\n", " ")

                    # Color based on status
                    status_color = {
                        "active": "green",
                        "superseded": "yellow",
                        "deprecated": "red",
                    }.get(d.status, "dim")

                    # Color based on confidence
                    conf_color = (
                        "green"
                        if d.confidence >= 0.9
                        else "yellow"
                        if d.confidence >= 0.7
                        else "dim"
                    )

                    source = d.source_path or ""
                    if len(source) > 25:
                        source = "..." + source[-22:]

                    table.add_row(
                        str(d.id),
                        d.decision_type or "-",
                        text,
                        f"[{conf_color}]{d.confidence:.0%}[/]",
                        f"[{status_color}]{d.status}[/]",
                        source,
                    )

                console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing decisions:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command("decision")
@click.argument("decision_id", type=int)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON",
)
def show_decision(decision_id: int, output_json: bool) -> None:
    """Show details for a specific decision.

    DECISION_ID: ID of the decision to show.
    """
    import json

    from rich.panel import Panel

    from bob.extract.decisions import get_decision

    try:
        decision = get_decision(decision_id)

        if not decision:
            console.print(f"[red]Decision {decision_id} not found.[/]")
            sys.exit(1)

        if output_json:
            output = {
                "id": decision.id,
                "decision_text": decision.decision_text,
                "context": decision.context,
                "decision_type": decision.decision_type,
                "status": decision.status,
                "superseded_by": decision.superseded_by,
                "confidence": decision.confidence,
                "source_path": decision.source_path,
                "project": decision.project,
                "decision_date": decision.decision_date.isoformat()
                if decision.decision_date
                else None,
                "extracted_at": decision.extracted_at.isoformat(),
            }
            console.print(json.dumps(output, indent=2))
        else:
            # Color based on status
            status_color = {
                "active": "green",
                "superseded": "yellow",
                "deprecated": "red",
            }.get(decision.status, "dim")

            console.print(f"[bold blue]Decision #{decision.id}[/]\n")

            # Main decision text
            console.print(Panel(decision.decision_text, title="Decision"))

            # Metadata
            console.print(f"\n[bold]Type:[/] {decision.decision_type or 'Not classified'}")
            console.print(f"[bold]Status:[/] [{status_color}]{decision.status}[/]")
            console.print(f"[bold]Confidence:[/] {decision.confidence:.0%}")

            if decision.superseded_by:
                console.print(f"[bold]Superseded by:[/] Decision #{decision.superseded_by}")

            # Context
            if decision.context:
                console.print("\n[bold]Context:[/]")
                console.print(Panel(decision.context, border_style="dim"))

            # Source info
            console.print(f"\n[bold]Source:[/] {decision.source_path or 'Unknown'}")
            console.print(f"[bold]Project:[/] {decision.project or 'None'}")

            if decision.decision_date:
                console.print(f"[bold]Decision Date:[/] {decision.decision_date.date()}")

            console.print(f"[bold]Extracted:[/] {decision.extracted_at.strftime('%Y-%m-%d %H:%M')}")

    except Exception as e:
        console.print(f"[red]Error showing decision:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.command("supersede")
@click.argument("old_id", type=int)
@click.argument("new_id", type=int)
@click.option(
    "--reason",
    "-r",
    default=None,
    help="Reason for supersession",
)
def supersede_decision_cmd(old_id: int, new_id: int, reason: str | None) -> None:
    """Mark a decision as superseded by another.

    OLD_ID: ID of the decision being superseded.
    NEW_ID: ID of the newer decision that replaces it.
    """
    from bob.extract.decisions import get_decision, supersede_decision

    try:
        old = get_decision(old_id)
        new = get_decision(new_id)

        if not old:
            console.print(f"[red]Decision {old_id} not found.[/]")
            sys.exit(1)

        if not new:
            console.print(f"[red]Decision {new_id} not found.[/]")
            sys.exit(1)

        if old.status == "superseded":
            console.print(f"[yellow]Decision {old_id} is already superseded.[/]")
            sys.exit(1)

        # Show what we're doing
        console.print("[bold blue]Superseding decision...[/]\n")

        old_text = (
            old.decision_text[:60] + "..." if len(old.decision_text) > 60 else old.decision_text
        )
        new_text = (
            new.decision_text[:60] + "..." if len(new.decision_text) > 60 else new.decision_text
        )

        console.print(f"[yellow]Old:[/] #{old_id}: {old_text}")
        console.print(f"[green]New:[/] #{new_id}: {new_text}")

        if reason:
            console.print(f"[dim]Reason:[/] {reason}")

        if click.confirm("\nProceed with supersession?", default=True):
            result = supersede_decision(old_id, new_id, reason)

            if result:
                console.print(f"\n[green]✓[/] Decision #{old_id} is now superseded by #{new_id}")
            else:
                console.print("[red]Failed to supersede decision.[/]")
                sys.exit(1)
        else:
            console.print("[dim]Cancelled.[/]")

    except Exception as e:
        console.print(f"[red]Error superseding decision:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@cli.group()
def eval() -> None:
    """Evaluation commands for measuring retrieval quality."""
    pass


@eval.command("run")
@click.argument("golden_path", type=click.Path(exists=True))
@click.option(
    "--k",
    "-k",
    default=5,
    type=int,
    help="Number of results to evaluate (default: 5)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Write results to file",
)
def eval_run(golden_path: str, k: int, output_json: bool, output: str | None) -> None:
    """Run evaluation against a golden dataset.

    GOLDEN_PATH: Path to the golden dataset JSONL file.

    Each line should be JSON with 'question' and optionally 'expected_chunks'.
    """
    from rich.table import Table

    from bob.eval.runner import run_evaluation

    console.print("[bold blue]Running evaluation...[/]\n")

    try:
        result = run_evaluation(golden_path=golden_path, k=k)

        if output_json:
            # JSON output using built-in serialization
            json_str = result.to_json()

            if output:
                Path(output).write_text(json_str)
                console.print(f"[green]✓[/] Results written to [cyan]{output}[/]")
            else:
                console.print(json_str)
        else:
            # Human-readable output
            console.print(f"Golden dataset: [cyan]{golden_path}[/]")
            console.print(f"Queries evaluated: [cyan]{result.num_queries}[/]")
            console.print(f"Top-k: [cyan]{k}[/]\n")

            # Metrics table
            table = Table(title="Evaluation Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Mean", style="green")
            table.add_column("Std Dev", style="yellow")

            table.add_row("Recall@k", f"{result.recall_mean:.4f}", f"±{result.recall_std:.4f}")
            table.add_row(
                "Precision@k", f"{result.precision_mean:.4f}", f"±{result.precision_std:.4f}"
            )
            table.add_row("MRR", f"{result.mrr_mean:.4f}", f"±{result.mrr_std:.4f}")

            console.print(table)

            # Pass/fail summary
            console.print()
            console.print(f"Passed: [green]{result.num_passed}[/] / {result.num_queries}")
            console.print(f"Failed: [red]{result.num_failed}[/] / {result.num_queries}")

            # Quality assessment
            console.print()
            if result.recall_mean >= 0.8:
                console.print("[green]✓[/] Retrieval quality is good")
            elif result.recall_mean >= 0.5:
                console.print("[yellow]![/] Retrieval quality is moderate")
            else:
                console.print("[red]✗[/] Retrieval quality needs improvement")

            if output:
                # Write detailed JSON even in human-readable mode
                Path(output).write_text(result.to_json())
                console.print(f"\n[dim]Results also written to {output}[/]")

    except Exception as e:
        console.print(f"[red]Error during evaluation:[/] {e}")
        if get_config().logging.level == "DEBUG":
            console.print_exception()
        sys.exit(1)


@eval.command("compare")
@click.argument("baseline_path", type=click.Path(exists=True))
@click.argument("current_path", type=click.Path(exists=True))
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
def eval_compare(baseline_path: str, current_path: str, output_json: bool) -> None:
    """Compare two evaluation result files.

    BASELINE_PATH: Path to the baseline evaluation JSON file.
    CURRENT_PATH: Path to the current evaluation JSON file.
    """
    import json

    from rich.table import Table

    try:
        baseline = json.loads(Path(baseline_path).read_text())
        current = json.loads(Path(current_path).read_text())

        metrics = ["recall_mean", "precision_mean", "mrr_mean"]

        if output_json:
            comparison = {
                "baseline": {m: baseline.get(m, 0) for m in metrics},
                "current": {m: current.get(m, 0) for m in metrics},
                "delta": {m: current.get(m, 0) - baseline.get(m, 0) for m in metrics},
            }
            console.print(json.dumps(comparison, indent=2))
        else:
            console.print("[bold blue]Evaluation Comparison[/]\n")

            table = Table(title="Metrics Comparison")
            table.add_column("Metric", style="cyan")
            table.add_column("Baseline", style="yellow")
            table.add_column("Current", style="green")
            table.add_column("Delta", style="magenta")

            for key in metrics:
                baseline_val = baseline.get(key, 0)
                current_val = current.get(key, 0)
                delta = current_val - baseline_val

                delta_str = f"{delta:+.4f}"
                if delta > 0:
                    delta_str = f"[green]{delta_str}[/]"
                elif delta < 0:
                    delta_str = f"[red]{delta_str}[/]"

                table.add_row(
                    key,
                    f"{baseline_val:.4f}",
                    f"{current_val:.4f}",
                    delta_str,
                )

            console.print(table)

            # Summary
            recall_delta = current.get("recall_mean", 0) - baseline.get("recall_mean", 0)
            if recall_delta > 0.05:
                console.print("\n[green]✓[/] Significant improvement in recall")
            elif recall_delta < -0.05:
                console.print("\n[red]✗[/] Regression detected in recall")
            else:
                console.print("\n[yellow]~[/] No significant change")

    except Exception as e:
        console.print(f"[red]Error comparing results:[/] {e}")
        sys.exit(1)


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


@cli.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1 for local-only)",
)
@click.option(
    "--port",
    "-p",
    default=8080,
    type=int,
    help="Port to listen on (default: 8080)",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development",
)
def serve(host: str, port: int, reload: bool) -> None:
    """Start the B.O.B API server.

    Starts a local HTTP API server that the web interface uses.
    The server binds to localhost by default for security.

    WARNING: Binding to 0.0.0.0 exposes the server to your network.
    Only do this if you understand the security implications.
    """
    import uvicorn

    from bob.db import get_database

    # Warn about non-localhost binding
    if host != "127.0.0.1" and host != "localhost":
        console.print(
            f"[bold yellow]⚠️  Warning:[/] Binding to non-localhost address [cyan]{host}[/]"
        )
        console.print("   This exposes the server to your network. B.O.B has no authentication.")
        console.print()

    # Ensure database is initialized
    try:
        db = get_database()
        db.migrate()
    except Exception as e:
        console.print(f"[red]Error initializing database:[/] {e}")
        sys.exit(1)

    console.print("[bold blue]Starting B.O.B API server...[/]")
    console.print(f"  Host: [cyan]{host}[/]")
    console.print(f"  Port: [cyan]{port}[/]")
    console.print(f"  URL: [cyan]http://{host}:{port}[/]")
    console.print(f"  API docs: [cyan]http://{host}:{port}/docs[/]")
    console.print()

    if reload:
        console.print("[yellow]Auto-reload enabled (development mode)[/]")
        console.print()

    console.print("Press [bold]Ctrl+C[/] to stop the server.\n")

    try:
        uvicorn.run(
            "bob.api.app:create_app",
            host=host,
            port=port,
            reload=reload,
            factory=True,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n[bold green]Server stopped.[/]")


@cli.command()
@click.option(
    "--host",
    default=None,
    help="Host to bind to (default from config, localhost only recommended)",
)
@click.option(
    "--port",
    "-p",
    default=None,
    type=int,
    help="Port to listen on (default from config)",
)
def mcp(host: str | None, port: int | None) -> None:
    """Start the B.O.B MCP server for agent interoperability."""
    from bob.agents.mcp_server import run_server
    from bob.config import get_config

    config = get_config()
    target_host = host or config.mcp.host
    if target_host not in {"127.0.0.1", "localhost"}:
        console.print(
            f"[bold yellow]⚠️  Warning:[/] Binding MCP server to [cyan]{target_host}[/]"
        )
        console.print("   This exposes the MCP server to your network. No auth is enabled.")
        console.print()

    run_server(host=host, port=port)


if __name__ == "__main__":
    cli()
