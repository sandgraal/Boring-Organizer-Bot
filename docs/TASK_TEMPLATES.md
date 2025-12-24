# Task Templates

> Standard task formats for agent work on B.O.B.

**Last Updated:** 2024-12-23

---

## How to Use This Document

Each task template provides:

- **Inputs:** What you need before starting
- **Expected Outputs:** What you must deliver
- **Tests:** How to verify the work
- **Review Checklist:** What reviewers will check

Copy the relevant template when creating a task or issue.

---

## Task 1: Add a New Ingestor (Parser)

### Description

Add support for parsing a new document type (e.g., HTML, RTF, JSON).

### Inputs

- [ ] File type specification (extension, MIME type)
- [ ] Sample files for testing (at least 3)
- [ ] Desired locator format (how to cite back to source)

### Expected Outputs

1. **Parser file:** `bob/ingest/<type>.py`

   ```python
   class <Type>Parser(BaseParser):
       EXTENSIONS = [".ext"]

       def parse(self, path: Path) -> ParsedDocument:
           # Implementation
   ```

2. **Registry entry:** Update `bob/ingest/registry.py`

3. **Tests:** `tests/test_ingest_<type>.py`

   - Test: parses valid file correctly
   - Test: extracts locator information
   - Test: handles malformed input gracefully
   - Test: returns correct metadata

4. **Documentation:** Update supported types in README.md

### Tests to Run

```bash
pytest tests/test_ingest_<type>.py -v
make check
```

### Review Checklist

- [ ] Parser inherits from `BaseParser`
- [ ] Locators follow format in `docs/architecture.md`
- [ ] All public methods have docstrings
- [ ] Tests cover happy path and error cases
- [ ] No external network calls
- [ ] README updated with new type

### Example: Add HTML Parser

**Inputs:**

- Extension: `.html`, `.htm`
- Locator: `{element_id, xpath, text_preview}`
- Sample files: `tests/fixtures/sample.html`

**Acceptance:**

```bash
bob index ./pages --project web-archive
bob ask "What is on the homepage?"
# Should return results with HTML locators
```

---

## Task 2: Implement Date Confidence Logic

### Description

Enhance date confidence to parse dates from document content, not just file metadata.

### Inputs

- [ ] List of date patterns to recognize
- [ ] Examples of documents with inline dates
- [ ] Confidence level definitions (HIGH/MEDIUM/LOW thresholds)

### Expected Outputs

1. **Date parser module:** `bob/index/date_parser.py`

   ```python
   def extract_date_from_content(content: str) -> datetime | None:
       """Extract document date from content."""

   def parse_date_hint(text: str) -> datetime | None:
       """Parse 'as of', 'updated', 'dated' patterns."""
   ```

2. **Integration:** Update `bob/ingest/*.py` to call date parser

3. **Tests:** `tests/test_date_parser.py`

   - Test: ISO 8601 dates
   - Test: Natural language dates ("January 15, 2024")
   - Test: Relative dates ("updated last month") → skip
   - Test: "as of" pattern
   - Test: Returns None when ambiguous

4. **Config:** Add date parsing options to `bob.yaml.example`

### Tests to Run

```bash
pytest tests/test_date_parser.py -v
pytest tests/test_formatter.py -v  # Ensure confidence still works
make check
```

### Review Checklist

