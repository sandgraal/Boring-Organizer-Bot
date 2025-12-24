# Agent Prompts Library

This directory contains prompt templates for AI agents working with B.O.B.

## Overview

These prompts define roles, responsibilities, success criteria, and guardrails for AI agents that contribute to the B.O.B project. Each agent has a specific scope and must follow the contracts defined in `docs/AGENTS.md`.

## Agent Types

| Agent         | Prompt File                              | Scope                            |
| ------------- | ---------------------------------------- | -------------------------------- |
| **Indexer**   | [indexer_agent.md](indexer_agent.md)     | Add parsers, improve chunking    |
| **Retrieval** | [retrieval_agent.md](retrieval_agent.md) | Search quality, scoring, ranking |
| **Citation**  | [citation_agent.md](citation_agent.md)   | Locator precision, output format |
| **Decision**  | [decision_agent.md](decision_agent.md)   | Extract and manage decisions     |
| **Eval**      | [eval_agent.md](eval_agent.md)           | Golden sets, metrics, regression |
| **Docs**      | [docs_agent.md](docs_agent.md)           | Documentation consistency        |

## Structure

```
prompts/
├── README.md              # This file
├── indexer_agent.md       # Indexer agent prompt
├── retrieval_agent.md     # Retrieval agent prompt
├── citation_agent.md      # Citation agent prompt
├── decision_agent.md      # Decision agent prompt
├── eval_agent.md          # Evaluation agent prompt
├── docs_agent.md          # Documentation agent prompt
└── system/
    └── retrieval.md       # System prompt for retrieval
```

## Using Prompts

### For AI Agents

1. Read the relevant prompt file before starting a task
2. Follow the scope and success criteria
3. Use the checklist before completing work
4. Stop and ask when stop conditions are met
5. Always include citations and date confidence in outputs

### For Humans

1. Reference prompts when creating issues/tasks
2. Use task templates from `docs/TASK_TEMPLATES.md`
3. Review agent work against the checklist

## Prompt Components

Each agent prompt includes:

### 1. Role Definition

What the agent is responsible for and what it's NOT responsible for.

### 2. Success Criteria

How to measure if the work is successful.

### 3. Allowed Tools

What resources the agent can use:

- Repository files (always allowed)
- External resources (only if explicitly permitted)
- Never: network calls, external APIs, user's personal data

### 4. Required Outputs

What files/artifacts must be produced.

### 5. Stop Conditions

When to pause and ask for human input:

- Ambiguous requirements
- Breaking changes
- Security concerns
- Missing test coverage

### 6. Checklist

Final verification before completing work.

## Non-Negotiable Rules

All agents must follow these rules (from `docs/AGENTS.md`):

1. **Citations required** — Every answer must cite sources
2. **Date confidence** — Always include in outputs
3. **Local-first** — No cloud dependencies for core features
4. **No background daemons** — Manual commands only
5. **Data safety** — Never commit personal content

## Adding New Prompts

1. Create new file: `prompts/<agent_type>_agent.md`
2. Follow the template structure from existing prompts
3. Include all required sections
4. Update this README with the new agent

## Placeholder Syntax

Use `{{variable}}` for dynamic content in prompts:

```
You are analyzing a document from {{project}}.
The document was last updated on {{source_date}}.
```

---

## Sources

- [AGENTS.md](../docs/AGENTS.md) — Agent contracts
- [TASK_TEMPLATES.md](../docs/TASK_TEMPLATES.md) — Task formats

**Date Confidence:** HIGH (document updated 2025-12-23)
