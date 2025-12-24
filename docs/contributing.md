# Contributing to B.O.B

Thank you for your interest in contributing to B.O.B!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Set up development environment:

```bash
cd Boring-Organizer-Bot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Development Workflow

1. Create a feature branch:

```bash
git checkout -b feat/my-feature
```

2. Make your changes with tests

3. Run checks:

```bash
make check  # Runs lint + test
```

4. Commit with conventional commit messages:

```
feat: add Excel sheet name filtering
fix: handle empty markdown files
docs: update architecture diagram
test: add chunker edge case tests
```

5. Push and open a PR

## What to Contribute

### Good First Issues

- Add tests for uncovered code paths
- Improve error messages
- Add documentation examples
- Fix typos and formatting

### Features

Check issues labeled `enhancement` or propose new features in discussions.

### Parsers

Adding support for new file types:

1. Create `bob/ingest/newformat.py`
2. Implement the `Parser` class
3. Register in `bob/ingest/registry.py`
4. Add tests in `tests/test_ingest_newformat.py`
5. Update documentation

## Code Review

All PRs are reviewed for:

- Code quality and style
- Test coverage
- Documentation
- Breaking changes

## Questions?

Open a discussion or issue if you're unsure about anything.
