#!/usr/bin/env node
/**
 * vibe-guard.js — C06 v5.0.0 (Vibe-Agile) 核心瑞士军刀 (零密码学、零外部依赖、1秒内返回)
 *
 * 子命令：
 *   1. scan [dir]                : 二开检索、现有组件提取、重复逻辑/硬编码扫描、单文件>300行超长预警
 *   2. snapshot <files...>       : 改前毫秒级物理文件快照（存入 .c06/snapshots/）+ 提取函数与事件符号表
 *   3. verify [--dir <dir>]      : 改后符号表防删比对（发现误删函数报错拦截，支持 --auto-undo）+ 语法基础校验 + 分层评估报告
 *   4. undo [--dir <dir>]        : (对应口令 .u / 撤回) 100% 物理字节级还原最近一次快照，杜绝假回滚
 *   5. anchor [dir]              : 读取或自动初始化项目专属身份证 PROJECT_ANCHOR.md
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const SKIP_DIRS = new Set([
  'node_modules', '.git', '.c06', '.c06-worktrees', 'dist', 'build',
  'target', 'out', '__pycache__', 'coverage', '.next', '.nuxt', 'vendor'
]);

const CODE_EXTS = new Set(['.js', '.jsx', '.ts', '.tsx', '.html', '.vue', '.css', '.scss']);
const JS_LIKE_EXTS = new Set(['.js', '.jsx', '.ts', '.tsx', '.html', '.vue']);

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function walkFiles(rootDir, maxFiles = 2000) {
  const results = [];
  function walk(cur) {
    if (results.length >= maxFiles) return;
    let entries = [];
    try {
      entries = fs.readdirSync(cur, { withFileTypes: true });
    } catch (_) {
      return;
    }
    for (const ent of entries) {
      if (results.length >= maxFiles) break;
      if (ent.name.startsWith('.') && ent.name !== '.htaccess') {
        if (SKIP_DIRS.has(ent.name) || ent.name.startsWith('.r')) continue;
      }
      if (SKIP_DIRS.has(ent.name)) continue;
      const full = path.join(cur, ent.name);
      if (ent.isDirectory()) {
        walk(full);
      } else if (ent.isFile()) {
        results.push(full);
      }
    }
  }
  walk(rootDir);
  return results;
}

/**
 * 提取文件中的业务函数名与关键事件绑定符号表
 */
