# QA: PR #22 — triggered / no-input agents (`hub-agent-setup`)

**Branch:** `claude/no-input-agents-071832`  
**Scope:** Skill QA only (not Kestrel deploy, not Hub live registration).  
**Date:** 2026-10-28  

## Verdict

The PR description matches the shipped skill content and `tool_mocks.py` behavior. Offline checks pass (packaging, skills CLI install, `tool_mocks` self-test, Example 8 stub + FnChecks). **Live Hub registration, connection test with detailed `input_schema`, and mock-driven Hub judges were not run** (no Hub credentials in this environment).

**Recommendation:** Merge after one live Hub smoke on a throwaway Structured agent (steps below). Optional doc nits do not block merge.

---

## 1. Document review vs PR description

| PR claim | Review |
| --- | --- |
| `triggered-agents.md`: recognize triggered/hybrid, `{inputs, mocks}` in, `{summary, tool_calls, side_effects}` out | **Accurate.** Matches `hub/hub-agent-setup/references/triggered-agents.md`. |
| Mock rules: ordered list, `when` / `returns` / `sequence` / `error`, shorthand single rule | **Accurate.** Documented and implemented in `scripts/tool_mocks.py`. |
| Wrapper duties: per-request reset, injection seams, neutralized writes, trace output | **Accurate.** Includes lock/concurrency, `max_iterations`, local mock verification step. |
| Discoverability: Mockable tools in `description`; `build_input_schema()` supplementary; fallback `"mocks": {"type": "object"}` | **Accurate.** `SKILL.md` step 4 and triggered-agents §Make the mock surface discoverable align. |
| `tool_mocks.py` stdlib-only, copy beside wrapper | **Accurate.** 275 lines; skills CLI install copies skill tree including script. |
| `scenario-generator` Example 8 + no-input subsection | **Accurate.** Example 8 uses same envelope and `ToolHarness`; SKILL §No-input agents cross-links hub skill. |
| Plugin 1.3.0 → 1.4.0 | **Verified.** `.claude-plugin/plugin.json` and `.grok-plugin/plugin.json` both `1.4.0`. |
| `hub-agent-setup` metadata `1.2.0` | **Verified** in `SKILL.md` frontmatter. |

**Cross-doc consistency (minor):**

- `scenario-generator` SKILL says `metadata={"side_effects": {...}}` (object), while Example 8 / `local-verify` record `side_effects` as a **flat list** of write records. Hub triggered contract shows a **grouped** audit object (`emails_sent`, etc.). All three shapes are usable if callers agree; worth one sentence in `triggered-agents.md` that giskard-checks examples may use a flat recorder list in `Interaction.metadata` while the Hub wrapper should prefer the grouped audit shape from the doc.
- Example 8 does not pass `parameters=` to `ToolHarness`; triggered-agents recommends it for rejecting bad `when` keys at validation time. Fine for demos; live wrappers should pass tool parameter names.

**`local-verify/`:** Helpful QA artifacts (Vertex GLM run notes, stub agent). Not part of plugin manifests; default `GLM_BASE_URL` points at an internal-looking Vertex project—acceptable for team QA, not required for skill consumers.

---

## 2. Offline checks executed

| Check | Result |
| --- | --- |
| `python3.12 scripts/smoke_plugins.py packaging` | **PASS** — 5 skills; manifests match |
| `python3.12 scripts/smoke_plugins.py skills` | **PASS** — hub-agent-setup copied with `scripts/tool_mocks.py` |
| `npx @anthropic-ai/claude-code@2.1.263 plugin validate .` | **PASS** |
| `artifacts/qa_tool_mocks_selftest.py` (Python 3.12) | **PASS** — static, `when` (incl. `"102"`/`102`, `true`≠`1`, null/omitted), sequence repeat, error raise/return, unknown tool + fake exception with `raise_errors=False`, deep-copy on `returns`, validation typos/unknown tools/unknown `when` args, `build_input_schema` shape |
| Example 8 stub (`local-verify/example8_invoice_cron.py` + `run_tick`) | **PASS** — intentional SSN leak and duplicate payment detected; ERP error mock does not crash; mocked read shows `"mocked": true` |
| Full Example 8 suite **without** `GLM_API_KEY` (`giskard-checks` 1.0.6) | **Expected:** FnChecks injection + ERP **PASS**; PII + duplicate **FAIL** on stub; Conformity checks **ERROR** (no judge); `SuiteResult.model_dump_json()` **succeeds** (~33k chars) |
| `uv run … smoke_plugins` (README path) | **Skipped** — `uv` not installed on VM; used `python3.12` + pip smoke deps instead |
| Grok catalog smoke | **Skipped** — requires downloading pinned `plugin_catalog.py` per README |

Re-run helpers (optional):

