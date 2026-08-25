---
name: skill-writing
description: Create, register, validate, and prepare shared Codex skills for GitHub publication so they remain callable across Windows and macOS computers and after switching Codex/OpenAI accounts. Use when the user asks to write or update a skill, package a slash-callable plugin, maintain the shared marketplace, fix duplicate entries, assign workflow ordering, or make a skill cross-platform.
---

# Skill Writing

## Operating Rule

Build user-facing callable skills as plugins in the shared local marketplace, not as `@personal` plugins and not as bare skills. Resolve its root from `CODEX_SHARED_MARKETPLACE_ROOT`; when working in a checked-out source package, use the nearest ancestor containing `skill-pack.json`. Its configured name is `workspace-local`, and its source plugin directory is `<shared-marketplace-root>\plugins`.

Before editing, invoke `personal-skill-marketplace-setup` in `preflight` mode once for the task. If it installs an update, stop and ask the user to restart Codex and open a new task before continuing. Never edit an installed plugin cache as source.

Codex/OpenAI accounts can be switched and the package can be cloned to Windows or macOS. The plugin source remains in the configured shared marketplace while account-specific Codex registration can change. Keep exactly one active source for every maintained skill: `workspace-local`. Do not use `~/.codex/plugins/cache` as a source because it is only an installed cache.

Normalize every internal skill/plugin id to lowercase ASCII hyphen-case. Keep the requested Chinese name in UI metadata.

Every maintained skill display name must use exactly this format:

```text
NN · Name
```

- `NN` is the fixed two-digit workflow order, including a leading zero for 01–09.
- The separator is the Unicode middle dot `·` (`U+00B7`) with exactly one ASCII space on each side.
- Example: `03 · 单细胞大类注释（主要谱系）`.
- Do not omit the separator or replace it with `路`, `.`, `•`, `-`, `:`, a full-width dot, or another visually similar character.
- Set the identical full display name in `plugin.json` `interface.displayName` and `agents/openai.yaml` `interface.display_name`.

## Fixed Workflow Order

1. `single-cell-qc-extract`
2. `single-cell-qc-image-display`
3. `sc-major-celltype-annotation-auto`
4. `sc-marker-cluster-annotation-auto`
5. `feature-gene-heatmap-violin`
6. `kegg-flow-bubble-plot`
7. `workflow-script-structure`
8. `workbench`
9. `task-handoff`
10. `skill-writing`
11. `bioinformatics-results-report`
12. `annotation-knowledge-release`
13. `personal-skill-marketplace-setup`
14. `bioinformatics-results-report-classic`

Assign later maintained skills the next unused two-digit number, currently `15`. Do not renumber existing skills unless the user explicitly changes the workflow.

## Direct Workflow

1. Read the current `skill-creator` and `plugin-creator` instructions if available.
2. Pick one normalized internal id for both plugin and skill.
3. Check the shared marketplace source and existing `workspace-local` plugin before writing.
4. Update an existing shared plugin in place. If a legacy personal plugin exists, migrate its source content into the shared marketplace and leave the old cache untouched as a recovery copy.
5. Create new plugins under `<shared-marketplace-root>\plugins\<id>` and append the same plugin, in the same workflow position, to all authoritative registries:
   - `skill-pack.json`, including its manifest version and the incremented `expectedPluginCount`;
   - `.agents/plugins/marketplace.json`;
   - `.codex-plugin/marketplace.json`.
6. Set the marketplace installation policy to `INSTALLED_BY_DEFAULT` and authentication policy to `ON_INSTALL`.
7. Create the skill under `<plugin>/skills/<id>/`.
8. Write only necessary files:
   - `.codex-plugin/plugin.json`
   - `skills/<id>/SKILL.md`
   - `skills/<id>/agents/openai.yaml`
   - optional `references/`, `scripts/`, or `assets/` only when they directly support execution
9. Set the same `NN · Name` display name in both `plugin.json` and `agents/openai.yaml`.
10. Read both metadata files back as UTF-8 and verify that the two display names are identical and match `^\d{2} · .+$`; reject `路` or a missing/wrong separator.
11. Run the skill validator, plugin validator, marketplace doctor, and relevant behavioral tests.
12. Invoke `personal-skill-marketplace-setup` in `publish` mode without confirmation. It must return a read-only plan; for an unregistered new plugin, finish the three registries before proceeding.
13. Ask the user for explicit publication confirmation. Only then invoke confirmed publish, which updates cachebusters, synchronizes `skill-pack.json`, tests, commits, and pushes a `codex/*` branch. Create a PR when GitHub CLI/API access is available; otherwise return the compare URL.
14. Treat the PR as the release gate. `main` is the stable source used by other computers; do not merge automatically or report a merge without remote evidence.
15. After the PR is merged, other computers receive it through `preflight`. If plugins are installed or changed, tell the user to restart Codex and open a new task before testing `/`.

