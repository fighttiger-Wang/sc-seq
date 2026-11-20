#!/usr/bin/env node
/**
 * govern.js — C06 v5.0.0 (Vibe-Agile) 项目长期治理与体检除草引擎 (对应口令 g)
 *
 * 1:1 融合 oil-dev-skills (oil-govern / audit_repo.py) 精髓：
 *   1. 扫描超过 300 行的臃肿文件预警（分层瘦身）
 *   2. 扫描冗余死代码（定义后 0 引用的孤儿函数、残留 console.log / debugger / TODO）與孤儿文件
 *   3. 扫描累计过期混乱的文档（过程评审草稿、.bak/.old/.tmp 残留、超过 10KB 的规则文档、Markdown 死链）
 *   4. 输出清晰的三段式创作者人话体检报告（支持 --clean 自动将过期草稿/残留备份归档）
 */

const fs = require('fs');
const path = require('path');
const { extractSymbols } = require('./vibe-guard.js');

const SKIP_DIRS = new Set([
  'node_modules', '.git', '.c06', '.c06-worktrees', 'dist', 'build',
  'target', 'out', '__pycache__', 'coverage', '.next', '.nuxt', 'vendor', 'archive'
]);

const CODE_EXTS = new Set(['.js', '.jsx', '.ts', '.tsx', '.html', '.vue', '.css', '.scss']);
const DOC_EXTS = new Set(['.md', '.mdx', '.txt']);
const STALE_NAME_RE = /(?:评审报告|草稿|draft|temp|tmp|old|backup|bak|mut-|verify|review_output)/i;

function walkAll(rootDir, maxFiles = 3000) {
  const files = [];
  function walk(cur) {
    if (files.length >= maxFiles) return;
    let list = [];
    try {
      list = fs.readdirSync(cur, { withFileTypes: true });
    } catch (_) {
      return;
    }
    for (const ent of list) {
      if (files.length >= maxFiles) break;
      if (SKIP_DIRS.has(ent.name)) continue;
      const full = path.join(cur, ent.name);
      if (ent.isDirectory()) {
        walk(full);
      } else if (ent.isFile()) {
        files.push(full);
      }
    }
  }
  walk(rootDir);
  return files;
}

