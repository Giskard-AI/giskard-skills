# Giskard Skills
Agent skills to streamline adoption and usage of Giskard products — compatible with any coding agent, including Claude Code, Cursor, and others.

## Prerequisites

- Node.js with `npx`

## Available Skills

| Skill | Install Command | When to Use |
|-------|-----------------|-------------|
| scenario-generator | `npx skills add Giskard-AI/giskard-skills --skill scenario-generator` | Use when a user describes their AI agent and wants to create adversarial test scenarios, red-team their AI, generate evaluation suites, or build checks using the `giskard.checks` library. Triggers on phrases like "create scenarios", "test my agent", "evaluate my chatbot", "red-team my AI", or "generate checks". |