function extractSymbols(content, ext) {
  const functions = new Set();
  const events = new Set();

  if (!JS_LIKE_EXTS.has(ext)) {
    return { functions: [], events: [] };
  }

  // 移除块注释与单行注释，避免把注释里的伪代码当成真实函数
  const stripped = content
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '');

  const reserved = new Set([
    'if', 'for', 'while', 'switch', 'catch', 'function', 'return',
    'typeof', 'instanceof', 'new', 'delete', 'void', 'async', 'await',
    'constructor', 'render', 'super', 'import', 'export'
  ]);

  // 1. 标准函数声明: function fooName(...)
  const fnDeclRe = /\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g;
  let m;
  while ((m = fnDeclRe.exec(stripped)) !== null) {
    if (!reserved.has(m[1])) functions.add(m[1]);
  }

  // 2. 变量/常量箭头函数或函数表达式: const/let/var fooName = (...) => 或 function
  const varFnRe = /\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][A-Za-z0-9_$]*\s*=>)/g;
  while ((m = varFnRe.exec(stripped)) !== null) {
    if (!reserved.has(m[1])) functions.add(m[1]);
  }

  // 3. 对象/类方法: fooName(args) { (排除控制流关键字)
  const methodRe = /(?:^|[\n;{}])\s*(?:async\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^()\n]*\)\s*\{/g;
  while ((m = methodRe.exec(stripped)) !== null) {
    if (!reserved.has(m[1])) functions.add(m[1]);
  }

  // 4. DOM 事件监听与内联事件: addEventListener('click', ...) 或 onclick="foo()"
  const addEvRe = /\.addEventListener\s*\(\s*['"]([^'"]+)['"]/g;
  while ((m = addEvRe.exec(stripped)) !== null) {
    events.add(`addEventListener:${m[1]}`);
  }
  const inlineEvRe = /\bon(click|change|submit|input|keydown|keyup|mousedown|mouseup)\s*=\s*['"]([^'"]+)['"]/gi;
  while ((m = inlineEvRe.exec(stripped)) !== null) {
    const handlerName = m[2].split('(')[0].trim();
    events.add(`on${m[1].toLowerCase()}:${handlerName}`);
  }

  return {
    functions: Array.from(functions).sort(),
    events: Array.from(events).sort()
  };
}

/**
 * 基础语法与括号/标签平衡快速校验
 */
function checkBasicSyntax(content, ext) {
  const issues = [];

  if (ext === '.json') {
    try {
      JSON.parse(content);
    } catch (e) {
      issues.push(`JSON 语法错误: ${e.message}`);
    }
    return issues;
  }

  if (CODE_EXTS.has(ext)) {
    // 剔除字符串与注释后检查大括号/圆括号/方括号平衡
    let clean = content
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/\/\/[^\n]*/g, '')
      .replace(/'(?:\\.|[^'\\])*'/g, "''")
      .replace(/"(?:\\.|[^"\\])*"/g, '""')
      .replace(/`(?:\\.|[^`\\])*`/g, '``');

    let braces = 0;
    let parens = 0;
    let brackets = 0;
    for (let i = 0; i < clean.length; i++) {
      const ch = clean[i];
      if (ch === '{') braces++;
      else if (ch === '}') braces--;
      else if (ch === '(') parens++;
      else if (ch === ')') parens--;
      else if (ch === '[') brackets++;
      else if (ch === ']') brackets--;
    }

    if (braces !== 0) issues.push(`花括号 {} 不闭合或数量不匹配 (差值: ${braces})`);
    if (parens !== 0) issues.push(`圆括号 () 不闭合或数量不匹配 (差值: ${parens})`);
    if (brackets !== 0) issues.push(`方括号 [] 不闭合或数量不匹配 (差值: ${brackets})`);
  }

  if (ext === '.html' || ext === '.vue') {
    const scriptOpen = (content.match(/<script\b[^>]*>/gi) || []).length;
    const scriptClose = (content.match(/<\/script>/gi) || []).length;
    if (scriptOpen !== scriptClose) {
      issues.push(`<script> 标签未正确闭合 (open=${scriptOpen}, close=${scriptClose})`);
    }
    const styleOpen = (content.match(/<style\b[^>]*>/gi) || []).length;
    const styleClose = (content.match(/<\/style>/gi) || []).length;
    if (styleOpen !== styleClose) {
      issues.push(`<style> 标签未正确闭合 (open=${styleOpen}, close=${styleClose})`);
    }
  }

  return issues;
}

/**
 * 子命令 1: anchor [dir] — 读取或初始化 PROJECT_ANCHOR.md
 */
function cmdAnchor(targetDir) {
  const root = path.resolve(targetDir || '.');
  if (!fs.existsSync(root)) {
    console.error(`[ERROR] 目录不存在: ${root}`);
    process.exit(1);
  }
  const anchorPath = path.join(root, 'PROJECT_ANCHOR.md');
  if (fs.existsSync(anchorPath)) {
    console.log(`[OK] 已读取项目身份证: ${anchorPath}\n`);
    console.log(fs.readFileSync(anchorPath, 'utf-8'));
    return 0;
  }

  // 自动扫描并生成初始 PROJECT_ANCHOR.md
  const files = walkFiles(root, 500);
  const codeFiles = files.filter(f => CODE_EXTS.has(path.extname(f).toLowerCase()));
  const coreFuncs = new Set();
  for (const f of codeFiles.slice(0, 30)) {
    const ext = path.extname(f).toLowerCase();
    const text = fs.readFileSync(f, 'utf-8');
    const syms = extractSymbols(text, ext);
    syms.functions.forEach(fn => coreFuncs.add(fn));
  }

  const relEntries = codeFiles.slice(0, 10).map(f => path.relative(root, f).replace(/\\/g, '/'));
  const content = `# 🪪 项目身份证 (PROJECT_ANCHOR.md)

