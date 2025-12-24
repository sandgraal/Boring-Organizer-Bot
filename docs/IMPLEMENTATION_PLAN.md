# B.O.B Implementation Plan

> A phased roadmap for building a local-first, citation-grounded knowledge assistant with a beautiful interface.

**Last Updated:** 2025-12-24  
**Status:** Active  
**Version:** 2.1.0

---

## Table of Contents

1. [Guiding Principles](#guiding-principles)
2. [Boring Defaults](#boring-defaults)
3. [What We Are Not Doing](#what-we-are-not-doing)
4. [Phase 1: Core Retrieval](#phase-1-core-retrieval)
5. [Phase 2: Local API Server](#phase-2-local-api-server)
6. [Phase 3: Web Interface](#phase-3-web-interface)
7. [Track: Answer Audit Trail](#track-answer-audit-trail)
8. [Track: Knowledge Health Dashboard](#track-knowledge-health-dashboard)
9. [Track: Capture Helpers (Templates + Linter)](#track-capture-helpers-templates--linter)
10. [Track: Connectors (Opt-in)](#track-connectors-opt-in)
11. [Track: Agent Interoperability (MCP)](#track-agent-interoperability-mcp)
12. [Track: Coach Mode (Opt-in)](#track-coach-mode-opt-in)
13. [Phase 4: Better Retrieval](#phase-4-better-retrieval)
14. [Phase 5: Decision Layer](#phase-5-decision-layer)
15. [Phase 6: Optional Generation](#phase-6-optional-generation)
16. [Phase 7: Evaluation Harness](#phase-7-evaluation-harness)
17. [Phase 8: Desktop Packaging (Optional)](#phase-8-desktop-packaging-optional)
18. [Timeline Overview](#timeline-overview)

---

## Guiding Principles

1. **Local-first**: All data stays on user's machine. No cloud dependencies for core functionality.
2. **Citation-grounded**: Every claim must be backed by a source. No hallucinations.
3. **Boring technology**: SQLite, Python, simple file parsers. No exotic dependencies.
4. **Manual commands**: User triggers actions explicitly. No background daemons or automation.
5. **Metadata always**: Every piece of data includes: project, date, language, source.

---

## Boring Defaults

These are intentionally simple choices that prioritize reliability over sophistication:

| Category   | Default Choice         | Why                                                |
| ---------- | ---------------------- | -------------------------------------------------- |
| Database   | SQLite + sqlite-vec    | Single file, no server, portable                   |
| Embeddings | `all-MiniLM-L6-v2`     | Fast, 384 dims, good enough for most use cases     |
| Chunking   | 512 tokens, 50 overlap | Standard for retrieval, not too fragmented         |
| Search     | Pure vector similarity | Simple, deterministic, debuggable                  |
| Output     | Plain text + citations | Machine-readable, no formatting magic              |
| Mode       | Boring B.O.B (neutral) | Trust-first default; Coach Mode is opt-in          |
| LLM        | None (Phase 1-5)       | Retrieval is the hard part; generation is optional |
| Interface  | Local web UI           | Browser-native, no build step, inspectable         |
| API        | Local HTTP only        | FastAPI, single-process, manual start              |

---

## What We Are Not Doing

These are explicit non-goals to avoid scope creep:

- ❌ **Cloud sync or collaboration** — This is a personal tool
- ❌ **Real-time file watching** — Index manually when ready
- ❌ **Remote/cloud API** — Local-only; no remote exposure by default
- ❌ **Multiple databases** — One SQLite file per user
- ❌ **Complex ranking models** — Start simple, add complexity only with evidence
- ❌ **Auto-summarization** — Return passages, let user read
- ❌ **Internet search** — Local documents only
- ❌ **Always-on daemons** — Manual server start only
- ❌ **Personal data in repo** — `/data` is gitignored; never commit content
- ❌ **Desktop app (yet)** — Web UI first; Tauri/Electron later if needed
- ❌ **Ambient surveillance** — No screen/audio memory, no passive capture

---

## Phase 1: Core Retrieval

**Goal:** Index documents, search with embeddings, return cited passages without generation.

### Status: 🔄 In Progress

### Features

1. **Ingestion Pipeline**

   - [x] Markdown parser with heading locators
   - [x] PDF parser with page locators
   - [x] Word (.docx) parser with paragraph locators
   - [x] Excel parser with sheet locators
   - [x] Recipe YAML/JSON parser
   - [x] Git repository docs parser
   - [x] Validate all parsers produce consistent locator format

2. **Chunking**

   - [x] Token-based chunking with overlap
   - [x] Preserve locator information across chunks
   - [x] Add chunk quality validation (min content, no boilerplate)

3. **Storage**

   - [x] SQLite database with migrations
   - [x] sqlite-vec for vector similarity
   - [x] Fallback for systems without sqlite-vec
   - [x] Content hash for change detection

4. **Search**

   - [x] Vector similarity search
   - [x] Project filtering
   - [x] Return "No results" gracefully when nothing matches

5. **Output**
   - [x] Citation formatting with locators
   - [x] Date confidence levels
   - [x] "May be outdated" warnings
   - [x] Machine-readable JSON output option

### Acceptance Criteria

- [ ] `bob index ./docs --project test` indexes all supported file types
- [ ] `bob ask "question"` returns relevant passages with citations
- [ ] Every result includes: source file, locator, date, confidence
- [ ] Re-indexing unchanged files is skipped (content hash check)
- [ ] `make test` passes with >80% coverage on core modules

### Test Plan

| Test                | Description                                         | File                      |
| ------------------- | --------------------------------------------------- | ------------------------- |
| Unit: Parsers       | Each parser extracts content and locators correctly | `tests/test_ingest_*.py`  |
| Unit: Chunker       | Chunks respect size limits and preserve locators    | `tests/test_chunker.py`   |
| Unit: Formatter     | Citations format correctly for each locator type    | `tests/test_formatter.py` |
| Integration: Index  | Full pipeline from file to database                 | `tests/test_indexing.py`  |
| Integration: Search | Query returns relevant results                      | `tests/test_search.py`    |

### Risks

| Risk                                      | Impact                         | Mitigation                             |
| ----------------------------------------- | ------------------------------ | -------------------------------------- |
| sqlite-vec not available on all platforms | Users can't search             | Fallback to brute-force numpy search   |
| Large PDFs cause memory issues            | Indexing fails                 | Add file size limits, streaming parser |
| Locators become stale after edits         | Citations point to wrong place | Re-index on file change, warn on date  |

### Definition of Done

- [x] All parsers tested with real documents
- [x] Search returns results for indexed content
- [x] Citations are accurate and verifiable
- [x] CLI commands documented in README
- [x] No regressions in `make check`

---

## Phase 2: Local API Server

**Goal:** Expose core functionality via a local HTTP API that the web UI will consume.

### Status: ✅ Complete

### Prerequisites

- Phase 1 complete (core retrieval working via CLI) ✅

### Features

1. **API Framework**

   - [x] FastAPI server in `bob/api/`
   - [x] Single-process, local-only binding (127.0.0.1)
   - [x] Manual start: `bob serve` command
   - [x] Graceful shutdown on Ctrl+C
   - [x] CORS configured for local development

2. **Core Endpoints**

   - [x] `POST /ask` — Query with answer + citations + footer fields
   - [x] `POST /index` — Start indexing job, return job ID
   - [x] `GET /index/{job_id}` — Get indexing progress and errors
   - [x] `GET /projects` — List all projects
   - [x] `GET /documents` — List documents with filters
   - [x] `POST /open` — Request to open file at locator (returns instruction)

   > **Note:** `GET /decisions` and `GET /recipes` endpoints are Phase 5 features that require the Decision Layer to be implemented first.

3. **Response Format**

   - [x] All responses include structured JSON with consistent schema
   - [x] Every `/ask` response includes: answer, sources[], date_confidence, may_be_outdated
   - [x] Error responses follow RFC 7807 Problem Details
   - [x] "Not found in sources" returned when grounding fails

4. **Job Management**

   - [x] In-memory job queue (single-user, no persistence needed)
   - [x] Progress reporting via polling

   > **Note:** Job cancellation is a nice-to-have for Phase 4+.

### Acceptance Criteria

- [x] `bob serve` starts server on localhost:8080 (configurable)
- [x] `POST /index` starts background job and returns immediately
- [x] API only binds to localhost by default
- [x] All endpoints documented with OpenAPI spec

> **Note:** Performance benchmark (`<500ms for 10k chunks`) to be validated in Phase 4 with real-world data.

### Test Plan

| Test               | Description                               | File                         |
| ------------------ | ----------------------------------------- | ---------------------------- |
| Unit: Endpoints    | Each endpoint returns correct schema      | `tests/test_api.py` ✅       |
| Integration: Ask   | Full query pipeline via API               | `tests/test_api_ask.py`      |
| Integration: Index | Indexing job lifecycle via API            | `tests/test_api_index.py`    |
| Security: Binding  | Server only accepts localhost connections | `tests/test_api_security.py` |

### Risks

| Risk                            | Impact             | Mitigation                            |
| ------------------------------- | ------------------ | ------------------------------------- |
| API adds latency vs direct call | Slower queries     | Keep serialization minimal            |
| Port conflicts                  | Server won't start | Configurable port, clear error msg    |
| Concurrent requests on indexing | Race conditions    | Single-threaded queue, reject if busy |

### Definition of Done

- [x] API server starts and serves requests
- [x] OpenAPI spec generated and accurate
- [x] All endpoints tested with example requests
- [x] Documentation in API_CONTRACT.md complete
- [x] No security exposure beyond localhost

---

## Phase 3: Web Interface

**Goal:** Ship a beautiful, citation-first local web UI that makes B.O.B accessible without CLI.

### Status: ✅ Complete

### Prerequisites

- Phase 2 complete (API server working) ✅

### Features

1. **Tech Stack**

   - [x] Static HTML/CSS/JS served by the API server
   - [x] No build step required (vanilla JS or lightweight bundled)
   - [x] Single `bob/ui/` directory with all assets
   - [x] Served at `http://localhost:8080/` when server runs

2. **Core Screens**

   - [x] **Ask (3-pane layout)**
     - Left: Project filter sidebar
     - Center: Query input + Answer display
     - Right: Sources panel with click-to-open
   - [x] **Library/Browse**
     - Document list with filters (project, type, date)
     - Document preview with chunk breakdown
   - [x] **Indexing Dashboard**
     - Current job progress
     - History of indexed paths
     - Error log display

   > **Note:** Decisions View and Recipes View will be added when Phase 5 (Decision Layer) is implemented. These are enhancement features, not blockers for Phase 3 completion.

3. **Citation Behaviors**

   - [x] Every source is clickable
   - [x] Click opens file at exact locator (via `/open` endpoint)
   - [x] If file can't be opened, show path + locator for manual access
   - [x] Locator display: heading name, line range, or page number

4. **Answer Footer (mandatory)**

   - [x] Sources section always visible
   - [x] Date confidence badge (HIGH/MEDIUM/LOW)
   - [x] "This may be outdated" warning when applicable
   - [x] "Not found in sources" message when grounding fails

5. **Responsive Design**

   - [x] Works on desktop browsers (Chrome, Firefox, Safari)
   - [x] Minimum viable mobile support (single-column layout)
   - [x] Dark mode support

### Acceptance Criteria

- [x] User can ask a question and see answer with clickable sources
- [x] User can click a source and open the file at the exact location
- [x] Indexing progress is visible during `POST /index` job
- [x] Every answer shows Sources + Date confidence + outdated warning
- [x] "Not found in sources" appears when no relevant chunks exist
- [x] UI works without internet connection (all assets local)

### Test Plan

| Test              | Description                                | File                   |
| ----------------- | ------------------------------------------ | ---------------------- |
| Smoke: Load       | All pages load without JS errors           | `tests/test_api.py` ✅ |
| E2E: Ask flow     | Query → Answer → Click source              | Manual testing         |
| E2E: Index flow   | Start indexing → See progress → Complete   | Manual testing         |
| Visual: Citations | Footer always present with required fields | Manual inspection      |

### Risks

| Risk                     | Impact                | Mitigation                         |
| ------------------------ | --------------------- | ---------------------------------- |
| JS complexity grows      | Maintenance burden    | Keep vanilla, add framework later  |
| File opening fails on OS | Bad UX                | Fallback to showing path + locator |
| Asset caching issues     | Stale UI after update | Version query params, cache-bust   |

### Definition of Done

- [x] All core screens implemented and functional
- [x] Click-to-open works for markdown, PDF, and code files
- [x] Answer footer appears on every query result
- [x] UI documented in UI_PLAN.md
- [x] No external network requests (fully local)

---

## Track: Answer Audit Trail

**Goal:** Make trust visible by showing what was retrieved, what was used, and what was rejected.

### Status: 🔜 Not Started

### Prerequisites

- Phase 2 complete (API server) ✅
- Phase 3 complete (Ask UI) ✅

### Features

1. **Audit Panel (Ask UI)**

   - [ ] Show retrieved chunks ranked with scores
   - [ ] Mark which chunks were used in the final answer
   - [ ] Surface unused chunks for transparency

2. **Unsupported Claim Detection**

   - [ ] Detect answer spans without citations
   - [ ] Remove or mark unsupported spans before rendering
   - [ ] Expose unsupported spans in audit payload

3. **Copy as Report**

   - [ ] Export answer + sources in a clean, shareable format
   - [ ] Optional inclusion of retrieved/used lists
   - [ ] Preserve locators and date confidence

### Acceptance Criteria

- [ ] Audit panel shows top-k retrieved chunks and scores
- [ ] Used chunks are clearly labeled and linked to citations
- [ ] Unsupported claims never appear unmarked in the answer
- [ ] "Copy as report" output is consistent and citation-complete

### Test Plan

| Test                         | Description                                       | File                    |
| ---------------------------- | ------------------------------------------------- | ----------------------- |
| Unit: Claim validator        | Unsupported spans detected and removed/marked     | `tests/test_audit.py`   |
| Integration: /ask audit data | API returns retrieved + used + unsupported fields | `tests/test_api_ask.py` |
| UI: Audit panel              | Panel renders and filters correctly               | Manual + E2E            |

### Risks

| Risk                          | Impact                | Mitigation                            |
| ----------------------------- | --------------------- | ------------------------------------- |
| Audit data is confusing       | Trust decreases       | Clear labeling + defaults hidden      |
| Claim validation false alarms | Missing info          | Conservative matching and warnings    |
| Report export drifts          | Inconsistent citations | Golden tests for report format        |

### Definition of Done

- [ ] Audit payload returned in /ask
- [ ] UI panel shows retrieved vs used chunks
- [ ] Unsupported claims are blocked or marked
- [ ] Report export works offline

---

## Track: Knowledge Health Dashboard

**Goal:** Provide a reliability dashboard for coverage, metadata hygiene, staleness, and ingestion breakage.

### Status: 🔜 Not Started

### Prerequisites

- Phase 1 complete (index + retrieval) ✅
- Phase 2 complete (API server) ✅

### Features

1. **Coverage Metrics**

   - [ ] Low indexed volume per project
   - [ ] Low retrieval hit rate per project

2. **Metadata Hygiene**

   - [ ] Missing project/date/language/source counts
   - [ ] Top offenders by file count

3. **Staleness Radar**

   - [ ] Decisions/notes older than thresholds
   - [ ] Configurable age buckets (3/6/12 months)

4. **Ingestion Failures**

   - [ ] PDFs with no text
   - [ ] Parse errors and oversized files
   - [ ] Recent failures list with file paths

5. **Fix Queue**
   - [ ] One-click list of highest-impact cleanup tasks
   - [ ] Links to open file or re-index path

### Acceptance Criteria

- [ ] Dashboard page shows coverage, hygiene, staleness, failures
- [ ] Fix queue lists actionable items with open/reindex actions
- [ ] Metrics update after indexing runs

### Test Plan

| Test                   | Description                          | File                        |
| ---------------------- | ------------------------------------ | --------------------------- |
| Unit: Metrics          | Coverage and hygiene computed        | `tests/test_health.py`      |
| Integration: Dashboard | API returns dashboard payload        | `tests/test_api_health.py`  |
| UI: Health view        | Dashboard renders and links work     | Manual + E2E                |

### Risks

| Risk                     | Impact            | Mitigation                       |
| ------------------------ | ----------------- | -------------------------------- |
| Metrics are noisy        | Confusion         | Clear thresholds + explanations |
| Dashboard becomes heavy  | Slow UI           | Cache and incremental updates    |

### Definition of Done

- [ ] Dashboard metrics are available via API
- [ ] UI shows health signals and fix queue
- [ ] Coach Mode can read dashboard metrics

---

## Track: Capture Helpers (Templates + Linter)

**Goal:** Improve capture consistency with structured templates and quality linting.

### Status: 🔜 Not Started

### Prerequisites

- Phase 2 complete (API server) ✅
- Phase 3 complete (UI) ✅

### Features

1. **Built-in Templates**

   - [ ] Decision
   - [ ] Experiment / evaluation
   - [ ] Trip plan + trip debrief
   - [ ] Recipe (structured fields)
   - [ ] Meeting / daily log

2. **New Note Workflow**

   - [ ] "New note" UI action writes template into vault
   - [ ] Local-first file creation only (no cloud)
   - [ ] Template variables (date, project) expanded on creation

3. **Capture Linter**
   - [ ] Flag "Decision without rationale"
   - [ ] Flag "Decision missing rejected options"
   - [ ] Surface lint warnings in UI and API

### Acceptance Criteria

- [ ] Templates ship in repo and are selectable in UI
- [ ] New note writes file to configured vault path
- [ ] Linter flags missing required sections with low false positives

### Test Plan

| Test                 | Description                             | File                       |
| -------------------- | --------------------------------------- | -------------------------- |
| Unit: Templates      | Template rendering and variable fill    | `tests/test_templates.py`  |
| Unit: Linter         | Lint rules detect missing fields        | `tests/test_linter.py`     |
| Integration: New note | API writes new note with template       | `tests/test_api_notes.py`  |

---

## Track: Connectors (Opt-in)

**Goal:** Add safe, explicit capture connectors without ambient surveillance.

### Status: 🔜 Not Started

### Prerequisites

- Phase 1 complete (ingestion + indexing) ✅
- Phase 2 complete (API server) ✅

### Features

1. **Bookmarks Import**

   - [ ] Import browser HTML export
   - [ ] Convert to local markdown files for indexing
   - [ ] Preserve folder hierarchy as metadata

2. **Manual Highlights**

   - [ ] "Save highlight to vault" action from UI
   - [ ] Prompt for project + source URL
   - [ ] Store highlight as a local note

3. **PDF Annotation Import (Optional)**
   - [ ] Import highlights from local PDF reader exports
   - [ ] Link annotations back to source PDF

### Acceptance Criteria

- [ ] Bookmarks import creates local notes without network calls
- [ ] Manual highlights are stored as local files and indexed
- [ ] PDF annotations import is opt-in and best-effort

### Test Plan

| Test                   | Description                               | File                           |
| ---------------------- | ----------------------------------------- | ------------------------------ |
| Unit: Bookmarks parser | Parses HTML export correctly              | `tests/test_bookmarks.py`      |
| Integration: Import    | End-to-end import and indexing            | `tests/test_api_connectors.py` |

---

## Track: Agent Interoperability (MCP)

**Goal:** Provide a minimal MCP-compatible local tool server for agent ecosystems.

### Status: 🔜 Not Started

### Prerequisites

- Phase 2 complete (API server) ✅

### Features

1. **MCP Server (Local)**

   - [ ] Expose search/ask with citations
   - [ ] Read/write note
   - [ ] List projects
   - [ ] Index status

2. **Permissioning**

   - [ ] Allowed paths list
   - [ ] Read/write scopes
   - [ ] Dry-run mode for writes

3. **Compatibility**
   - [ ] MCP JSON-RPC framing
   - [ ] Explicit errors for denied actions

### Acceptance Criteria

- [ ] MCP server runs locally and is opt-in
- [ ] Permissions enforced for all tools
- [ ] Tool responses include citations where applicable

### Test Plan

| Test                 | Description                         | File                       |
| -------------------- | ----------------------------------- | -------------------------- |
| Unit: Permissions    | Deny/allow rules enforced           | `tests/test_mcp_auth.py`   |
| Integration: MCP API | Tools work end-to-end               | `tests/test_mcp_server.py` |

---

## Track: Coach Mode (Opt-in)

**Goal:** Add an optional, non-intrusive coaching layer that provides bounded suggestions without weakening grounded answers.

### Status: 🔜 Not Started

### Prerequisites

- Phase 3 complete (baseline Ask flow with citations-first footer) ✅

### Features

1. **Mode + UX Controls**

   - [ ] Default mode is **Boring B.O.B** (neutral, no unsolicited suggestions)
   - [ ] Coach Mode is opt-in per session (Ask screen toggle)
   - [ ] Persisted setting with per-project overrides

2. **Suggestion Engine (Deterministic)**

   - [ ] Generate suggestions from retrieval metadata, indexing stats, health signals, and decision gaps
   - [ ] No LLM required for Phase 1; deterministic rules only
   - [ ] Optional LLM-assisted phrasing later, post-filtered

3. **Output Constraints**

   - [ ] Suggestions never alter the grounded answer
   - [ ] Suggestions appear only in a separate "Suggestions (Coach Mode)" section
   - [ ] Max 3 suggestions, each with a "Why" line

4. **Gating + Cooldowns**

   - [ ] Respect gating rules (low confidence, low source count, not-found)
   - [ ] Cooldown per suggestion type per project (default 7 days)

5. **Storage**

   - [ ] Persist user settings (global + per-project)
   - [ ] Log suggestion fingerprints to prevent repeats

### Acceptance Criteria

- [ ] Coach Mode off yields zero suggestions
- [ ] Coach Mode on shows suggestions in a separate section (max 3)
- [ ] Suggestions never violate citation rules or alter base answer
- [ ] "Not found in sources" answers only get coverage/capture suggestions
- [ ] Cooldown prevents repeated suggestions within the configured window
- [ ] Default mode remains Boring B.O.B across sessions and projects

### Test Plan

| Test                      | Description                                               | File                         |
| ------------------------- | --------------------------------------------------------- | ---------------------------- |
| Unit: Gating rules        | Coach rules enforce limits by confidence/source count     | `tests/test_coach_rules.py`  |
| Unit: Cooldown            | Repeated suggestions suppressed within cooldown window    | `tests/test_coach_rules.py`  |
| Integration: Low confidence | LOW confidence answers return at most 1 suggestion       | `tests/test_api_ask.py`      |
| Integration: No sources   | Not-found answers only return coverage suggestions        | `tests/test_api_ask.py`      |
| UI: Toggle + settings     | Toggle controls per-session and per-project persistence   | Manual + E2E                 |

### Risks

| Risk                                 | Impact                         | Mitigation                                  |
| ------------------------------------ | ------------------------------ | ------------------------------------------- |
| Suggestions feel nagging or noisy    | User distrust                  | Cooldowns + max 3 + opt-in only             |
| Suggestions drift into speculation   | Trustworthiness compromised    | Evidence-only or labeled hypothesis + gates |
| UI clutter reduces readability       | Answer harder to verify        | Separate section after required footer      |

### Definition of Done

- [ ] Coach Mode is opt-in with persisted per-project settings
- [ ] Suggestions are bounded, deterministic, and citation-safe
- [ ] Cooldowns prevent repeated prompts within 7 days
- [ ] Documentation in COACH_MODE_SPEC.md complete

---

## Phase 4: Better Retrieval

**Goal:** Improve search quality with hybrid scoring, metadata boosts, and citation precision.

### Status: 🔄 In Progress

### Features

1. **Hybrid Scoring**

   - [x] Combine vector similarity with BM25-style keyword matching
   - [x] Configurable weight between semantic and keyword scores
   - [x] Score normalization for consistent ranking

2. **Metadata Boosts**

   - [x] Boost recent documents (configurable decay)
   - [ ] Boost documents from same project as query context
   - [ ] Boost documents matching query language
   - [x] Configurable boost weights in `bob.yaml`

3. **Citation Precision**

   - [ ] Narrow locators to most relevant paragraph within chunk
   - [ ] Support line-level citations for code/markdown
   - [x] Highlight matching terms in output

4. **Date Confidence Logic**

   - [ ] Parse dates from document content (not just file metadata)
   - [ ] Detect "as of" and "updated" statements
   - [ ] Inherit date from parent document for sub-sections
   - [ ] Add `--max-age` filter to search

5. **Search Improvements**
   - [x] Support quoted phrases for exact matching
   - [x] Support `-term` for exclusion
   - [x] Support `project:name` inline filter
   - [x] `bob search` command for retrieval-only queries
   - [x] `--max-age` filter to exclude old documents

### Acceptance Criteria

- [x] Hybrid search outperforms pure vector search on golden set
- [x] Recent documents rank higher (when relevance is similar)
- [x] `bob ask "exact phrase"` returns only exact matches
- [ ] Date confidence reflects actual document age, not just file mtime

### Test Plan

| Test                    | Description                             | File                           |
| ----------------------- | --------------------------------------- | ------------------------------ |
| Unit: Hybrid scorer     | Combined score is weighted correctly    | `tests/test_scoring.py`        |
| Unit: Date parser       | Dates extracted from various formats    | `tests/test_date_parser.py`    |
| Eval: Retrieval quality | Compare retrieval metrics on golden set | `tests/test_eval_retrieval.py` |

### Risks

| Risk                       | Impact            | Mitigation                              |
| -------------------------- | ----------------- | --------------------------------------- |
| Hybrid scoring too complex | Debugging is hard | Keep weights simple, log scores         |
| Date parsing errors        | Wrong confidence  | Fallback to file mtime, log warnings    |
| Performance degradation    | Slow queries      | Add benchmarks, profile before shipping |

### Definition of Done

- [ ] Hybrid search implemented and tested
- [ ] Metadata boosts configurable
- [ ] Retrieval metrics tracked in evaluation harness
- [ ] No performance regression (query time <500ms for 10k chunks)

---

## Phase 5: Decision Layer

**Goal:** Extract, store, and query decisions from documents with full traceability.

### Status: ✅ Complete

### Features

1. **Decision Extraction**

   - [x] Pattern-based extraction (regex + heuristics)
   - [x] Support common formats: ADRs, decision logs, meeting notes
   - [x] Extract: decision text, date, context, alternatives rejected
   - [x] Confidence score for extraction quality

2. **Decision Lifecycle**

   - [x] Decision ID (auto-generated, stable)
   - [x] Decision text (the actual decision)
   - [x] Context (why this decision was made)
   - [x] Rejected alternatives (what was not chosen and why)
   - [ ] Status: `proposed`, `decided`, `superseded`, `obsolete`
   - [ ] Superseded by (link to replacement decision) + chronology
   - [ ] Review cadence view (manual): filter by age + project
   - [x] Source chunk ID (for citation back to original)

3. **CLI Commands**

   - [x] `bob extract-decisions [--project]` — Scan and extract decisions
   - [ ] `bob decisions [--status decided]` — List decisions
   - [x] `bob decision <id>` — Show decision details with full context
   - [x] `bob supersede <old_id> <new_id>` — Mark decision as superseded
   - [ ] `bob decisions --older-than 6m --project cdc` — Review cadence filter

4. **Integration with Search**
   - [x] `bob search` shows decision badges on results
   - [ ] Decision results show lifecycle status and supersession info
   - [ ] Warn if returning a superseded/obsolete decision

### Acceptance Criteria

- [ ] Decision states include proposed/decided/superseded/obsolete
- [ ] Superseded decisions link to replacements with chronology
- [ ] Review cadence view lists older decisions by project
- [ ] Search can filter by decision lifecycle state

### Test Plan

| Test             | Description                                  | File                                |
| ---------------- | -------------------------------------------- | ----------------------------------- |
| Unit: Patterns   | Decision patterns match expected text        | `tests/test_decision_patterns.py`   |
| Unit: Extraction | Decisions extracted with correct fields      | `tests/test_decision_extraction.py` |
| Integration: CLI | `extract-decisions` command works end-to-end | `tests/test_cli_decisions.py`       |

### Risks

| Risk                         | Impact                          | Mitigation                                      |
| ---------------------------- | ------------------------------- | ----------------------------------------------- |
| Low precision extraction     | False positives clutter results | High confidence threshold, manual review option |
| Complex supersession chains  | Confusing output                | Show chain clearly, limit depth                 |
| Performance on large corpora | Slow extraction                 | Batch processing, incremental updates           |

### Definition of Done

- [ ] Decision lifecycle implemented with new states
- [ ] Supersession relationships tracked with chronology
- [ ] Review cadence queries documented
- [ ] Extraction precision remains >80%

---

## Phase 6: Optional Generation

**Goal:** Add optional LLM generation with strict grounding (no hallucinations).

### Status: 🔜 Not Started

### Features

1. **Local LLM Support**

   - [ ] llama.cpp integration via `llama-cpp-python`
   - [ ] Configurable model path in `bob.yaml`
   - [ ] Support for common GGUF models
   - [ ] CPU inference (no GPU required)

2. **Grounded Generation**

   - [ ] Prompt template that enforces citation
   - [ ] Model can only use provided passages
   - [ ] Must cite source for every claim
   - [ ] "I don't know" when evidence insufficient

3. **Output Format**

   - [ ] Generated answer clearly marked as synthesized
   - [ ] Inline citations: `[1]`, `[2]`, etc.
   - [ ] Sources section after answer
   - [ ] Date confidence and freshness warnings

4. **Safety Rails**

   - [ ] No generation if retrieval returns nothing
   - [ ] Refuse to answer if passages are all low-confidence
   - [ ] Log prompt and response for debugging
   - [ ] `--no-generate` flag to skip LLM (retrieval only)
   - [ ] Claim-level validation to remove or mark unsupported spans

5. **CLI Changes**
   - [ ] `bob ask "question" --generate` — Enable generation
   - [ ] `bob generate` — Configure LLM settings
   - [ ] Default: retrieval only (opt-in generation)

### Acceptance Criteria

- [ ] Generated answers cite sources correctly
- [ ] No hallucinated facts (verified on golden set)
- [ ] `--no-generate` returns same results as Phase 1
- [ ] Works offline with local GGUF model

### Test Plan

| Test               | Description                          | File                              |
| ------------------ | ------------------------------------ | --------------------------------- |
| Unit: Prompt       | Grounding prompt formatted correctly | `tests/test_prompts.py`           |
| Eval: Groundedness | Generated claims have citations      | `tests/test_eval_groundedness.py` |
| Integration: LLM   | End-to-end generation works          | `tests/test_llm_integration.py`   |

### Risks

| Risk               | Impact            | Mitigation                                    |
| ------------------ | ----------------- | --------------------------------------------- |
| LLM hallucinations | False information | Strict prompt, post-hoc verification          |
| Slow inference     | Bad UX            | Streaming output, model size limits           |
| Large model files  | Storage burden    | Document requirements, support smaller models |

### Definition of Done

- [ ] Local LLM runs without network
- [ ] Every claim in output is cited
- [ ] Groundedness evaluation shows >95% citation rate
- [ ] User can opt-out of generation entirely

---

## Phase 7: Evaluation Harness

**Goal:** Build a repeatable evaluation framework with golden Q/A sets and regression tests.

### Status: 🔜 Not Started

### Features

1. **Golden Dataset**

   - [ ] JSON Lines format for Q/A pairs
   - [ ] Fields: question, expected_chunks, expected_answer (optional)
   - [ ] Small golden sets per domain (Food/Travel/CDC/Construction/Business)
   - [ ] Tool to create Q/A pairs from existing indexed content

2. **Retrieval Metrics**

   - [ ] Recall@k — Are expected chunks in top k?
   - [ ] Precision@k — What fraction of top k is relevant?
   - [ ] MRR — Mean Reciprocal Rank of first relevant chunk
   - [ ] Per-query breakdown for debugging

3. **Generation Metrics** (Phase 4+)

   - [ ] Groundedness — All claims cited?
   - [ ] Faithfulness — Claims match source?
   - [ ] Answer relevance — Addresses the question?

4. **Regression Runner**

   - [ ] `bob eval run` — Run all evaluations
   - [ ] `bob eval compare <baseline>` — Compare against previous run
   - [ ] Output: summary table + detailed JSON
   - [ ] CI integration (run on PR)

5. **Drift Detection UI**

   - [ ] UI page showing regression status
   - [ ] "Answers changed since last week" diff view
   - [ ] Per-domain delta summary

6. **Artifacts**
   - [ ] `docs/eval/example_gold.jsonl` — Example golden set
   - [ ] `tests/test_eval_runner.py` — Evaluation runner tests
   - [ ] `bob/eval/` — Evaluation module

### Acceptance Criteria

- [ ] Example golden set with at least 20 Q/A pairs
- [ ] Golden sets exist for core domains
- [ ] `bob eval run` produces metrics report
- [ ] Metrics are reproducible (same input → same output)
- [ ] Regressions detected on golden set changes
- [ ] UI shows regressions and answer drift deltas

### Test Plan

| Test              | Description                     | File                             |
| ----------------- | ------------------------------- | -------------------------------- |
| Unit: Metrics     | Metric calculations are correct | `tests/test_eval_metrics.py`     |
| Unit: Runner      | Evaluation runs without errors  | `tests/test_eval_runner.py`      |
| Integration: Full | End-to-end eval on example set  | `tests/test_eval_integration.py` |

### Risks

| Risk                 | Impact                 | Mitigation                              |
| -------------------- | ---------------------- | --------------------------------------- |
| Golden set too small | Metrics not meaningful | Commit to minimum size, grow over time  |
| Flaky metrics        | False regressions      | Use deterministic settings, seed random |
| Evaluation is slow   | Blocks CI              | Run subset on PR, full on merge         |

### Definition of Done

- [ ] Golden dataset created and documented
- [ ] Retrieval metrics implemented and tested
- [ ] Regression baseline established
- [ ] CI runs evaluation on every PR

---

## Timeline Overview

| Phase       | Focus                   | Prerequisites | Est. Duration |
| ----------- | ----------------------- | ------------- | ------------- |
| **Phase 1** | Core Retrieval          | —             | 2-3 weeks     |
| **Phase 2** | Local API Server        | Phase 1       | 1-2 weeks     |
| **Phase 3** | Web Interface           | Phase 2       | 2-3 weeks     |
| **Track**   | Answer Audit Trail      | Phase 3       | 1-2 weeks     |
| **Track**   | Knowledge Health        | Phase 2       | 1-2 weeks     |
| **Track**   | Capture Helpers         | Phase 3       | 1-2 weeks     |
| **Track**   | Connectors              | Phase 2       | 1-2 weeks     |
| **Track**   | Agent Interop (MCP)      | Phase 2       | 1-2 weeks     |
| **Track**   | Coach Mode (Opt-in)      | Phase 3       | 1-2 weeks     |
| **Phase 4** | Better Retrieval        | Phase 1       | 2 weeks       |
| **Phase 5** | Decision Layer          | Phase 1       | 2-3 weeks     |
| **Phase 6** | Optional Generation     | Phase 4       | 2 weeks       |
| **Phase 7** | Evaluation Harness      | Phase 1       | 1-2 weeks     |
| **Phase 8** | Desktop Packaging (opt) | Phase 3       | 2-3 weeks     |

**Critical Path:** Phase 1 → Phase 2 → Phase 3 (delivers usable UI)

Tracks can proceed after Phase 2/3 and in parallel with Phases 4, 5, and 7.
Phase 8 is optional and only triggered if desktop packaging is needed.

---

## Phase 8: Desktop Packaging (Optional)

**Goal:** Wrap the local web UI in a native desktop application for easier distribution.

### Status: 🔜 Not Started (Conditional)

### Prerequisites

- Phase 3 complete and stable
- User feedback indicates desktop app is needed

### Why Optional

The local web UI (Phase 3) already provides:

- Full functionality via browser
- No installation beyond Python
- Cross-platform support

A desktop wrapper adds:

- Single-click launch
- System tray integration
- Native file associations
- Offline-first distribution

### Triggers for Phase 8

Consider this phase if:

- Users struggle with `bob serve` workflow
- File opening via browser is unreliable
- Distribution to non-technical users needed
- System integration (tray, notifications) requested

### Features (if triggered)

1. **Tauri Wrapper (preferred)**

   - [ ] Rust backend with existing Python server
   - [ ] Small binary size (<10MB)
   - [ ] Native file dialogs
   - [ ] System tray with status

2. **Alternative: Electron**

   - [ ] Use if Tauri proves too complex
   - [ ] Larger size (~100MB) but simpler setup

3. **Distribution**
   - [ ] macOS .dmg with code signing
   - [ ] Windows .msi or portable .exe
   - [ ] Linux AppImage

### Definition of Done (if triggered)

- [ ] Desktop app launches and embeds web UI
- [ ] File opening works natively
- [ ] Can be distributed without Python installed
- [ ] Auto-start option available

---

## Appendix: File Structure After All Phases

```
bob/
├── __init__.py
├── config.py
├── cli/
│   └── main.py
├── api/                  # Phase 2
│   ├── __init__.py
│   ├── server.py
│   ├── routes/
│   │   ├── ask.py
│   │   ├── index.py
│   │   ├── documents.py
│   │   └── open.py
│   └── schemas.py
├── ui/                   # Phase 3
│   ├── index.html
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── app.js
│   │   ├── ask.js
│   │   ├── library.js
│   │   └── indexing.js
│   └── components/
│       └── *.html
├── db/
│   ├── database.py
│   └── migrations/
├── ingest/
│   ├── markdown.py
│   ├── pdf.py
│   └── ...
├── index/
│   ├── chunker.py
│   ├── embedder.py
│   └── indexer.py
├── retrieval/
│   ├── search.py
│   ├── hybrid.py        # Phase 4
│   └── scoring.py       # Phase 4
├── answer/
│   ├── formatter.py
│   └── generator.py     # Phase 6
├── extract/
│   ├── decisions.py     # Phase 5
│   └── patterns.py      # Phase 5
├── eval/                 # Phase 7
│   ├── metrics.py
│   ├── runner.py
│   └── golden.py
└── agents/               # Agent tools
    ├── __init__.py
    └── tools.py
```

---

## Sources

- [architecture.md](architecture.md) — System architecture
- [data-model.md](data-model.md) — Database schema
- [conventions.md](conventions.md) — Code style and conventions
- [UI_PLAN.md](UI_PLAN.md) — UI design and screens
- [API_CONTRACT.md](API_CONTRACT.md) — API endpoint specifications
- [COACH_MODE_SPEC.md](COACH_MODE_SPEC.md) — Coach Mode requirements

**Date Confidence:** HIGH (document created 2025-12-23)

---

_This implementation plan is a living document. Update as phases complete._
