# B.O.B Routines Specification

> Defines the routine entry points, templates, capture hygiene, feedback loops, and Coach Mode integration that make B.O.B a daily-use partner while honoring local-first constraints (manual triggers only, chunk → embed → store, metadata always includes project/date/language/source, docs limited to Markdown/PDF/recipes/notes/Git). All routines are built on the same retrieval pipeline that powers the Ask screen.

> **Status:** In progress—routine endpoints and the UI Routines/Health pages are live, browser-saves connectors (bookmarks/highlights) are implemented, while lint-driven remediation and calendar connectors remain on the roadmap (see [`docs/CURRENT_STATE.md`](CURRENT_STATE.md) for the implemented stack).

**Last Updated:** 2025-12-27

---

## Routine Entry Points (One-Click Actions)

The following routine actions are exposed in the UI, wired to `/routines/<action>` endpoints, and always include citations derived from the chunk → embed → store pipeline before any write. Each action writes to vault paths in the pattern described below, uses canonical templates, and surfaces retrieval context on the Routines screen (action list + rendered template + cited retrievals). The Fix Queue is surfaced separately via `GET /health/fix-queue` on the Health page (no routine write).

| Action | Vault Output Pattern | Template Headings + Metadata | Retrieval Workload | UI Display | Failure Behavior |
| --- | --- | --- | --- | --- | --- |
| **Daily Check-in** | `vault/routines/daily/{{YYYY-MM-DD}}.md` | Front matter: `project`, `date`, `language`, `source: routine/daily-checkin`; headings: `## Morning Review`, `## Open Loops`, `## Today’s Focus` | Queries: `"open loop"` + `"recent context"` (lookback 3 days) | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **End-of-Day Debrief** | `vault/routines/daily/{{YYYY-MM-DD}}-debrief.md` | Metadata same as Daily; headings: `## Wins`, `## Lessons`, `## Open Loops / Follow-ups` | Queries: `"recent context"` + `"decisions decided today"` (lookback 1 day) | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **Meeting Prep** | `vault/meetings/{{project}}/{{meeting-slug}}-prep.md` | Metadata includes `meeting_date`, `participants`, `source`; sections (shared meeting template): `## Agenda`, `## Relevant Decisions`, `## Post-Meeting Decisions`, `## Next Actions` | Queries: `"recent decisions"` + `"unresolved questions"` + `"recent notes"` (lookback 7 days) | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **Meeting Debrief** | `vault/meetings/{{project}}/{{meeting-slug}}-debrief.md` | Sections (shared meeting template): `## Agenda`, `## Relevant Decisions`, `## Post-Meeting Decisions`, `## Next Actions` | Queries: `"meeting notes"` (lookback 1 day) + `"open decisions"` | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **Weekly Review** | `vault/routines/weekly/{{YYYY}}-W{{week}}.md` | Headings: `## Highlights`, `## Stale Decisions`, `## Actions for next week` with metadata `week_range` | Queries: `"weekly highlights"` + `"stale decisions"` + `"missing metadata"` | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **New Decision** | `vault/decisions/decision-{{slug}}.md` | Mandatory sections: `### Decision`, `### Context`, `### Evidence`, `### Rejected Options`, `### Next Actions`, optional `### Supersedes` | Queries: `"related decision sources"` + `"conflicting decisions"` | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **Trip Debrief** | `vault/trips/{{trip-slug}}/debrief.md` | Sections: `## Goals`, `## Learnings`, `## Checklist Seeds`, `## Follow-up` | Queries: `"trip notes"` (lookback 30 days) + `"trip recipes"` + `"trip open loops"` | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |
| **Trip Plan** | `vault/trips/{{trip-slug}}/plan.md` | Front matter: `project`, `date`, `language`, `source: routine/trip-plan`, `trip_name`, `trip_dates`; sections: `## Purpose`, `## Destinations`, `## Logistics`, `## Packing`, `## Questions to Answer`, `## Open Loops` | Queries: `"trip learnings"` + `"destination travel"` + `"packing checklist"` (no date bounds) | Routines panel renders the template and cited retrievals for the run. | Warns when a retrieval bucket is empty; warns on overwrite. |

Every routine response includes chunk IDs, similarity scores, and locator data (heading, lines, page) alongside the rendered note, ensuring evidence is citable and locatable. Retrievals run before the write, and empty retrieval buckets are surfaced as warnings in the response.

## Templates & Capture Hygiene

### Canonical Templates

A `docs/templates/` directory contains the canonical field- and heading-guided templates that these routines reuse. `POST /notes/create` now exposes the same template rendering flow for manual note creation. Each template begins with YAML front matter:

```yaml
project: "{{project}}"
date: "{{date}}"
language: "{{language}}"
source: "template/<name>"
```

Required templates:

