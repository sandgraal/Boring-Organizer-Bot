"""Test configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from bob.config import reset_config
from bob.db.database import reset_database


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_markdown(temp_dir):
    """Create a sample markdown file."""
    content = """# Test Document

This is the introduction paragraph.

## Section One

This section has some content about topic A.
It spans multiple lines.

### Subsection 1.1

More detailed information here.

## Section Two

Another section with different content.
"""
    path = temp_dir / "test.md"
    path.write_text(content)
    return path


@pytest.fixture
def sample_recipe(temp_dir):
    """Create a sample recipe file."""
    content = """name: Test Recipe
description: A simple test recipe
prep_time: 10 minutes
cook_time: 20 minutes
servings: 4
ingredients:
  - item: flour
    amount: 2 cups
  - item: sugar
    amount: 1 cup
instructions:
  - Mix dry ingredients
  - Add wet ingredients
  - Bake at 350F
notes: This is a test recipe
"""
    path = temp_dir / "test.recipe.yaml"
    path.write_text(content)
    return path


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state between tests."""
    yield
    reset_config()
    reset_database()


@pytest.fixture
def test_db(temp_dir):
    """Create a test database."""
    from bob.db.database import Database

    db_path = temp_dir / "test.db"
    db = Database(db_path)
    db.migrate()
    yield db
    db.close()
