"""Watchlist helpers keep indexing installable."""

import pytest

from bob.watchlist import (
    WatchlistEntry,
    add_watchlist_entry,
    clear_watchlist,
    load_watchlist,
    remove_watchlist_entry,
)


@pytest.fixture(autouse=True)
def _watchlist_env(monkeypatch, tmp_path):
    """Redirect watchlist operations to a temporary file."""
    watchlist_file = tmp_path / "watchlist.yaml"
    monkeypatch.setenv("BOB_WATCHLIST_PATH", str(watchlist_file))
    yield
    if watchlist_file.exists():
        watchlist_file.unlink()


def test_add_and_load_watchlist(tmp_path):
    """Adding an entry stores it and returns it on load."""
    entry = WatchlistEntry(
        path=str(tmp_path / "notes"),
        project="personal",
        language="en",
    )

    assert add_watchlist_entry(entry)
    entries = load_watchlist()
    assert len(entries) == 1
    assert entries[0].project == "personal"
    assert entries[0].language == "en"


def test_watchlist_prevents_duplicates(tmp_path):
    """Duplicate paths are not re-added."""
    entry = WatchlistEntry(path=str(tmp_path / "docs"))
    assert add_watchlist_entry(entry)
    assert not add_watchlist_entry(WatchlistEntry(path=entry.path))

    entries = load_watchlist()
    assert len(entries) == 1


def test_remove_watchlist_entry(tmp_path):
    """Removing an entry deletes it from the list."""
    path = str(tmp_path / "docs")
    add_watchlist_entry(WatchlistEntry(path=path, project="personal"))
    assert remove_watchlist_entry(path)

    assert load_watchlist() == []
    assert not remove_watchlist_entry(path)


def test_clear_watchlist(tmp_path):
    """Clear removes the file."""
    add_watchlist_entry(WatchlistEntry(path=str(tmp_path / "docs")))
    clear_watchlist()

    assert load_watchlist() == []


def test_watchlist_handles_git_urls():
    """Git URLs are stored and de-duplicated."""
    url = "https://github.com/example/repo"
    assert add_watchlist_entry(WatchlistEntry(path=url))
    assert not add_watchlist_entry(WatchlistEntry(path=url))

    entries = load_watchlist()
    assert len(entries) == 1
    assert entries[0].path == url

    assert remove_watchlist_entry("https:/github.com/example/repo")
    assert load_watchlist() == []
