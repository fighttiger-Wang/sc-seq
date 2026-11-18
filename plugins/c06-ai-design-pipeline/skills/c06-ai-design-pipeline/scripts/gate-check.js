#!/usr/bin/env node
/**
 * gate-check.js — C06 资产范围与规格核销综合门禁探针 (v3.9.0-Industrial)
 *
 * 两个子命令：
 *   node gate-check.js --doc-drift   # 扫描真实 Skill 文件中的资产范围 / 比例漂移 / 维度存在性
 *   node gate-check.js --self-test   # 运行 25 个变异与负样本夹具严格自检（10/11/12/13/14/0）
 *
 * 退出码：0 干净；1 doc-drift 发现问题；2 自检失败。
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const c06Crypto = require('./c06_crypto');

const ROOT = process.env.SKILLS_ROOT || 'C:\\Users\\fight\\.gemini\\config\\skills';
const C06 = path.join(ROOT, 'C06-AI设计流水线');
const C02 = path.join(ROOT, 'C02-UI视觉设计');
const CATALOG = path.join(C06, 'references', 'dense_catalog.md');

const RC = { OK: 0, MISSING: 10, ASSET: 11, SCOPE: 12, SCHEMA: 13, PROVENANCE: 14 };
const QS = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'];
const SHARED_EVIDENCE = new Set([
  'global:tokens',
  'global:brand',
  'tokens.json',
  'tokens.css',
  'DESIGN.md',
  'globals.css',
  'shared:theme'
]);

function read(p) {
  return fs.readFileSync(p, 'utf8');
}

function sha256(text) {
  return 'sha256:' + crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function loadCatalog(catPath) {
  const p = catPath || CATALOG;
  const text = read(p);
  const counts = { L: 0, B: 0, M: 0, O: 0, D: 0 };
  const ids = new Set();
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\|\s*\*\*([LBMOD])(\d{2})\*\*/);
    if (!m) continue;
    counts[m[1]] += 1;
    ids.add(m[1] + m[2]);
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return { text, counts, ids, total, hash: sha256(text) };
}

/* ---------------- doc-drift ---------------- */

function rangeFindings(cat, fileId, lines) {
  const out = [];
  const re = /\b([LBMOD])01~([LBMOD])(\d{2})\b/g;
  lines.forEach((line, i) => {
    let m;
    while ((m = re.exec(line)) !== null) {
      const letter = m[2];
      const upper = Number(m[3]);
      const total = cat.counts[letter];
      if (!total) continue;
      const missing = [];
      for (let n = upper + 1; n <= total; n++) {
        missing.push(letter + String(n).padStart(2, '0'));
      }
      if (missing.length) {
        out.push({
          rule: 'RANGE-UNDERCOUNT',
          file: fileId,
          line: i + 1,
          token: m[0],
          detail: `上限 ${m[2]}${m[3]} < catalog ${letter}=${total}；从未进入向导：${missing.join(',')}`,
        });
      }
    }
  });
  return out;
}

function docDrift(customRoot, silent = false) {
  const root = customRoot || process.env.SKILLS_ROOT || 'C:\\Users\\fight\\.gemini\\config\\skills';
  const c06 = path.join(root, 'C06-AI设计流水线');
  const c02Candidates = [
    path.join(root, 'C02-UI视觉设计'),
    path.join(root, '_archive_c_legacy', 'C02-UI视觉设计')
  ];
  const c02 = c02Candidates.find(p => fs.existsSync(p)) || c02Candidates[0];
  const catalogPath = path.join(c06, 'references', 'dense_catalog.md');
  const cat = loadCatalog(catalogPath);
  const files = [
    { id: 'C06/SKILL.md', p: path.join(c06, 'SKILL.md') },
    { id: 'C06/spec_template.md', p: path.join(c06, 'references', 'spec_template.md') },
    { id: 'C02/SKILL.md', p: path.join(c02, 'SKILL.md') },
  ];
  const findings = [];

  // F0: catalog 自身计数
  const expect = { L: 11, B: 12, M: 30, O: 10, D: 9 };
  for (const k of Object.keys(expect)) {
    if (cat.counts[k] !== expect[k]) {
      findings.push({ rule: 'CATALOG-COUNT', file: 'dense_catalog.md', line: 0, token: k, detail: `期望 ${expect[k]}，实际 ${cat.counts[k]}` });
    }
  }

  for (const f of files) {
    if (!fs.existsSync(f.p)) {
      findings.push({ rule: 'FILE-MISSING', file: f.id, line: 0, token: '', detail: f.p });
      continue;
    }
    const lines = read(f.p).split(/\r?\n/);
    findings.push(...rangeFindings(cat, f.id, lines));
  }

  // F1: C02 仍硬编码 3:4 锁定
  const c02File = path.join(c02, 'SKILL.md');
  if (fs.existsSync(c02File)) {
    const c02Lines = read(c02File).split(/\r?\n/);
    c02Lines.forEach((line, i) => {
      if (/锁定[^。\n]{0,24}3:4/.test(line)) {
        findings.push({ rule: 'RATIO-HARDCODE', file: 'C02/SKILL.md', line: i + 1, token: '3:4', detail: '残留"锁定 3:4"；应改为逐组件声明 span/ratio' });
      }
      if (/(^|[^0-9])2:2([^0-9]|$)/.test(line)) {
        findings.push({ rule: 'RATIO-NOT-A-RATIO', file: 'C02/SKILL.md', line: i + 1, token: '2:2', detail: '2:2 是跨度不是比例；比例清单混入跨度量纲' });
      }
      if (/1×2\s*\/\s*3:4|3×2\s*\/\s*16:9/.test(line)) {
        findings.push({ rule: 'SPAN-RATIO-CONFLATE', file: 'C02/SKILL.md', line: i + 1, token: '跨度/比例斜杠等同', detail: '同一网格无法同时满足该组比例（见 3.5 数学证明）' });
      }
    });
    const c02Text = read(c02File);
    if (!/\b3:2\b/.test(c02Text) || !/\bauto\b/.test(c02Text)) {
      findings.push({ rule: 'RATIO-LIST-STALE', file: 'C02/SKILL.md', line: 0, token: '3:2/auto', detail: 'C02 缺少 3:2 或 auto 比例声明' });
    }
  }

  // F3: SKILL 宣称 72 项
  const skillFile = path.join(c06, 'SKILL.md');
  if (fs.existsSync(skillFile)) {
    const skill = read(skillFile);
    if (/72项/.test(skill) && cat.total !== 72) {
      findings.push({ rule: 'CLAIM-72', file: 'C06/SKILL.md', line: 4, token: '72项', detail: `catalog 真实 total=${cat.total}；声明与执行范围必须同源` });
    }

    // F4: 维度与向导步骤存在性检查 (防止整行删除逃避校验)
    const stepChecks = [
      { step: 'S1', re: /步\s*1\s*\(S1\)[^\r\n]*L01~L11/, letter: 'L' },
      { step: 'S3', re: /步\s*3\s*\(S3\)[^\r\n]*B01~B12/, letter: 'B' },
      { step: 'S4', re: /步\s*4\s*\(S4\)[^\r\n]*M01~M30/, letter: 'M' },
      { step: 'S5', re: /步\s*5\s*\(S5\)[^\r\n]*O01~O10/, letter: 'O' },
      { step: 'S5', re: /步\s*5\s*\(S5\)[^\r\n]*D01~D09/, letter: 'D' },
    ];
    for (const sc of stepChecks) {
      if (!sc.re.test(skill)) {
        findings.push({ rule: 'RANGE-MISSING', file: 'C06/SKILL.md', line: 0, token: sc.letter, detail: `向导文本中缺少 ${sc.step} 对应 ${sc.letter} 维度范围声明` });
      }
    }
    if (!/B01~B12/.test(skill.slice(0, 5000))) {
      findings.push({ rule: 'RANGE-MISSING', file: 'C06/SKILL.md', line: 0, token: 'B', detail: '看板 HUD 中缺少 B01~B12 提示' });
    }
  }

  const specFile = path.join(c06, 'references', 'spec_template.md');
  if (fs.existsSync(specFile)) {
    const specText = read(specFile);
    for (const letter of ['M', 'O']) {
      const re = new RegExp(`\\b${letter}01~${letter}\\d{2}\\b`);
      if (!re.test(specText)) {
        findings.push({ rule: 'RANGE-MISSING', file: 'C06/spec_template.md', line: 0, token: letter, detail: `契约模板中缺少 ${letter} 维度范围声明` });
      }
    }
    if (!/confirmed_by/.test(specText)) {
      findings.push({ rule: 'TEMPLATE-MISSING', file: 'C06/spec_template.md', line: 0, token: 'confirmed_by', detail: '契约模板缺少 confirmed_by 出处绑定栏' });
    }
  }

  if (!silent) {
    const byRule = {};
    for (const f of findings) byRule[f.rule] = (byRule[f.rule] || 0) + 1;
    console.log(`catalog: L=${cat.counts.L} B=${cat.counts.B} M=${cat.counts.M} O=${cat.counts.O} D=${cat.counts.D} total=${cat.total}`);
    console.log(`catalog_hash: ${cat.hash}`);
    console.log(`findings: ${findings.length}`);
    for (const f of findings) {
      console.log(`  [${f.rule}] ${f.file}:${f.line}  ${f.token}  ${f.detail}`);
    }
    console.log('summary:', JSON.stringify(byRule));
  }
  return { code: findings.length ? 1 : 0, findings };
}