- [ ] Dates parsed correctly for ISO 8601
- [ ] Ambiguous dates return None (don't guess)
- [ ] File mtime used as fallback
- [ ] Confidence levels match spec
- [ ] No false positives on random numbers
- [ ] Tests cover edge cases

---

## Task 3: Add Decision Extraction

### Description

Implement the decision extraction feature to identify and store decisions from documents.

### Inputs

- [ ] Decision patterns to match (see `bob/extract/decisions.py` TODO)
- [ ] Sample documents with decisions (ADRs, meeting notes)
- [ ] Decision schema from `docs/data-model.md`

### Expected Outputs

1. **Pattern file:** `bob/extract/patterns.py`

   ```python
   DECISION_PATTERNS = [
       r"(?i)we decided to\s+(.+)",
       r"(?i)decision:\s*(.+)",
       r"(?i)ADR[-\s]?\d+:\s*(.+)",
   ]
   ```

2. **Extraction logic:** Complete `bob/extract/decisions.py`

   ```python
   def extract_decisions_from_chunk(
       chunk_id: int, content: str, metadata: dict
   ) -> list[ExtractedDecision]:
       # Implementation
   ```

3. **Database migration:** `bob/db/migrations/003_decisions.sql`

4. **CLI command:** Make `bob extract-decisions` work

5. **Tests:** `tests/test_decision_extraction.py`
   - Test: ADR format extraction
   - Test: "We decided" pattern
   - Test: Rejected alternatives
   - Test: False positive filtering

### Tests to Run

```bash
pytest tests/test_decision_extraction.py -v
bob extract-decisions ./tests/fixtures/decisions/
make check
```

### Review Checklist

- [ ] Patterns match real-world decision formats
- [ ] False positive rate acceptable (<10%)
- [ ] Decisions stored with full provenance
- [ ] CLI command documented
- [ ] Migration is idempotent

---

## Task 4: Create Evaluation Set

### Description

Build a golden evaluation dataset for measuring retrieval quality.

### Inputs

- [ ] Access to indexed test corpus
- [ ] Minimum 20 Q/A pairs
- [ ] Expected chunks for each question

### Expected Outputs

1. **Golden set file:** `docs/eval/example_gold.jsonl`

   ```jsonl
   {"question": "How do I configure the database?", "expected_chunks": [12, 45], "notes": "Config section"}
   {"question": "What file formats are supported?", "expected_chunks": [8, 9, 10], "notes": "Ingest docs"}
   ```

2. **Documentation:** `docs/eval/README.md`

   - How to create Q/A pairs
   - How to run evaluation
   - How to interpret results

3. **Runner script:** `bob/eval/runner.py`

   ```python
   def run_evaluation(golden_path: Path) -> EvalResult:
       # Load golden set, run queries, compute metrics
   ```

4. **CLI command:** `bob eval run`

### Tests to Run

```bash
bob eval run --golden docs/eval/example_gold.jsonl
pytest tests/test_eval_runner.py -v
```

### Review Checklist

- [ ] At least 20 Q/A pairs
- [ ] Questions cover different document types
- [ ] Expected chunks verified manually
- [ ] Metrics: Recall@5, Precision@5, MRR
- [ ] Results reproducible (deterministic)

---

## Task 5: Add Hybrid Search Scoring

### Description

Combine vector similarity with keyword matching for better retrieval.

### Inputs

- [ ] Current vector-only search implementation
- [ ] Keyword matching algorithm (BM25 or simple TF-IDF)
- [ ] Weight configuration (how to balance scores)

### Expected Outputs

1. **Scoring module:** `bob/retrieval/scoring.py`

   ```python
   def hybrid_score(
       query: str,
       chunk_content: str,
       vector_distance: float,
       config: ScoringConfig,
   ) -> float:
       # Combine vector and keyword scores
   ```

2. **Search integration:** Update `bob/retrieval/search.py`

3. **Config:** Add scoring weights to `bob.yaml.example`

   ```yaml
   scoring:
     vector_weight: 0.7
     keyword_weight: 0.3
   ```

4. **Tests:** `tests/test_scoring.py`

   - Test: pure vector (keyword_weight=0)
   - Test: pure keyword (vector_weight=0)
   - Test: hybrid balancing
   - Test: exact phrase matching boost

5. **Evaluation:** Compare retrieval metrics before/after

### Tests to Run

```bash
pytest tests/test_scoring.py -v
bob eval run  # Compare to baseline
make check
```

### Review Checklist

- [ ] Default weights produce good results
- [ ] Can disable hybrid (pure vector mode)
- [ ] Performance acceptable (<500ms query)
- [ ] Evaluation shows improvement
- [ ] Config documented

---

## Task 6: Add JSON Output Format

### Description

Add machine-readable JSON output for CLI commands.

### Inputs

- [ ] Current text output format
- [ ] JSON schema for output
- [ ] Compatibility requirements

### Expected Outputs

1. **JSON formatter:** Update `bob/answer/formatter.py`

   ```python
   def format_answer_json(
       question: str,
       results: list[SearchResult]
   ) -> dict:
       # Structured output
   ```

2. **CLI flag:** `--output json`

   ```bash
   bob ask "question" --output json
   ```

3. **Schema file:** `docs/schemas/answer.json`

4. **Tests:** `tests/test_formatter.py`
   - Test: JSON is valid
   - Test: All required fields present
   - Test: Citations included
   - Test: Date confidence included

### Tests to Run

```bash
pytest tests/test_formatter.py -v
bob ask "test question" --output json | jq .  # Validate JSON
make check
```

### Review Checklist

- [ ] JSON schema documented
- [ ] All fields from text output included
- [ ] Backward compatible (text still default)
- [ ] jq/parsing works correctly

---

## Task Checklist Template

Copy this for any new task:

````markdown
## Task: [Title]

### Description

[What needs to be done]

### Inputs

- [ ] [Required input 1]
- [ ] [Required input 2]

### Expected Outputs

1. [File or artifact 1]
2. [File or artifact 2]
3. Tests in `tests/test_*.py`

### Tests to Run

```bash
[Commands]
```
````

### Review Checklist

- [ ] Tests pass
- [ ] Citations work correctly
- [ ] Date confidence included
- [ ] Documentation updated
- [ ] No personal data
- [ ] `make check` passes

### Sources

- [Relevant doc](link)

### Date Confidence

HIGH | MEDIUM | LOW (reason)

```

---

## Sources

- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Phase details
- [AGENTS.md](AGENTS.md) — Agent contracts
- [conventions.md](conventions.md) — Code style

**Date Confidence:** HIGH (document created 2024-12-23)
```
