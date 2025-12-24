# Agent Prompts Library

This directory contains prompt templates for AI agents working with B.O.B.

## Structure

```
prompts/
├── README.md           # This file
├── system/             # System prompts for agents
├── tasks/              # Task-specific prompts
└── examples/           # Example interactions
```

## Usage

Prompts are plain text or markdown files that can be loaded and used by agents.

## Adding Prompts

1. Create a new file in the appropriate subdirectory
2. Use clear naming: `task-name.md` or `agent-role.md`
3. Include context about when to use the prompt

## Placeholder Syntax

Use `{{variable}}` for dynamic content:

```
You are analyzing a document from {{project}}.
The document was last updated on {{source_date}}.
```

## TODO

- [ ] Add system prompts for different agent roles
- [ ] Add task prompts for decision extraction
- [ ] Add example prompts for Q&A