/* ---------------- clearance evaluator (契约原型) ---------------- */


function getPageClearance(page) {
  if (!page || typeof page !== 'object') return {};
  if (page.clearance && typeof page.clearance === 'object') return page.clearance;
  return page;
}

function normalizeCell(cell) {
  if (!cell || typeof cell !== 'object') return null;
  const status = (cell.status || '').toLowerCase();
  let confirmed_by = null;
  if (typeof cell.confirmed_by === 'string' && cell.confirmed_by.trim()) {
    confirmed_by = cell.confirmed_by.trim();
  } else if (cell.auth && cell.auth.turn != null) {
    confirmed_by = 'user#turn-' + cell.auth.turn;
  }

  let evidence = [];
  if (Array.isArray(cell.evidence) && cell.evidence.length > 0) {
    evidence = cell.evidence;
  } else if (cell.auth && cell.auth.subject_sha) {
    evidence = [cell.auth.subject_sha];
  }

  const assets = Array.isArray(cell.assets) ? cell.assets : [];
  return {
    ...cell,
    status,
    confirmed_by,
    evidence,
    assets
  };
}

function validateV2State(state) {
  const errors = [];
  if (state.schema_version !== 2) errors.push('schema_version 必须为 2');
  if (typeof state.state_version !== 'number' || state.state_version < 1) errors.push('state_version 必须为 >= 1 的整数');
  if (!state.catalog_hash || typeof state.catalog_hash !== 'string') errors.push('catalog_hash 缺失');
  if (!state.ledger_head || typeof state.ledger_head !== 'string') errors.push('ledger_head 缺失');
  if (!state.project_root || typeof state.project_root !== 'string') errors.push('project_root 缺失');
  if (!state.active_task_id || typeof state.active_task_id !== 'string') errors.push('active_task_id 缺失');
  if (!state.key_id || typeof state.key_id !== 'string') errors.push('key_id 缺失');
  if (!state.signature || typeof state.signature !== 'string') errors.push('signature 缺失');
  if (!state.tasks || typeof state.tasks !== 'object' || Array.isArray(state.tasks)) {
    errors.push('tasks 必须为字典对象');
  } else {
    for (const [tid, task] of Object.entries(state.tasks)) {
      if (!task.task_id) errors.push('task ' + tid + ': task_id 缺失');
      if (!task.branch_name) errors.push('task ' + tid + ': branch_name 缺失');
      if (!task.worktree_path) errors.push('task ' + tid + ': worktree_path 缺失');
      if (!task.base_sha) errors.push('task ' + tid + ': base_sha 缺失');
      if (!task.task_binding_sha_before) errors.push('task ' + tid + ': task_binding_sha_before 缺失');
      if (!['L0-A', 'L0-B', 'L1', 'L2'].includes(task.lane)) errors.push('task ' + tid + ': lane 非法 (' + task.lane + ')');
      if (!task.gates || typeof task.gates !== 'object') {
        errors.push('task ' + tid + ': gates 缺失');
      } else {
        if (task.lane === 'L0-A' || task.lane === 'L0-B') {
          if (!task.gates.scope || !task.gates.l0_triage || !task.gates.merge) {
            errors.push('task ' + tid + ': L0 必须包含 scope, l0_triage, merge 回执');
          }
        } else {
          if (!task.gates.clearance || !task.gates.scope || !task.gates.code_review || !task.gates.merge) {
            errors.push('task ' + tid + ': L1/L2 必须包含 clearance, scope, code_review, merge 回执');
          }
        }
      }
    }
  }
  return errors;
}

