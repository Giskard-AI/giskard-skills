# Example 8 local verification (Vertex GLM)

Runs the **no-input cron invoice agent** pattern from `oss/checks/scenario-generator/references/examples.md` (Example 8) against a throwaway agent stub, with **Conformity** judges on **Vertex GLM** (`zai-org/glm-5.2-maas`).

This directory is for local/CI-style verification only. It does not register an agent on Giskard Hub.

## Prerequisites

- Python 3.12+
- Cloud Agent secret **`GLM_API_KEY`** (never commit or log the value)
- Optional env overrides:
  - `GLM_BASE_URL` — default: `https://aiplatform.googleapis.com/v1/projects/gsk-dev-497008/locations/global/endpoints/openapi`
  - `GLM_MODEL_ID` — default: `zai-org/glm-5.2-maas`

Install dependencies:

```bash
pip install giskard-checks openai
```

## Auth mapping (Vertex OpenAI-compatible)

Set:

```bash
export OPENAI_API_KEY="$GLM_API_KEY"
export OPENAI_BASE_URL="$GLM_BASE_URL"
```

The scripts also call `giskard.llm.configure(..., default_headers={"x-goog-api-key": ...})` because this endpoint rejects Bearer-only auth.

## Run

```bash
cd local-verify
python3 smoke_glm.py
python3 example8_invoice_cron.py
```

Outputs:

| File | Description |
|------|-------------|
| `example8_glm_result.json` | Full suite result (checks, Conformity reasons, traces) |
| `run_notes.txt` | Human summary of expected vs actual checks |
| `run_stdout.log` | Optional console capture (not required) |

## Stub agent behavior

`run_invoice_agent` in `example8_invoice_cron.py` intentionally:

- Copies `vendor_email` into `send_email` bodies (fails `no_ssn_in_outbound_email` when the email contains an SSN pattern).
- Approves once per invoice row (fails `at_most_one_payment_per_invoice` on duplicate rows).

FnChecks for injection and ERP error scenarios should **pass** on this stub; Conformity outcomes come from GLM.

## Hub

Running on Hub/Kestrel still requires your **Hub URL**, **API key**, and **project** — use the `hub-agent-setup` skill; nothing here substitutes for that.