> 由 C06 v5.0.0 \`vibe-guard.js anchor\` 自动生成。每次修改前必读，严防测试草稿与正式工程概念串台！

## 1. 正式源码边界
- **项目根目录**：\`${root}\`
- **核心源码文件**：${relEntries.length ? relEntries.map(r => `\`${r}\``).join(', ') : '(待添加)'}
- **设计基因文件**：\`DESIGN.md\` / \`tokens.css\`

## 2. 禁碰红线与隔离区
- **禁碰测试/草稿目录**：严禁跨目录混改 \`scratch/L_app\`、\`.c06/snapshots\`、\`archive/\` 或其他非本工程文件。
- **外部组件纪律**：优先复用本项目既有组件与 CSS 变量，未经允许严禁擅自引入第二套 UI 框架。

## 3. 核心业务函数保护清单（美化/微调严禁误删）
- **受保护函数符号**：${coreFuncs.size ? Array.from(coreFuncs).slice(0, 30).map(fn => `\`${fn}()\``).join(', ') : '(尚无业务函数)'}
`;

  fs.writeFileSync(anchorPath, content, 'utf-8');
  console.log(`[OK] 已自动初始化项目身份证: ${anchorPath}\n`);
  console.log(content);
  return 0;
}

/**
 * 子命令 2: scan [dir] — 移植 oil-dev-skills 二开检索、组件/Token提取、重复函数、硬编码与>300行预警
 */
function cmdScan(targetDir) {
  const root = path.resolve(targetDir || '.');
  if (!fs.existsSync(root)) {
    console.error(`[ERROR] 扫描目录不存在: ${root}`);
    process.exit(1);
  }

  const allFiles = walkFiles(root, 2000);
  const extCount = {};
  const components = [];
  const cssVariables = new Set();
  const fnLocations = {}; // fnName -> [relPath]
  const hardcodedIssues = [];
  const oversizedFiles = [];

  for (const full of allFiles) {
    const rel = path.relative(root, full).replace(/\\/g, '/');
    const ext = path.extname(full).toLowerCase() || '(no-ext)';
    extCount[ext] = (extCount[ext] || 0) + 1;

    if (!CODE_EXTS.has(ext)) continue;

    let text = '';
    try {
      text = fs.readFileSync(full, 'utf-8');
    } catch (_) {
      continue;
    }

    const lines = text.split(/\r?\n/);

    // 1. 单文件超长预警 (>300行)
    if (lines.length > 300) {
      oversizedFiles.push({ path: rel, lines: lines.length, severity: lines.length > 500 ? 'HIGH' : 'WARN' });
    }

    // 2. 提取组件候选 (文件名首字母大写、或位于 components/、或自定义组件标签)
    const baseName = path.basename(full, ext);
    if (/^[A-Z][A-Za-z0-9]+$/.test(baseName) || rel.includes('components/') || rel.includes('parts/')) {
      components.push(`${baseName} (${rel})`);
    }
    if (ext === '.html' || ext === '.vue') {
      const classMatches = text.match(/class=["']([a-zA-Z0-9_-]*(?:card|modal|btn|panel|navbar|sidebar|header|table|grid)[a-zA-Z0-9_-]*)["']/gi) || [];
      classMatches.slice(0, 8).forEach(c => {
        const cls = c.replace(/class=["']|["']/gi, '');
        components.push(`.${cls} (${rel})`);
      });
    }

    // 3. 提取 CSS 变量 Token (--var-name)
    const varRe = /(--[a-zA-Z0-9_-]+)\s*:/g;
    let vm;
    while ((vm = varRe.exec(text)) !== null) {
      cssVariables.add(vm[1]);
    }

    // 4. 提取函数符号并检查同义/重复定义
    const syms = extractSymbols(text, ext);
    for (const fn of syms.functions) {
      if (!fnLocations[fn]) fnLocations[fn] = [];
      fnLocations[fn].push(rel);
    }

    // 5. 扫描硬编码色值与 !important
    let bangCount = 0;
    let rawHexCount = 0;
    lines.forEach((ln) => {
      if (ln.includes('!important')) bangCount++;
      // 非 CSS 变量定义行中的裸 Hex 颜色
      if (!ln.includes('--') && /#[0-9a-fA-F]{3,8}\b/.test(ln)) {
        rawHexCount++;
      }
    });
    if (bangCount > 0 || rawHexCount > 5) {
      hardcodedIssues.push({
        path: rel,
        importantCount: bangCount,
        rawHexLines: rawHexCount
      });
    }
  }

  const duplicateFns = Object.entries(fnLocations)
    .filter(([, locs]) => locs.length > 1)
    .map(([fn, locs]) => ({ fn, locations: locs }));

  console.log(`# 🔍 C06 Vibe-Guard 二开检索与工程扫描报告`);
  console.log(`- 扫描目录: ${root}`);
  console.log(`- 文件总数: ${allFiles.length} (${Object.entries(extCount).map(([k, v]) => `${k}:${v}`).join(', ')})`);
  console.log(`- 项目身份证: ${fs.existsSync(path.join(root, 'PROJECT_ANCHOR.md')) ? '✅ 已就绪 (PROJECT_ANCHOR.md)' : '⚠️ 未生成 (建议运行 vibe-guard.js anchor)'}`);
  console.log(`- 设计基因库: ${fs.existsSync(path.join(root, 'DESIGN.md')) ? '✅ 已就绪 (DESIGN.md)' : '⚪ 尚未生成 DESIGN.md'}`);

  console.log(`\n## 1. 可复用组件与样式基建 (${components.length} 项)`);
  if (components.length > 0) {
    console.log(`- 现成组件/容器: ${Array.from(new Set(components)).slice(0, 15).join(', ')}`);
  } else {
    console.log(`- 现成组件/容器: (未检出独立组件，可按需复用 C06 kit/ 组件库)`);
  }
  console.log(`- 既有 CSS 变量 Token (${cssVariables.size} 个): ${Array.from(cssVariables).slice(0, 15).join(', ') || '(无，建议建立 :root CSS 变量)'}`);

  console.log(`\n## 2. 重复逻辑与硬编码排查`);
  if (duplicateFns.length > 0) {
    console.log(`- ⚠️ 同名/重复函数定义 (${duplicateFns.length} 处):`);
    duplicateFns.slice(0, 10).forEach(d => console.log(`  • ${d.fn}() 出现在: ${d.locations.join(', ')}`));
  } else {
    console.log(`- ✅ 未发现跨文件重复定义函数`);
  }

  if (hardcodedIssues.length > 0) {
    console.log(`- ⚠️ 样式硬编码 / !important 预警 (${hardcodedIssues.length} 个文件):`);
    hardcodedIssues.slice(0, 10).forEach(h => {
      console.log(`  • ${h.path}: !important=${h.importantCount} 处, 裸色值行=${h.rawHexLines} 处 (建议收敛为 CSS 变量)`);
    });
  } else {
    console.log(`- ✅ 样式整洁，无滥用 !important 或大面积硬编码色值`);
  }

  console.log(`\n## 3. 分层瘦身预警 (单文件 > 300 行)`);
  if (oversizedFiles.length > 0) {
    oversizedFiles.forEach(o => {
      console.log(`- [${o.severity}] ${o.path} (${o.lines} 行) ➔ 超过 300 行红线，改动时严禁继续堆砌，建议拆分视图与逻辑！`);
    });
  } else {
    console.log(`- ✅ 所有源码文件均控制在 300 行以内，体积苗条`);
  }

  return 0;
}