```bash
python3.12 artifacts/qa_tool_mocks_selftest.py
cd local-verify && pip install 'giskard-checks>=1.0.6' && python3.12 ../artifacts/qa_example8_offline.py
```

---

## 3. Gaps for REAL Hub registration (live steps)

Not executed here. Follow **`hub-agent-setup`** with user-supplied credentials only.

### 3.1 Environment

- `GISKARD_HUB_BASE_URL`, `GISKARD_HUB_API_KEY`, target **project id/name**
- `AGENT_WRAPPER_API_KEY` (separate from Hub key)
- HTTPS wrapper URL (deploy or tunnel) + `POST /giskard/invoke` (or chosen path)

### 3.2 Register Structured triggered agent

1. Implement wrapper `invoke(body)` per `triggered-agents.md` (harness, fresh world, write fakes/recorders, return trace).
2. **`input_schema`:** start with `build_input_schema(tool_specs)` from copied `tool_mocks.py`.
3. **`output_schema`:** required `summary`, `tool_calls`, `side_effects` (as in triggered-agents).
4. **`auto_bindings`:** `[]`.
5. **`description`:** product paragraph + **Mockable tools** block (names, params, return shapes, example rules, flagged write tools).
6. **`hub.agents.create`** (or update) with `headers: {"X-API-Key": wrapper_key}`.

### 3.3 If Hub rejects detailed `input_schema`

Documented fallback in triggered-agents:

- Replace per-tool `mocks` properties with `"mocks": {"type": "object"}` only.
- Rely on **description** Mockable tools section for Kestrel/scenario generators.
- Re-run **`hub.agents.test_connection`** with the simplified schema.

**Unknown until live test:** whether ART Hub accepts the full `anyOf` / `oneOf` rule schema for every tool, or whether connection test sample payload fails validation before the wrapper is hit.

### 3.4 Connection test vs mocks

- `test_connection` typically sends a sample **without** `mocks` → one full agent run on default fakes (slow; raise wrapper timeout).
- Does **not** prove per-tool mock wiring; after pass, send a manual **`generate_completion`** or evaluation input with `mocks.get_pending_invoices` containing SSN in `vendor_email` and confirm a Hub judge/scenario flags `send_email` arguments (PR verification checklist).

### 3.5 Pre-register local safety (skill-required)

One local POST per mock kind (static, `when`, `sequence`, `error`) confirming `"mocked": true/false`, writes hit fakes only, error mock does not crash—see [verify-the-mocks-locally](hub/hub-agent-setup/references/triggered-agents.md#verify-the-mocks-locally).

---

## 4. Recommended skill fixes (optional, pre- or post-merge)

| Priority | Fix |
| --- | --- |
| Low | One paragraph in `triggered-agents.md` reconciling **grouped** Hub `side_effects` vs **flat list** in giskard-checks Example 8 metadata. |
| Low | Example 8 comment: optional `parameters={...}` from tool definitions for stricter mock validation. |
| Low | `hub-sdk.md`: one-line pointer to `triggered-agents.md` for Structured `{inputs, mocks}` registration (today only in wrapper-contracts link). |
| Process | Add a committed `tests/test_tool_mocks.py` or document `artifacts/qa_tool_mocks_selftest.py` in README Dev checks so PR verification is one command (PR claims unit-check but no test file in repo). |

No code changes were required for QA pass; branch left unchanged except this artifact.

---

## 5. Draft PR comment (not posted)

> **QA (skill-focused, no Hub live):** Reviewed `triggered-agents.md`, `tool_mocks.py`, `SKILL.md` routing, and Example 8 against the PR description — aligned. Ran `smoke_plugins.py packaging` + `skills`, Claude `plugin validate`, and a local `tool_mocks` self-test (all pass). Re-ran Example 8 stub: FnChecks behave as documented (SSN + duplicate fail on intentional leaky stub; injection/ERP pass); without `GLM_API_KEY`, Conformity ERRORs and `model_dump_json()` still works. **Still needed before we call this fully verified:** one real Hub Structured registration + `test_connection` (try full `build_input_schema`, fall back to loose `mocks` if Hub rejects), then a mocked SSN-in-`get_pending_invoices` completion to confirm judges see `tool_calls`. Optional doc nit: clarify `side_effects` list vs grouped audit object between checks examples and Hub wrapper.

---

## 6. Files reviewed

- `hub/hub-agent-setup/SKILL.md`
- `hub/hub-agent-setup/references/triggered-agents.md`
- `hub/hub-agent-setup/references/wrapper-contracts.md`
- `hub/hub-agent-setup/scripts/tool_mocks.py`
- `oss/checks/scenario-generator/SKILL.md` (no-input section)
- `oss/checks/scenario-generator/references/examples.md` (Example 8)
- `local-verify/example8_invoice_cron.py` (stub verification)
