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
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON for machine consumption",
)
def ask(question: str, project: str | None, top_k: int | None, output_json: bool) -> None:
    """Ask a question and get answers with citations.

    QUESTION: The question to ask.
    """
    import json

    from bob.answer import format_answer
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

        if output_json:
            # Machine-readable JSON output
            from bob.answer.formatter import get_date_confidence, is_outdated

            json_results = {
                "question": question,
                "project": project,
                "top_k": top_k,
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
            console.print("[yellow]No relevant documents found.[/]")
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


if __name__ == "__main__":
    cli()
