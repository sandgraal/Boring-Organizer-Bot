"""Git repository documentation parser.

Only indexes README and /docs directory from git repositories.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

from bob.config import get_config
from bob.ingest.base import ParsedDocument
from bob.ingest.registry import get_parser


def is_git_url(path: str) -> bool:
    """Check if a path is a git URL."""
    return path.startswith(("http://", "https://", "git@", "git://"))


def clone_repo(url: str, target_dir: Path) -> str:
    """Clone a git repository.

    Args:
        url: Repository URL.
        target_dir: Directory to clone into.

    Returns:
        The commit SHA of HEAD.
    """
    import git

    config = get_config()
    repo = git.Repo.clone_from(
        url,
        target_dir,
        depth=config.git_docs.clone_depth,
        branch=config.git_docs.default_branch,
    )
    return repo.head.commit.hexsha


def find_docs_files(repo_dir: Path) -> Iterator[Path]:
    """Find documentation files in a cloned repository.

    Args:
        repo_dir: Path to cloned repository.

    Yields:
        Paths to documentation files.
    """
    config = get_config()

    for include_path in config.git_docs.include_paths:
        target = repo_dir / include_path

        if target.is_file():
            yield target
        elif target.is_dir():
            # Recursively find supported files
            for ext_list in config.paths.extensions.values():
                for ext in ext_list:
                    yield from target.rglob(f"*{ext}")


def parse_git_repo(
    url: str,
    project: str,
) -> Iterator[ParsedDocument]:
    """Parse documentation from a git repository.

    Args:
        url: Repository URL.
        project: Project name for indexing.

    Yields:
        ParsedDocument for each documentation file.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir)
        commit_sha = clone_repo(url, repo_dir)

        # Parse URL for repo name
        parsed = urlparse(url)
        repo_name = parsed.path.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        for doc_path in find_docs_files(repo_dir):
            parser = get_parser(doc_path)
            if parser is None:
                continue

            try:
                parsed_doc = parser.parse(doc_path)

                # Add git metadata
                relative_path = doc_path.relative_to(repo_dir)
                parsed_doc.source_path = f"{url}#{relative_path}"
                parsed_doc.source_type = "git"
                parsed_doc.metadata["project"] = project
                parsed_doc.metadata["git_repo"] = url
                parsed_doc.metadata["git_commit"] = commit_sha
                parsed_doc.metadata["git_file"] = str(relative_path)

                # Update locators with git context
                for section in parsed_doc.sections:
                    section.locator_value["git_file"] = str(relative_path)
                    section.locator_value["git_commit"] = commit_sha[:8]

                yield parsed_doc

            except Exception as e:
                # Log error but continue with other files
                import logging

                logging.warning(f"Failed to parse {doc_path}: {e}")
                continue
