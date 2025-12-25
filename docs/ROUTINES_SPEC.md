# B.O.B Routines Specification

> Defines the routine entry points, templates, capture hygiene, feedback loops, and Coach Mode integration that make B.O.B a daily-use partner while honoring local-first constraints (manual triggers only, chunk → embed → store, metadata always includes project/date/language/source, docs limited to Markdown/PDF/recipes/notes/Git). All routines are built on the same retrieval pipeline that powers the Ask screen.

> **Status:** Planning / roadmap with `/routines/daily-checkin` now available. The other `/routines/*` actions remain aspirational—see [`docs/CURRENT_STATE.md`](CURRENT_STATE.md) for the implemented CLI/API/UI surface and how it differs from this spec.

**Last Updated:** 2025-12-24

---

## Routine Entry Points (One-Click Actions)

The following actions are exposed in the UI, wired to new `/routines/<action>` endpoints, and always include citations derived from the chunk → embed → store pipeline before any write. Each action writes to vault paths in the pattern described below, uses canonical templates, and surfaces retrieval context on the Routines screen (left column for action list, center for retrieved snippets and template preview, right for citations / failure notices).

| Action | Vault Output Pattern | Template Headings + Metadata | Retrieval Workload | UI Display | Failure Behavior |
| --- | --- | --- | --- | --- | --- |
| **Daily Check-in** | `vault/routines/daily/{{YYYY-MM-DD}}.md` | Front matter: `project`, `date`, `language`, `source: routine/daily-checkin`; headings: `## Morning Review`, `## Open Loops`, `## Today’s Focus` | Queries: `open_loops(project, status=proposed)` + `recent_context(days=3, project)` | Routines screen shows morning priorities and open loops with inline citations; footer offers “Save Daily Note” | If no sources, suggest manual entry and log “Not found”; low confidence warns before write. |
| **End-of-Day Debrief** | `vault/routines/daily/{{YYYY-MM-DD}}-debrief.md` | Metadata same as Daily; headings: `## Wins`, `## Lessons`, `## Open Loops / Follow-ups` | Queries: `recent_context(days=1)` + `decisions(status=decided, modified=today)` | Center pane lists lessons + unresolved open loops with citations and emoji status | If metadata missing or low confidence, UI prompts for manual summary and adds lint warning to Fix Queue |
| **Meeting Prep** | `vault/meetings/{{project}}/{{meeting-slug}}-prep.md` | Metadata includes `meeting_date`, `participants`, `source`; sections: `## Agenda bullets`, `## Relevant Decisions`, `## Questions to Ask` | Queries: `last_decisions(project, limit=5)` + `unresolved_questions(project)` + `notes(recent=7days, project)` | Prep card shows agenda bullets plus quick-links to relevant decisions/notes | If no relevant notes, UI offers “Add manual context” and marks outcome as “Needs more data”. |
| **Meeting Debrief** | `vault/meetings/{{project}}/{{meeting-slug}}-debrief.md` | Sections: `## Decisions`, `## Rejected Options`, `## Next Actions`, `## Citations`; links to decision index entry | Queries: `meeting_notes(last_meeting)` + `open_decisions(project)` | After save, automatically updates decision index (new decision file or supersedes existing one) and shows citation list | Missing rejected options or next actions triggers lint flag; user can postpone write until enriched or add comment to Fix Queue |
| **Weekly Review** | `vault/routines/weekly/{{YYYY}}-W{{week}}.md` | Headings: `## Highlights`, `## Stale Decisions`, `## Actions for next week` with metadata `week_range` | Queries: `notes(last=7days)` + `decisions(status=decided, older_than=6m)` + `missing_metadata(project)` | UI shows timeline of week’s notes and flagged decisions, plus stale decision notices requiring review | Stale decisions with missing context appear in Fix Queue; routine surfaces missing metadata warnings before writing |
| **New Decision** | `vault/decisions/decision-{{slug}}.md` | Mandatory sections: `### Decision`, `### Context`, `### Evidence`, `### Rejected Options`, `### Next Actions`, optional `### Supersedes` | Queries: `related_sources(query)` to link evidence, `decisions(conflicts=topic)` to detect supersedes | UI pre-fills evidence from retrieved citation list; decision index updates summary view | If no rejected options or evidence, lint warns and Coach Mode can label suggestion as “Hypothesis”. |
| **Trip Debrief** | `vault/trips/{{trip-name}}/debrief.md` | Sections: `## What I Learned`, `## Checklist Seeds`, `## Reusable Recipes / Tips` | Queries: `trip_notes(project, tag=trip)` + `recipes(trip_related)` + `open_loops(trip)` | Debrief preview surfaces lessons plus checklist seeds and links to reusable resources | If insufficient lessons, prompt to capture manually and add to Fix Queue as a pending insight. |
| **Fix Queue** | _No file output_ (drives health dashboard actions) | N/A | Queries: `health_metrics()` + `feedback_counts()` + `lint_issues()` | Opens health dashboard with prioritized tasks (metadata fixes, ingestion re-runs, repeated questions) | If health metrics missing, show diagnostic notice and log attempted refresh. |

