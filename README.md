# Giskard Skills
Agent skills to streamline adoption and usage of Giskard products — compatible with any coding agent, including Claude Code, Cursor, and others.

## Prerequisites

- Node.js with `npx`

## Available Skills

<table>
  <thead>
    <tr>
      <th width="20%">Skill</th>
      <th width="30%">Install Command</th>
      <th>When to Use</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>scenario-generator</td>
      <td><code>npx skills add Giskard-AI/giskard-skills --skill scenario-generator</code></td>
      <td>Use when a user describes their AI agent and wants to create adversarial test scenarios, red-team their AI, generate evaluation suites, or build checks using the <code>giskard.checks</code> library. Triggers on phrases like "create scenarios", "test my agent", "evaluate my chatbot", "red-team my AI", or "generate checks".</td>
    </tr>
  </tbody>
</table>