1. `daily.md` – Sections `## Morning Review`, `## Open Loops`, `## Today's Focus`.
2. `daily-debrief.md` – Sections `## Wins`, `## Lessons`, `## Open Loops / Follow-ups`.
3. `weekly.md` – Sections `## Highlights`, `## Stale Decisions`, `## Actions for Next Week` + `week_range` metadata.
4. `meeting.md` – Sections `## Agenda`, `## Relevant Decisions`, `## Post-Meeting Decisions`, `## Next Actions`.
5. `decision.md` – Sections `### Decision`, `### Context`, `### Evidence`, `### Rejected Options`, `### Next Actions`, optional `### Supersedes`.
6. `experiment.md` – Sections `## Hypothesis`, `## Setup`, `## Results`, `## Learnings`.
7. `recipe.md` – Sections `# Ingredients`, `# Steps`, `# Notes`, `# Source` with structured ingredient list.
8. `trip.md` – Sections `## Goals`, `## Learnings`, `## Checklist Seeds`, `## Follow-up`.
9. `trip-plan.md` – Sections `## Purpose`, `## Destinations`, `## Logistics`, `## Packing`, `## Questions to Answer`, `## Open Loops` + `trip_name`, `trip_dates` metadata.

Templates can contain placeholder variables (project, date) that the API expands before writing. The routine APIs share the same rendering logic used by `POST /notes/create`.

### Capture Hygiene Rules (Lint)

Lint rules are implemented and scan allowed vault paths before Fix Queue tasks are assembled. They flag:

- `missing_rationale`: Decision captures without a `Context` or `Evidence` section.
- `missing_rejected_options`: Decision captures lacking any rejected alternatives or reasons.
- `missing_metadata`: Notes missing required metadata fields (`project`, `date`, `language`, `source`).
- `missing_next_actions`: Meetings or debriefs without `Next Actions` or `Checklist Seeds`.

Lint output is surfaced in the Fix Queue (and later Coach Mode suggestions) with the note path and issue reason so the user can jump directly to the file and fix it.

## Feedback Loop & Fix Queue

### Feedback Controls

Every answer pane includes five feedback buttons: **Helpful**, **Wrong or missing source**, **Outdated**, **Too long**, **Didn’t answer**. Pressing a button hits `POST /feedback` and appends a structured log entry:

```json
{
  "question": "...",
  "timestamp": "2025-12-24T10:00:00Z",
  "project": "docs",
  "retrieved_source_ids": [123, 456],
  "answer_id": "ans_123",
  "feedback_reason": "wrong_source"
}
```

### Failure Dashboards

Failure metrics collected locally include:

- **Not found frequency** per project (percentage of feedback entries labeled `didnt_answer`). 
- **Missing metadata counts** (documents missing `source_date`, `project`, or `language`), plus top offenders by file count. 
- **Low indexed volume** per project (document counts below the health threshold).
- **Low retrieval hit rate** per project (recent searches returning zero results).
- **Stale notes/decisions** in configurable age buckets (default 3/6/12 months).
- **Repeated questions** (same query text >1 within rolling 48 hours). 
- **Permission denials** (scope/path blocks on `/routines/*` writes).
- **Capture lint issues** (missing rationale, rejected options, metadata, or next actions) from vault notes.

### Fix Queue Generation Rule

A runner converts these metrics into prioritized Fix Queue tasks (returned by `GET /health/fix-queue` and shown on the Fix Queue panel). Each task includes:

- `id`: stable identifier.
- `action`: `fix_metadata`, `fix_capture`, `run_routine`, `run_query`, `raise_scope`, `allow_path`, or `review_permissions`.
- `target`: file path or routine name.
- `reason`: human-readable explanation of the signal (e.g., not-found frequency or missing metadata).
- `priority`: derived from error severity and frequency.

Permission-denial tasks include `raise_scope` targets for blocked scope levels and `allow_path` targets for denied vault paths; repeated-question tasks surface the question text as the `target` with `action: run_query`. Lint tasks use `fix_capture` and point to the offending note path.

The Fix Queue screen lists tasks and lets the user run the associated routine (e.g., “Daily Check-in” for a not-found spike). Lint/metadata tasks include one-click open actions; permission/path/scope actions remain listed without remediation. Tasks tied to Coach Mode and routines surface before optional Generation improvements, ensuring the system remains grounded.

## Coach Mode Integration

Coach Mode routine suggestions now surface health-driven signals (feedback gaps, staleness, low coverage, permissions, ingestion errors) and follow these rules:

1. Evidence-backed suggestions cite the retrieval context (e.g., “Five open decisions lack final context; run a New Decision capture” with citations to the open decision notes).
2. When evidence is thin, the suggestion is labeled **Hypothesis** (e.g., “You have three repeated questions about trip planning; consider running Trip Debrief”).
3. The routine tag in Coach Mode links directly to the `/routines/<action>` endpoint so the user can execute the workflow from the suggestion.
4. Non-routine health prompts can link to quick actions (open indexing/health/settings or rerun a query) when available.

Planned: Coach Mode will surface lint-driven suggestions with citations and deeper Fix Queue remediation guidance (metadata fixes, capture lint, connector toggles) while respecting permission scopes (see `docs/PERMISSIONS.md`).

---

**See also:**

- `docs/UI_PLAN.md` for Routines & Fix Queue screen designs.
- `docs/API_CONTRACT.md` for the `/routines/<action>`, `/feedback`, and `/health` contracts.
