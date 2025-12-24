# B.O.B Implementation Plan

> A phased roadmap for building a local-first, citation-grounded knowledge assistant.

**Last Updated:** 2024-12-23  
**Status:** Active  
**Version:** 1.0.0

---

## Table of Contents

1. [Guiding Principles](#guiding-principles)
2. [Boring Defaults](#boring-defaults)
3. [What We Are Not Doing](#what-we-are-not-doing)
4. [Phase 1: Core Retrieval](#phase-1-core-retrieval)
5. [Phase 2: Better Retrieval](#phase-2-better-retrieval)
6. [Phase 3: Decision Layer](#phase-3-decision-layer)
7. [Phase 4: Optional Generation](#phase-4-optional-generation)
8. [Phase 5: Evaluation Harness](#phase-5-evaluation-harness)
9. [Timeline Overview](#timeline-overview)

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
| LLM        | None (Phase 1-3)       | Retrieval is the hard part; generation is optional |

---

## What We Are Not Doing

These are explicit non-goals to avoid scope creep:

- ❌ **Cloud sync or collaboration** — This is a personal tool
- ❌ **Real-time file watching** — Index manually when ready
- ❌ **Web UI** — CLI is sufficient; build a UI later if needed
- ❌ **Multiple databases** — One SQLite file per user
- ❌ **Complex ranking models** — Start simple, add complexity only with evidence
- ❌ **Auto-summarization** — Return passages, let user read
- ❌ **Internet search** — Local documents only
- ❌ **Always-on daemons** — Manual commands only
- ❌ **Personal data in repo** — `/data` is gitignored; never commit content

---

## Phase 1: Core Retrieval

**Goal:** Index documents, search with embeddings, return cited passages without generation.

### Status: ✅ Scaffolding Complete

### Features

1. **Ingestion Pipeline**

   - [x] Markdown parser with heading locators
   - [x] PDF parser with page locators
   - [x] Word (.docx) parser with paragraph locators
   - [x] Excel parser with sheet locators
   - [x] Recipe YAML/JSON parser
   - [x] Git repository docs parser
   - [ ] Validate all parsers produce consistent locator format

2. **Chunking**

   - [x] Token-based chunking with overlap
   - [x] Preserve locator information across chunks
   - [ ] Add chunk quality validation (min content, no boilerplate)

3. **Storage**

   - [x] SQLite database with migrations
   - [x] sqlite-vec for vector similarity
   - [x] Fallback for systems without sqlite-vec
   - [x] Content hash for change detection

4. **Search**

   - [x] Vector similarity search
   - [x] Project filtering
   - [ ] Return "No results" gracefully when nothing matches

5. **Output**
   - [x] Citation formatting with locators
   - [x] Date confidence levels
   - [x] "May be outdated" warnings
   - [ ] Machine-readable JSON output option

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

- [ ] All parsers tested with real documents
- [ ] Search returns results for indexed content
- [ ] Citations are accurate and verifiable
- [ ] CLI commands documented in README
- [ ] No regressions in `make check`

---

## Phase 2: Better Retrieval

**Goal:** Improve search quality with hybrid scoring, metadata boosts, and citation precision.

### Status: 🔜 Not Started

### Features

1. **Hybrid Scoring**

   - [ ] Combine vector similarity with BM25-style keyword matching
   - [ ] Configurable weight between semantic and keyword scores
   - [ ] Score normalization for consistent ranking

2. **Metadata Boosts**

   - [ ] Boost recent documents (configurable decay)
   - [ ] Boost documents from same project as query context
   - [ ] Boost documents matching query language
   - [ ] Configurable boost weights in `bob.yaml`

3. **Citation Precision**

   - [ ] Narrow locators to most relevant paragraph within chunk
   - [ ] Support line-level citations for code/markdown
   - [ ] Highlight matching terms in output

4. **Date Confidence Logic**

   - [ ] Parse dates from document content (not just file metadata)
   - [ ] Detect "as of" and "updated" statements
   - [ ] Inherit date from parent document for sub-sections
   - [ ] Add `--max-age` filter to search

5. **Search Improvements**
   - [ ] Support quoted phrases for exact matching
   - [ ] Support `-term` for exclusion
   - [ ] Support `project:name` inline filter
   - [ ] `bob search` as alias for `bob ask` (retrieval only)

### Acceptance Criteria

- [ ] Hybrid search outperforms pure vector search on golden set
- [ ] Recent documents rank higher (when relevance is similar)
- [ ] `bob ask "exact phrase"` returns only exact matches
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

## Phase 3: Decision Layer

**Goal:** Extract, store, and query decisions from documents with full traceability.

### Status: 🔜 Not Started

### Features

1. **Decision Extraction**

   - [ ] Pattern-based extraction (regex + heuristics)
   - [ ] Support common formats: ADRs, decision logs, meeting notes
   - [ ] Extract: decision text, date, context, alternatives rejected
   - [ ] Confidence score for extraction quality

2. **Decision Schema**

   - [ ] Decision ID (auto-generated, stable)
   - [ ] Decision text (the actual decision)
   - [ ] Context (why this decision was made)
   - [ ] Rejected alternatives (what was not chosen and why)
   - [ ] Status: `active`, `superseded`, `deprecated`
   - [ ] Superseded by (link to replacement decision)
   - [ ] Source chunk ID (for citation back to original)

3. **CLI Commands**

   - [ ] `bob extract-decisions [--project]` — Scan and extract decisions
   - [ ] `bob decisions [--status active]` — List decisions
   - [ ] `bob decision <id>` — Show decision details with full context
   - [ ] `bob supersede <old_id> <new_id>` — Mark decision as superseded

4. **Integration with Search**
   - [ ] `bob ask "What did we decide about X?"` prioritizes decision chunks
   - [ ] Decision results show status and any supersession info
   - [ ] Warn if returning a superseded decision

### Acceptance Criteria

- [ ] `bob extract-decisions` finds decisions in ADR-format documents
- [ ] Each decision has a stable ID and full provenance
- [ ] Superseded decisions are marked and linked to replacements
- [ ] Search can filter by decision status

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

- [ ] Decisions extracted from test corpus with >80% precision
- [ ] Full CRUD for decision lifecycle
- [ ] Supersession relationships tracked
- [ ] Documentation and examples for decision formats

---

## Phase 4: Optional Generation

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

## Phase 5: Evaluation Harness

**Goal:** Build a repeatable evaluation framework with golden Q/A sets and regression tests.

### Status: 🔜 Not Started

### Features

1. **Golden Dataset**

   - [ ] JSON Lines format for Q/A pairs
   - [ ] Fields: question, expected_chunks, expected_answer (optional)
   - [ ] Example dataset in `docs/eval/`
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

5. **Artifacts**
   - [ ] `docs/eval/example_gold.jsonl` — Example golden set
   - [ ] `tests/test_eval_runner.py` — Evaluation runner tests
   - [ ] `bob/eval/` — Evaluation module

### Acceptance Criteria

- [ ] Example golden set with at least 20 Q/A pairs
- [ ] `bob eval run` produces metrics report
- [ ] Metrics are reproducible (same input → same output)
- [ ] Regressions detected on golden set changes

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

| Phase       | Focus               | Prerequisites | Est. Duration |
| ----------- | ------------------- | ------------- | ------------- |
| **Phase 1** | Core Retrieval      | —             | 2-3 weeks     |
| **Phase 2** | Better Retrieval    | Phase 1       | 2 weeks       |
| **Phase 3** | Decision Layer      | Phase 1       | 2-3 weeks     |
| **Phase 4** | Optional Generation | Phase 1, 2    | 2 weeks       |
| **Phase 5** | Evaluation Harness  | Phase 1       | 1-2 weeks     |

Phases 2, 3, and 5 can proceed in parallel after Phase 1 is complete.

---

## Appendix: File Structure After All Phases

```
bob/
├── __init__.py
├── config.py
├── cli/
│   └── main.py
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
│   ├── hybrid.py        # Phase 2
│   └── scoring.py       # Phase 2
├── answer/
│   ├── formatter.py
│   └── generator.py     # Phase 4
├── extract/
│   ├── decisions.py     # Phase 3
│   └── patterns.py      # Phase 3
├── eval/                 # Phase 5
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

**Date Confidence:** HIGH (document created 2024-12-23)

---

_This implementation plan is a living document. Update as phases complete._