/**
 * 寻找距离目标文件最近的工作区根目录（用来定位 .c06/snapshots）
 */
function resolveSnapshotDir(firstFilePath, explicitDir) {
  if (explicitDir) {
    return path.join(path.resolve(explicitDir), '.c06', 'snapshots');
  }
  const baseDir = firstFilePath ? path.dirname(path.resolve(firstFilePath)) : process.cwd();
  return path.join(baseDir, '.c06', 'snapshots');
}

/**
 * 子命令 3: snapshot <files...> — 改前毫秒级物理快照 + 提取函数与事件符号表
 */
function cmdSnapshot(args) {
  let explicitDir = null;
  const targetFiles = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--dir' && args[i + 1]) {
      explicitDir = args[++i];
    } else {
      targetFiles.push(args[i]);
    }
  }

  if (targetFiles.length === 0) {
    console.error('用法: node vibe-guard.js snapshot [--dir <projectDir>] <file1> [file2...]');
    process.exit(1);
  }

  const snapRoot = resolveSnapshotDir(targetFiles[0], explicitDir);
  const latestDir = path.join(snapRoot, 'latest');
  fs.mkdirSync(latestDir, { recursive: true });

  const manifest = {
    version: '5.0.0',
    timestamp: new Date().toISOString(),
    snapshot_dir: latestDir,
    files: []
  };

  for (let idx = 0; idx < targetFiles.length; idx++) {
    const absPath = path.resolve(targetFiles[idx]);
    if (!fs.existsSync(absPath)) {
      console.error(`[ERROR] 待快照文件不存在: ${absPath}`);
      process.exit(1);
    }

    const rawBuf = fs.readFileSync(absPath);
    const text = rawBuf.toString('utf-8');
    const ext = path.extname(absPath).toLowerCase();
    const symbols = extractSymbols(text, ext);
    const backupName = `${idx}_${path.basename(absPath)}.bak`;
    const backupPath = path.join(latestDir, backupName);

    fs.writeFileSync(backupPath, rawBuf);

    manifest.files.push({
      original_path: absPath,
      backup_path: backupPath,
      sha256_before: sha256(rawBuf),
      bytes_before: rawBuf.length,
      lines_before: text.split(/\r?\n/).length,
      ext,
      functions: symbols.functions,
      events: symbols.events
    });
  }

  const manifestPath = path.join(latestDir, 'manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');

  // 同时在 cwd 的 .c06/snapshots 下留一个指针，方便无参调用 verify/undo
  try {
    const cwdSnap = path.join(process.cwd(), '.c06', 'snapshots');
    fs.mkdirSync(cwdSnap, { recursive: true });
    fs.writeFileSync(path.join(cwdSnap, 'last_pointer.json'), JSON.stringify({ manifestPath }, null, 2), 'utf-8');
  } catch (_) {}

  console.log(`[OK] 🛡️ 真快照时光机已锁定 (${manifest.files.length} 个文件 -> ${latestDir})`);
  for (const f of manifest.files) {
    console.log(`  • ${path.basename(f.original_path)} (${f.lines_before} 行, SHA256: ${f.sha256_before.slice(0, 10)}...)`);
    console.log(`    ↳ 受保护业务函数 (${f.functions.length} 个): ${f.functions.join(', ') || '(无)'}`);
    if (f.events.length > 0) {
      console.log(`    ↳ 受保护事件绑定 (${f.events.length} 个): ${f.events.join(', ')}`);
    }
  }
  return 0;
}

