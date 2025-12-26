"""Tests for capture hygiene linting."""

from __future__ import annotations

from pathlib import Path

from bob.config import Config, PathsConfig, PermissionsConfig
from bob.health.lint import collect_capture_lint_issues


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_capture_lint_detects_missing_sections(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    decision_path = vault / "decisions" / "decision-01.md"
    _write(
        decision_path,
        """---
project: "alpha"
date: "2025-01-01"
language: "en"
source: "template/decision"
---
# Decision Record

### Decision
- Summary:
""",
    )

    meeting_path = vault / "meetings" / "main" / "meeting-prep.md"
    _write(
        meeting_path,
        """---
project: "main"
date: "2025-01-02"
language: "en"
source: "template/meeting"
---
# Meeting Capture

## Agenda
- Item:
""",
    )

    trip_path = vault / "trips" / "italy" / "debrief.md"
    _write(
        trip_path,
        """---
project: "travel"
date: "2025-01-03"
language: "en"
source: "template/trip"
---
# Trip Debrief

## Goals
- Plan:
""",
    )

    routine_path = vault / "routines" / "daily" / "2025-01-01.md"
    _write(
        routine_path,
        """---
date: "2025-01-01"
language: "en"
source: "routine/daily-checkin"
---
# Daily Check-in
""",
    )

    config = Config(
        paths=PathsConfig(vault=vault),
        permissions=PermissionsConfig(
            allowed_vault_paths=[
                "vault/decisions",
                "vault/meetings",
                "vault/trips",
                "vault/routines",
            ]
        ),
    )

    issues = collect_capture_lint_issues(config, limit=10)
    codes = [issue.code for issue in issues]
    assert codes.count("missing_rationale") == 1
    assert codes.count("missing_rejected_options") == 1
    assert codes.count("missing_next_actions") == 2
    assert codes.count("missing_metadata") == 1

    paths = {issue.file_path for issue in issues}
    assert decision_path in paths
    assert meeting_path in paths
    assert trip_path in paths
    assert routine_path in paths


def test_capture_lint_filters_by_project(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    alpha_path = vault / "decisions" / "decision-alpha.md"
    _write(
        alpha_path,
        """---
project: "alpha"
date: "2025-01-01"
language: "en"
source: "template/decision"
---
# Decision Record

### Decision
- Summary:
""",
    )

    beta_path = vault / "decisions" / "decision-beta.md"
    _write(
        beta_path,
        """---
project: "beta"
date: "2025-01-02"
language: "en"
source: "template/decision"
---
# Decision Record

### Decision
- Summary:
""",
    )

    config = Config(
        paths=PathsConfig(vault=vault),
        permissions=PermissionsConfig(allowed_vault_paths=["vault/decisions"]),
    )

    issues = collect_capture_lint_issues(config, limit=10, project="alpha")
    assert issues
    assert {issue.file_path for issue in issues} == {alpha_path}