Every action’s retrieval response includes chunk IDs, similarity scores, and locator data (heading, lines, page) before the write is allowed, ensuring evidence is citable and locatable. When metadata is missing in the target project’s configuration, UI prompts to fill the missing fields before saving and records the problem in the Fix Queue.

## Templates & Capture Hygiene

### Canonical Templates

A `docs/templates/` directory contains the canonical field- and heading-guided templates that these routines (and any `POST /notes/create` requests) reuse. Each template begins with YAML front matter:

```yaml
project: "{{project}}"
date: "{{date}}"
language: "{{language}}"
source: "template/<name>"
```

Required templates:

1. `daily.md` – Sections `## Morning Review`, `## Open Loops`, `## Today’s Focus`.
2. `weekly.md` – Sections `## Highlights`, `## Stale Decisions`, `## Actions for Next Week` + `week_range` metadata.
3. `meeting.md` – Sections `## Agenda`, `## Relevant Decisions`, `## Post-Meeting Decisions`, `## Next Actions`.
4. `decision.md` – Sections `### Decision`, `### Context`, `### Evidence`, `### Rejected Options`, `### Next Actions`, optional `### Supersedes`.
5. `experiment.md` – Sections `## Hypothesis`, `## Setup`, `## Results`, `## Learnings`.
6. `recipe.md` – Sections `# Ingredients`, `# Steps`, `# Notes`, `# Source` with structured ingredient list.
7. `trip.md` – Sections `## Goals`, `## Learnings`, `## Checklist Seeds`, `## Follow-up`.

Templates can contain placeholder variables (project, date) that the API expands before writing. The routine APIs and `POST /notes/create` share the same rendering logic to keep output consistent.

### Capture Hygiene Rules (Lint)

Lint rules run on every created note and when requested manually. Flags include:

- `missing_rationale`: Decision captures without a `Context` or `Evidence` section.
- `missing_rejected_options`: Decision captures lacking any rejected alternatives or reasons.
- `missing_metadata`: Notes missing required metadata fields (`project`, `date`, `language`, `source`).
- `missing_next_actions`: Meetings or debriefs without `Next Actions` or `Checklist Seeds`.

Lint output is surfaced in the Fix Queue and in Coach Mode suggestions (the latter only when Coach Mode is enabled) with explicit citations to the offending file so the user can jump directly to the section and fix it.

## Feedback Loop & Fix Queue

### Feedback Controls

Every answer pane includes five feedback buttons: **Helpful**, **Wrong or missing source**, **Outdated**, **Too long**, **Didn’t answer**. Pressing a button hits `POST /feedback` and appends a structured log entry:

```json
{
  "question": "...",
  "timestamp": "2025-12-24T10:00:00Z",
  "project": "docs",
  "retrieved_sources": ["docs/notes.md@..."],
  "answer_id": "ans_123",
  "feedback_reason": "wrong_source"
}
```

### Failure Dashboards

Failure metrics collected locally include:

- **Not found frequency** per project (percentage of queries with `footer.not_found`).
- **PDFs with no text / ingestion errors** (counts grouped by error type). 
- **Missing metadata counts** (per metadata field, per project). 
- **Repeated questions** (same query text >1 within rolling 48 hours) so discoverability issues surface.

### Fix Queue Generation Rule

A runner converts these metrics, lint findings, and feedback spikes into prioritized Fix Queue tasks (returned by `GET /health/fix-queue` and shown on the Fix Queue panel). Each task includes:

- `id`: stable identifier.
- `action`: `open`, `reindex`, `fix_metadata`, `run_routine`.
- `target`: file path or routine name.
- `reason`: e.g., `missing_metadata`, `not_found_spike`, `decisions_without_rationale`.
- `priority`: derived from error severity and frequency.

The Fix Queue screen lets the user run the associated routine (e.g., “Create a New Decision note” for a missing rationale task) or re-index a path. Tasks tied to Coach Mode and routines surface before optional Generation improvements, ensuring the system remains grounded.

## Coach Mode Integration

Coach Mode suggestions can reference routine actions only when the mode is enabled and the relevant routine is off cooldown. Suggestions follow this rule:

1. Evidence-backed suggestions cite the retrieval context (e.g., “Five open decisions lack final context; run a New Decision capture” with citations to the open decision notes).
2. When evidence is thin, the suggestion is labeled **Hypothesis** (e.g., “You have three repeated questions about trip planning; consider running Trip Debrief”).
3. The routine tag in Coach Mode links directly to the `/routines/<action>` endpoint so the user can execute the workflow from the suggestion.

Coach Mode also surfaces Fix Queue metrics, inviting the user to resolve lint flags, ingest missing sources, or run a routine that writes to the vault while respecting permission scopes (see `docs/PERMISSIONS.md`).

---

**See also:**

- `docs/UI_PLAN.md` for Routines & Fix Queue screen designs.
- `docs/API_CONTRACT.md` for the `/routines/<action>`, `/feedback`, and `/health` contracts.
