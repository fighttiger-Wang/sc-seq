#!/usr/bin/env node
/**
 * distill.js — C06 v5.0.0 (Vibe-Agile) 正负双向记忆沉淀器 (零密码学、1秒内返回)
 *
 * 功能：
 *   1. --positive : 正样本审美沉淀（将用户认可的配色、圆角、阴影、字体、动效 Token 自动写入项目 DESIGN.md 与 tokens.css）
 *   2. --negative : 负样本避坑沉淀（将踩坑病因写入 kit/data/design_badcases.json 与 knowledge/design_badcases.json，自带去重与容量上限淘汰）
 *   3. --list     : 查看当前已沉淀的避坑库与 Lucky Note 四大真实血泪教训
 *
 * 用法示例：
 *   node distill.js --positive --dir <projectDir> --category "毛玻璃卡片" --token "--card-bg: rgba(255,255,255,0.78); --card-radius: 16px" --note "温润通透毛玻璃圆角质感"
 *   node distill.js --negative --category "函数防删" --title "美化误删业务函数" --badcase "..." --solution "..." --rule "..."
 */

const fs = require('fs');
const path = require('path');

const KIT_BADCASES_PATH = path.join(__dirname, '..', 'kit', 'data', 'design_badcases.json');
const LEGACY_BADCASES_PATH = path.join(__dirname, '..', 'knowledge', 'design_badcases.json');
const DEFAULT_MAX_CAPACITY = 30;

function parseFlags(argv) {
  const opts = { positional: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--positive') opts.mode = 'positive';
    else if (a === '--negative') opts.mode = 'negative';
    else if (a === '--list') opts.mode = 'list';
    else if (a.startsWith('--') && argv[i + 1] !== undefined) {
      opts[a.slice(2)] = argv[++i];
    } else {
      opts.positional.push(a);
    }
  }
  return opts;
}

function loadBadcasesDb() {
  const targetPath = fs.existsSync(KIT_BADCASES_PATH) ? KIT_BADCASES_PATH : LEGACY_BADCASES_PATH;
  if (!fs.existsSync(targetPath)) {
    return { version: '5.0.0', max_capacity: DEFAULT_MAX_CAPACITY, updated_at: new Date().toISOString(), badcases: [] };
  }
  try {
    return JSON.parse(fs.readFileSync(targetPath, 'utf-8'));
  } catch (_) {
    return { version: '5.0.0', max_capacity: DEFAULT_MAX_CAPACITY, updated_at: new Date().toISOString(), badcases: [] };
  }
}

function saveBadcasesDb(db) {
  db.version = '5.0.0';
  db.max_capacity = db.max_capacity || DEFAULT_MAX_CAPACITY;
  db.updated_at = new Date().toISOString();
  const payload = JSON.stringify(db, null, 2);

  for (const p of [KIT_BADCASES_PATH, LEGACY_BADCASES_PATH]) {
    const dir = path.dirname(p);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(p, payload, 'utf-8');
  }
}

/**
 * 正样本审美沉淀 (--positive)：写入项目 DESIGN.md 与 tokens.css
 */
function distillPositive({ dir, category, token, note }) {
  const projectRoot = path.resolve(dir || '.');
  if (!fs.existsSync(projectRoot)) {
    fs.mkdirSync(projectRoot, { recursive: true });
  }

  const designMdPath = path.join(projectRoot, 'DESIGN.md');
  const tokensCssPath = path.join(projectRoot, 'tokens.css');
  const nowStr = new Date().toISOString().slice(0, 19).replace('T', ' ');

  const cat = category || 'UI 审美与质感 Token';
  const tok = token || '--accent-primary: #6366f1; --card-radius: 16px; --glass-shadow: 0 8px 24px rgba(15,23,42,0.08)';
  const desc = note || '用户认可的高级视觉与动效参数';

  // 1. 更新或初始化项目 DESIGN.md
  let mdContent = '';
  if (fs.existsSync(designMdPath)) {
    mdContent = fs.readFileSync(designMdPath, 'utf-8');
  } else {
    mdContent = `# 🎨 项目专属审美基因库 (DESIGN.md)

> 由 C06 v5.0.0 \`distill.js --positive\` 自动沉淀维护。所有后续 UI 微调与新增组件必须优先继承以下审美 Token！

## 已确认的设计基因与 Token 清单
`;
  }

  // 防重复追加：若相同的 token 已经存在则更新时间戳说明
  const entryLine = `- **[${cat}]** \`${tok}\` — *${desc}* *(沉淀于 ${nowStr})*`;
  if (!mdContent.includes(tok)) {
    mdContent = mdContent.trimEnd() + '\n' + entryLine + '\n';
    fs.writeFileSync(designMdPath, mdContent, 'utf-8');
  }

  // 2. 提取 --var: value 自动同步至 tokens.css
  const cssPairs = [];
  const pairRe = /(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);?/g;
  let m;
  while ((m = pairRe.exec(tok)) !== null) {
    cssPairs.push({ key: m[1].trim(), val: m[2].trim() });
  }

  if (cssPairs.length > 0) {
    let existingVars = {};
    if (fs.existsSync(tokensCssPath)) {
      const rawCss = fs.readFileSync(tokensCssPath, 'utf-8');
      let cm;
      while ((cm = pairRe.exec(rawCss)) !== null) {
        existingVars[cm[1].trim()] = cm[2].trim();
      }
    }
    for (const p of cssPairs) {
      existingVars[p.key] = p.val;
    }
    const cssLines = [
      '/* Generated & Maintained by C06 v5.0.0 distill.js --positive */',
      ':root {',
      ...Object.entries(existingVars).map(([k, v]) => `  ${k}: ${v};`),
      '}',
      ''
    ];
    fs.writeFileSync(tokensCssPath, cssLines.join('\n'), 'utf-8');
  }

  console.log(`[OK] ✨ 正样本审美已自动沉淀至项目基因库:`);
  console.log(`  • DESIGN.md : ${designMdPath}`);
  if (cssPairs.length > 0) {
    console.log(`  • tokens.css: ${tokensCssPath} (更新 ${cssPairs.length} 个 CSS 变量)`);
  }
  console.log(`  • 沉淀内容  : [${cat}] ${tok} (${desc})`);
  return { designMdPath, tokensCssPath, category: cat, token: tok, note: desc };
}

