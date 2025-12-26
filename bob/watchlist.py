"""Watchlist helpers for onboarding local documents."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from bob.ingest.git_docs import is_git_url, normalize_git_url
DEFAULT_WATCHLIST_FILE = ".bob_watchlist.yaml"


def _normalize_path(path: str) -> str:
    """Return a normalized absolute path for comparison."""
    if is_git_url(path):
        return normalize_git_url(path)
    resolved = Path(path).expanduser().resolve(strict=False)
    return str(resolved)


def get_watchlist_path() -> Path:
    """Get the path to the watchlist file (env override supported)."""
    env_path = os.environ.get("BOB_WATCHLIST_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return Path.cwd() / DEFAULT_WATCHLIST_FILE


@dataclass
class WatchlistEntry:
    """Metadata for a watchlist target."""

    path: str
    project: str | None = None
    language: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the entry to a dict for storage."""
        data: dict[str, str | None] = {"path": self.path}
        if self.project:
            data["project"] = self.project
        if self.language:
            data["language"] = self.language
        return data


def load_watchlist(path: Path | None = None) -> list[WatchlistEntry]:
    """Load the watchlist entries from disk."""
    watchlist_path = path or get_watchlist_path()
    if not watchlist_path.exists():
        return []

    try:
        raw = yaml.safe_load(watchlist_path.read_text()) or []
    except yaml.YAMLError:
        return []

    entries: list[WatchlistEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path_value = item.get("path")
        if not path_value:
            continue
        entries.append(
            WatchlistEntry(
                path=path_value,
                project=item.get("project"),
                language=item.get("language"),
            )
        )
    return entries


def save_watchlist(entries: Iterable[WatchlistEntry], path: Path | None = None) -> None:
    """Persist watchlist entries to disk."""
    watchlist_path = path or get_watchlist_path()
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    data = [entry.to_dict() for entry in entries]
    watchlist_path.write_text(yaml.safe_dump(data, sort_keys=False))


def add_watchlist_entry(entry: WatchlistEntry, path: Path | None = None) -> bool:
    """Add a path to the watchlist if it does not already exist.

    Returns:
        True if the entry was added; False if it already existed.
    """
    current = load_watchlist(path)
    normalized_new = _normalize_path(entry.path)
    for existing in current:
        if _normalize_path(existing.path) == normalized_new:
            return False

    current.append(entry)
    save_watchlist(current, path)
    return True


def remove_watchlist_entry(target_path: str, path: Path | None = None) -> bool:
    """Remove the watchlist entry matching the provided path.

    Returns:
        True if an entry was removed; False otherwise.
    """
    current = load_watchlist(path)
    normalized_target = _normalize_path(target_path)
    filtered = [entry for entry in current if _normalize_path(entry.path) != normalized_target]
    if len(filtered) == len(current):
        return False

    save_watchlist(filtered, path)
    return True


def clear_watchlist(path: Path | None = None) -> None:
    """Remove all entries from the watchlist."""
    watchlist_path = path or get_watchlist_path()
    if watchlist_path.exists():
        watchlist_path.unlink()
