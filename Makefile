.PHONY: install dev lint format test check clean run help backup

# Default target
help:
	@echo "B.O.B Development Commands"
	@echo ""
	@echo "  make install    Install package in development mode"
	@echo "  make dev        Install with development dependencies"
	@echo "  make lint       Run linting checks"
	@echo "  make format     Format code with ruff"
	@echo "  make test       Run tests"
	@echo "  make check      Run all checks (lint + test)"
	@echo "  make clean      Clean build artifacts"
	@echo "  make init       Initialize the database"
	@echo "  make backup     Create a compressed backup"
	@echo ""
	@echo "CLI Commands (after install):"
	@echo "  bob init                    Initialize database"
	@echo "  bob index <paths>           Index documents"
	@echo "  bob ask '<question>'        Ask a question"
	@echo "  bob status                  Show status"
	@echo "  bob backup <path>           Backup database"
	@echo "  bob restore <path>          Restore database"

# Installation
install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pre-commit install

# Code quality
lint:
	ruff check bob tests
	ruff format --check bob tests
	mypy bob

format:
	ruff check --fix bob tests
	ruff format bob tests

# Testing
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=bob --cov-report=term-missing --cov-report=html

# Combined check
check: lint test

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Database
init:
	bob init

backup:
	@mkdir -p backups
	@echo "Creating backup..."
	bob backup backups/bob-$$(date +%Y-%m-%d-%H%M%S).db --compress
	@echo "Backup complete!"

# Development helpers
shell:
	python -c "from bob.db import get_database; db = get_database(); import code; code.interact(local=dict(db=db))"
