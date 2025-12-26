# Coach Mode Spec

> Optional coaching layer that adds bounded suggestions without weakening grounded answers.

**Last Updated:** 2025-12-24  
**Status:** Draft  
**Version:** 1.0.0

---

## Table of Contents

A. [Overview](#a-overview)  
B. [Modes and UX](#b-modes-and-ux)  
C. [Output Format Requirements](#c-output-format-requirements)  
D. [Suggestion Types (Allowed)](#d-suggestion-types-allowed)  
E. [Prohibited Behaviors](#e-prohibited-behaviors)  
F. [Deterministic Gating Rules](#f-deterministic-gating-rules)  
G. [Data Model Additions](#g-data-model-additions)  
H. [Coach Engine Architecture](#h-coach-engine-architecture)  
I. [Implementation Steps (Phased)](#i-implementation-steps-phased)  
J. [Acceptance Criteria](#j-acceptance-criteria)  
K. [Test Plan](#k-test-plan)

---

## A) Overview

**Purpose:** Provide forward-looking suggestions to improve (a) B.O.B itself and (b) the jefe's capture/workflow, while staying grounded and non-annoying.

**Core principle:** Coach Mode is additive; it never changes the answer's groundedness rules.

**Non-negotiables:**

- Local-first, offline-capable, and no always-on daemons
- Citations required for every claim and suggestion with evidence
- "No citation => no claim" enforced; otherwise return "Not found in sources"
- Default behavior remains neutral and non-chatty

---

## B) Modes and UX

### Mode Definitions

1. **Boring B.O.B (default):** Neutral, no unsolicited suggestions.
2. **Coach Mode (opt-in):** Adds a clearly separated "Suggestions (Coach Mode)" section.

### UI Requirements

- Visible toggle on the Ask screen (per-session).
- Persisted setting for default mode (Boring/Coach).
- Per-project preference supported (Coach on/off by project).
- Coach suggestions never appear unless Coach Mode is enabled.

---

## C) Output Format Requirements

### Base Answer Output (Unchanged)

Every answer must end with:

- Sources
- Date confidence
- "This may be outdated" if applicable

If no sources are found, the base answer must return "Not found in sources."

### Coach Mode Placement

When Coach Mode is enabled, append a separate section **after** the required footer:

```
Suggestions (Coach Mode):
1. ...
```

### Hard Limits

- Max 3 suggestions per response.
- Each suggestion is 1-3 sentences.
- Include a "Why:" line for each suggestion.

### Actions

- Suggestions may include optional quick actions (run routine, open indexing/health/settings, or rerun a query).
- Actions should respect the project scope of the suggestion when available.

### Evidence and Labeling

- If a suggestion is based on vault evidence, include citations to the examples.
- If not evidence-backed, label as **Hypothesis** and avoid claims about the user.

---

## D) Suggestion Types (Allowed)

Only the following categories are permitted:

1. **Capture hygiene**
   - Missing decision record, missing rationale, missing metadata, inconsistent templates.
   - Lint-based alerts (e.g., Decision missing rejected options).
2. **Staleness / revisit prompts**
   - Topic likely outdated based on date confidence thresholds.
3. **Coverage gaps**
   - "No sources found" guidance: propose what to add/index, where to record, which project tag to use.
4. **System improvements**
   - Indexing failures, parser issues, evaluation gaps, weak citation precision.
   - Knowledge Health dashboard signals (coverage, staleness, hygiene).
5. **Workflow nudges (jefe-oriented)**
   - Suggestions to use templates or run a command (index, extract-decisions, add tags), without judgment.

---

## E) Prohibited Behaviors

- No buddy/roleplay tone, no flattery, no emotional language.
- No unverifiable claims about the user (must cite or label as Hypothesis).
- No changing the grounded answer or adding extra "knowledge" beyond sources.
- No nagging: no repeating the same suggestion within a configurable cooldown window.

---

## F) Deterministic Gating Rules

Suggestions are allowed only if all gates pass:

1. **Coach Mode enabled:** If off, show zero suggestions.
2. **Not found in sources:** Suggestions may be shown, but only for coverage/capture (no content advice).
3. **Low date confidence:** If Date confidence is LOW, allow at most 1 suggestion and prioritize:
   - Revisit/outdated prompt, or
   - Missing decision/capture hygiene.
4. **Low retrieval evidence:** If fewer than **N = 2** cited chunks are returned, limit suggestions to coverage improvements.
5. **Cooldown rule:**
   - Store `last_shown` timestamp + `suggestion_type` + `project`.
   - Default cooldown: 7 days per suggestion type per project.
   - User can override with an explicit "Show anyway" action.

If any gate fails or required citations are missing, return zero suggestions.

---

## G) Data Model Additions

### `user_settings`

Store Coach Mode preferences (table or config file).

Required fields:

- `global_mode_default`: `"boring"` | `"coach"`
  - Exposed in the API as `coach_mode_default` for UI/state consistency.
- `per_project_mode`: map of `project -> "boring" | "coach"`

### `coach_suggestion_log`

Track suggestion display to enforce cooldowns.

Required fields:

- `id`
- `datetime`
- `project`
- `suggestion_type`
- `suggestion_fingerprint`
- `was_shown`

**Suggestion fingerprint:** Hash of `suggestion_type + normalized_text` where `normalized_text` lowercases and collapses whitespace. This prevents repeats across minor phrasing changes.

---

## H) Coach Engine Architecture

### Deterministic Engine (Default)

Inputs:

- Retrieval metadata (source dates, date confidence, project, cited chunk count)
- Indexing stats/errors
- Presence/absence of decision records for the topic
- Knowledge Health dashboard metrics (coverage, hygiene, staleness)
- Template lint results (missing rationale, rejected options)

Pipeline:

1. Run gating rules (Coach enabled, confidence, evidence count, cooldown).
2. Generate candidate suggestions per allowed category.
3. Attach citations for evidence-backed suggestions.
4. Label remaining suggestions as Hypothesis.
5. Dedupe by suggestion fingerprint and enforce max-3 limit.

### Optional LLM-Assisted Phrasing (Later)

Allowed only if:

- Suggestions remain within allowed categories
- Evidence-backed suggestions include citations, otherwise Hypothesis label
- Output is filtered through the deterministic gates above

---

## I) Implementation Steps (Phased)

### Phase 1: Deterministic Coach Mode (no LLM)

- Based on date confidence, missing sources, indexing errors, missing decision records

### Phase 2: Evidence-Backed Pattern Detection (deterministic)

- Detect repeated "Decision:" headers without "Rationale:" blocks

### Phase 3: Optional LLM-Assisted Suggestion Phrasing

- Strict post-filtering by allowed categories and gates

---

## J) Acceptance Criteria

- Coach Mode off => zero suggestions.
- Coach Mode on => suggestions appear in their own section; max 3.
- Suggestions never break citation rules.
- Repeated queries do not spam the same suggestion within cooldown.
- "Not found in sources" answers produce only coverage/capture suggestions.
- UI toggle works; per-project preference persists.

---

## K) Test Plan

- Unit tests for gating rules and cooldown.
- Golden tests for formatting (base footer always present).
- Integration test: ask with low confidence => at most 1 suggestion.
- Integration test: ask with no sources => coverage suggestion only.
- Regression test for "no citation => no claim" unaffected.

---

## Sources

- [AGENTS.md](AGENTS.md) — Local-first and citation-grounded rules
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — Baseline phases and defaults
- [UI_PLAN.md](UI_PLAN.md) — Ask flow and mandatory footer
- [API_CONTRACT.md](API_CONTRACT.md) — Ask response schema and endpoints

**Date Confidence:** HIGH (document created 2025-12-23)
