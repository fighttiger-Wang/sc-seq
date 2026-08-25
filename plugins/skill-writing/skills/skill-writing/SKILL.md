---
name: skill-writing
description: Create or update shared local Codex skills that remain callable across Windows and macOS computers and after switching Codex/OpenAI accounts. Use when the user asks to write a skill, package a slash-callable skill, migrate a personal plugin, maintain the shared skill marketplace, debug account-switch invocation, fix duplicate entries, assign workflow ordering, or make a skill cross-platform.
---

# Skill Writing

## Operating Rule

Build user-facing callable skills as plugins in the shared local marketplace, not as `@personal` plugins and not as bare skills. Resolve its root from `CODEX_SHARED_MARKETPLACE_ROOT`; when working in a checked-out source package, use the nearest ancestor containing `skill-pack.json`. Its configured name is `workspace-local`, and its source plugin directory is `<shared-marketplace-root>\plugins`.

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

Assign later maintained skills the next unused two-digit number, currently `14`. Do not renumber existing skills unless the user explicitly changes the workflow.

## Direct Workflow

1. Read the current `skill-creator` and `plugin-creator` instructions if available.
2. Pick one normalized internal id for both plugin and skill.
3. Check the shared marketplace source and existing `workspace-local` plugin before writing.
4. Update an existing shared plugin in place. If a legacy personal plugin exists, migrate its source content into the shared marketplace and leave the old cache untouched as a recovery copy.
5. Create new plugins under `<shared-marketplace-root>\plugins\<id>` and register the plugin in `<shared-marketplace-root>\.agents\plugins\marketplace.json`.
6. Set the marketplace installation policy to `INSTALLED_BY_DEFAULT` and authentication policy to `ON_INSTALL`.
7. Create the skill under `<plugin>/skills/<id>/`.
8. Write only necessary files:
   - `.codex-plugin/plugin.json`
   - `skills/<id>/SKILL.md`
   - `skills/<id>/agents/openai.yaml`
   - optional `references/`, `scripts/`, or `assets/` only when they directly support execution
9. Set the same `NN · Name` display name in both `plugin.json` and `agents/openai.yaml`.
10. Read both metadata files back as UTF-8 and verify that the two display names are identical and match `^\d{2} · .+$`; reject `路` or a missing/wrong separator.
11. Validate the skill and plugin.
12. Update the plugin cachebuster.
13. Run the platform entrypoint to add the marketplace and install every maintained plugin: `tools/Sync-SharedCodexSkills.ps1` on Windows or `tools/Sync-SharedCodexSkills.sh` on macOS/Linux.
14. Tell the user to open a new Codex thread/window before testing `/`, because the current session may keep the old skill list in memory.

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
python3 <installed-plugin-creator>/scripts/update_plugin_cachebuster.py <plugin>
<shared-marketplace-root>/tools/Sync-SharedCodexSkills.sh
```

After synchronization, verify every maintained plugin is enabled under `workspace-local`. Windows may use the existing `CodexSharedSkillsSync` scheduler. On macOS, rerun `Install-PersonalSkillMarketplace.sh` after switching accounts; the source path is retained in `~/.codex/workspace-local.json`.

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

When modifying an already installed shared plugin, update the shared source, run validation, update the cachebuster, run the synchronization script, and ask the user to test in a new session.