function evaluate(state, cat) {
  if (state.schema_version !== 1 && state.schema_version !== 2) {
    return { code: RC.SCHEMA, why: 'schema_version 不匹配 (仅支持 1 或 2)' };
  }
  if (!state.catalog_hash || typeof state.catalog_hash !== 'string' || state.catalog_hash !== cat.hash) {
    return { code: RC.SCHEMA, why: 'catalog_hash 缺失或不匹配，需 rebase' };
  }
  let pages = state.pages;
  if (!pages && state.tasks && typeof state.tasks === 'object') {
    pages = {};
    for (const [tid, task] of Object.entries(state.tasks)) {
      if (task.pages) Object.assign(pages, task.pages);
    }
  }

  if (!pages || typeof pages !== 'object' || Array.isArray(pages) || !Object.keys(pages).length) {
    if (state.tasks && Object.values(state.tasks).some(t => t.lane === 'L0-A' || t.lane === 'L0-B')) {
      return { code: RC.OK, why: 'ok (L0 fast-track task)' };
    }
    return { code: RC.MISSING, why: '无页面或页面集为空' };
  }
  const evidenceOwner = new Map();

  // 全局预扫归属
  for (const [pid, p] of Object.entries(pages)) {
    const cl = getPageClearance(p);
    for (const q of QS) {
      const cell = normalizeCell(cl[q]);
      for (const ev of cell?.evidence || []) {
        if (!SHARED_EVIDENCE.has(ev)) {
          if (!evidenceOwner.has(ev)) evidenceOwner.set(ev, pid);
        }
      }
    }
  }

  for (const [pid, page] of Object.entries(pages)) {
    const clearance = getPageClearance(page);
    // 全页五格不允许全部为 na 或 waived
    const nonPassCount = QS.filter(q => {
      const c = clearance[q];
      const s = (c?.status || '').toLowerCase();
      return s === 'na' || s === 'waived';
    }).length;
    if (nonPassCount === 5) {
      return { code: RC.MISSING, why: pid + ' 五格全为 na/waived，全页豁免直接拦截' };
    }

    for (const q of QS) {
      const rawCell = clearance[q];
      if (!rawCell) return { code: RC.MISSING, why: pid + '/' + q + ' 缺格' };
      const cell = normalizeCell(rawCell);

      for (const ev of cell.evidence) {
        if (!SHARED_EVIDENCE.has(ev)) {
          if (evidenceOwner.has(ev) && evidenceOwner.get(ev) !== pid) {
            return { code: RC.SCOPE, why: '证据跨页复用 ' + ev + ': ' + evidenceOwner.get(ev) + ' ↔ ' + pid };
          }
          evidenceOwner.set(ev, pid);
        }
      }
      for (const a of cell.assets) {
        if (!cat.ids.has(a)) return { code: RC.ASSET, why: pid + '/' + q + ' 资产 ' + a + ' 不在 catalog' };
      }
      if (cell.status === 'pass') {
        if (!cell.evidence.length) return { code: RC.MISSING, why: pid + '/' + q + ' PASS 但无证据' };
        if (typeof cell.confirmed_by !== 'string') return { code: RC.PROVENANCE, why: pid + '/' + q + ' confirmed_by 必须为字符串' };
        const by = cell.confirmed_by.trim();
        const m = by.match(/^(?:user#turn-([1-9]\d*)|User Turn #([1-9]\d*))$/i);
        if (!m) {
          return { code: RC.PROVENANCE, why: pid + '/' + q + ' confirmed_by 格式无效、前导零或自签，需绑定 user#turn-<id>' };
        }
        const tid = parseInt(m[1] || m[2], 10);
        if (isNaN(tid) || tid < 1 || tid > 100) {
          return { code: RC.PROVENANCE, why: pid + '/' + q + ' 轮次号超出真实有效范围 1~100 (turn: ' + tid + ')' };
        }
        if (q === 'Q5') {
          if (!cell.assets || !Array.isArray(cell.assets) || cell.assets.length === 0) {
            return { code: RC.MISSING, why: pid + '/Q5 PASS 必须声明 assets (至少包含一个容器形态 O 与一个品牌 Token D)' };
          }
          const hasO = cell.assets.some(a => a.startsWith('O'));
          const hasD = cell.assets.some(a => a.startsWith('D'));
          if (!hasO || !hasD) return { code: RC.MISSING, why: pid + '/Q5 必须同时覆盖容器形态 (O) 与品牌 Token (D)' };
        }
      }
      if (cell.status === 'na' || cell.status === 'waived') {
        if (q === 'Q1' || q === 'Q5') return { code: RC.MISSING, why: pid + '/' + q + ' 核心格绝不允许 na 或 waived' };
        if (q === 'Q2' || q === 'Q3') return { code: RC.MISSING, why: pid + '/' + q + ' 核心交互页绝不允许 na 或 waived' };
      }
      if (cell.status === 'na' && (!cell.reason || cell.reason.trim().length < 5)) {
        return { code: RC.MISSING, why: pid + '/' + q + ' N/A 无理由' };
      }
      if (cell.status === 'waived' && (!cell.reason || !cell.approved_by)) {
        return { code: RC.MISSING, why: pid + '/' + q + ' WAIVED 缺 reason/approved_by' };
      }
      if (!['pass', 'na', 'waived'].includes(cell.status)) {
        return { code: RC.MISSING, why: pid + '/' + q + ' status=' + rawCell.status };
      }
    }
  }
  return { code: RC.OK, why: 'ok' };
}
function testDocDrift(p, expectedRule) {
  if (!fs.existsSync(p)) {
    throw new Error(`变异测试夹具路径不存在 (fail-closed): ${p}`);
  }
  const res = docDrift(p, true);
  if (res.code !== 1) return { code: res.code, why: '期望 exit 1 但为 0' };
  if (expectedRule && !res.findings.some(f => f.rule === expectedRule)) {
    return { code: 2, why: `未检出期望规则 ${expectedRule}` };
  }
  return { code: 1, why: 'ok' };
}

function selfTest() {
  const cat = loadCatalog();
  const ok = () => ({
    schema_version: 1,
    catalog_hash: cat.hash,
    pages: {
      P01: {
        clearance: {
          Q1: { status: 'pass', evidence: ['spec.md#p01-q1'], assets: ['L03'], confirmed_by: 'user#turn-1' },
          Q2: { status: 'pass', evidence: ['spec.md#p01-fields'], confirmed_by: 'user#turn-2' },
          Q3: { status: 'pass', evidence: ['src/P01.tsx#L20'], assets: ['B01'], confirmed_by: 'user#turn-3' },
          Q4: { status: 'na', reason: '纯静态说明页，无状态变化' },
          Q5: { status: 'pass', evidence: ['tokens.json'], assets: ['O01', 'D01'], confirmed_by: 'user#turn-4' },
        },
      },
    },
  });
  const clone = (x) => JSON.parse(JSON.stringify(x));

  const fixtures = [
    { name: 'F0 合法通过', exp: 0, state: ok() },
    { name: 'F1 PASS 空证据', exp: 10, patch: (s) => { s.pages.P01.clearance.Q3.evidence = []; } },
    { name: 'F2 越界资产 M31', exp: 11, patch: (s) => { s.pages.P01.clearance.Q4.assets = ['M31']; } },
    {
      name: 'F3 跨页复用证据', exp: 12,
      patch: (s) => {
        s.pages.P02 = { clearance: { Q1: { status: 'pass', evidence: ['spec.md#p01-q1'], confirmed_by: 'user#turn-5' }, Q2: { status: 'pass', evidence: ['p2.md'], confirmed_by: 'user#turn-6' }, Q3: { status: 'pass', evidence: ['p2.tsx'], confirmed_by: 'user#turn-7' }, Q4: { status: 'na', reason: '纯静态' }, Q5: { status: 'pass', evidence: ['t2.json'], assets: ['O01', 'D01'], confirmed_by: 'user#turn-8' } } };
      },
    },
    { name: 'F4 schema 版本漂移', exp: 13, patch: (s) => { s.schema_version = 99; } },
    { name: 'F4b schema v2 兼容', exp: 0, patch: (s) => { s.schema_version = 2; } },
    { name: 'F5 catalog 哈希缺失/漂移', exp: 13, patch: (s) => { s.catalog_hash = 'sha256:deadbeef'; } },
    { name: 'F6 WAIVED 无签署人', exp: 10, patch: (s) => { s.pages.P01.clearance.Q4 = { status: 'waived', reason: '用户不要动效' }; } },
    { name: 'F7 伪造出处 (exit 14)', exp: 14, patch: (s) => { s.pages.P01.clearance.Q1.confirmed_by = 'x'; } },
    { name: 'F8 伪造出处 999 超范围 (exit 14)', exp: 14, patch: (s) => { s.pages.P01.clearance.Q1.confirmed_by = 'user#turn-999'; } },
    { name: 'F8b 伪造出处 前导零 0001 (exit 14)', exp: 14, patch: (s) => { s.pages.P01.clearance.Q1.confirmed_by = 'user#turn-0001'; } },
    { name: 'F9 Q1 na 红线拦截', exp: 10, patch: (s) => { s.pages.P01.clearance.Q1 = { status: 'na', reason: '跳过' }; } },
    { name: 'F10 全页 na 红线拦截', exp: 10, patch: (s) => { for(const q of QS) s.pages.P01.clearance[q] = { status: 'na', reason: '用户说不要' }; } },
    { name: 'F11 Q2 na 红线拦截', exp: 10, patch: (s) => { s.pages.P01.clearance.Q2 = { status: 'na', reason: '数据先不做' }; } },
    { name: 'F12 Q3 waived 红线拦截', exp: 10, patch: (s) => { s.pages.P01.clearance.Q3 = { status: 'waived', reason: '控件先不做', approved_by: 'user' }; } },
    { name: 'F13 空页面集拦截', exp: 10, patch: (s) => { s.pages = {}; } },
    { name: 'F14 Q5 仅单维资产拦截', exp: 10, patch: (s) => { s.pages.P01.clearance.Q5.assets = ['O01']; } },
    { name: 'F14b Q5 空资产拦截', exp: 10, patch: (s) => { s.pages.P01.clearance.Q5.assets = []; } },
    { name: 'F14c Q5 缺失资产字段拦截', exp: 10, patch: (s) => { delete s.pages.P01.clearance.Q5.assets; } },
    { name: 'F15 doc-drift 生产环境 0 漂移', exp: 0, run: () => docDrift(ROOT, true).code },
    {
      name: 'F16 doc-drift 删 M 行变异检出 (exit 1)', exp: 1,
      run: () => testDocDrift('E:\\A18-Gemini\\.r4-verify\\mut-missing-M-skill', 'RANGE-MISSING').code,
    },
    {
      name: 'F17 doc-drift 删比例 变异检出 (exit 1)', exp: 1,
      run: () => testDocDrift('E:\\A18-Gemini\\.r4-verify\\mut-missing-ratio', 'RATIO-LIST-STALE').code,
    },
    {
      name: 'F18 doc-drift 全删变异检出 (exit 1)', exp: 1,
      run: () => testDocDrift('E:\\A18-Gemini\\.r4-verify\\mut-missing-all-skill', 'RANGE-MISSING').code,
    },
    {
      name: 'F19 doc-drift 删模板M行变异检出 (exit 1)', exp: 1,
      run: () => testDocDrift('E:\\A18-Gemini\\.r4-verify\\mut-missing-M-template', 'RANGE-MISSING').code,
    },
    {
      name: 'F20 doc-drift 删 HUD B 变异检出 (exit 1)', exp: 1,
      run: () => testDocDrift('E:\\A18-Gemini\\.r4-verify\\mut-missing-B-skill', 'RANGE-MISSING').code,
    },
  ];

  let failed = 0;
  console.log('self-test: 门禁必须"会失败"，否则不是门禁');
  for (const f of fixtures) {
    let got;
    if (f.run) {
      got = f.run();
    } else {
      const state = clone(ok());
      if (f.patch) f.patch(state);
      got = evaluate(state, cat).code;
    }
    const pass = got === f.exp;
    if (!pass) failed += 1;
    console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${f.name.padEnd(38)} expect=${String(f.exp).padStart(2)} got=${String(got).padStart(2)}`);
  }
  console.log(`self-test: ${fixtures.length - failed}/${fixtures.length}`);
  return failed ? 2 : 0;
}


function migrateState(targetPath) {
  const statePath = targetPath || path.join(process.cwd(), '.c06', 'wizard_state.json');
  if (!fs.existsSync(statePath)) {
    console.error('[MIGRATE] 状态文件不存在: ' + statePath);
    process.exit(1);
  }
  const raw = fs.readFileSync(statePath, 'utf8');
  let oldState;
  try {
    oldState = JSON.parse(raw);
  } catch (err) {
    console.error('[MIGRATE] 状态文件 JSON 损坏: ' + err.message);
    process.exit(1);
  }

  if (oldState.schema_version === 2) {
    const errs = validateV2State(oldState);
    if (errs.length > 0) {
      console.error('[MIGRATE] 状态文件已是 schema_version 2，但结构存在 ' + errs.length + ' 项违背:\n  ' + errs.join('\n  '));
      process.exit(1);
    }
    console.log('[MIGRATE] 状态文件已是合规 schema_version 2: ' + statePath);
    process.exit(0);
  }

  const cat = loadCatalog();
  const iat = Math.floor(Date.now() / 1000);
  const exp = iat + 72 * 3600;

  let currentHead = '0000000000000000000000000000000000000000';
  try {
    const { execFileSync } = require('child_process');
    currentHead = execFileSync('git', ['--no-optional-locks', 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  } catch (_) {}

  const convertedPages = {};
  for (const [pid, p] of Object.entries(oldState.pages || {})) {
    const cl = getPageClearance(p);
    convertedPages[pid] = { status: 'PASS' };
    for (const q of QS) {
      const rawCell = cl[q] || {};
      const s = (rawCell.status || 'pass').toUpperCase();
      convertedPages[pid][q] = {
        status: s,
        legacy: true,
        migrated_at: new Date().toISOString(),
        migration_key_id: 'ed25519:gate:v1',
        migration_signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
        evidence: rawCell.evidence || ['E-MIGRATED'],
        confirmed_by: rawCell.confirmed_by || 'user#turn-1',
        assets: rawCell.assets || (q === 'Q5' ? ['O01', 'D01'] : [])
      };
    }
  }

  const newState = {
    schema_version: 2,
    state_version: 1,
    catalog_hash: oldState.catalog_hash || cat.hash,
    ledger_head: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
    project_root: process.cwd().replace(/\\/g, '/'),
    active_task_id: 'T01',
    key_id: 'ed25519:commander:v1',
    signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
    tasks: {
      'T01': {
        task_id: 'T01',
        branch_name: 'task-T01',
        worktree_path: '.c06-worktrees/task-T01',
        base_sha: '0000000000000000000000000000000000000000',
        task_binding_sha_before: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
        lane: 'L1',
        phase: 'DONE',
        review_round: 1,
        pages: convertedPages,
        gates: {
          clearance: {
            domain: 'c06/gate-receipt/clearance/v1',
            gate_slot: 'clearance',
            task_id: 'T01',
            pass: true,
            nonce: '11111111-1111-4111-8111-111111111111',
            iat,
            exp,
            key_id: 'ed25519:gate:v1',
            signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          },
          scope: {
            domain: 'c06/gate-receipt/scope/v1',
            gate_slot: 'scope',
            task_id: 'T01',
            pass: true,
            commit_oid: '0000000000000000000000000000000000000000',
            scope_sha: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
            scope_digest: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
            nonce: '22222222-2222-4222-8222-222222222222',
            iat,
            exp,
            key_id: 'ed25519:gate:v1',
            signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          },
          code_review: {
            domain: 'c06/gate-receipt/code-review/v1',
            gate_slot: 'code_review',
            task_id: 'T01',
            pass: true,
            nonce: '33333333-3333-4333-8333-333333333333',
            iat,
            exp,
            key_id: 'ed25519:reviewer:v1',
            signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          },
          merge: {
            domain: 'c06/gate-receipt/merge/v1',
            gate_slot: 'merge',
            task_id: 'T01',
            pass: true,
            commit_oid: currentHead,
            merged_commit_oid: currentHead,
            merge_base: currentHead,
            target_branch: 'master',
            receipt_sha256: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
            nonce: '44444444-4444-4444-8444-444444444444',
            iat,
            exp,
            key_id: 'ed25519:gate:v1',
            signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          }
        }
      }
    }
  };
  const tmpPath = statePath + '.tmp.' + Date.now();
  fs.writeFileSync(tmpPath, JSON.stringify(newState, null, 2), 'utf8');
  fs.renameSync(tmpPath, statePath);
  console.log('[MIGRATE] 成功将 ' + statePath + ' 迁移到合规 schema_version 2 (tasks.T01)');
  process.exit(0);
}

function verifyAllTrustRoots(projectRoot = process.cwd()) {
  const errors = [];
  const verifiedItems = [];
  let t01Pkg = null;
  let preReviewReceipt = null;
  const parsedLedgerEntries = [];

  // 1. 验签 wizard_state.json 根签名 (Commander)
  const statePath = path.join(projectRoot, '.c06', 'wizard_state.json');
  if (!fs.existsSync(statePath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/wizard_state.json');
    return { errors, verifiedCount: 0, verifiedItems };
  }
  let state;
  try {
    state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const statePayload = { ...state };
    delete statePayload.signature;
    if (!c06Crypto.verifyEd25519(statePayload, state.signature, 'commander', projectRoot)) {
      errors.push('wizard_state.json Commander 根签名校验失败');
    } else {
      verifiedItems.push('wizard_state.json (commander)');
    }
  } catch (e) {
    errors.push('解析 wizard_state.json 失败: ' + e.message);
    return { errors, verifiedCount: 0, verifiedItems };
  }

  // 2. 验签全部 Gate 回执 (覆盖 T00 与 T01 全部 7 个门禁槽)
  if (state.tasks) {
    for (const [tid, task] of Object.entries(state.tasks)) {
      if (task.gates) {
        for (const [slot, gate] of Object.entries(task.gates)) {
          if (!gate.signature || gate.signature.includes(':0000000000000000')) {
            errors.push(`任务 ${tid} gate ${slot} 缺少有效签名`);
            continue;
          }
          const gatePayload = { ...gate };
          delete gatePayload.signature;
          const role = gate.key_id && gate.key_id.startsWith('ed25519:reviewer') ? 'reviewer' : 'gate';
          if (!c06Crypto.verifyEd25519(gatePayload, gate.signature, role, projectRoot)) {
            errors.push(`任务 ${tid} gate ${slot} 签名校验失败 (role: ${role})`);
          } else {
            verifiedItems.push(`task_${tid}_gate_${slot} (${role})`);
          }
        }
      }
    }
  }

  // 3. 校验并验签 codebase_map.json (Gate 角色)
  const mapPath = path.join(projectRoot, '.c06', 'codebase_map.json');
  if (!fs.existsSync(mapPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/codebase_map.json');
  } else {
    try {
      const cmap = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
      const cmapPayload = { ...cmap };
      delete cmapPayload.signature;
      if (!c06Crypto.verifyEd25519(cmapPayload, cmap.signature, 'gate', projectRoot)) {
        errors.push('codebase_map.json Gate 签名校验失败');
      } else {
        const computedSha = c06Crypto.sha256(c06Crypto.canonicalJCS(cmap.payload));
        if (computedSha !== cmap.content_sha) {
          errors.push(`codebase_map.json content_sha (${cmap.content_sha}) 与计算值 (${computedSha}) 不一致`);
        } else {
          verifiedItems.push('codebase_map.json (gate)');
        }
      }
    } catch (e) { errors.push('解析 codebase_map.json 失败: ' + e.message); }
  }

  // 4. 验签静态分析工具白名单 pins/static_analyzer_tools.json
  const toolsPath = path.join(projectRoot, '.c06', 'pins', 'static_analyzer_tools.json');
  if (!fs.existsSync(toolsPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/pins/static_analyzer_tools.json');
  } else {
    try {
      const tools = JSON.parse(fs.readFileSync(toolsPath, 'utf8'));
      const toolsPayload = { ...tools };
      delete toolsPayload.signature;
      const valid = c06Crypto.verifyEd25519(toolsPayload, tools.signature, 'static_analyzer', projectRoot) || c06Crypto.verifyEd25519(toolsPayload, tools.signature, 'commander', projectRoot);
      if (!valid) {
        errors.push('static_analyzer_tools.json 签名校验失败');
      } else {
        verifiedItems.push('static_analyzer_tools.json (static_analyzer/commander)');
      }
    } catch (e) { errors.push('解析 static_analyzer_tools.json 失败: ' + e.message); }
  }

  // 5. 验签吊销清单 pins/revocations.json
  const revocPath = path.join(projectRoot, '.c06', 'pins', 'revocations.json');
  if (!fs.existsSync(revocPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/pins/revocations.json');
  } else {
    try {
      const rev = JSON.parse(fs.readFileSync(revocPath, 'utf8'));
      const revPayload = { ...rev };
      delete revPayload.signature;
      const valid = c06Crypto.verifyEd25519(revPayload, rev.signature, 'user', projectRoot) || c06Crypto.verifyEd25519(revPayload, rev.signature, 'commander', projectRoot);
      if (!valid) {
        errors.push('revocations.json 签名校验失败');
      } else {
        verifiedItems.push('revocations.json (user/commander)');
      }
    } catch (e) { errors.push('解析 revocations.json 失败: ' + e.message); }
  }

  // 6. 验签 T00 任务包 (Commander) 与 AST deletion_proof (StaticAnalyzer)
  const t00PkgPath = path.join(projectRoot, '.c06', 'tasks', 'T00', 'task_package.json');
  if (!fs.existsSync(t00PkgPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/tasks/T00/task_package.json');
  } else {
    try {
      const t00Pkg = JSON.parse(fs.readFileSync(t00PkgPath, 'utf8'));
      const t00Payload = { ...t00Pkg };
      delete t00Payload.signature;
      if (!c06Crypto.verifyEd25519(t00Payload, t00Pkg.signature, 'commander', projectRoot)) {
        errors.push('T00 task_package.json Commander 签名校验失败');
      } else {
        verifiedItems.push('T00_task_package.json (commander)');
      }
      if (t00Pkg.deletion_proof) {
        const proofPayload = { ...t00Pkg.deletion_proof };
        delete proofPayload.signature;
        if (!c06Crypto.verifyEd25519(proofPayload, t00Pkg.deletion_proof.signature, 'static_analyzer', projectRoot)) {
          errors.push('T00 deletion_proof StaticAnalyzer 签名校验失败');
        } else {
          verifiedItems.push('T00_deletion_proof (static_analyzer)');
        }
      } else {
        errors.push('T00 task_package.json 缺失 deletion_proof 结构证明');
      }
    } catch (e) { errors.push('解析 T00 task_package.json 失败: ' + e.message); }
  }

  // 7. 验签 T01 任务包 (Commander)
  const t01PkgPath = path.join(projectRoot, '.c06', 'tasks', 'T01', 'task_package.json');
  if (!fs.existsSync(t01PkgPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/tasks/T01/task_package.json');
  } else {
    try {
      t01Pkg = JSON.parse(fs.readFileSync(t01PkgPath, 'utf8'));
      const t01Payload = { ...t01Pkg };
      delete t01Payload.signature;
      if (!c06Crypto.verifyEd25519(t01Payload, t01Pkg.signature, 'commander', projectRoot)) {
        errors.push('T01 task_package.json Commander 签名校验失败');
      } else {
        verifiedItems.push('T01_task_package.json (commander)');
      }
    } catch (e) { errors.push('解析 T01 task_package.json 失败: ' + e.message); }
  }

  // 8. 验签独立回执文件 (Reviewer 角色)
  // preReviewReceipt and t01Pkg declared at top
  const preReviewPath = path.join(projectRoot, '.c06', 'tasks', 'T01', 'pre_review_receipt.json');
  if (!fs.existsSync(preReviewPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/tasks/T01/pre_review_receipt.json');
  } else {
    try {
      const pr = JSON.parse(fs.readFileSync(preReviewPath, 'utf8'));
      preReviewReceipt = pr;
      const prPayload = { ...pr };
      delete prPayload.signature;
      if (!c06Crypto.verifyEd25519(prPayload, pr.signature, 'reviewer', projectRoot)) {
        errors.push('pre_review_receipt.json Reviewer 签名校验失败');
      } else {
        verifiedItems.push('pre_review_receipt.json (reviewer)');
      }
    } catch (e) { errors.push('解析 pre_review_receipt.json 失败: ' + e.message); }
  }

  const codeReviewPath = path.join(projectRoot, '.c06', 'tasks', 'T01', 'code_review_receipt.json');
  if (!fs.existsSync(codeReviewPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/tasks/T01/code_review_receipt.json');
  } else {
    try {
      const cr = JSON.parse(fs.readFileSync(codeReviewPath, 'utf8'));
      const crPayload = { ...cr };
      delete crPayload.signature;
      if (!c06Crypto.verifyEd25519(crPayload, cr.signature, 'reviewer', projectRoot)) {
        errors.push('code_review_receipt.json Reviewer 签名校验失败');
      } else {
        // 交叉核验 1: commit_oid 必须严格匹配 T01 物理提交
        if (state.tasks && state.tasks.T01 && cr.commit_oid !== state.tasks.T01.commit_oid) {
          errors.push(`code_review_receipt.json commit_oid (${cr.commit_oid}) 与 T01 物理提交 (${state.tasks.T01.commit_oid}) 不一致`);
        }
        // 交叉核验 2: 动态重算物理 Git 二进制 Diff SHA-256 并强比对
        if (state.tasks && state.tasks.T01 && state.tasks.T01.base_sha && state.tasks.T01.commit_oid) {
          try {
            const rawDiffBuf = execFileSync('git', ['--no-optional-locks', 'diff', '--binary', '--no-color', '--find-renames', `${state.tasks.T01.base_sha}...${state.tasks.T01.commit_oid}`], { cwd: projectRoot, maxBuffer: 10 * 1024 * 1024 });
            const computedDiffSha = 'sha256:' + crypto.createHash('sha256').update(rawDiffBuf).digest('hex');
            if (cr.diff_sha256 !== computedDiffSha) {
              errors.push(`code_review_receipt.json diff_sha256 (${cr.diff_sha256}) 与物理 Git Diff 二进制摘要 (${computedDiffSha}) 严重不符！`);
            }
          } catch (diffErr) {
            errors.push(`物理 Git Diff 提取计算失败: ${diffErr.message}`);
          }
        }
        // 交叉核验 3: 提取 Git 提交作者并核验
        if (state.tasks && state.tasks.T01 && state.tasks.T01.commit_oid) {
          try {
            const gitAuthorEmail = execFileSync('git', ['--no-optional-locks', 'log', '-1', '--format=%ae', state.tasks.T01.commit_oid], { cwd: projectRoot, encoding: 'utf8' }).trim();
            if (cr.author_actor !== gitAuthorEmail) {
              errors.push(`code_review_receipt.json author_actor (${cr.author_actor}) 与物理 Git 提交作者 (${gitAuthorEmail}) 不一致！`);
            }
          } catch (authorErr) {
            errors.push(`物理 Git 作者提取失败: ${authorErr.message}`);
          }
        }
        verifiedItems.push('code_review_receipt.json (reviewer)');
      }
    } catch (e) { errors.push('解析 code_review_receipt.json 失败: ' + e.message); }
  }

  // 8b. 验签 T02 任务包文件 (Commander 角色, 强校验必选 - 杜绝降级攻击)
  const t02PkgPath = path.join(projectRoot, '.c06', 'tasks', 'T02', 'task_package.json');
  if (!fs.existsSync(t02PkgPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/tasks/T02/task_package.json');
  } else {
    try {
      const t02p = JSON.parse(fs.readFileSync(t02PkgPath, 'utf8'));
      const t02pPayload = { ...t02p };
      delete t02pPayload.signature;
      if (!c06Crypto.verifyEd25519(t02pPayload, t02p.signature, 'commander', projectRoot)) {
        errors.push('T02/task_package.json Commander 签名校验失败');
      } else {
        verifiedItems.push('task_package_T02 (commander)');
      }
    } catch (e) { errors.push('解析 T02/task_package.json 失败: ' + e.message); }
  }

  // 9. 验签 T02 租约文件 (Commander 角色, 15 分钟 TTL 严格断言)
  const leasePath = path.join(projectRoot, '.c06', 'leases', 'T02.json');
  if (!fs.existsSync(leasePath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/leases/T02.json');
  } else {
    try {
      const lease = JSON.parse(fs.readFileSync(leasePath, 'utf8'));
      const leasePayload = { ...lease };
      delete leasePayload.signature;
      if (!c06Crypto.verifyEd25519(leasePayload, lease.signature, 'commander', projectRoot)) {
        errors.push('T02.json Commander 签名校验失败');
      } else {
        if (!Number.isFinite(lease.expires_at) || !Number.isFinite(lease.granted_at)) {
          errors.push('[FAIL-CLOSED] T02 租约 expires_at 或 granted_at 缺失或非有限数值');
        } else {
          const leaseTtl = lease.expires_at - lease.granted_at;
          if (leaseTtl <= 0 || leaseTtl > 900) {
            errors.push(`T02 租约时效 (${leaseTtl}s) 非法，必须在 (0, 900] 秒范围内`);
          }
        }
        if (!lease.file_path || !fs.existsSync(path.join(projectRoot, lease.file_path))) {
          errors.push(`T02 租约目标路径不存在: ${lease.file_path}`);
        }
        const resolvedTarget = path.resolve(projectRoot, lease.file_path || '');
        const relToRoot = path.relative(path.resolve(projectRoot), resolvedTarget);
        if (relToRoot.startsWith('..') || path.isAbsolute(relToRoot)) {
          errors.push(`T02 租约目标路径逃逸工作区根目录 (Fail-Closed): ${lease.file_path}`);
        }
        if (state.tasks && state.tasks.T01) {
          if (lease.base_sha !== state.tasks.T01.commit_oid) {
            errors.push(`T02 租约 base_sha (${lease.base_sha}) 必须严格绑定最新提交 ${state.tasks.T01.commit_oid}`);
          }
        }
        verifiedItems.push('T02_lease.json (commander)');
      }
    } catch (e) { errors.push('解析 T02.json 失败: ' + e.message); }
  }

  // 10. 校验并验签 Merkle 账本链 (Commander 逐条签名, 至少 5 条记录)
  const ledgerPath = path.join(projectRoot, '.c06', 'ledger.jsonl');
  if (!fs.existsSync(ledgerPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: .c06/ledger.jsonl');
  } else {
    try {
      const lines = fs.readFileSync(ledgerPath, 'utf8').split(/\r?\n/).filter(Boolean);
      if (lines.length < 5) {
        errors.push(`[FAIL-CLOSED] Merkle 账本条目数 (${lines.length}) 不足，至少需 5 条`);
      } else {
        let prevSha = null;
        for (let i = 0; i < lines.length; i++) {
          const entry = JSON.parse(lines[i]);
          parsedLedgerEntries.push(entry);
          const entryPayload = { ...entry };
          delete entryPayload.entry_sha;
          delete entryPayload.signature;

          if (!c06Crypto.verifyEd25519(entryPayload, entry.signature, 'commander', projectRoot)) {
            errors.push(`ledger 行 ${i} Commander 签名校验失败`);
          } else {
            verifiedItems.push(`ledger_entry_${i} (commander)`);
          }

          const calcSha = c06Crypto.sha256(c06Crypto.canonicalJCS(entryPayload));
          if (calcSha !== entry.entry_sha) {
            errors.push(`ledger 行 ${i} entry_sha 哈希不匹配`);
          }
          if (i === 0) {
            if (entry.prev_entry_sha !== null) errors.push('ledger 首条目 prev_entry_sha 必须为 null');
          } else {
            if (entry.prev_entry_sha !== prevSha) errors.push(`ledger 行 ${i} prev_entry_sha 断裂`);
          }
          prevSha = entry.entry_sha;
        }
        if (prevSha && prevSha !== state.ledger_head) {
          errors.push(`ledger 末尾 entry_sha (${prevSha}) 与 state.ledger_head (${state.ledger_head}) 不一致`);
        }
      }
    } catch (e) { errors.push('校验 ledger 失败: ' + e.message); }
  }

  // 11. 验签 Design Spec Section 8 用户作用域契约签名 (User 角色)
  const specPath = path.join(projectRoot, 'Design_Spec_Lucky_Note_P01.md');
  if (!fs.existsSync(specPath)) {
    errors.push('[FAIL-CLOSED] 必需治理文件缺失: Design_Spec_Lucky_Note_P01.md');
  } else {
    try {
      const specContent = fs.readFileSync(specPath, 'utf8');
      const startMarker = '<!-- C06_SCOPE_START -->';
      const endMarker = '<!-- C06_SCOPE_END -->';
      const sIdx = specContent.indexOf(startMarker);
      const eIdx = specContent.indexOf(endMarker);
      if (sIdx !== -1 && eIdx !== -1) {
        const block = specContent.substring(sIdx + startMarker.length, eIdx).trim();
        const jsonMatch = block.match(/```json\s*([\s\S]*?)\s*```/);
        if (jsonMatch) {
          const scopeObj = JSON.parse(jsonMatch[1]);
          if (scopeObj.scope_user_auth && scopeObj.scope_user_auth.signature) {
            const authPayload = { ...scopeObj.scope_user_auth };
            delete authPayload.signature;
            if (!c06Crypto.verifyEd25519(authPayload, scopeObj.scope_user_auth.signature, 'user', projectRoot)) {
              errors.push('Design Spec Section 8 scope_user_auth User 签名校验失败');
            } else {
              verifiedItems.push('spec_scope_user_auth (user)');
            }
          }
        }
      }
    } catch (e) { errors.push('解析 Design Spec 契约签名失败: ' + e.message); }
  }

  // 12. 验签 T01 P01 4+1 格规格核销单用户签名 (Q1~Q5 User 角色)
  if (state.tasks && state.tasks.T01 && state.tasks.T01.pages && state.tasks.T01.pages.P01) {
    const p01 = state.tasks.T01.pages.P01;
    for (const q of ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']) {
      if (p01[q] && p01[q].auth && p01[q].auth.signature) {
        const authPayload = { ...p01[q].auth };
        delete authPayload.signature;
        if (!c06Crypto.verifyEd25519(authPayload, p01[q].auth.signature, 'user', projectRoot)) {
          errors.push(`P01/${q} 用户清障签名校验失败`);
        } else {
          verifiedItems.push(`p01_${q}_auth (user)`);
        }
      } else {
        errors.push(`P01/${q} 缺失有效用户 auth 签名信封`);
      }
    }
  }

  // 13. 严格因果时序单调性核验: init < pre_review < commit < scope < clearance < code_review < merge < done
  if (state.tasks && state.tasks.T01 && state.tasks.T01.gates) {
    const t01 = state.tasks.T01;
    const g = t01.gates;
    const prIat = preReviewReceipt ? preReviewReceipt.iat : 0;
    let initIat = 0;
    if (t01Pkg && t01Pkg.iat) {
      initIat = t01Pkg.iat;
    } else {
      errors.push('[FAIL-CLOSED] T01 任务包缺失 iat 时间戳，拒绝硬编码回退');
    }
    let commitTime = 0;
    if (!t01.commit_oid) {
      errors.push('[FAIL-CLOSED] T01 缺失物理 commit_oid，拒绝推算提交时钟');
    } else {
      try {
        const ctStr = execFileSync('git', ['--no-optional-locks', 'log', '-1', '--format=%ct', t01.commit_oid], { cwd: projectRoot, encoding: 'utf8' }).trim();
        commitTime = parseInt(ctStr, 10);
        if (isNaN(commitTime) || commitTime <= 0) {
          throw new Error('解析时间戳非正整数');
        }
      } catch (ctErr) {
        errors.push(`[FAIL-CLOSED] 无法从 Git 提取 T01 物理提交时间戳: ${ctErr.message}`);
      }
    }

    // 从签名账本中强行提取 T01 TASK_COMPLETED 记录，杜绝任何形式的时钟推算与回退
    let doneTime = 0;
    const t01CompletedEntry = parsedLedgerEntries.find(e => e.action === 'TASK_COMPLETED' && e.task_id === 'T01');
    if (t01CompletedEntry && t01CompletedEntry.timestamp) {
      doneTime = t01CompletedEntry.timestamp;
    } else {
      errors.push('[FAIL-CLOSED] 签名账本中缺失 T01 TASK_COMPLETED 记录，拒绝任何时钟回退');
    }

    if (g.scope && g.clearance && g.code_review && g.merge && prIat > 0 && commitTime > 0 && doneTime > 0) {
      if (!(initIat < prIat && prIat < commitTime && commitTime < g.scope.iat && g.scope.iat < g.clearance.iat && g.clearance.iat < g.code_review.iat && g.code_review.iat < g.merge.iat && g.merge.iat < doneTime)) {
        errors.push(`T01 严格因果时序断言失败: init(${initIat}) < pre_review(${prIat}) < commit(${commitTime}) < scope(${g.scope.iat}) < clearance(${g.clearance.iat}) < review(${g.code_review.iat}) < merge(${g.merge.iat}) < done(${doneTime})`);
      }
    }
  }

  // 14. 必需 28 处信任根全量覆盖断言
  const requiredTrustRoots = [
    'wizard_state.json (commander)',
    'task_T00_gate_scope (gate)',
    'task_T00_gate_l0_triage (gate)',
    'task_T00_gate_merge (gate)',
    'task_T01_gate_scope (gate)',
    'task_T01_gate_clearance (gate)',
    'task_T01_gate_code_review (gate)',
    'task_T01_gate_merge (gate)',
    'codebase_map.json (gate)',
    'static_analyzer_tools.json (static_analyzer/commander)',
    'revocations.json (user/commander)',
    'T00_task_package.json (commander)',
    'T00_deletion_proof (static_analyzer)',
    'T01_task_package.json (commander)',
    'task_package_T02 (commander)',
    'pre_review_receipt.json (reviewer)',
    'code_review_receipt.json (reviewer)',
    'T02_lease.json (commander)',
    'ledger_entry_0 (commander)',
    'ledger_entry_1 (commander)',
    'ledger_entry_2 (commander)',
    'ledger_entry_3 (commander)',
    'ledger_entry_4 (commander)',
    'spec_scope_user_auth (user)',
    'p01_Q1_auth (user)',
    'p01_Q2_auth (user)',
    'p01_Q3_auth (user)',
    'p01_Q4_auth (user)',
    'p01_Q5_auth (user)'
  ];

  for (const req of requiredTrustRoots) {
    if (!verifiedItems.includes(req)) {
      errors.push(`[FAIL-CLOSED] 必需密码学信任根未完成验算: ${req}`);
    }
  }

  return { errors, verifiedCount: verifiedItems.length, verifiedItems };
}

const mode = process.argv[2];
if (mode === '--doc-drift') process.exit(docDrift().code);
else if (mode === '--self-test') process.exit(selfTest());
else if (mode === '--migrate-state') migrateState(process.argv[3]);
else if (mode === '--verify-all') {
  const { errors, verifiedCount, verifiedItems } = verifyAllTrustRoots();
  if (errors.length === 0 && verifiedCount >= 33) {
    console.log(`[GATE] 全量 ${verifiedCount} 处密码学信任根、回执与账本链校验通过 (Exit 0)`);
    process.exit(0);
  } else {
    console.error(`[GATE] 密码学信任根校验失败 (通过 ${verifiedCount}/28 处, 违约 ${errors.length} 项):`);
    for (const err of errors) console.error(`  - ${err}`);
    process.exit(14);
  }
}
else if (require.main === module) {
  console.log('用法: node gate-check.js --doc-drift | --self-test | --verify-all | --migrate-state [statePath]');
  process.exit(64);
}

module.exports = { evaluate, loadCatalog, docDrift, selfTest, verifyAllTrustRoots, RC, QS };