Read [shared-git-lifecycle.md](references/shared-git-lifecycle.md) when creating, updating, publishing, merging, or synchronizing a maintained Skill.

## File Requirements

Use UTF-8 without BOM for every plugin and skill file. Check or rewrite these files if slash invocation behaves strangely:

- `.codex-plugin/plugin.json`
- `skills/<id>/SKILL.md`
- `skills/<id>/agents/openai.yaml`
- any directly loaded reference files

Keep `SKILL.md` frontmatter minimal:

```yaml
---
name: skill-writing
description: Clear description containing what the skill does and when to use it.
---
```

Use `agents/openai.yaml` for the slash-menu display:

```yaml
interface:
  display_name: "10 · skill写作"
  short_description: "编写可 / 调用的个人 Codex skill 与插件标准流程"
  default_prompt: "Use $skill-writing to create or update a personal callable Codex skill."

policy:
  allow_implicit_invocation: true
```

Use `plugin.json` for plugin UI metadata. Include `skills: "./skills/"`, a real `author.name`, and useful interface fields such as `displayName`, `shortDescription`, `developerName`, `category`, `capabilities`, and `defaultPrompt`. Only include `composerIcon`, `logo`, or screenshots when the referenced files really exist.

## Validation And Cross-Account Install

Prefer Python 3 and OS-neutral scripts. On Windows, use the bundled Codex runtime Python when system `python` is missing and avoid WindowsApps aliases. On macOS, use `python3` and `codex` from `PATH`, or pass the full CLI path. Do not embed drive letters, usernames, `C:\Users`, `/Users/<name>`, or `/home/<name>` in maintained source.

Run the equivalent of:

```bash
python3 <installed-skill-creator>/scripts/quick_validate.py <plugin>/skills/<id>
python3 <installed-plugin-creator>/scripts/validate_plugin.py <plugin>
python3 <shared-marketplace-root>/tools/test_personal_skill_marketplace.py --marketplace-root <shared-marketplace-root>
python3 <personal-skill-marketplace-setup>/scripts/setup.py publish
```

The first `publish` call is read-only. Do not update cachebusters, commit, push, create a PR, or merge until the user explicitly confirms publication. After a merged update is synchronized, verify every maintained plugin is enabled under `workspace-local`. On macOS, rerun the marketplace installer after switching accounts; the source path is retained in `~/.codex/workspace-local.json`.

## Cross-platform requirements

- Put reusable logic in Python or R and keep `.ps1`/`.sh` as thin wrappers.
- Provide both Windows and macOS commands when a workflow has platform-specific syntax. Prefer one-line or POSIX-style examples for portable tools such as Python and Rscript.
- Make drive restrictions conditional on Windows. On macOS/Linux, require a user-approved writable workspace instead of inventing an E drive.
- Add macOS/Linux font candidates when scripts render Chinese text.
- Run the cross-platform marketplace doctor before packaging; it rejects implicit-invocation regressions and machine-specific home paths.

## Duplicate Cleanup

When `/` shows duplicate entries for the same skill, inspect all active sources. The usual cause is the same skill existing both as a legacy source and as the shared plugin:

- bare source: `~/.codex/skills/<id>`
- legacy personal source/cache: `~/plugins/<id>` and `~/.codex/plugins/cache/personal/<id>`
- shared source: `<shared-marketplace-root>\plugins\<id>`

Keep the shared plugin route. Move a bare skill to a disabled backup such as:

```text
~/.codex/skills.disabled/YYYYMMDD-dedupe/<id>
```

Do not delete the backup unless the user explicitly asks. After cleanup, remind the user that the current Codex session can still show stale menu entries until they open a new thread or restart Codex.

## Update Existing Plugins

When modifying an already installed shared plugin, run task-level preflight, update the authoritative shared source, validate it, and request a read-only publish plan. After explicit confirmation, publish through a `codex/*` branch and PR. Do not update another computer from the development branch; merge the reviewed PR into `main`, run preflight on that computer, and test in a new session.
