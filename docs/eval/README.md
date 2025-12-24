# Evaluation Harness

This directory contains the evaluation framework for B.O.B retrieval quality.

## Overview

The evaluation harness measures how well B.O.B retrieves relevant documents for user questions. It uses a golden dataset of question-answer pairs where the expected chunks are manually verified.

## Files

```
docs/eval/
├── README.md              # This file
├── example_gold.jsonl     # Example golden dataset
├── domains/               # Per-domain golden sets
│   ├── food.jsonl
│   ├── travel.jsonl
│   ├── cdc.jsonl
│   ├── construction.jsonl
│   └── business.jsonl
└── baseline.json          # Baseline metrics (after first run)
```

## Golden Dataset Format

Golden datasets use JSON Lines format (`.jsonl`), one example per line:

```json
{
  "id": 1,
  "question": "How do I install B.O.B?",
  "expected_chunks": [5, 6],
  "difficulty": "easy",
  "category": "installation",
  "notes": "README installation section"
}
```

### Fields

| Field             | Required | Description                                  |
| ----------------- | -------- | -------------------------------------------- |
| `id`              | Yes      | Unique identifier for the example            |
| `question`        | Yes      | Natural language question                    |
| `expected_chunks` | Yes      | List of chunk IDs that should be retrieved   |
| `expected_answer` | No       | Optional expected answer text                |
| `difficulty`      | No       | `easy`, `medium`, or `hard`                  |
| `category`        | No       | Topic category for analysis                  |
| `notes`           | No       | Explanation for why this example was created |

### Negative Examples

For questions that should NOT return results (testing "I don't know" behavior):

```json
{
  "id": 99,
  "question": "How do I configure the flux capacitor?",
  "expected_chunks": [],
  "difficulty": "medium",
  "notes": "Negative example - topic not in corpus"
}
```

## Domain Golden Sets

Maintain small golden sets per domain to catch regressions in specific areas.

- Food
- Travel
- CDC
- Construction
- Business

Each domain set should include at least 10 questions and 2-3 negative examples.

## Running Evaluation

### CLI Command

```bash
# Run with default golden set
bob eval run

# Run with custom golden set
bob eval run --golden docs/eval/custom_gold.jsonl

# Compare to baseline
bob eval compare --baseline docs/eval/baseline.json

# Run only a domain set
bob eval run --golden docs/eval/domains/cdc.jsonl
```

### Programmatic API

```python
from bob.agents import run_eval

result = run_eval(golden_path="docs/eval/example_gold.jsonl", k=5)

if result.success:
    print(f"Recall@5: {result.data['recall_at_k']:.2f}")
    print(f"Precision@5: {result.data['precision_at_k']:.2f}")
    print(f"MRR: {result.data['mrr']:.2f}")
```

## Metrics

### Recall@k

**Formula:** `|relevant ∩ retrieved@k| / |relevant|`

**Interpretation:** What fraction of expected chunks are in the top k results?

- 1.0 = All expected chunks found
- 0.5 = Half of expected chunks found
- 0.0 = None found

### Precision@k

**Formula:** `|relevant ∩ retrieved@k| / k`

**Interpretation:** What fraction of top k results are relevant?

- 1.0 = All results are relevant
- 0.5 = Half are relevant
- 0.0 = None are relevant

### MRR (Mean Reciprocal Rank)

**Formula:** `1 / rank_of_first_relevant`

**Interpretation:** How high is the first relevant result?

- 1.0 = First result is relevant
- 0.5 = Second result is relevant
- 0.33 = Third result is relevant
- 0.0 = No relevant results

## Creating Golden Sets

### Step 1: Index Your Corpus

```bash
bob index ./docs --project eval-corpus
```

### Step 2: Identify Questions

Think about what questions users would ask. Categories:

- **Installation:** "How do I install X?"
- **Configuration:** "How do I configure Y?"
- **Usage:** "How do I do Z?"
- **Troubleshooting:** "Why is X not working?"
- **API:** "What does function X do?"

### Step 3: Find Expected Chunks

For each question, query the database to find which chunks contain the answer:

```bash
bob ask "How do I install B.O.B?" --output json | jq '.sources[].chunk_id'
```

### Step 4: Verify Manually

**IMPORTANT:** Do not trust the search results blindly. Manually verify that:

1. The expected chunks actually contain the answer
2. You haven't missed other relevant chunks
3. The question is clear and unambiguous

### Step 5: Create JSONL File

```bash
echo '{"id": 1, "question": "How do I install B.O.B?", "expected_chunks": [5, 6]}' >> docs/eval/my_gold.jsonl
```

## Interpreting Results

### Good Metrics

For a well-tuned retrieval system:

- Recall@5 > 0.8 — Most relevant content is found
- Precision@5 > 0.6 — Results are mostly relevant
- MRR > 0.7 — First result is usually good

### Debugging Poor Results

If **Recall is low:**

- Expected chunks might not be indexed
- Embedding model doesn't capture semantic similarity
- Query terms don't match document vocabulary

If **Precision is low:**

- Too many irrelevant results
- Need better ranking or filtering
- Chunk size might be too small (matching noise)

If **MRR is low:**

- First result is often wrong
- Need reranking
- Scoring function needs tuning

## Baseline Management

After establishing a stable golden set, save baseline metrics:

```bash
bob eval run > docs/eval/baseline.json
```

On every change to retrieval, compare:

```bash
bob eval compare --baseline docs/eval/baseline.json
```

Flag regressions:

- Recall drop > 5%
- MRR drop > 10%
- Any individual query drops from pass to fail

## Drift Detection (UI)

When the server is running, the Eval page shows:

- Per-domain deltas since the last baseline
- Answer changes with before/after diffs
- Links to the sources that caused drift

---

## Sources

- [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) — Phase 5 details
- [AGENTS.md](../AGENTS.md) — Agent contracts

**Date Confidence:** HIGH (document created 2025-12-23)
