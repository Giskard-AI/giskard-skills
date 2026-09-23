# Maintaining skills and plugin support

## Skill changes

- Each skill has its own directory containing `SKILL.md`, with YAML frontmatter that includes a unique `name` matching the directory name and a nonempty `description`. Keep supporting references and scripts inside that directory so installations remain self-contained.
- When adding, renaming, or removing a skill, update the available-skills table in `README.md` and the `skills` array in **both** `.claude-plugin/plugin.json` and `.grok-plugin/plugin.json`.
- The two manifests must remain identical. List individual skill directories (for example `./hub/hub-agent-setup`), never parent collections such as `./hub/`. Grok's indexer does not recursively discover skills from those collection paths.
- When updating a skill, review its dependencies, credentials, and network behavior against the README and update that documentation if needed.
- Keep plugin versions synchronized. Bump the plugin version for a release that changes shipped skills or resources; also update the changed skill's `metadata.version` when applicable. CI-only changes do not require a plugin version bump.

## Validation

Follow the commands in the README's **Development checks** section. `.github/workflows/plugin-smoke.yml` runs shared packaging checks, Claude's validator, Grok's indexer, and `npx skills` installation checks on pull requests and pushes to `main`. Use uv to manage Python and the smoke-test dependencies; CI uses Python 3.14 and Node.js 24 LTS.

- Packaging checks require the manifests to include every tracked `SKILL.md` exactly once. Add new skill files to Git's index before running the checks; the snapshots use the current contents of tracked files, including uncommitted edits.
- Verify discovery with the real provider tooling. Do not replace those checks with a homemade approximation of a provider's loader.
- The skills CLI check installs into a temporary project for Claude Code, Cursor, and Grok and compares every tracked skill file, including references and scripts, with the installed copy.
- Keep smoke tests free of model calls, service credentials, live exports, and tunnels. They verify packaging and discovery, not whether an agent follows the skill correctly. They must not install skills globally or modify the developer's agent configuration.
- External tools are pinned: Claude and the Grok indexer in the workflow, the skills CLI in `scripts/smoke_plugins.py`, and Python dependencies in `scripts/requirements-smoke.txt`. Update pins deliberately and rerun the relevant checks.
- When changing GitHub Actions versions, verify the exact tag or commit exists and contains `action.yml`. A release such as `v10.2.0` does not guarantee a `v10` alias exists. Pin setup-uv to its verified release commit with a version comment.

## New plugin or marketplace support

- Distinguish a new plugin format from a marketplace listing. A marketplace that already accepts an existing manifest may need only a catalog entry, not another manifest.
- Read the provider's current official requirements and validate with its tooling before claiming compatibility.
- For a new plugin format, add its manifest and document its installation path. Extend `MANIFESTS` and the packaging checks in `scripts/smoke_plugins.py`, plus the CI matrix and provider validation steps. Preserve identical manifests where schemas allow; if a provider requires different fields, compare shared metadata and skill coverage explicitly instead of dropping consistency checks.
- For a new skills CLI target, add its agent identifier and expected installation directory to the installation check. Do not claim runtime compatibility based solely on copied files.
- For a marketplace submission, follow that catalog's pinning, generation, and validation requirements separately. For xAI, pin a published commit SHA, regenerate its component index, and run its catalog checks in the marketplace repository.
