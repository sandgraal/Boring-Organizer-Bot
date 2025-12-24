# Conventions

## Code Style

- Python 3.11+
- Formatted with `ruff format`
- Linted with `ruff check`
- Type checked with `mypy --strict`

## Naming

- **Files**: lowercase with underscores (`my_module.py`)
- **Classes**: PascalCase (`MyClass`)
- **Functions/Variables**: snake_case (`my_function`)
- **Constants**: UPPERCASE (`MY_CONSTANT`)

## Documentation

- All public functions have docstrings (Google style)
- Module-level docstrings explain purpose
- Type hints on all function signatures

Example:

```python
def my_function(param: str, count: int = 5) -> list[str]:
    """Short description of function.

    Longer description if needed, explaining behavior,
    edge cases, and important notes.

    Args:
        param: Description of param.
        count: Description of count.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param is empty.
    """
```

## Error Handling

- Use specific exception types
- Log errors with context
- Provide helpful error messages for CLI

## Testing

- Tests in `/tests` mirror `/bob` structure
- Unit tests for pure functions
- Integration tests for CLI and database
- Use fixtures for database setup/teardown

## Git

- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
- Keep commits focused and atomic
- Write clear commit messages

## Adding Features

1. Create branch from `main`
2. Implement with tests
3. Update documentation
4. Run `make check`
5. Open PR

## File Organization

```
bob/
├── __init__.py          # Version and package info
├── config.py            # Configuration management
├── cli/                 # CLI commands
├── api/                 # FastAPI server and routes
├── ui/                  # Static web interface assets
├── db/                  # Database and migrations
├── ingest/              # Document parsers
├── index/               # Chunking and embedding
├── retrieval/           # Search functions
├── answer/              # Output formatting
├── eval/                # Evaluation harness
├── agents/              # Agent tool interfaces
└── extract/             # Decision extraction
```

## Dependencies

- Core deps in `[project.dependencies]`
- Dev deps in `[project.optional-dependencies.dev]`
- Optional features (like LLM) in separate optional groups

## Configuration Priority

1. Environment variables (highest)
2. `./bob.yaml`
3. `~/.config/bob/bob.yaml`
4. Default values (lowest)
