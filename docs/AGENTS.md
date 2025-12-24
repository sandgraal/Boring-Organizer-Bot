# Agent Contracts

> Rules and conventions for AI agents working in the B.O.B repository.

**Last Updated:** 2025-12-24  
**Applies to:** All coding agents, research agents, QA agents, documentation agents

---

## Table of Contents

1. [Core Principles](#core-principles)
2. [Repository Rules](#repository-rules)
3. [Data Rules](#data-rules)
4. [Citation Rules](#citation-rules)
5. [Decision Rules](#decision-rules)
6. [Output Rules](#output-rules)
7. [Safety Rules](#safety-rules)
8. [Stop Conditions](#stop-conditions)

---

## Core Principles

### Local-First Commitment

This repository builds a **local-first** personal knowledge assistant. Agents must:

- ✅ Assume all operations run on user's local machine
- ✅ Keep data local — no cloud uploads or external API calls for core functionality
- ✅ Support offline operation for all core features
- ❌ Never add always-on services, daemons, or background processes
- ❌ Never require internet connectivity for basic indexing/search

### Citation-Grounded Output

Every answer, recommendation, or generated content must be backed by evidence:

- ✅ Cite source files and locators for every claim
- ✅ Include date confidence in all outputs
- ✅ Fail explicitly when no evidence exists
- ❌ Never generate facts without source attribution
- ❌ Never extrapolate beyond what sources support

---

## Repository Rules

### File Organization

```
bob/                    # Python source code
  cli/                  # CLI commands only
  api/                  # FastAPI server and routes
  ui/                   # Static web interface (HTML/CSS/JS)
  db/                   # Database and migrations
  ingest/               # Document parsers
  index/                # Chunking and embedding
  retrieval/            # Search functions
  answer/               # Output formatting
  extract/              # Decision extraction
  eval/                 # Evaluation harness
  agents/               # Agent tool interfaces

prompts/                # Agent prompt templates
  system/               # System prompts
  indexer_agent.md      # Indexer agent prompt
  retrieval_agent.md    # Retrieval agent prompt
  ...

tests/                  # Unit and integration tests
  test_*.py             # Mirror bob/ structure

docs/                   # Documentation
  *.md                  # Architecture, guides, plans

data/                   # LOCAL DATA - GITIGNORED
  bob.db                # User's database
  models/               # Downloaded models
```

### Where to Put Code

| Type of code        | Location                 | Notes                     |
| ------------------- | ------------------------ | ------------------------- |
| CLI commands        | `bob/cli/main.py`        | Use Click decorators      |
| Document parsers    | `bob/ingest/<type>.py`   | Inherit from `BaseParser` |
| Search logic        | `bob/retrieval/`         | Pure functions preferred  |
| API endpoints       | `bob/api/routes/`        | FastAPI route handlers    |
| Web UI assets       | `bob/ui/`                | Static HTML/CSS/JS        |
| Database migrations | `bob/db/migrations/`     | Sequential numbered SQL   |
| Agent tools         | `bob/agents/tools.py`    | Stable API wrappers       |
| Tests               | `tests/test_<module>.py` | Mirror source structure   |

### How to Run Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_chunker.py -v

# Run with coverage
make test-cov

# Run all checks (lint + type + test)
make check
```

### How to Format Code

```bash
# Format with ruff
make format

# Check without fixing
make lint
```

### How to Add Database Migrations

1. Create new file: `bob/db/migrations/NNN_description.sql`
2. Number sequentially (e.g., `003_add_decisions.sql`)
3. Use idempotent SQL (IF NOT EXISTS, etc.)
4. Test migration on fresh database

Example migration:

```sql
-- 003_add_decisions.sql
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    decision_text TEXT NOT NULL,
    context TEXT,
    status TEXT DEFAULT 'decided',
    superseded_by INTEGER REFERENCES decisions(id),
    superseded_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
```

---

## Data Rules

### The /data Directory

The `/data` directory is for **local user data only**:

- ✅ Contains user's SQLite database (`bob.db`)
- ✅ Contains downloaded embedding models
- ✅ May contain evaluation results and logs
- ❌ **NEVER** committed to git (gitignored)
- ❌ **NEVER** contains personal documents or secrets
- ❌ **NEVER** referenced in tests with real content

### Test Data

For tests, use:

- Synthetic test fixtures in `tests/fixtures/`
- Temporary databases via pytest `tmp_path`
- Mock data generators, not real documents

```python
# Good: synthetic test data
def test_chunker():
    content = "# Test Heading\n\nThis is test content."
    chunks = chunk_document(content)
    assert len(chunks) > 0

# Bad: real user data
def test_chunker():
    with open("/data/my-real-notes.md") as f:  # NEVER DO THIS
        content = f.read()
```

### Metadata Requirements

Every piece of indexed data must include:

| Field         | Required | Description                 |
| ------------- | -------- | --------------------------- |
| `project`     | Yes      | Project/collection name     |
| `source_date` | Yes\*    | Document date (ISO 8601)    |
| `language`    | Yes      | ISO 639-1 code (e.g., "en") |
| `source_path` | Yes      | Original file path or URL   |

\*If date cannot be determined, use file modification time and flag as `UNKNOWN` confidence.

---

## Citation Rules

### Locator Format by Source Type

Every search result must include a locator that allows the user to find the exact source:

| Source Type | Locator Format                                 | Example                            |
| ----------- | ---------------------------------------------- | ---------------------------------- |
| Markdown    | `{heading, start_line, end_line}`              | `heading: "Setup" (lines 45-67)`   |
| PDF         | `{page, total_pages}`                          | `page 12/45`                       |
| Word        | `{paragraph_index, parent_heading}`            | `paragraph 5 under "Introduction"` |
| Excel       | `{sheet_name, row_count}`                      | `sheet "Q1 Data", 150 rows`        |
| Recipe      | `{section}`                                    | `section: "ingredients"`           |
| Git         | `{git_file, git_commit, start_line, end_line}` | `README.md@a1b2c3d (lines 10-20)`  |

### Citation Output Format

Every answer must end with a Sources section:

```
[Answer content here]

Sources:
  1. [docs/guide.md] heading: "Configuration" (lines 45-67)
     Date: 2025-03-15 | Confidence: HIGH

  2. [notes/meeting.md] heading: "API Discussion" (lines 12-34)
     Date: 2023-06-20 | Confidence: LOW
     ⚠️  This may be outdated (>6 months old)

Date Confidence: MEDIUM (based on source ages)
```

### When No Evidence Exists

If search returns no relevant results, agents must:

1. **Return explicit "Not Found"** — Do not invent an answer
2. **Suggest alternatives** — Different keywords, broader search
3. **Never fabricate sources** — No made-up citations

```
❌ No relevant documents found for: "quantum flux capacitor setup"

Suggestions:
  • Try different keywords: "configuration", "setup guide"
  • Check if relevant documents are indexed: `bob status`
  • Index more documents: `bob index ./path --project name`

Sources: None
Date Confidence: N/A
```

---

## Decision Rules

### What is a Decision?

A decision is an explicit choice documented in source material:

- ✅ "We decided to use PostgreSQL for the main database"
- ✅ "ADR-001: Authentication will use JWT tokens"
- ✅ "Rejected: GraphQL was considered but REST was simpler"
- ❌ Implicit preferences or undocumented choices
- ❌ Speculation about what might have been decided

### Decision Schema

When extracting decisions, capture:

```yaml
decision:
  id: DEC-001 # Stable identifier
  text: "Use SQLite for local storage" # The decision itself
  date: 2025-01-15 # When decided
  context: "Evaluated Postgres, MySQL" # Why this choice

  rejected_alternatives:
    - option: "PostgreSQL"
      reason: "Requires running a server"
    - option: "MySQL"
      reason: "Heavier than needed"

  status: decided # proposed | decided | superseded | obsolete
  superseded_by: null # DEC-XXX if replaced
  source_chunk_id: 1234 # For citation
```

### Marking Superseded Decisions

When a decision is replaced:

1. Find the original decision by ID
2. Set `status: superseded`
3. Set `superseded_by: <new_decision_id>`
4. New decision should reference what it replaces

```bash
# CLI command
bob supersede DEC-001 DEC-042 --reason "Scaling requirements changed"
```

### Decision Queries

```bash
# List all decided decisions
bob decisions --status decided

# Show decision with full context
bob decision DEC-001

# Search decisions about a topic
bob ask "What did we decide about authentication?" --type decisions
```

---

## Output Rules

### Every Output Must Include

All agent outputs must end with:

```markdown
---

**Sources:**
[List of cited sources with locators]

**Date Confidence:** HIGH | MEDIUM | LOW | UNKNOWN
(Explanation if not HIGH)

**⚠️ This may be outdated** (if any source >6 months old)
```

### Metadata in Structured Output

When generating JSON or structured data:

```json
{
  "answer": "...",
  "sources": [
    {
      "file": "docs/guide.md",
      "locator": { "heading": "Config", "start_line": 45, "end_line": 67 },
      "date": "2025-03-15",
      "confidence": "HIGH"
    }
  ],
  "metadata": {
    "project": "bob",
    "query_date": "2025-12-23",
    "language": "en"
  },
  "warnings": ["Source 2 may be outdated"]
}
```

---

## Safety Rules

### No Background Daemons

- ❌ No file watchers that run continuously
- ❌ No scheduled tasks or cron jobs
- ❌ No services that auto-start
- ✅ All operations triggered by explicit CLI commands

### No Network Calls (Core Features)

- ❌ No telemetry or analytics
- ❌ No license checks requiring internet
- ❌ No cloud storage integration
- ✅ Optional: downloading embedding models (user-initiated)
- ✅ Optional: git clone for external docs (user-initiated)

### No Secrets in Code

- ❌ No API keys in source files
- ❌ No passwords or tokens
- ❌ No personal file paths
- ✅ Use environment variables for optional features
- ✅ Use `.env.example` as template

### Data Isolation

- ❌ Never access files outside specified index paths
- ❌ Never read user's home directory without explicit path
- ❌ Never modify files outside `/data` and `/bob`
- ✅ Respect project boundaries in queries

---

## Stop Conditions

### When Agents Must Stop and Ask for Human Input

1. **Ambiguous requirements** — Multiple valid interpretations
2. **Breaking changes** — Modifications to public API or schema
3. **Security concerns** — Code that could expose data
4. **Missing test coverage** — Cannot verify behavior
5. **Conflicting documentation** — Sources disagree
6. **No evidence found** — Cannot cite sources for answer

### When Agents Must Refuse

1. **Requests to commit /data contents** — Always refuse
2. **Requests to add cloud dependencies** — Explain local-first principle
3. **Requests to add background services** — Explain manual-only principle
4. **Requests to remove citation requirements** — Core to project identity

### Escalation Template

```markdown
## ⚠️ Stopping for Human Input

**Reason:** [Brief description]

**What I found:**

- [Evidence or context]

**Options:**

1. [Option A with implications]
2. [Option B with implications]

**My recommendation:** [If applicable]

**What I need from you:**

- [Specific question or decision needed]
```

---

## Agent Checklist

Before completing any task, verify:

- [ ] All code changes have corresponding tests
- [ ] All outputs include citations with locators
- [ ] All outputs include date confidence
- [ ] No personal data in committed files
- [ ] No background processes added
- [ ] No network dependencies for core features
- [ ] Documentation updated if behavior changed
- [ ] `make check` passes

---

## Sources

- [architecture.md](architecture.md) — System design principles
- [conventions.md](conventions.md) — Code style guide
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Feature roadmap

**Date Confidence:** HIGH (document created 2025-12-23)

---

_This document defines the contract between AI agents and the B.O.B repository. All agents must follow these rules._