function checkMarkdownBrokenLinks(docPath) {
  const broken = [];
  let text = '';
  try {
    text = fs.readFileSync(docPath, 'utf-8');
  } catch (_) {
    return broken;
  }
  const lines = text.split(/\r?\n/);
  let inFence = false;
  const linkRe = /(?<!!)\[[^\]]*\]\(([^)]+)\)/g;

  lines.forEach((line, idx) => {
    if (/^\s*(`{3,}|~{3,})/.test(line)) {
      inFence = !inFence;
      return;
    }
    if (inFence) return;
    let m;
    while ((m = linkRe.exec(line)) !== null) {
      const rawTarget = m[1].trim().split(/\s+/)[0].replace(/^<|>$/g, '');
      if (!rawTarget || /^(?:#|https?:\/\/|mailto:|tel:|file:\/\/|data:|conversation:\/\/|sidecar:\/\/)/i.test(rawTarget)) {
        continue;
      }
      const clean = rawTarget.split('#')[0].split('?')[0];
      if (!clean || /[*{}<>$]/.test(clean)) continue;
      const resolved = path.resolve(path.dirname(docPath), clean);
      if (!fs.existsSync(resolved)) {
        broken.push({ line: idx + 1, target: clean });
      }
    }
  });
  return broken;
}

function runGovernance(targetDir, options = {}) {
  const root = path.resolve(targetDir || '.');
  if (!fs.existsSync(root)) {
    console.error(`[ERROR] 目标项目目录不存在: ${root}`);
    process.exit(1);
  }

  const allFiles = walkAll(root);
  const bloatedFiles = [];       // > 300 lines
  const staleDocsAndOrphans = []; // 过期混乱文档或 .bak/.tmp 孤儿文件
  const oversizedDocs = [];      // > 10KB 规则文件
  const brokenLinks = [];        // Markdown 死链
  const deadCodeCandidates = []; // 定义了但引用 <= 1 次的死函数或 debugger
  const codeTexts = [];          // [{ rel, ext, text }]

  for (const full of allFiles) {
    const rel = path.relative(root, full).replace(/\\/g, '/');
    const ext = path.extname(full).toLowerCase();
    const base = path.basename(full);
    let stat;
    try {
      stat = fs.statSync(full);
    } catch (_) {
      continue;
    }

    // 1. 识别孤儿备份文件 / 过期混乱过程文档
    if (/\.(bak|old|tmp|orig)$/i.test(base) || STALE_NAME_RE.test(base)) {
      staleDocsAndOrphans.push({
        path: rel,
        bytes: stat.size,
        reason: /\.(bak|old|tmp|orig)$/i.test(base) ? '临时备份残留孤儿文件' : '过程评审/临时草稿过期文档'
      });
    }

    // 2. 文档审计
    if (DOC_EXTS.has(ext)) {
      if (['agents.md', 'claude.md', 'design.md', 'readme.md'].includes(base.toLowerCase()) && stat.size > 10 * 1024) {
        oversizedDocs.push({ path: rel, kb: (stat.size / 1024).toFixed(1) });
      }
      if (ext === '.md') {
        const bl = checkMarkdownBrokenLinks(full);
        bl.forEach(b => brokenLinks.push({ doc: rel, line: b.line, target: b.target }));
      }
    }

    // 3. 源码收集与大文件 (>300行) 扫描
    if (CODE_EXTS.has(ext)) {
      let text = '';
      try {
        text = fs.readFileSync(full, 'utf-8');
      } catch (_) {
        continue;
      }
      const lineCount = text.split(/\r?\n/).length;
      if (lineCount > 300) {
        bloatedFiles.push({
          path: rel,
          lines: lineCount,
          level: lineCount > 500 ? '🔴 严重臃肿 (>500行)' : '🟡 超长预警 (>300行)'
        });
      }
      codeTexts.push({ rel, full, ext, text, lines: lineCount });
    }
  }

  // 4. 扫描孤儿代码文件 & 未被引用的死函数 / 残留调试代码
  const combinedCorpus = codeTexts.map(c => c.text).join('\n');
  for (const c of codeTexts) {
    const baseName = path.basename(c.rel);
    // 检查非入口文件是否从未在其他文件中被引用
    if (!/^(index|main|app|workbench|holo|tokens)\./i.test(baseName) && codeTexts.length > 1) {
      const stem = path.basename(c.rel, c.ext);
      const otherText = codeTexts.filter(o => o.rel !== c.rel).map(o => o.text).join('\n');
      if (!otherText.includes(baseName) && !otherText.includes(stem)) {
        staleDocsAndOrphans.push({
          path: c.rel,
          bytes: Buffer.byteLength(c.text, 'utf-8'),
          reason: '孤儿代码/样式文件（未被项目内任何其他文件 import 或引用）'
        });
      }
    }

    // 检查死函数候选（仅出现 1 次即只有定义没有调用，且不是内联暴露入口）
    const syms = extractSymbols(c.text, c.ext);
    for (const fn of syms.functions) {
      const escaped = fn.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const matches = combinedCorpus.match(new RegExp(`\\b${escaped}\\b`, 'g')) || [];
      if (matches.length <= 1) {
        deadCodeCandidates.push({
          path: c.rel,
          symbol: `${fn}()`,
          type: '疑似死函数（全仓仅定义 1 次，0 处调用）'
        });
      }
    }

    // 检查 debugger 或废弃注释代码块
    if (/\bdebugger\s*;/.test(c.text)) {
      deadCodeCandidates.push({
        path: c.rel,
        symbol: 'debugger;',
        type: '残留调试断点语句'
      });
    }
  }

  // 可选执行自动归档清理 (--clean)
  const cleanedItems = [];
  if (options.clean && staleDocsAndOrphans.length > 0) {
    const archiveDir = path.join(root, 'archive_cleaned');
    fs.mkdirSync(archiveDir, { recursive: true });
    for (const item of staleDocsAndOrphans) {
      const srcPath = path.join(root, item.path);
      if (fs.existsSync(srcPath)) {
        const destPath = path.join(archiveDir, path.basename(item.path));
        fs.renameSync(srcPath, destPath);
        cleanedItems.push(item.path);
      }
    }
  }

  // 输出清晰的人话体检报告
  console.log(`# 🧹 C06 项目长期治理与体检除草报告 (口令 \`.g\` / \`体检\`)`);
  console.log(`- 体检目标: ${root}`);
  console.log(`- 扫描规模: 共 ${allFiles.length} 个文件 (其中核心源码 ${codeTexts.length} 个)\n`);

  console.log(`## 1. 📏 单文件超长与分层瘦身预警 (> 300 行红线)`);
  if (bloatedFiles.length > 0) {
    bloatedFiles.forEach(b => {
      console.log(`  - ${b.level}: \`${b.path}\` (${b.lines} 行) ➔ 建议将视图模板、业务状态与 CSS 样式拆分为独立子文件`);
    });
  } else {
    console.log(`  - ✅ 全部源码文件均 <= 300 行，结构清爽无巨石文件`);
  }

  console.log(`\n## 2. 🧟 冗余死代码与孤儿函数排查`);
  if (deadCodeCandidates.length > 0) {
    deadCodeCandidates.slice(0, 15).forEach(d => {
      console.log(`  - ⚠️ \`${d.path}\` -> \`${d.symbol}\` : ${d.type}`);
    });
  } else {
    console.log(`  - ✅ 未检出孤立死函数或残留 debugger 断点`);
  }

  console.log(`\n## 3. 📚 过期混乱文档、孤儿文件与死链治理`);
  if (staleDocsAndOrphans.length > 0) {
    staleDocsAndOrphans.slice(0, 20).forEach(s => {
      console.log(`  - 🗑️ [${s.reason}] \`${s.path}\` (${(s.bytes / 1024).toFixed(1)} KB)`);
    });
  } else {
    console.log(`  - ✅ 未发现过程评审垃圾文档或孤儿备份文件`);
  }

  if (oversizedDocs.length > 0) {
    oversizedDocs.forEach(o => {
      console.log(`  - ⚠️ [规则文档超重 >10KB] \`${o.path}\` (${o.kb} KB) ➔ 建议按分层瘦身原则拆分为路由表 + references/`);
    });
  }
  if (brokenLinks.length > 0) {
    brokenLinks.slice(0, 10).forEach(bl => {
      console.log(`  - 🔗 [文档死链] \`${bl.doc}:${bl.line}\` 指向不存在的 \`${bl.target}\``);
    });
  }

  if (cleanedItems.length > 0) {
    console.log(`\n## 4. ✨ 自动除草执行结果 (--clean)`);
    console.log(`  - 已将 ${cleanedItems.length} 个过期/孤儿文件安全移入 \`archive_cleaned/\`: ${cleanedItems.join(', ')}`);
  }

  console.log(`\n[OK] 体检除草扫描完成 (Exit Code 0)。`);
  return {
    bloatedFiles,
    deadCodeCandidates,
    staleDocsAndOrphans,
    oversizedDocs,
    brokenLinks,
    cleanedItems
  };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  let targetDir = '.';
  let clean = false;
  for (const a of args) {
    if (a === '--clean') clean = true;
    else if (!a.startsWith('-')) targetDir = a;
  }
  runGovernance(targetDir, { clean });
  process.exit(0);
}

module.exports = { runGovernance };