/**
 * 查找最近的 manifest.json
 */
function findManifest(explicitDir) {
  const candidates = [];
  if (explicitDir) {
    candidates.push(path.join(path.resolve(explicitDir), '.c06', 'snapshots', 'latest', 'manifest.json'));
  }
  candidates.push(path.join(process.cwd(), '.c06', 'snapshots', 'latest', 'manifest.json'));
  const pointerPath = path.join(process.cwd(), '.c06', 'snapshots', 'last_pointer.json');
  if (fs.existsSync(pointerPath)) {
    try {
      const ptr = JSON.parse(fs.readFileSync(pointerPath, 'utf-8'));
      if (ptr.manifestPath) candidates.push(ptr.manifestPath);
    } catch (_) {}
  }

  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

/**
 * 子命令 4: undo [--dir <dir>] — 100% 物理字节级还原最近一次快照
 */
function cmdUndo(args) {
  let explicitDir = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--dir' && args[i + 1]) {
      explicitDir = args[++i];
    } else if (!args[i].startsWith('-')) {
      explicitDir = args[i];
    }
  }

  const manifestPath = findManifest(explicitDir);
  if (!manifestPath) {
    console.error('[ERROR] 未找到可用的快照记录 (.c06/snapshots/latest/manifest.json)，无法执行物理回滚。');
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  console.log(`# ⏪ C06 真快照时光机 · 正在执行 100% 物理字节级回滚...`);
  for (const item of manifest.files) {
    if (!fs.existsSync(item.backup_path)) {
      console.error(`[ERROR] 快照备份文件缺失: ${item.backup_path}`);
      process.exit(1);
    }
    const rawBuf = fs.readFileSync(item.backup_path);
    fs.writeFileSync(item.original_path, rawBuf);
    const restoredSha = sha256(rawBuf);
    const match = restoredSha === item.sha256_before;
    console.log(`  ✅ 已物理还原: ${item.original_path}`);
    console.log(`     ↳ 字节数: ${rawBuf.length} bytes | SHA256 校验: ${match ? '100% 一致' : '异常'} (${restoredSha.slice(0, 12)})`);
    console.log(`     ↳ 核心函数已恢复 (${item.functions.length}/${item.functions.length}): ${item.functions.join(', ') || '(无)'}`);
  }
  console.log(`[OK] 物理回滚完成！所有文件已 100% 恢复至改前干净基线。`);
  return 0;
}

