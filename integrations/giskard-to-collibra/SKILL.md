---
name: giskard-to-collibra
description: Export Giskard scan results into Collibra AI Governance. Use this whenever the user asks to export, push, sync, or import a Giskard scan, agent, or project (e.g. "Zephyr") into Collibra, or to update Collibra AI Governance assets, monitors, or Quality-tab metrics from Giskard. Also use it when the user asks to "retrieve the latest scan of a project and send it to Collibra", even if they do not say the word "export".
license: Apache-2.0
metadata:
  author: Giskard
  version: 1.0.0
  category: integration
  tags: [giskard, collibra, ai-governance, scan, vulnerability, export, metrics]
---

# Giskard to Collibra export

This skill is self-contained. `scripts/giskard_to_collibra.py` does the whole job: it finds the scan in Giskard Hub, builds the Collibra asset hierarchy (AI Agent, AI Agent Version, AI Endpoint, AI Monitors, and the deployment complex relation), imports it into Collibra, and pushes pass/fail metrics.

All paths below are relative to this skill's base directory.

## One-time setup

The user may not be technical. Do these checks for them and explain in plain language.

1. Check Python 3.10 or newer is available (`python3 --version`).
2. Install the dependencies: `python3 -m pip install -r requirements.txt`. If the environment blocks system-wide installs, create a virtualenv first and use its Python for every command below.
3. Check that a `.env` file exists in the current working directory (or next to the script) with values for all six variables listed in `env.example`. If the file is missing, or any of the six variables has no value, do not guess and do not proceed. Explicitly ask the user for each missing value, then create or complete `.env`. Never print or echo the secret values back.

## Run the export

1. If the user gives a scan ID, run `python3 scripts/giskard_to_collibra.py --scan-id <SCAN_ID>`. It exports exactly that scan. Done.
2. If the user gives a project ID, run `python3 scripts/giskard_to_collibra.py --project-id <PROJECT_ID>`. It exports the project's latest finished scan. Done.
3. If the user gives a project name (the usual case), first run `python3 scripts/giskard_to_collibra.py --list-projects`. It prints one `id  name` line per project. Match the user's words against the names yourself. Tolerate case differences and small typos ("zyphyr" means "Zephyr"). If the match is not obvious, show the names and ask the user. Then run with `--project-id <the matched id>`.

The script loads `.env` itself, waits for the Collibra import job, and prints a link to the agent asset in Collibra. Share that link with the user.

## Notes

- The script caps AI Monitors at 36 because Collibra's Quality-tab chart breaks above that. Do not raise `--max-monitors` past 36 unless the user insists.
- Re-runs are safe. Asset IDs are deterministic, so Collibra updates existing assets instead of duplicating them.
- If the import job ends with a result other than SUCCESS, the script prints the Collibra error message. Report it to the user instead of retrying blindly.
- The Collibra instance must have Collibra AI Governance. The asset types and the metrics endpoint the script uses only exist there. "Unknown type" import errors usually mean it is missing.
