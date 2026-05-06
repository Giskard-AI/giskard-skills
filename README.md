# Giskard Skills
Agent skills to streamline adoption and usage of Giskard products — compatible with any coding agent, including Claude Code, Cursor, and others.

## Prerequisites

- Node.js with `npx`

## Available Skills

<table>
  <thead>
    <tr>
      <th width="20%">Skill</th>
      <th width="40%">Install Command</th>
      <th width="40%">When to Use</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>scenario-generator</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill scenario-generator</code></td>
      <td>Use when a user describes their AI agent and wants to create adversarial test scenarios, red-team their AI, generate evaluation suites, or build checks using the <code>giskard.checks</code> library. Triggers on phrases like "create scenarios", "test my agent", "evaluate my chatbot", "red-team my AI", or "generate checks".</td>
    </tr>
    <tr>
      <td>rag-evaluator</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill rag-evaluator</code></td>
      <td>Use when a user wants to evaluate a RAG (Retrieval-Augmented Generation) system or a Q&amp;A bot grounded in documents — for groundedness, answer relevance, retrieval quality, hallucination, citation accuracy, or out-of-scope refusal. Triggers on phrases like "evaluate my RAG", "test my retrieval", "check groundedness", "build a RAG eval suite", or "test if my agent hallucinates". Quality-focused; for adversarial / red-teaming use <code>scenario-generator</code> instead.</td>
    </tr>
  </tbody>
</table>

## Install as a Claude Code Plugin

This repository can also be used as a [Claude Code plugin](https://code.claude.com/docs/en/plugins). Clone the repo and start Claude with the `--plugin-dir` flag pointing at it:

```bash
claude --plugin-dir ./giskard-skills
```

Once Claude Code is running, use the `/giskard-skills` command to list the available skills.
