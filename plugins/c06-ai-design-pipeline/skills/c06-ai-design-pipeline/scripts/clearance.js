#!/usr/bin/env node
/**
 * clearance.js — C06 生产级向导规格核销机器门禁脚本 (v3.9.0-Industrial)
 *
 * 用法：
 *   node clearance.js <page_id> [--strict] [--state <path>]
 *   node clearance.js --all [--state <path>]
 *   node clearance.js --self-test
 *
 * 退出码契约：
 *   0  = 全部通过或合法 N/A / 严格豁免 / L0 放行
 *   10 = 缺项 / 证据为空 / N/A 无理由 / 门禁红线违背 / 空页面集 / Q5单维缺失
 *   11 = 资产不在 catalog（非 72 项基线）
 *   12 = 页面作用域冲突 / 跨页复用证据
 *   13 = schema 版本或 catalog_hash 缺失/漂移 (需 rebase)
 *   14 = 用户出处伪造 / 签名无效 / Nonce重放 / 未绑定有效 user#turn-<id> / 假冒 Legacy / 缺失 turns.jsonl (Fail-Closed)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const c06Crypto = require('./c06_crypto');

const ROOT = process.env.C06_ROOT || path.resolve(__dirname, '..');
const CATALOG = path.join(ROOT, 'references', 'dense_catalog.md');

const RC = {
  OK: 0,
  MISSING: 10,
  ASSET: 11,
  SCOPE: 12,
  SCHEMA: 13,
  PROVENANCE: 14
};

const QS = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5'];

// 白名单：允许跨页面共享的合规全局资产 (与 gate-check.js 严格完全一致)
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

function sha256(buf) {
  return 'sha256:' + crypto.createHash('sha256').update(buf).digest('hex');
}

function loadCatalog(catalogPath) {
  const p = catalogPath || CATALOG;
  const content = read(p);
  const items = new Set();
  const m = content.matchAll(/\|\s*(?:\*\*|`)?([A-Z][0-9]{2}(?:-[A-Za-z0-9]+)?)(?:\*\*|`)?\s*\|/g);
  for (const match of m) {
    items.add(match[1]);
  }
  return {
    raw: content,
    hash: sha256(content),
    items
  };
}

function findStateFile(explicitPath) {
  if (explicitPath) return path.resolve(explicitPath);
  const candidates = [
    path.join(process.cwd(), '.c06', 'wizard_state.json'),
    path.join(process.cwd(), 'wizard_state.json'),
    path.join(__dirname, '..', 'wizard_state.json'),
    path.join(__dirname, '..', '..', '..', '.c06', 'wizard_state.json')
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

function findTurnsFile(statePath) {
  if (statePath) {
    const dir = path.dirname(path.resolve(statePath));
    const cand = path.join(dir, 'turns.jsonl');
    if (fs.existsSync(cand)) return cand;
  }
  const local = path.join(process.cwd(), '.c06', 'turns.jsonl');
  if (fs.existsSync(local)) return local;
  return null;
}

function loadUserTurns(statePath) {
  const p = findTurnsFile(statePath);
  if (!p) return null; // Fail-Closed: 缺失返回 null
  const turns = new Set();
  try {
    for (const line of read(p).split(/\r?\n/).filter(Boolean)) {
      try {
        const item = JSON.parse(line);
        const tid = item.id != null ? item.id : item.turn;
        const role = (item.role || item.actor || '').toLowerCase();
        if (tid != null && role === 'user') {
          turns.add(parseInt(tid, 10));
        }
      } catch (e) {}
    }
  } catch (_) {
    return null;
  }
  return turns;
}

function getPageClearance(page) {
  if (!page || typeof page !== 'object') return {};
  if (page.clearance && typeof page.clearance === 'object') return page.clearance;
  return page;
}

function normalizeCell(cell) {
  if (!cell || typeof cell !== 'object') return null;
  const rawStatus = (cell.status || '').trim();
  const status = rawStatus.toLowerCase();
  let confirmed_by = null;
  if (typeof cell.confirmed_by === 'string' && cell.confirmed_by.trim()) {
    confirmed_by = cell.confirmed_by.trim();
  } else if (cell.auth && cell.auth.turn != null) {
    confirmed_by = `user#turn-${cell.auth.turn}`;
  }

  let evidence = [];
  if (Array.isArray(cell.evidence) && cell.evidence.length > 0) {
    evidence = cell.evidence;
  } else if (cell.auth && cell.auth.subject_sha) {
    evidence = [cell.auth.subject_sha];
  }

  return {
    ...cell,
    rawStatus,
    status,
    confirmed_by,
    evidence
  };
}

function evaluatePage(pid, pageData, catalog, evidenceOwner, userTurns, options = {}) {
  const issues = [];
  const pendingNonces = [];
  const clearance = getPageClearance(pageData);

  // 页面级 status 校验 (Fail-Closed)
  if (pageData && pageData.status) {
    const pStatus = String(pageData.status).toLowerCase();
    if (!['pass', 'waived', 'na'].includes(pStatus)) {
      issues.push({ code: RC.SCHEMA, q: 'PAGE', why: `页面 ${pid} 状态非法: "${pageData.status}"` });
    }
  }

  for (const q of QS) {
    const rawCell = clearance[q];
    if (!rawCell) {
      issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 维度缺失未填写` });
      continue;
    }

    const cell = normalizeCell(rawCell);
    if (!cell) {
      issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 格式非法` });
      continue;
    }

    // 状态枚举校验 (大小写兼容)
    const validStatuses = ['pass', 'waived', 'na', 'pending'];
    if (!validStatuses.includes(cell.status)) {
      issues.push({ code: RC.SCHEMA, q, why: `${pid}/${q} 状态非法: "${cell.rawStatus}"` });
      continue;
    }

    // pending 状态 Fail-Closed 拦截 (与 gate-check.js 完全对齐)
    if (cell.status === 'pending') {
      issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 处于 pending 状态，未就绪 (Fail-Closed 拦截)` });
      continue;
    }

    // strict 严格模式校验：绝不允许任何 waived 或 na
    if (options.strict && (cell.status === 'waived' || cell.status === 'na')) {
      issues.push({ code: RC.MISSING, q, why: `[STRICT] ${pid}/${q} 处于严格模式，不允许 ${cell.status} 状态` });
    }

    // Q1 门禁红线：几何拓扑绝对不可豁免
    if (q === 'Q1') {
      if (cell.status === 'waived') {
        issues.push({ code: RC.MISSING, q, why: `${pid}/Q1 违反门禁红线：核心几何拓扑绝不允许 waived 豁免` });
      }
      if (cell.status === 'na') {
        issues.push({ code: RC.MISSING, q, why: `${pid}/Q1 违反门禁红线：核心几何拓扑绝不允许标为 na` });
      }
    }

    // WAIVED 校验
    if (cell.status === 'waived') {
      if (q === 'Q1') {
        // 已拦截
      } else {
        if (!cell.reason || typeof cell.reason !== 'string' || !cell.reason.trim()) {
          issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 标为 waived 但未填写豁免理由` });
        }
        if (!cell.approved_by || typeof cell.approved_by !== 'string' || !cell.approved_by.trim()) {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 标为 waived 但缺少批准人 approved_by` });
        }
      }
    }

    // NA 校验
    if (cell.status === 'na') {
      if (!cell.reason || typeof cell.reason !== 'string' || !cell.reason.trim()) {
        issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 标为 na 但未填写合理理由` });
      }
      if (q === 'Q2' || q === 'Q3') {
        issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 违反门禁红线：核心交互页 Q2数据与Q3控件绝不允许 waived 或 na` });
      }
    }

    // PASS 门禁要求
    if (cell.status === 'pass') {
      if (!cell.evidence || !cell.evidence.length) {
        issues.push({ code: RC.MISSING, q, why: `${pid}/${q} 标为 PASS，但证据列表为空` });
      }

      // 出处防伪校验 (必须严格绑定有效 user#turn-<id>)
      if (typeof cell.confirmed_by !== 'string') {
        issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 出处 confirmed_by 缺失或无效` });
      } else {
        const by = cell.confirmed_by.trim();
        const m = by.match(/^(?:user#turn-([1-9]\d*)|User Turn #([1-9]\d*))$/i);
        if (!m) {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 出处格式无效、前导零或自签 (confirmed_by: "${by}")，必须严格匹配 user#turn-<id> 或 User Turn #<id>` });
        } else {
          const tid = parseInt(m[1] || m[2], 10);
          if (isNaN(tid) || tid < 1 || tid > 100) {
            issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 轮次号超出真实有效范围 1~100 (turn: ${tid})` });
          } else if (userTurns === null) {
            // Fail-Closed: 缺失 turns.jsonl 直接拦截
            issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 缺失 .c06/turns.jsonl 用户出处账本 (Fail-Closed 拒绝)` });
          } else if (!userTurns.has(tid)) {
            issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 轮次 user#turn-${tid} 未在 .c06/turns.jsonl 用户账本中登记 (伪造出处)` });
          }
        }
      }

      // 用户信封验签与 Nonce 强制核验 (PASS 单元格强制要求 auth)
      if (!cell.auth || typeof cell.auth !== 'object') {
        issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 标为 PASS，但缺少强制的 user auth 签名信封 (Fail-Closed 拦截)` });
      } else {
        const auth = cell.auth;
        if (auth.action !== 'CELL_PASS') {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} PASS 单元格签名信封 action 必须为 CELL_PASS (当前: ${auth.action})` });
        }
        const expectedTurn = parseInt((cell.confirmed_by || '').replace(/[^0-9]/g, ''), 10);
        if (!isNaN(expectedTurn) && auth.turn !== expectedTurn) {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 用户信封 turn (${auth.turn}) 与出处 confirmed_by 中的 turn (${expectedTurn}) 不一致` });
        }
        if (c06Crypto.isKeyRevoked(auth.key_id)) {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 签名私钥已被撤销: ${auth.key_id}` });
        }
        if (c06Crypto.isNonceConsumed(auth.nonce)) {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 签名 Nonce 已被消费 (重放拦截): ${auth.nonce}` });
        }
        if (!auth.signature) {
          issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 用户信封缺少 signature 签名字段` });
        } else {
          const authPayload = { ...auth };
          delete authPayload.signature;
          if (!c06Crypto.verifyEd25519(authPayload, auth.signature, 'user')) {
            issues.push({ code: RC.PROVENANCE, q, why: `${pid}/${q} 用户信封 Ed25519 签名校验失败` });
          } else {
            pendingNonces.push({ role: 'user', nonce: auth.nonce, iat: auth.iat });
          }
        }
      }

      // Q5 容器与品牌双覆盖校验 (必须显式声明 assets，非空且至少同时包含一个 O 与一个 D)
      if (q === 'Q5') {
        if (!cell.assets || !Array.isArray(cell.assets) || cell.assets.length === 0) {
          issues.push({ code: RC.MISSING, q, why: `${pid}/Q5 标为 PASS 必须声明 assets (至少包含一个容器形态 O 与一个品牌 Token D)` });
        } else {
          const hasO = cell.assets.some(a => a.startsWith('O'));
          const hasD = cell.assets.some(a => a.startsWith('D'));
          if (!hasO || !hasD) {
            issues.push({ code: RC.MISSING, q, why: `${pid}/Q5 必须同时覆盖容器形态 (O) 与品牌 Token (D)` });
          }
        }
      }

      // 资产与证据存在性及跨页唯一性
      if (cell.evidence && Array.isArray(cell.evidence)) {
        for (const ev of cell.evidence) {
          if (!SHARED_EVIDENCE.has(ev)) {
            if (evidenceOwner.has(ev) && evidenceOwner.get(ev) !== pid) {
              issues.push({
                code: RC.SCOPE,
                q,
                why: `${pid}/${q} 证据 [${ev}] 与已登记页面 ${evidenceOwner.get(ev)} 冲突 (证据跨页复用拦截)`
              });
            } else {
              evidenceOwner.set(ev, pid);
            }
          }
        }
      }

      if (cell.assets && Array.isArray(cell.assets)) {
        for (const ast of cell.assets) {
          if (!catalog.items.has(ast)) {
            issues.push({
              code: RC.ASSET,
              q,
              why: `${pid}/${q} 声明了非法或未登记资产 [${ast}] (非 dense_catalog 72项标准资产)`
            });
          }
        }
      }
    }
  }

  // 仅在无全局批处理接管时提交，否则返回 pendingNonces 供全局单写者事务使用
  if (options.collector && Array.isArray(options.collector)) {
    options.collector.push(...pendingNonces);
  } else if (issues.length === 0 && !options.noRecordNonce && pendingNonces.length > 0) {
    c06Crypto.atomicBatchRecordNonces(pendingNonces);
  }
  return issues;
}

function selfTest() {
  console.log('--- clearance.js v3.9.0-Industrial 自检运行 ---');
  const cat = loadCatalog();
  const dummyTurns = new Set([1, 2, 3, 4, 5, 10, 11]);

  let passCount = 0;
  function assert(name, cond) {
    if (!cond) {
      console.error(`  FAIL: ${name}`);
      process.exit(2);
    }
    console.log(`  PASS: ${name}`);
    passCount++;
  }

  // 构造具有真实 Ed25519 签名的测试用例
  let userPrivKey = null;
  const vaultPath = path.join(os.homedir(), '.c06-vault', 'user.pem');
  if (fs.existsSync(vaultPath)) {
    try {
      userPrivKey = crypto.createPrivateKey(fs.readFileSync(vaultPath, 'utf8'));
    } catch (_) {}
  }

  function makeTestAuth(turn, nonceUuid) {
    const payload = {
      action: 'CELL_PASS',
      turn,
      subject_sha: 'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      nonce: nonceUuid,
      iat: 1794954180,
      exp: 1795213380,
      key_id: 'ed25519:user:v1'
    };
    if (userPrivKey) {
      const msg = Buffer.from(c06Crypto.canonicalJCS(payload), 'utf8');
      const sig = 'sig:ed25519:' + crypto.sign(null, msg, userPrivKey).toString('hex');
      return { ...payload, signature: sig };
    }
    return { ...payload, signature: 'sig:ed25519:0000000000000000000000000000000000000000000000000000000000000000' };
  }

  // 1. 合法 PASS (符合 Schema：页面状态 pass 且单元格均含有效 auth 签名信封)
  const validP01 = {
    status: 'pass',
    Q1: { status: 'PASS', evidence: ['E1'], confirmed_by: 'user#turn-1', auth: makeTestAuth(1, 'a1111111-1111-4111-8111-111111111111') },
    Q2: { status: 'PASS', evidence: ['E2'], confirmed_by: 'user#turn-2', auth: makeTestAuth(2, 'a2222222-2222-4222-8222-222222222222') },
    Q3: { status: 'PASS', evidence: ['E3'], confirmed_by: 'user#turn-3', auth: makeTestAuth(3, 'a3333333-3333-4333-8333-333333333333') },
    Q4: { status: 'PASS', evidence: ['E4'], confirmed_by: 'user#turn-4', auth: makeTestAuth(4, 'a4444444-4444-4444-8444-444444444444') },
    Q5: { status: 'PASS', evidence: ['E5'], confirmed_by: 'user#turn-5', assets: ['O01', 'D01'], auth: makeTestAuth(5, 'a5555555-5555-4555-8555-555555555555') }
  };
  const iss1 = evaluatePage('P01', validP01, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('合规页面全部 PASS 退出码 0', iss1.length === 0);

  // 2. Q1 豁免拦截 (Exit 10)
  const badQ1 = { ...validP01, Q1: { status: 'waived', reason: 'reason', approved_by: 'user' } };
  const iss2 = evaluatePage('P01', badQ1, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('Q1 几何红线不可豁免 (Exit 10)', iss2.some(i => i.code === RC.MISSING && i.q === 'Q1'));

  // 3. 非法资产 (Exit 11)
  const badAsset = { ...validP01, Q5: { status: 'PASS', evidence: ['E5'], confirmed_by: 'user#turn-5', assets: ['O01', 'D99'], auth: makeTestAuth(5, 'b5555555-5555-4555-8555-555555555555') } };
  const iss3 = evaluatePage('P01', badAsset, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('非法资产 D99 拦截 (Exit 11)', iss3.some(i => i.code === RC.ASSET));

  // 4. 证据跨页复用 (Exit 12)
  const sharedOwner = new Map([['E1', 'P01']]);
  const iss4 = evaluatePage('P02', validP01, cat, sharedOwner, dummyTurns, { noRecordNonce: true });
  assert('证据 E1 跨页复用拦截 (Exit 12)', iss4.some(i => i.code === RC.SCOPE));

  // 5. 出处前导零伪造 (Exit 14)
  const badTurn = { ...validP01, Q1: { status: 'PASS', evidence: ['E1'], confirmed_by: 'user#turn-01', auth: makeTestAuth(1, 'c1111111-1111-4111-8111-111111111111') } };
  const iss5 = evaluatePage('P01', badTurn, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('出处带前导零拦截 (Exit 14)', iss5.some(i => i.code === RC.PROVENANCE));

  // 6. 出处未在 turns.jsonl 登记 (Exit 14)
  const unregTurn = { ...validP01, Q1: { status: 'PASS', evidence: ['E1'], confirmed_by: 'user#turn-99', auth: makeTestAuth(99, 'c9999999-9999-4999-8999-999999999999') } };
  const iss6 = evaluatePage('P01', unregTurn, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('未登记出处 turn-99 拦截 (Exit 14)', iss6.some(i => i.code === RC.PROVENANCE));

  // 7. Q5 缺失品牌 Token D (Exit 10)
  const missD = { ...validP01, Q5: { status: 'PASS', evidence: ['E5'], confirmed_by: 'user#turn-5', assets: ['O01'], auth: makeTestAuth(5, 'd5555555-5555-4555-8555-555555555555') } };
  const iss7 = evaluatePage('P01', missD, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('Q5 仅单维资产缺少 D 拦截 (Exit 10)', iss7.some(i => i.code === RC.MISSING && i.q === 'Q5'));

  // 8. Q5 缺失容器 O (Exit 10)
  const missO = { ...validP01, Q5: { status: 'PASS', evidence: ['E5'], confirmed_by: 'user#turn-5', assets: ['D01'], auth: makeTestAuth(5, 'e5555555-5555-4555-8555-555555555555') } };
  const iss8 = evaluatePage('P01', missO, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('Q5 仅单维资产缺少 O 拦截 (Exit 10)', iss8.some(i => i.code === RC.MISSING && i.q === 'Q5'));

  // 9. Fail-Closed: 缺失 turns.jsonl 时出处拦截 (Exit 14)
  const iss9 = evaluatePage('P01', validP01, cat, new Map(), null);
  assert('缺失 turns.jsonl 时出处校验 Fail-Closed 拦截 (Exit 14)', iss9.some(i => i.code === RC.PROVENANCE));

  // 10. 用户信封伪造签名拦截 (Exit 14)
  const forgedAuthPage = {
    ...validP01,
    Q1: {
      status: 'PASS',
      evidence: ['E1'],
      confirmed_by: 'user#turn-1',
      auth: {
        action: 'CLEARANCE_APPROVE',
        turn: 1,
        subject_sha: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
        nonce: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
        key_id: 'ed25519:user:v1',
        signature: 'sig:ed25519:00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
      }
    }
  };
  const iss10 = evaluatePage('P01', forgedAuthPage, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('伪造用户 Ed25519 签名信封拦截 (Exit 14)', iss10.some(i => i.code === RC.PROVENANCE));

  // 11. pending 状态 Fail-Closed 拦截 (Exit 10)
  const pendingPage = {
    ...validP01,
    Q1: { status: 'pending', evidence: ['E1'], confirmed_by: 'user#turn-1' }
  };
  const iss11 = evaluatePage('P01', pendingPage, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('pending 状态 Fail-Closed 拦截 (Exit 10)', iss11.some(i => i.code === RC.MISSING && i.q === 'Q1'));

  // 12. PASS 单元格缺失 auth 签名信封拦截 (Exit 14)
  const noAuthPage = {
    ...validP01,
    Q1: { status: 'PASS', evidence: ['E1'], confirmed_by: 'user#turn-1' } // 无 auth
  };
  const iss12 = evaluatePage('P01', noAuthPage, cat, new Map(), dummyTurns, { noRecordNonce: true });
  assert('PASS 缺少 auth 签名信封 Fail-Closed 拦截 (Exit 14)', iss12.some(i => i.code === RC.PROVENANCE && i.q === 'Q1'));

  // 13. strict 严格模式拦截 waived (Exit 10)
  const waivedStrict = {
    ...validP01,
    Q2: { status: 'waived', reason: '跳过', approved_by: 'user' }
  };
  const iss13 = evaluatePage('P01', waivedStrict, cat, new Map(), dummyTurns, { strict: true });
  assert('strict 严格模式拦截 waived (Exit 10)', iss13.some(i => i.code === RC.MISSING && i.q === 'Q2'));

  console.log(`自检完成: 全部 ${passCount} 项测试通过 (Exit 0)`);
  return 0;
}

function runCLI() {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) {
    process.exit(selfTest());
  }

  let statePath = null;
  let targetPage = null;
  let checkAll = false;
  let strict = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--state' && args[i + 1]) {
      statePath = args[++i];
    } else if (args[i] === '--all') {
      checkAll = true;
    } else if (args[i] === '--strict') {
      strict = true;
    } else if (!args[i].startsWith('--')) {
      targetPage = args[i];
    }
  }

  const realStatePath = findStateFile(statePath);
  if (!realStatePath || !fs.existsSync(realStatePath)) {
    console.error(`[GATE] 未找到 wizard_state.json (Exit 13): ${realStatePath || statePath}`);
    process.exit(RC.SCHEMA);
  }

  let state;
  try {
    state = JSON.parse(read(realStatePath));
  } catch (err) {
    console.error(`[GATE] 解析 wizard_state.json 失败 (Exit 13):`, err.message);
    process.exit(RC.SCHEMA);
  }

  const catalog = loadCatalog();

  // 校验 catalog_hash
  if (state.catalog_hash && state.catalog_hash !== catalog.hash) {
    console.error(`[GATE] catalog_hash 与当前 dense_catalog.md 不匹配 (Exit 13): 状态中 ${state.catalog_hash} vs 当前 ${catalog.hash}`);
    process.exit(RC.SCHEMA);
  }

  const userTurns = loadUserTurns(realStatePath);
  const evidenceOwner = new Map();

  // 提取页面集
  let pages = state.pages;
  if (!pages && state.tasks) {
    const activeId = state.active_task_id;
    if (activeId && state.tasks[activeId] && state.tasks[activeId].pages) {
      pages = state.tasks[activeId].pages;
    } else {
      for (const t of Object.values(state.tasks)) {
        if (t.pages && typeof t.pages === 'object' && Object.keys(t.pages).length > 0) {
          pages = t.pages;
          break;
        }
      }
    }
  }

  if (!pages || typeof pages !== 'object' || Object.keys(pages).length === 0) {
    console.error(`[GATE] 状态中页面集 pages 为空 (Exit 10)`);
    process.exit(RC.MISSING);
  }

  const allIssues = [];
  const allPendingNonces = [];
  if (checkAll) {
    for (const [pid, pdata] of Object.entries(pages)) {
      const issues = evaluatePage(pid, pdata, catalog, evidenceOwner, userTurns, { strict, collector: allPendingNonces });
      allIssues.push(...issues);
    }
  } else if (targetPage) {
    if (!pages[targetPage]) {
      console.error(`[GATE] 未找到指定页面 ${targetPage} (Exit 10)`);
      process.exit(RC.MISSING);
    }
    const issues = evaluatePage(targetPage, pages[targetPage], catalog, evidenceOwner, userTurns, { strict, collector: allPendingNonces });
    allIssues.push(...issues);
  } else {
    console.error('用法: node clearance.js <page_id> [--strict] [--state <path>] 或 node clearance.js --all');
    process.exit(RC.MISSING);
  }

  // 关键：全量页面 100% 校验通过后，仅在显式传入 --commit-nonces 时单一全局事务原子提交所有页面的 Nonce (满足 Gate 零磁盘写入原则)
  if (process.argv.includes('--commit-nonces') && allIssues.length === 0 && allPendingNonces.length > 0) {
    c06Crypto.atomicBatchRecordNonces(allPendingNonces);
  }

  if (allIssues.length > 0) {
    console.error(`[GATE] 规格核销门禁拦截 (共 ${allIssues.length} 项违背):`);
    for (const issue of allIssues) {
      console.error(`  - [Exit ${issue.code}] ${issue.why}`);
    }
    // 返回最严重的退出码
    const priority = [RC.PROVENANCE, RC.SCHEMA, RC.SCOPE, RC.ASSET, RC.MISSING];
    for (const p of priority) {
      if (allIssues.some(i => i.code === p)) {
        process.exit(p);
      }
    }
    process.exit(RC.MISSING);
  }

  console.log(`[GATE] 规格核销全部通过 (Exit 0)`);
  process.exit(RC.OK);
}

if (require.main === module) {
  runCLI();
}

module.exports = {
  RC,
  QS,
  SHARED_EVIDENCE,
  loadCatalog,
  loadUserTurns,
  evaluatePage,
  selfTest
};
