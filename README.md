# B.O.B – Boring Organizer Bot

> A local-first personal knowledge assistant with a beautiful web interface. No cloud required. Just your files, chunked, embedded, and searchable.

## Philosophy

- **Boring is good.** Simple, predictable, maintainable.
- **Local-first.** Your data stays on your machine. No API keys required for core functionality.
- **Citations or nothing.** Every answer includes source file + locator. No hallucinated claims.
- **Date-aware.** Answers include confidence about freshness and warn when content may be outdated.
- **Beautiful & inspectable.** A local web UI that makes source verification one click away.

## Quick Start

### Install

```bash
# Clone the repo
git clone https://github.com/sandgraal/Boring-Organizer-Bot.git
cd Boring-Organizer-Bot

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Initialize the database
bob init
```

### Index Your Documents

```bash
# Index a folder of markdown files
bob index ./my-notes --project "personal-notes"

# Index multiple paths
bob index ./docs ./recipes ./projects --project "everything"

# Index a git repository (README + /docs only)
bob index https://github.com/user/repo --project "external-docs"
```

### Ask Questions

```bash
# Simple query
bob ask "How do I configure logging?"

# Filter by project
bob ask "What are the main ingredients for pasta?" --project "recipes"

# Get more context
bob ask "What decisions were made about the API?" --top-k 10
```

### Output Format

Every answer includes:

```
Answer: [synthesized response based on retrieved chunks]

Sources:
  1. [docs/api.md] heading: "Logging Configuration" (lines 45-67)
     Date: 2024-03-15 | Confidence: HIGH
  2. [notes/decisions.md] heading: "API Design" (lines 12-34)
     Date: 2023-11-20 | Confidence: MEDIUM
     ⚠️  This may be outdated (>6 months old)
```

### Check Status

```bash
# Show indexed documents and stats
bob status

# Show status for specific project
bob status --project "personal-notes"
```

### Web Interface (Coming Soon)

```bash
# Start the local web server
bob serve

# Open http://localhost:8080 in your browser
```

The web UI provides:

- **Ask view**: 3-pane layout with filters, answer, and clickable sources
- **Library**: Browse and manage indexed documents
- **Decisions**: View extracted decisions with status tracking
- **Indexing dashboard**: Monitor indexing progress in real-time

## Configuration

Configuration lives in `bob.yaml` (project root or `~/.config/bob/bob.yaml`):

```yaml
# See bob.yaml.example for full options
database:
  path: ./data/bob.db

embedding:
  model: all-MiniLM-L6-v2
  dimension: 384

defaults:
  project: main
  language: en
```

Environment variables override config:

- `BOB_DB_PATH` – database path
- `BOB_EMBEDDING_MODEL` – embedding model name
- `BOB_DEFAULT_PROJECT` – default project name

## Supported Inputs

| Type                | Extensions                     | Locator Format             |
| ------------------- | ------------------------------ | -------------------------- |
| Markdown            | `.md`, `.markdown`             | heading + line range       |
| PDF                 | `.pdf`                         | page range                 |
| Word                | `.docx`                        | paragraph index            |
| Excel               | `.xlsx`, `.xls`                | sheet + row range          |
| Recipe (structured) | `.recipe.yaml`, `.recipe.json` | section                    |
| Git Docs            | URL or path                    | commit + file + line range |

## Project Structure

```
/bob                 # Python package
  /api               # HTTP API server (Phase 2)
  /ui                # Web interface assets (Phase 3)
  /cli               # CLI commands
  /ingest            # File parsers
  /index             # Chunking and embedding
  /retrieval         # Search and ranking
  /answer            # Citation formatting
  /db                # Database and migrations
/prompts             # Agent prompt templates
/tests               # Unit and integration tests
/docs                # Architecture documentation
/data                # Local data (gitignored)
```

## Documentation

- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) – Phased roadmap
- [UI Plan](docs/UI_PLAN.md) – Interface design specification
- [API Contract](docs/API_CONTRACT.md) – HTTP API endpoints
- [Architecture](docs/architecture.md) – System design
- [Data Model](docs/data-model.md) – Database schema

## Development

```bash
# Run tests
make test

# Format code
make format

# Lint
make lint

# All checks
make check
```

## License

MIT – See [LICENSE](LICENSE)

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
