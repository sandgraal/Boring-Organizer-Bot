# B.O.B Permission Model

> Describes the explicit, local-first permission scopes that govern how routines, connectors, and writes operate inside the B.O.B vault. Agents, UI code, and tests must honor these levels to avoid hidden writes or inappropriate access.

**Last Updated:** 2025-12-24

---

## Permission Goals

1. **Local-first & manual**: No background daemons or automatic uploads. Every scope escalation is user-initiated, documented, and reversible.
2. **Scope-bounded writes**: Only Level 3 or higher may write, and those writes must originate from templates or controlled connectors.
3. **Optional deep access**: Calendar imports and manual browser saves exist but are opt-in and recorded in settings.
4. **Trustworthy defaults**: Start at Level 0 (read-only) and escalate only when the user explicitly enables a connector or routine.

## Scope Levels

| Level | Capabilities | Notes |
| --- | --- | --- |
| **0 (Read)** | Search, retrieval, dashboards, feedback, Fix Queue viewing | Default for every user; no writes permitted. |
| **1 (Calendar Import)** | Local ICS/CalDAV file ingestion APIs (e.g., `POST /connectors/calendar-import`) | Optional opt-in in UI; stored under `vault/calendar/`; import logs show enablement time. |
| **2 (Browser Saves)** | Manual “save highlight/bookmark to vault” actions that produce well-formed markdown notes | Requires explicit toolbar button; writes go into `vault/manual-saves/`; always synchronous and logged. |
| **3 (Template Writes)** | All routine/actions writes (`POST /notes/create`, `/routines/*`) that render from canonical templates | Vault paths locked to `vault/routines/`, `vault/decisions/`, `vault/trips/`; any attempt to point elsewhere is rejected and reported to Fix Queue. |
| **4 (External Accounts)** | Out of scope for now — no OAuth or cloud storage is supported | Mentioned for completeness but always denied in code. |

By default, operations run at scope level **3 (Template Writes)** so the routine APIs succeed. Drop the `permissions.default_scope` value toward `0` for read-only inspections and raise it back to `3` (plus connector toggles) when you trust the vault directories the routines write to; denied attempts are surfaced in the Fix Queue and the API returns `PERMISSION_DENIED`.

Calendar and browser connector toggles are grouped in settings (see `bob.yaml` snippet below and the UI settings panel) and default to `false`. Activating them flips the scope flag for that project/session, guaranteeing user control over deep access.

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
    - vault/manual-saves
```

 - `default_scope` drives the initial experience (read-only vs template writes); the Fix Queue surfaces denials so you can raise it only when you trust the destination paths.
 - `enabled_connectors` toggles optional deep access; flipping one pushes the session to the matching level and logs the event for Fix Queue analytics.
- `allowed_vault_paths` lists the directories that template-enabled APIs may target; relative entries are resolved both against the configured `paths.vault` and against the repo root so you can move the vault without breaking the defaults. Any file outside this list is rejected before a write occurs.

## Enforcement & UI

- APIs that write (routine endpoints, `POST /notes/create`, manual highlight saves) first check the caller’s `scope_level`. If it is insufficient, they return a structured error (`error.code=PERMISSION_DENIED`, `details.scope_level`). 
- The UI Settings page greys out write buttons unless the required scope is granted and displays a banner for optional connectors (calendar or browser saves) that links to the same toggles. 
- Audit logs include `permission_level`, `action`, and `target_path` so Fix Queue and `GET /health` can surface denied attempts as health alerts.
- Attempting to write anywhere outside `permissions.allowed_vault_paths` also returns `PERMISSION_DENIED` with `allowed_paths` and the target path included so the Fix Queue can flag vault misconfiguration before any template is created.

## Tests

| Test | Description | File |
| --- | --- | --- |
| `tests/test_permissions.py` | Ensure Level 0 cannot write, Level 1/2 toggles remain opt-in, Level 3 writes only to allowed templates. | `tests/test_permissions.py` |
| `tests/test_routines_end_to_end.py` | Confirms `/routines/*` endpoints enforce scope, document path, and template-only writes. | `tests/test_routines_end_to_end.py` |
| `tests/test_connectors.py` | Calendar import and browser save endpoints respect opt-in toggles and log the connector enablement time. | `tests/test_connectors.py` |

## Agent Policy

Agents must consult this document before attempting to edit or write to the vault. The scope level for the current session should be declared in logs and the UI (`Settings > Permissions`). If a requested action would exceed the permitted scope, respond with `PERMISSION_DENIED` and propose an alternative (e.g., `Log the target info and let the user run the routine manually`).

---

**See also:** `docs/AGENTS.md` for agent contracts and `docs/ROUTINES_SPEC.md` for the concrete mappings between routines and vault paths.
