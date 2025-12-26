# B.O.B Permission Model

> Describes the explicit, local-first permission scopes that govern how routines, connectors, and writes operate inside the B.O.B vault. Agents, UI code, and tests must honor these levels to avoid hidden writes or inappropriate access.

**Last Updated:** 2025-12-24

---

## Permission Goals

1. **Local-first & manual**: No background daemons or automatic uploads. Every scope escalation is user-initiated, documented, and reversible.
2. **Scope-bounded writes**: Only Level 3 or higher may write, and those writes must originate from templates or controlled connectors.
3. **Optional deep access**: Calendar imports and manual browser saves are planned; they remain opt-in when implemented.
4. **Default configuration**: Ships with Level 3 enabled so routines can write; drop to Level 0 for read-only inspection when desired.

## Scope Levels

| Level | Capabilities | Notes |
| --- | --- | --- |
| **0 (Read)** | Search, retrieval, dashboards, feedback, Fix Queue viewing | Supported via `permissions.default_scope`; no writes permitted. |
| **1 (Calendar Import)** | Local ICS/CalDAV file ingestion APIs (e.g., `POST /connectors/calendar-import`) | Planned; no connector endpoints are implemented yet. |
| **2 (Browser Saves)** | Manual “save highlight/bookmark to vault” actions that produce well-formed markdown notes | Planned; no browser save endpoint or UI toggle is implemented yet. |
| **3 (Template Writes)** | Routine writes (`/routines/*`) that render from canonical templates | Implemented for routines only; `POST /notes/create` is not implemented yet. |
| **4 (External Accounts)** | Out of scope for now — no OAuth or cloud storage is supported | Mentioned for completeness but always denied in code. |

By default, operations run at scope level **3 (Template Writes)** so the routine APIs succeed. Drop the `permissions.default_scope` value toward `0` for read-only inspections and raise it back to `3` when you trust the vault directories the routines write to; denied attempts return `PERMISSION_DENIED`.

Calendar and browser connector toggles are defined in configuration but are not yet wired to any API endpoints or UI controls.

## Configuration

```yaml
permissions:
  default_scope: 3
  enabled_connectors:
    calendar_import: false
    browser_saves: false
  allowed_vault_paths:
    - vault/routines
    - vault/decisions
    - vault/trips
    - vault/meetings
    - vault/manual-saves
```

 - `default_scope` drives the initial experience (read-only vs template writes); the Fix Queue surfaces denials so you can raise it only when you trust the destination paths.
 - `enabled_connectors` is reserved for future connector endpoints; it is not enforced by the current API surface.
- `allowed_vault_paths` lists the directories (routines, decisions, trips, meetings, manual saves) that routine template writes may target; relative entries are resolved both against the configured `paths.vault` and against the repo root so you can move the vault without breaking the defaults. Any file outside this list is rejected before a write occurs.

## Enforcement & UI

- Routine endpoints (`/routines/*`) check `permissions.default_scope` and `permissions.allowed_vault_paths`. Insufficient scope or disallowed paths return `PERMISSION_DENIED` with the offending target path.
- Connector endpoints (`/connectors/*`) and `POST /notes/create` are not implemented yet, so no permission enforcement exists for them today.
- The UI does not currently gate write buttons or expose connector toggles based on permission scope.
- Permission denials are not yet recorded in an audit log or surfaced in Fix Queue metrics.

## Tests

No permission-specific tests exist yet. Planned coverage includes:

- `tests/test_permissions.py` — Level 0 blocks writes; Level 3 allows template writes to allowed paths only.
- `tests/test_routines_end_to_end.py` — Routine endpoints enforce scope + allowed paths.
- `tests/test_connectors.py` — Connector opt-ins and logs once connector endpoints are implemented.

## Agent Policy

Agents must consult this document before attempting to edit or write to the vault. The scope level for the current session should be declared in logs and the UI (`Settings > Permissions`). If a requested action would exceed the permitted scope, respond with `PERMISSION_DENIED` and propose an alternative (e.g., `Log the target info and let the user run the routine manually`).

---

**See also:** `docs/AGENTS.md` for agent contracts and `docs/ROUTINES_SPEC.md` for the concrete mappings between routines and vault paths.
