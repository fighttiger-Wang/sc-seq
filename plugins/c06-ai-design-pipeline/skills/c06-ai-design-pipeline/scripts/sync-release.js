#!/usr/bin/env node
/**
 * sync-release.js — C06 v5.0.0 (Vibe-Agile) 一键多端副本同步器
 *
 * 同步目标：
 *   1. 主目录 (Master Source):
 *      C:\Users\fight\.gemini\config\skills\C06-AI设计流水线
 *   2. 本地市场插件副本 (Codex Marketplace):
 *      C:\Users\fight\.codex\marketplaces\local-marketplace-stable\plugins\C06-AI设计流水线\skills\C06-AI设计流水线
 *   3. 活跃本地市场仓库 (Active Workspace Marketplace):
 *      E:\A002-Codex\工作区\local-marketplace-stable-20260916-193427-e53a557c\plugins\c06-ai-design-pipeline
 *      E:\A002-Codex\工作区\local-marketplace-stable\plugins\c06-ai-design-pipeline
 *   4. sc-seq 本地 Git 仓库:
 *      E:\A002-Codex\工作区\sc-seq\plugins\c06-ai-design-pipeline
 */

const fs = require('fs');
const path = require('path');

const SRC_SKILL_DIR = path.resolve(__dirname, '..');
const VERSION_CORE = '5.0.0';
const VERSION_CODEX = '5.0.0+codex.20261120003000';
const DISPLAY_NAME_MARKET = '19 · C06-AI设计流水线 v5.0.0 (Vibe-Agile)';
const DESCRIPTION_SHORT = '面向 App Vibe Coding 的敏捷 UI 设计、微创修 Bug、组件复用与审美自动沉淀流水线（C06 v5.0.0）';
const DESCRIPTION_LONG = '面向 App Vibe Coding 的敏捷 UI 设计、微创修 Bug、组件复用与审美自动沉淀流水线（C06 v5.0.0）。提供三轨智能分流（L1 免问卷微创直达 / L2 三问功能模块 / L3 五步向导与打包）、改前真快照防删函数护栏（vibe-guard.js）、正负样本自动沉淀（distill.js）与项目长期体检除草治理（govern.js）。';

function copyDirRecursive(src, dest, transformSkillMdFn = null) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const ent of entries) {
    if (ent.name === '.git' || ent.name === '.c06' || ent.name === 'node_modules') continue;
    const sPath = path.join(src, ent.name);
    const dPath = path.join(dest, ent.name);
    if (ent.isDirectory()) {
      copyDirRecursive(sPath, dPath, transformSkillMdFn);
    } else if (ent.isFile()) {
      if (ent.name === 'SKILL.md' && transformSkillMdFn) {
        const raw = fs.readFileSync(sPath, 'utf-8');
        fs.writeFileSync(dPath, transformSkillMdFn(raw), 'utf-8');
      } else {
        fs.copyFileSync(sPath, dPath);
      }
    }
  }
}

function cleanAndCopySkill(targetSkillDir, pluginId, displayName) {
  if (fs.existsSync(targetSkillDir)) {
    fs.rmSync(targetSkillDir, { recursive: true, force: true });
  }
  fs.mkdirSync(targetSkillDir, { recursive: true });

  copyDirRecursive(SRC_SKILL_DIR, targetSkillDir, (rawMd) => {
    let out = rawMd;
    if (pluginId) {
      out = out.replace(/^name:\s*.*$/m, `name: ${pluginId}`);
    }
    if (displayName) {
      out = out.replace(/^displayName:\s*.*$/m, `displayName: ${displayName}`);
    }
    return out;
  });

  // 生成 agents/openai.yaml 保持 Codex marketplace 100% 兼容
  const agentsDir = path.join(targetSkillDir, 'agents');
  fs.mkdirSync(agentsDir, { recursive: true });
  const openaiYaml = `interface:
  display_name: "${displayName}"
  short_description: "${DESCRIPTION_SHORT}"
  default_prompt: "Use $${pluginId} to run C06 v5.0.0 Vibe-Agile UI design, micro bug-fix, snapshot guard, and aesthetic distillation."

policy:
  allow_implicit_invocation: true
`;
  fs.writeFileSync(path.join(agentsDir, 'openai.yaml'), openaiYaml, 'utf-8');
}

function writePluginJson(pluginDir, pluginId, displayName, versionStr) {
  const codexPluginDir = path.join(pluginDir, '.codex-plugin');
  fs.mkdirSync(codexPluginDir, { recursive: true });
  const pluginJson = {
    name: pluginId,
    version: versionStr,
    description: DESCRIPTION_LONG,
    author: { name: 'fight' },
    skills: './skills/',
    interface: {
      displayName,
      shortDescription: DESCRIPTION_SHORT,
      longDescription: DESCRIPTION_LONG,
      developerName: 'fight',
      category: 'Development',
      capabilities: [
        'Three-track Vibe-Agile router (L1 zero-quiz micro / L2 3-question feature / L3 5-step wizard)',
        'True file snapshot time-machine and zero function-deletion guard (vibe-guard.js)',
        'Positive aesthetic token & negative badcase auto-distillation (distill.js)',
        'Long-term repository governance and dead-code/bloat scanner (govern.js)'
      ],
      defaultPrompt: `使用 $${pluginId} 启动 C06-AI设计流水线 v5.0.0 (Vibe-Agile)，执行敏捷 UI 微调、微创修 Bug、防删快照核验与审美自动沉淀。`
    }
  };
  fs.writeFileSync(path.join(codexPluginDir, 'plugin.json'), JSON.stringify(pluginJson, null, 2), 'utf-8');
}