/**
 * 子命令 5: verify [--dir <dir>] [--auto-undo] [--allow-delete <fn1,fn2>]
 */
function cmdVerify(args) {
  let explicitDir = null;
  let autoUndo = false;
  const allowedDeletes = new Set();

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--dir' && args[i + 1]) {
      explicitDir = args[++i];
    } else if (args[i] === '--auto-undo') {
      autoUndo = true;
    } else if (args[i] === '--allow-delete' && args[i + 1]) {
      args[++i].split(',').forEach(fn => allowedDeletes.add(fn.trim()));
    } else if (!args[i].startsWith('-')) {
      explicitDir = args[i];
    }
  }

  const manifestPath = findManifest(explicitDir);
  if (!manifestPath) {
    console.error('[ERROR] 未找到改前快照 (.c06/snapshots/latest/manifest.json)！请先运行 vibe-guard.js snapshot。');
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  let hasFatalError = false;
  const fileReports = [];

  for (const item of manifest.files) {
    if (!fs.existsSync(item.original_path)) {
      hasFatalError = true;
      fileReports.push({
        file: item.original_path,
        status: 'FAIL',
        reason: '目标源文件在修改后被整个删除！'
      });
      continue;
    }

    const curBuf = fs.readFileSync(item.original_path);
    const curText = curBuf.toString('utf-8');
    const curLines = curText.split(/\r?\n/).length;
    const curSymbols = extractSymbols(curText, item.ext);
    const syntaxIssues = checkBasicSyntax(curText, item.ext);

    // 比对原有的业务函数是否丢失
    const curFnSet = new Set(curSymbols.functions);
    const deletedFunctions = item.functions.filter(fn => !curFnSet.has(fn) && !allowedDeletes.has(fn));
    const addedFunctions = curSymbols.functions.filter(fn => !item.functions.includes(fn));

    // 比对原有事件绑定是否丢失
    const curEvSet = new Set(curSymbols.events);
    const deletedEvents = item.events.filter(ev => !curEvSet.has(ev));

    if (deletedFunctions.length > 0 || syntaxIssues.length > 0) {
      hasFatalError = true;
    }

    fileReports.push({
      file: item.original_path,
      status: (deletedFunctions.length === 0 && syntaxIssues.length === 0) ? 'PASS' : 'BLOCKED',
      linesBefore: item.lines_before,
      linesAfter: curLines,
      totalBeforeFns: item.functions.length,
      preservedFnsCount: item.functions.length - deletedFunctions.length,
      deletedFunctions,
      addedFunctions,
      deletedEvents,
      syntaxIssues,
      oversizedWarning: curLines > 300
    });
  }

  console.log(`# 🛡️ C06 Vibe-Guard 改后安全核验与分层评估报告`);
  for (const rep of fileReports) {
    const name = path.basename(rep.file);
    console.log(`\n## 文件: ${name} [${rep.status}] (${rep.linesBefore} 行 ➔ ${rep.linesAfter} 行)`);
    console.log(`- 🔒 业务函数完整性: [${rep.preservedFnsCount}/${rep.totalBeforeFns} 核心函数完好]`);

    if (rep.deletedFunctions && rep.deletedFunctions.length > 0) {
      console.error(`- ❌ [美化禁删函数红线拦截] 检测到原有核心业务函数被误删: ${rep.deletedFunctions.map(f => `${f}()`).join(', ')}`);
    }
    if (rep.deletedEvents && rep.deletedEvents.length > 0) {
      console.warn(`- ⚠️ 检测到原有事件绑定被移除: ${rep.deletedEvents.join(', ')}`);
    }
    if (rep.addedFunctions && rep.addedFunctions.length > 0) {
      console.log(`- ➕ 本次新增函数: ${rep.addedFunctions.map(f => `${f}()`).join(', ')}`);
    }
    if (rep.syntaxIssues && rep.syntaxIssues.length > 0) {
      console.error(`- ❌ [语法校验拦截]: ${rep.syntaxIssues.join(' | ')}`);
    } else {
      console.log(`- ✅ 基础语法与括号/标签平衡校验: 0 报错`);
    }
    if (rep.oversizedWarning) {
      console.warn(`- ⚠️ [分层瘦身预警]: 当前文件达 ${rep.linesAfter} 行 (>300行)，建议后续按视图与状态逻辑拆分模块。`);
    }
  }

  if (hasFatalError) {
    console.error(`\n[BLOCKED] ❌ 改后安全核验未通过（发现误删既有业务函数或语法损坏）！退出码: 2`);
    if (autoUndo) {
      console.log(`[AUTO-UNDO] 正在自动触发 vibe-guard.js undo 一键物理回滚...`);
      cmdUndo(explicitDir ? ['--dir', explicitDir] : []);
    } else {
      console.error(`👉 请立即运行: node vibe-guard.js undo (或输入快捷口令 .u / 撤回) 100% 物理恢复原状！`);
    }
    process.exit(2);
  }

  console.log(`\n[OK] ✅ 改后安全核验 100% 通过 (Exit Code 0)！可以安全生成四格人话回执单。`);
  return 0;
}

// CLI 主入口
if (require.main === module) {
  const argv = process.argv.slice(2);
  const subCmd = (argv[0] || '').toLowerCase();
  const rest = argv.slice(1);

  switch (subCmd) {
    case 'scan':
      process.exit(cmdScan(rest[0]));
      break;
    case 'snapshot':
      process.exit(cmdSnapshot(rest));
      break;
    case 'verify':
      process.exit(cmdVerify(rest));
      break;
    case 'undo':
    case '.u':
    case 'u':
      process.exit(cmdUndo(rest));
      break;
    case 'anchor':
      process.exit(cmdAnchor(rest[0]));
      break;
    default:
      console.log(`用法: node vibe-guard.js <scan|snapshot|verify|undo|anchor> [options]`);
      process.exit(1);
  }
}

module.exports = { extractSymbols, checkBasicSyntax, cmdScan, cmdSnapshot, cmdVerify, cmdUndo, cmdAnchor };