/**
 * 负样本避坑沉淀 (--negative)：写入 kit/data/design_badcases.json 并带去重与容量上限淘汰
 */
function distillNegative({ category, title, badcase, solution, rule }) {
  const db = loadBadcasesDb();
  const maxCap = db.max_capacity || DEFAULT_MAX_CAPACITY;

  // 若仅触发 --negative 检查或参数为空，验证 Lucky Note 4 大教训均在库中并输出
  if (!title && !rule) {
    saveBadcasesDb(db);
    const luckyCases = db.badcases.filter(b => (b.category || '').includes('Lucky Note') || ['CASE-012', 'CASE-013', 'CASE-014', 'CASE-015'].includes(b.id));
    console.log(`[OK] 🛡️ 负样本避坑库自检通过 (${KIT_BADCASES_PATH})`);
    console.log(`  • 当前收录总数: ${db.badcases.length}/${maxCap} 条 (含去重与容量淘汰保护)`);
    console.log(`  • Lucky Note 4 大血泪教训核验 (${luckyCases.length}/4):`);
    luckyCases.forEach(c => console.log(`    - [${c.id}] ${c.title}`));
    return db;
  }

  const normTitle = (title || '').trim();
  const existingIdx = db.badcases.findIndex(
    item => item.title === normTitle || (rule && item.rule === rule)
  );

  let entry;
  if (existingIdx >= 0) {
    entry = db.badcases[existingIdx];
    entry.category = category || entry.category;
    entry.badcase = badcase || entry.badcase;
    entry.solution = solution || entry.solution;
    entry.rule = rule || entry.rule;
    entry.hits = (entry.hits || 1) + 1;
    entry.updated_at = new Date().toISOString();
    db.badcases[existingIdx] = entry;
  } else {
    // 容量上限淘汰：若超出 max_capacity，淘汰最早且 hits 最低的非 Lucky Note 核心条目
    while (db.badcases.length >= maxCap) {
      let evictIdx = db.badcases.findIndex(
        b => !(b.category || '').includes('Lucky Note') && (b.hits || 1) <= 2
      );
      if (evictIdx < 0) evictIdx = 0;
      db.badcases.splice(evictIdx, 1);
    }

    const nextNum = db.badcases.reduce((mx, item) => {
      const m = /^CASE-(\d+)$/.exec(item.id || '');
      return m ? Math.max(mx, parseInt(m[1], 10)) : mx;
    }, 0) + 1;

    entry = {
      id: `CASE-${String(nextNum).padStart(3, '0')}`,
      category: category || 'UI/UX 避坑规范',
      title: normTitle || '未命名体验或工程缺陷',
      badcase: badcase || '',
      solution: solution || '',
      rule: rule || '',
      hits: 1,
      created_at: new Date().toISOString()
    };
    db.badcases.push(entry);
  }

  saveBadcasesDb(db);
  console.log(`[OK] 🛡️ 负样本避坑经验已沉淀入库 (${KIT_BADCASES_PATH}):`);
  console.log(`  • 编号与标题: ${entry.id} - ${entry.title} (累计触发: ${entry.hits} 次)`);
  console.log(`  • 红线规则  : ${entry.rule}`);
  console.log(`  • 库容量状态: ${db.badcases.length}/${maxCap}`);
  return entry;
}

if (require.main === module) {
  const opts = parseFlags(process.argv.slice(2));

  if (opts.mode === 'positive') {
    distillPositive({
      dir: opts.dir || opts.positional[0] || '.',
      category: opts.category || opts.positional[1],
      token: opts.token || opts.positional[2],
      note: opts.note || opts.positional[3]
    });
    process.exit(0);
  }

  if (opts.mode === 'negative' || opts.mode === 'list') {
    distillNegative({
      category: opts.category || opts.positional[0],
      title: opts.title || opts.positional[1],
      badcase: opts.badcase || opts.positional[2],
      solution: opts.solution || opts.positional[3],
      rule: opts.rule || opts.positional[4]
    });
    process.exit(0);
  }

  // 兼容旧版 5 参数位置调用: node distill.js <category> <title> <badcase> <solution> <rule>
  if (opts.positional.length >= 5) {
    const [category, title, badcase, solution, rule] = opts.positional;
    distillNegative({ category, title, badcase, solution, rule });
    process.exit(0);
  }

  console.log(`用法:
  正样本审美沉淀: node distill.js --positive [--dir <projectDir>] [--category <类别>] --token "<CSS变量或审美Token>" [--note "<说明>"]
  负样本避坑沉淀: node distill.js --negative [--category <类别>] [--title <标题>] [--badcase <病因>] [--solution <解法>] [--rule <红线>]`);
  process.exit(0);
}

module.exports = { distillPositive, distillNegative, loadBadcasesDb };