function updateMarketplaceIndex(repoRoot, pluginId, displayName, versionStr) {
  // 1. skill-pack.json
  const spPath = path.join(repoRoot, 'skill-pack.json');
  let sp = {
    schemaVersion: 1,
    name: 'workspace-local',
    displayName: 'Personal Shared Skills',
    expectedPluginCount: 1,
    plugins: []
  };
  if (fs.existsSync(spPath)) {
    try { sp = JSON.parse(fs.readFileSync(spPath, 'utf-8')); } catch (_) {}
  }
  const list = Array.isArray(sp.plugins) ? sp.plugins : [];
  const idx = list.findIndex(p => p.id === pluginId || p.id === 'c06-ai-design-pipeline' || p.id === 'C06-AI设计流水线');
  const newSpEntry = { id: pluginId, version: versionStr, displayName };
  if (idx >= 0) {
    list[idx] = newSpEntry;
  } else {
    list.push(newSpEntry);
  }
  sp.plugins = list;
  sp.expectedPluginCount = list.length;
  fs.writeFileSync(spPath, JSON.stringify(sp, null, 2), 'utf-8');

  // 2. marketplace.json (root, .codex-plugin/marketplace.json, .agents/plugins/marketplace.json)
  const marketRelPaths = [
    '.codex-plugin/marketplace.json',
    '.agents/plugins/marketplace.json',
    'marketplace.json'
  ];

  let updatedAny = false;
  for (const rel of marketRelPaths) {
    const mPath = path.join(repoRoot, rel);
    if (!fs.existsSync(mPath) && (rel !== 'marketplace.json' || updatedAny)) continue;
    updatedAny = true;
    let mp = {
      name: 'workspace-local',
      version: VERSION_CORE,
      plugins: []
    };
    if (fs.existsSync(mPath)) {
      try { mp = JSON.parse(fs.readFileSync(mPath, 'utf-8')); } catch (_) {}
    }
    const pList = Array.isArray(mp.plugins) ? mp.plugins : [];
    const eIdx = pList.findIndex(e => e.id === pluginId || e.name === pluginId || e.id === 'c06-ai-design-pipeline');

    // 判断该 marketplace.json 使用的是 .agents schema 还是 .codex-plugin schema
    const sample = pList[0] || {};
    let entry;
    if (sample.source && typeof sample.source === 'object') {
      entry = {
        name: pluginId,
        source: { source: 'local', path: `./plugins/${pluginId}` },
        policy: { installation: 'AVAILABLE', authentication: 'ON_INSTALL' },
        category: 'Development'
      };
    } else {
      entry = {
        id: pluginId,
        name: displayName,
        version: versionStr,
        description: DESCRIPTION_LONG,
        category: 'Development',
        source: `./plugins/${pluginId}`,
        installMode: 'ON_INSTALL',
        distribution: 'INSTALLED_BY_DEFAULT'
      };
    }

    if (eIdx >= 0) {
      pList[eIdx] = entry;
    } else {
      pList.push(entry);
    }
    mp.plugins = pList;
    fs.mkdirSync(path.dirname(mPath), { recursive: true });
    fs.writeFileSync(mPath, JSON.stringify(mp, null, 2), 'utf-8');
  }
}

function syncTargetRepo(repoRoot, pluginId, versionStr) {
  const pluginDir = path.join(repoRoot, 'plugins', pluginId);
  const targetSkillDir = path.join(pluginDir, 'skills', pluginId);
  cleanAndCopySkill(targetSkillDir, pluginId, DISPLAY_NAME_MARKET);
  writePluginJson(pluginDir, pluginId, DISPLAY_NAME_MARKET, versionStr);
  updateMarketplaceIndex(repoRoot, pluginId, DISPLAY_NAME_MARKET, versionStr);
  console.log(`[SYNCED] ✅ 已同步副本: ${targetSkillDir}`);
  console.log(`         ↳ plugin.json & marketplace.json 版本已更新为: ${versionStr}`);
}

if (require.main === module) {
  console.log(`# 🔄 C06 v5.0.0 (Vibe-Agile) 多端副本一键同步器`);
  console.log(`- 主源目录 (Master): ${SRC_SKILL_DIR}\n`);

  // 1. 同步 C:\Users\fight\.codex\marketplaces\local-marketplace-stable\plugins\C06-AI设计流水线\skills\C06-AI设计流水线
  const codexMarketRoot = 'C:\\Users\\fight\\.codex\\marketplaces\\local-marketplace-stable';
  syncTargetRepo(codexMarketRoot, 'C06-AI设计流水线', VERSION_CORE);

  // 2. 同步活跃市场仓库 E:\A002-Codex\工作区\local-marketplace-stable-20260916-193427-e53a557c
  const activeMarketRoot = 'E:\\A002-Codex\\工作区\\local-marketplace-stable-20260916-193427-e53a557c';
  if (fs.existsSync(activeMarketRoot)) {
    syncTargetRepo(activeMarketRoot, 'c06-ai-design-pipeline', VERSION_CODEX);
  }

  // 3. 同步 E:\A002-Codex\工作区\local-marketplace-stable
  const plainMarketRoot = 'E:\\A002-Codex\\工作区\\local-marketplace-stable';
  if (fs.existsSync(plainMarketRoot)) {
    syncTargetRepo(plainMarketRoot, 'c06-ai-design-pipeline', VERSION_CODEX);
  }

  // 4. 同步 sc-seq 本地 git 仓库 E:\A002-Codex\工作区\sc-seq
  const scSeqRoot = 'E:\\A002-Codex\\工作区\\sc-seq';
  if (fs.existsSync(scSeqRoot)) {
    syncTargetRepo(scSeqRoot, 'c06-ai-design-pipeline', VERSION_CODEX);
  }

  console.log(`\n[OK] 🎉 全端副本同步完成 (Exit Code 0)！`);
}
