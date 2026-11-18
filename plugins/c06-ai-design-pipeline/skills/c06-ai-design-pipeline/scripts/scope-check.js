#!/usr/bin/env node
/**
 * scope-check.js — C06 代码改动范围物理硬阻断门禁探针 (v3.9.0-Industrial)
 *
 * 核心契约与退出码 (严格对齐文档 Exit Code 表):
 *   0  = OK (全部门禁断言通过)
 *   20 = OUT_OF_SCOPE / DIRTY_WORKTREE (改动超出 owned_paths 白名单或工作区脏/未受控产物/缺失参数/参数覆盖)
 *   21 = FORBIDDEN_ZONE (触碰绝对禁区或 L0 快车道敏感鉴权词拦截 / 纯删除非零增行)
 *   22 = PATH_ESCAPE / STATIC_STYLE_VIOLATION (词法逃逸、非法路径、L0-B非样式扩展名或增行>5)
 *   23 = UNAUTHORIZED_DELETION / INVALID_RECEIPT (未授权删除或回执非法)
 *   24 = SIGNATURE_INVALID / EXPIRED (密码学验签失败或回执超时)
 *   25 = AST_PROOF_FAIL / EXECUTION_TIMEOUT (AST 不可达证明失败或超时)
 *   33 = STALE_LEASE / INTEGRITY_TAMPERED (租约过期或信任根被篡改)
 *   34 = STALE_MAP (实体地图过期或不匹配)
 *
 * 自检失败退出码：2 (与 gate-check 契约对齐)
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const crypto = require('crypto');
const c06Crypto = require('./c06_crypto');

const RC = {
  OK: 0,
  OUT_OF_SCOPE_OR_DIRTY: 20,
  FORBIDDEN_ZONE: 21,
  PATH_ESCAPE: 22,
  UNAUTHORIZED_DELETION: 23,
  SIGNATURE_INVALID: 24,
  AST_PROOF_FAIL_OR_TIMEOUT: 25,
  STALE_LEASE_OR_INTEGRITY: 33,
  STALE_MAP: 34
};

// 完整 33 项 L0 快车道硬编码绝对禁区清单 (严格对齐文档 §6.2)
const CORE_FORBIDDEN_FAST_TRACK = [
  "**/package.json",
  "**/pnpm-lock.yaml",
  "**/package-lock.json",
  "**/yarn.lock",
  "**/scripts/**",
  "**/.github/**",
  "**/src/core/**",
  "**/src/services/**",
  "**/src/router/**",
  "**/src/routes/**",
  "**/src/store/**",
  "**/src/state/**",
  "**/src/common/**",
  "**/src/shared/**",
  "**/src/lib/**",
  "**/src/hooks/**",
  "**/src/utils/**",
  "**/src/auth/**",
  "**/src/api/**",
  "**/tokens.css",
  "**/*.config.*",
  "**/.c06/**",
  "**/.c06-gate-vault/**",
  "**/tsconfig*.json",
  "**/.env*",
  "**/Design_Spec*.md",
  "**/specs/**",
  "**/spec.md",
  "**/.git/**",
  "**/.gitignore",
  "**/.gitattributes",
  "**/*.pem",
  "**/*.key"
];

// 22 个核心安全与鉴权敏感关键字 (大小写不敏感单词边界匹配)
const SENSITIVE_AUTH_KEYWORDS = [
  'auth', 'token', 'secret', 'password', 'permission',
  'credential', 'jwt', 'session', 'rbac', 'acl',
  'crypto', 'encrypt', 'decrypt', 'sign', 'verify',
  'private_key', 'api_key', 'bearer', 'oauth', 'cors',
  'csrf', 'bypass'
];

// L0-B 静态微调允许的文件扩展名白名单 (严禁 .ts, .tsx, .js, .jsx, .html 等可执行代码)
const L0_B_ALLOWED_EXTENSIONS = new Set([
  '.css', '.scss', '.json', '.svg', '.md'
]);

function normalizePath(p) {
  return p.replace(/\\/g, '/').toLowerCase().trim();
}

/**
 * 递归 Glob 匹配器，支持前段、中段、后段 ** 以及单段 *
 */
function matchGlob(filePath, pattern) {
  const normFile = normalizePath(filePath);
  const normPat = normalizePath(pattern);
  if (normPat === normFile) return true;

  let s = normPat.replace(/[\^$+?.()|[\]{}\\]/g, '\\$&');
  s = s.replace(/\*\*\//g, '__GLOBSTAR_SLASH__');
  s = s.replace(/\/\*\*/g, '__SLASH_GLOBSTAR__');
  s = s.replace(/\*\*/g, '__GLOBSTAR__');
  s = s.replace(/\*/g, '__SINGLESTAR__');

  s = s.replace(/__GLOBSTAR_SLASH__/g, '(?:.*/)?');
  s = s.replace(/__SLASH_GLOBSTAR__/g, '(?:/.*)?');
  s = s.replace(/__GLOBSTAR__/g, '.*');
  s = s.replace(/__SINGLESTAR__/g, '[^/]*');

  const re = new RegExp(`^${s}$`, 'i');
  return re.test(normFile);
}

/**
 * 深度词法与物理路径安全性检查 (Windows 尾随点/空格、ADS冒号、保留设备名、硬链接与Realpath)
 */
function assertPathLexicalSafety(rawPath, cwd) {
  // 1. Windows 尾随点与空格检查 (任何路径段以点或空格结尾/开头)
  const rawSegments = rawPath.replace(/\\/g, '/').split('/');
  for (const seg of rawSegments) {
    if (!seg) continue;
    if (seg.endsWith('.') || seg.endsWith(' ') || seg.startsWith(' ')) {
      return false;
    }
  }

  const norm = normalizePath(rawPath);

  // 2. 拦截 Alternate Data Streams (ADS) 冒号及控制字符
  if (rawPath.includes(':') || /[\x00-\x1f\x7f]/.test(rawPath)) {
    return false;
  }

  // 3. 拦截 Windows 保留设备名 (CON, PRN, AUX, NUL, COM1..9, LPT1..9)
  const baseName = path.basename(norm);
  const pureName = baseName.split('.')[0];
  const reserved = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;
  if (reserved.test(pureName)) {
    return false;
  }

  // 4. 物理文件硬链接与 Realpath 穿透核验 (若文件存在)
  const abs = path.resolve(cwd, rawPath);
  if (fs.existsSync(abs)) {
    try {
      const stat = fs.lstatSync(abs);
      if (stat.isSymbolicLink()) {
        return false;
      }
      if (stat.nlink > 1) {
        // 硬链接绕过防御
        return false;
      }
      const real = fs.realpathSync(abs);
      if (normalizePath(real) !== normalizePath(abs)) {
        return false;
      }
    } catch (_) {
      return false;
    }
  }

  return true;
}

/**
 * 工作区干净状态断言
 */
function assertCleanWorktree(cwd) {
  try {
    const status = execFileSync('git', ['--no-optional-locks', 'status', '--porcelain'], { cwd, encoding: 'utf8' }).trim();
    if (status.length > 0) {
      console.error('[GATE] 工作区存在未提交或未受控改动 (Fail-Closed Exit 20):\n' + status);
      return false;
    }
    return true;
  } catch (err) {
    console.error('[GATE] 执行 git status 失败 (Exit 20):', err.message);
    return false;
  }
}

/**
 * 断言 Commit 拓扑合法性
 */
function assertCommitOid(baseSha, commitOid, cwd) {
  try {
    execFileSync('git', ['--no-optional-locks', 'merge-base', '--is-ancestor', baseSha, commitOid], { cwd, stdio: 'ignore' });
    return true;
  } catch (err) {
    console.error(`[GATE] Commit 祖先关系校验失败: ${baseSha} 不是 ${commitOid} 的祖先 (Exit 33)`);
    return false;
  }
}

/**
 * 获取精确改动文件列表及状态
 */
function getChangedFiles(baseSha, commitOid, cwd) {
  try {
    const raw = execFileSync('git', ['--no-optional-locks', 'diff', '--name-status', '-M', baseSha, commitOid], { cwd, encoding: 'utf8' });
    const changes = [];
    const lines = raw.split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      const parts = line.split('\t');
      const status = parts[0];
      if (status.startsWith('R') || status.startsWith('C')) {
        changes.push({ status, oldPath: parts[1], path: parts[2] });
      } else {
        changes.push({ status, path: parts[1] });
      }
    }
    return { ok: true, changes };
  } catch (err) {
    console.error('[GATE] git diff --name-status 失败 (Exit 20):', err.message);
    return { ok: false, error: err };
  }
}

/**
 * L0 快车道度量、敏感词与扩展名断言
 */
function assertL0MetricsAndKeywords(baseSha, commitOid, lane, cwd, taskPackage) {
  // 1. git diff --numstat
  let linesAdded = 0;
  let linesDeleted = 0;
  let changedFilesCount = 0;
  try {
    const numstat = execFileSync('git', ['--no-optional-locks', 'diff', '--numstat', baseSha, commitOid], { cwd, encoding: 'utf8' });
    const lines = numstat.split(/\r?\n/).filter(Boolean);
    changedFilesCount = lines.length;
    for (const l of lines) {
      const [add, del] = l.split('\t');
      linesAdded += parseInt(add, 10) || 0;
      linesDeleted += parseInt(del, 10) || 0;
    }
  } catch (err) {
    return { pass: false, code: RC.OUT_OF_SCOPE_OR_DIRTY, reason: 'git diff --numstat 失败: ' + err.message };
  }

  // L0-A: 纯删除轨
  if (lane === 'L0-A') {
    if (linesAdded > 0) {
      return { pass: false, code: RC.FORBIDDEN_ZONE, reason: `L0-A 纯删除轨严禁新增任何代码行 (lines_added: ${linesAdded} > 0, Exit 21)` };
    }
    if (linesDeleted === 0) {
      return { pass: false, code: RC.FORBIDDEN_ZONE, reason: `L0-A 纯删除轨必须包含实际删除代码行 (lines_deleted: 0, Exit 21)` };
    }

    // 检查 taskPackage 中 deletion_proof
    if (taskPackage) {
      if (!taskPackage.deletion_proof || typeof taskPackage.deletion_proof !== 'object') {
        return { pass: false, code: RC.AST_PROOF_FAIL_OR_TIMEOUT, reason: 'L0-A 任务必须包含 deletion_proof 结构证明 (Exit 25)' };
      }
      const proof = taskPackage.deletion_proof;
      if (proof.incoming_refs !== 0 || proof.entrypoint_refs !== 0) {
        return { pass: false, code: RC.AST_PROOF_FAIL_OR_TIMEOUT, reason: `L0-A deletion_proof 存在未解依赖 (incoming_refs: ${proof.incoming_refs}, Exit 25)` };
      }

      // 验签 deletion_proof (StaticAnalyzer 角色 Ed25519)
      const proofPayload = { ...proof };
      delete proofPayload.signature;
      if (!c06Crypto.verifyEd25519(proofPayload, proof.signature, 'static_analyzer', cwd)) {
        return { pass: false, code: RC.SIGNATURE_INVALID, reason: 'L0-A deletion_proof StaticAnalyzer 签名校验失败 (Exit 24)' };
      }

      // 验证工具哈希白名单 (Fail-Closed: 必须存在且签名有效)
      const toolsJsonPath = path.join(cwd, '.c06', 'pins', 'static_analyzer_tools.json');
      if (!fs.existsSync(toolsJsonPath)) {
        return { pass: false, code: RC.AST_PROOF_FAIL_OR_TIMEOUT, reason: '缺少静态分析工具白名单 static_analyzer_tools.json (Exit 25)' };
      }
      try {
        const toolsData = JSON.parse(fs.readFileSync(toolsJsonPath, 'utf8'));
        const toolsPayload = { ...toolsData };
        delete toolsPayload.signature;
        if (!c06Crypto.verifyEd25519(toolsPayload, toolsData.signature, 'commander', cwd) && !c06Crypto.verifyEd25519(toolsPayload, toolsData.signature, 'static_analyzer', cwd)) {
          return { pass: false, code: RC.SIGNATURE_INVALID, reason: 'static_analyzer_tools.json Commander 签名校验失败 (Exit 24)' };
        }
        if (Array.isArray(toolsData.allowed_tool_hashes)) {
          const toolSha = proof.tool_sha256;
          if (!toolsData.allowed_tool_hashes.includes(toolSha)) {
            return { pass: false, code: RC.AST_PROOF_FAIL_OR_TIMEOUT, reason: `L0-A 工具哈希 ${toolSha} 不在 static_analyzer_tools 白名单中 (Exit 25)` };
          }
        } else {
          return { pass: false, code: RC.AST_PROOF_FAIL_OR_TIMEOUT, reason: 'static_analyzer_tools.json 格式非法 (Exit 25)' };
        }
      } catch (err) {
        return { pass: false, code: RC.AST_PROOF_FAIL_OR_TIMEOUT, reason: '解析 static_analyzer_tools.json 异常: ' + err.message };
      }
    }
  }

  // L0-B: 静态微调轨
  if (lane === 'L0-B') {
    if (changedFilesCount !== 1) {
      return { pass: false, code: RC.PATH_ESCAPE, reason: `L0-B 静态微调仅允许单文件改动 (当前改动文件数: ${changedFilesCount}, Exit 22)` };
    }
    if (linesAdded > 5) {
      return { pass: false, code: RC.PATH_ESCAPE, reason: `L0-B 静态微调新增行数严禁超过 5 行 (当前: ${linesAdded}, Exit 22)` };
    }

    // 检查改动文件扩展名 (白名单机制)
    const diffRes = getChangedFiles(baseSha, commitOid, cwd);
    if (diffRes.ok && diffRes.changes.length > 0) {
      const changedFile = diffRes.changes[0].path;
      const ext = path.extname(changedFile).toLowerCase();
      if (!L0_B_ALLOWED_EXTENSIONS.has(ext)) {
        return { pass: false, code: RC.PATH_ESCAPE, reason: `L0-B 静态微调仅允许修改样式/数据文件 (${Array.from(L0_B_ALLOWED_EXTENSIONS).join(', ')})，禁止可执行代码文件: ${changedFile} (Exit 22)` };
      }
    }

    // 租约有效性核验 (强绑定任务包、文件路径与模式)
    if (taskPackage) {
      const leasePath = path.join(cwd, '.c06', 'leases', `${taskPackage.task_id}.json`);
      if (!fs.existsSync(leasePath)) {
        return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: `L0-B 任务缺失有效租约凭证: ${leasePath} (Exit 33)` };
      }
      try {
        const lease = JSON.parse(fs.readFileSync(leasePath, 'utf8'));
        const leasePayload = { ...lease };
        delete leasePayload.signature;
        if (!c06Crypto.verifyEd25519(leasePayload, lease.signature, 'commander', cwd)) {
          return { pass: false, code: RC.SIGNATURE_INVALID, reason: 'L0-B 租约凭证 Ed25519 签名无效 (Exit 24)' };
        }
        let isTaskCompleted = false;
        try {
          const st = JSON.parse(fs.readFileSync(path.join(cwd, '.c06', 'wizard_state.json'), 'utf8'));
          if (st.tasks && st.tasks[taskPackage.task_id] && (st.tasks[taskPackage.task_id].phase === 'DONE' || (st.tasks[taskPackage.task_id].gates && st.tasks[taskPackage.task_id].gates.merge))) {
            isTaskCompleted = true;
          }
        } catch (_) {}

        const now = Math.floor(Date.now() / 1000);
        if (!isTaskCompleted && now > lease.expires_at) {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: `L0-B 租约已过期 (now: ${now} > exp: ${lease.expires_at}, Exit 33)` };
        }
        if (lease.domain !== 'c06/l0-lease/v1') {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: 'L0-B 租约 domain 必须为 c06/l0-lease/v1 (Exit 33)' };
        }
        if (lease.task_id !== taskPackage.task_id) {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: `L0-B 租约 task_id (${lease.task_id}) 与任务包 (${taskPackage.task_id}) 不匹配 (Exit 33)` };
        }
        if (taskPackage.lease_id && lease.lease_id !== taskPackage.lease_id) {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: `L0-B 租约 lease_id (${lease.lease_id}) 与任务包 (${taskPackage.lease_id}) 不匹配 (Exit 33)` };
        }
        if (lease.file_path !== taskPackage.owned_paths[0]) {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: `L0-B 租约 file_path (${lease.file_path}) 与任务 owned_paths (${taskPackage.owned_paths[0]}) 不匹配 (Exit 33)` };
        }
        if (lease.allowed_mode !== 'static_style') {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: 'L0-B 租约 allowed_mode 必须为 static_style (Exit 33)' };
        }
        if (lease.base_sha !== baseSha) {
          return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: 'L0-B 租约 base_sha 与当前基线不匹配 (Exit 33)' };
        }
      } catch (err) {
        return { pass: false, code: RC.STALE_LEASE_OR_INTEGRITY, reason: '解析 L0-B 租约失败: ' + err.message };
      }
    }
  }

  // 2. 敏感词扫描 (行级排除 git hunk header 与加号前缀)
  try {
    const diffText = execFileSync('git', ['--no-optional-locks', 'diff', '-U0', baseSha, commitOid], { cwd, encoding: 'utf8' });
    const kwRegex = new RegExp('\\b(' + SENSITIVE_AUTH_KEYWORDS.join('|') + ')\\b', 'i');
    const diffLines = diffText.split(/\r?\n/);
    for (const dl of diffLines) {
      if (dl.startsWith('+++') || dl.startsWith('---') || dl.startsWith('@@')) {
        continue;
      }
      if (dl.startsWith('+') || dl.startsWith('-')) {
        const content = dl.slice(1);
        const match = content.match(kwRegex);
        if (match) {
          return {
            pass: false,
            code: RC.FORBIDDEN_ZONE,
            reason: `L0 快车道改动中检测到安全鉴权敏感关键字 [${match[1]}] (Exit 21):\n${content.trim()}`
          };
        }
      }
    }
  } catch (err) {
    return { pass: false, code: RC.OUT_OF_SCOPE_OR_DIRTY, reason: '扫描敏感词 diff 失败: ' + err.message };
  }

  return { pass: true };
}

/**
 * 禁区与改动范围白名单双重断言 (含 rename 双端断言)
 */
function assertScopeAndForbidden(changedFiles, taskPackage, lane, cwd) {
  const ownedPatterns = taskPackage.owned_paths || [];
  const taskForbiddenPatterns = taskPackage.forbidden_paths || [];

  for (const item of changedFiles) {
    const pathsToCheck = [];
    if (item.oldPath) pathsToCheck.push(item.oldPath);
    if (item.path) pathsToCheck.push(item.path);

    for (const p of pathsToCheck) {
      // 1. 词法与物理路径安全性检查
      if (!assertPathLexicalSafety(p, cwd)) {
        console.error(`[GATE] 路径词法或物理特征异常 (Exit 22): ${p}`);
        return { pass: false, code: RC.PATH_ESCAPE };
      }

      // 2. L0 快车道硬编码 33 项绝对禁区拦截
      if (lane === 'L0-A' || lane === 'L0-B') {
        for (const fpat of CORE_FORBIDDEN_FAST_TRACK) {
          if (matchGlob(p, fpat)) {
            console.error(`[GATE] L0 快车道改动命中核心绝对禁区 (Exit 21): ${p} matches ${fpat}`);
            return { pass: false, code: RC.FORBIDDEN_ZONE };
          }
        }
      }

      // 3. 任务包自定义 forbidden_paths 拦截
      for (const fpat of taskForbiddenPatterns) {
        if (matchGlob(p, fpat)) {
          console.error(`[GATE] 改动命中任务包禁区规则 (Exit 21): ${p} matches ${fpat}`);
          return { pass: false, code: RC.FORBIDDEN_ZONE };
        }
      }

      // 4. owned_paths 白名单覆盖性断言
      let matchedOwned = false;
      for (const opat of ownedPatterns) {
        if (matchGlob(p, opat)) {
          matchedOwned = true;
          break;
        }
      }

      if (!matchedOwned) {
        console.error(`[GATE] 改动路径超出 task_package.owned_paths 授权白名单 (Exit 20): ${p}`);
        return { pass: false, code: RC.OUT_OF_SCOPE_OR_DIRTY };
      }
    }
  }

  return { pass: true };
}

/**
 * 解析并验证 Spec 文件中的 <!-- C06_SCOPE_START --> 物理契约块
 */
function canonicalText(str) {
  return str.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/[ \t]+$/gm, '');
}

/**
 * 解析并验证 Spec 文件中的 <!-- C06_SCOPE_START --> 物理契约块 (严格唯一性、规范化与验签)
 */
function verifySpecScope(specPath, cwd) {
  if (!fs.existsSync(specPath)) {
    console.error(`[GATE] Spec 规范文件不存在: ${specPath} (Exit 20)`);
    return { ok: false, code: RC.OUT_OF_SCOPE_OR_DIRTY };
  }

  const rawSpecContent = fs.readFileSync(specPath, 'utf8');
  const startMarker = '<!-- C06_SCOPE_START -->';
  const endMarker = '<!-- C06_SCOPE_END -->';

  const firstS = rawSpecContent.indexOf(startMarker);
  const lastS = rawSpecContent.lastIndexOf(startMarker);
  const firstE = rawSpecContent.indexOf(endMarker);
  const lastE = rawSpecContent.lastIndexOf(endMarker);

  if (firstS === -1 || firstE === -1 || firstE <= firstS || firstS !== lastS || firstE !== lastE) {
    console.error(`[GATE] Spec 文件缺失或包含重复的 <!-- C06_SCOPE_START --> / <!-- C06_SCOPE_END --> 标记块 (Exit 20)`);
    return { ok: false, code: RC.OUT_OF_SCOPE_OR_DIRTY };
  }

  const rawJsonBlock = rawSpecContent.slice(firstS + startMarker.length, firstE).trim();
  const jsonMatch = rawJsonBlock.match(/```(?:json)?\s*([\s\S]*?)\s*```/) || [null, rawJsonBlock];
  const jsonStr = jsonMatch[1].trim();

  let scopeObj;
  try {
    scopeObj = JSON.parse(jsonStr);
  } catch (err) {
    console.error(`[GATE] 解析 Spec 内 C06_SCOPE JSON 块失败 (Exit 20):`, err.message);
    return { ok: false, code: RC.OUT_OF_SCOPE_OR_DIRTY };
  }

  // 校验 scope_user_auth 用户信封
  const userAuth = scopeObj.scope_user_auth;
  if (!userAuth || typeof userAuth !== 'object') {
    console.error(`[GATE] Spec Scope 缺少 scope_user_auth 用户信封 (Exit 24)`);
    return { ok: false, code: RC.SIGNATURE_INVALID };
  }

  if (userAuth.action !== 'SCOPE_CONFIRM') {
    console.error(`[GATE] Spec scope_user_auth.action 必须为 SCOPE_CONFIRM (当前: ${userAuth.action}, Exit 24)`);
    return { ok: false, code: RC.SIGNATURE_INVALID };
  }

  // 验证用户 Ed25519 签名
  const authPayload = { ...userAuth };
  delete authPayload.signature;
  if (!c06Crypto.verifyEd25519(authPayload, userAuth.signature, 'user', cwd)) {
    console.error(`[GATE] Spec scope_user_auth 用户 Ed25519 签名校验失败 (Exit 24)`);
    return { ok: false, code: RC.SIGNATURE_INVALID };
  }

  // Nonce 防重放检查 (暂不消耗，全量断言通过后原子消耗)
  if (c06Crypto.isNonceConsumed(userAuth.nonce, cwd)) {
    console.error(`[GATE] Spec scope_user_auth nonce 已被消费 (重放攻击拦截, Exit 24)`);
    return { ok: false, code: RC.SIGNATURE_INVALID };
  }

  // 校验 scope_sha 哈希一致性
  const scopeContentToHash = { ...scopeObj };
  delete scopeContentToHash.scope_user_auth;
  delete scopeContentToHash.scope_sha;
  const computedScopeSha = c06Crypto.sha256(c06Crypto.canonicalJCS(scopeContentToHash));
  if (scopeObj.scope_sha && scopeObj.scope_sha !== computedScopeSha) {
    console.error(`[GATE] Spec scope_sha 校验不一致 (Exit 24): 声明 ${scopeObj.scope_sha} vs 计算 ${computedScopeSha}`);
    return { ok: false, code: RC.SIGNATURE_INVALID };
  }

  const normSpec = canonicalText(rawSpecContent);
  const specSha = c06Crypto.sha256(normSpec);

  return { ok: true, scopeObj, computedScopeSha, specSha, userAuth };
}

/**
 * CLI 主入口执行函数 (Fail-Closed, 彻底封死参数绕过并强制强一致性)
 */
function runCLI() {
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      const key = args[i].slice(2);
      options[key] = args[i + 1] && !args[i + 1].startsWith('--') ? args[++i] : true;
    }
  }

  const cwd = process.cwd();

  // 1. Clean 工作区断言
  if (!assertCleanWorktree(cwd)) {
    process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
  }

  // 2. Fail-Closed 检查：必须明确提供 --task 或 --spec
  if (!options.task && !options.spec) {
    console.error('[GATE] Fail-Closed: 必须指定 --task 或 --spec 参数 (Exit 20)');
    process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
  }

  let taskPackage = null;
  if (options.task) {
    let taskFile = options.task;
    if (!fs.existsSync(taskFile)) {
      const candidate = path.join(cwd, '.c06', 'tasks', options.task, 'task_package.json');
      if (fs.existsSync(candidate)) {
        taskFile = candidate;
      } else {
        console.error(`[GATE] 指定的 task 文件不存在: ${options.task} (Exit 20)`);
        process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
      }
    }
    try {
      taskPackage = JSON.parse(fs.readFileSync(taskFile, 'utf8'));
    } catch (err) {
      console.error('[GATE] 解析 task_package.json 失败 (Exit 24):', err.message);
      process.exit(RC.SIGNATURE_INVALID);
    }

    // 立即校验 CLI 参数冲突，严禁 CLI 覆盖已签名的 Task Package (Exit 20, 优先于 Nonce 消费)
    if (options.lane && options.lane !== taskPackage.lane) {
      console.error(`[GATE] CLI --lane (${options.lane}) 严禁覆盖签名 Task Package 中的 lane (${taskPackage.lane}) (Exit 20)`);
      process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
    }
    if (options.base && options.base !== taskPackage.base_sha) {
      console.error(`[GATE] CLI --base (${options.base}) 严禁覆盖签名 Task Package 中的 base_sha (${taskPackage.base_sha}) (Exit 20)`);
      process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
    }
    if (options.commit && options.commit !== taskPackage.commit_oid) {
      console.error(`[GATE] CLI --commit (${options.commit}) 严禁覆盖签名 Task Package 中的 commit_oid (${taskPackage.commit_oid}) (Exit 20)`);
      process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
    }

    // 验签 Task Package (Commander Ed25519)
    const pkgPayload = { ...taskPackage };
    delete pkgPayload.signature;
    if (!c06Crypto.verifyEd25519(pkgPayload, taskPackage.signature, 'commander', cwd)) {
      console.error('[GATE] task_package.json Ed25519 签名无效 (Exit 24)');
      process.exit(RC.SIGNATURE_INVALID);
    }

    // 校验任务包生命周期 TTL、时效性与单调性
    if (taskPackage.iat && taskPackage.exp) {
      if (taskPackage.exp <= taskPackage.iat) {
        console.error('[GATE] 任务包过期时间 exp 必须严格大于签发时间 iat (Exit 24)');
        process.exit(RC.SIGNATURE_INVALID);
      }
      if (taskPackage.exp - taskPackage.iat > 86400) {
        console.error('[GATE] 任务包生命周期超过最大允许上限 24 小时 (Exit 24)');
        process.exit(RC.SIGNATURE_INVALID);
      }
      const nowTs = Math.floor(Date.now() / 1000);
      if (nowTs > taskPackage.exp) {
        console.error(`[GATE] 任务包已过期 (当前时间: ${nowTs} > exp: ${taskPackage.exp}, Exit 24)`);
        process.exit(RC.SIGNATURE_INVALID);
      }
    }

    // 校验 codebase_map.json (Fail-Closed: 必需存在，Gate 签名必须有效，content_sha 必须匹配)
    const mapPath = path.join(cwd, '.c06', 'codebase_map.json');
    if (!fs.existsSync(mapPath)) {
      console.error('[GATE] 缺少必需代码库实体地图 codebase_map.json (Exit 34)');
      process.exit(RC.STALE_MAP);
    }
    let mapData;
    try {
      mapData = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
    } catch (err) {
      console.error('[GATE] 解析 codebase_map.json 失败 (Exit 34)');
      process.exit(RC.STALE_MAP);
    }
    const mapPayload = { ...mapData };
    delete mapPayload.signature;
    if (!c06Crypto.verifyEd25519(mapPayload, mapData.signature, 'gate', cwd)) {
      console.error('[GATE] codebase_map.json Gate 签名无效 (Exit 34)');
      process.exit(RC.STALE_MAP);
    }
    const computedContentSha = c06Crypto.sha256(c06Crypto.canonicalJCS(mapData.payload));
    if (taskPackage.codebase_map_sha && computedContentSha !== taskPackage.codebase_map_sha) {
      console.error(`[GATE] 代码库实体地图过期 (Exit 34): 任务绑定 ${taskPackage.codebase_map_sha} vs 计算 ${computedContentSha}`);
      process.exit(RC.STALE_MAP);
    }
    if (mapData.base_sha && taskPackage.base_sha && mapData.base_sha !== taskPackage.base_sha) {
      let isAncestor = false;
      try {
        execFileSync('git', ['--no-optional-locks', 'merge-base', '--is-ancestor', taskPackage.base_sha, mapData.base_sha], { cwd });
        isAncestor = true;
      } catch (_) {}
      if (!isAncestor && taskPackage.lane !== 'L0-A') {
        console.error(`[GATE] 代码库实体地图基线与任务基线不匹配 (Exit 34): map ${mapData.base_sha} vs task ${taskPackage.base_sha}`);
        process.exit(RC.STALE_MAP);
      }
    }

    // 检查 Nonce 是否已被消费 (前置断言全量通过后统一记录)
    if (c06Crypto.isNonceConsumed(taskPackage.nonce, cwd)) {
      console.error('[GATE] task_package.json nonce 已被消费 (重放攻击拦截, Exit 24)');
      process.exit(RC.SIGNATURE_INVALID);
    }
  }

  // 3. 校验 Spec 物理契约 (若提供 --spec 或 taskPackage 中包含 spec_path)
  let specUserAuth = null;
  const specPath = options.spec || taskPackage?.spec_path;
  if (specPath) {
    const specRes = verifySpecScope(specPath, cwd);
    if (!specRes.ok) {
      process.exit(specRes.code);
    }
    specUserAuth = specRes.userAuth;

    // 若同时存在 Task Package 与 Spec，断言二者哈希强绑定
    if (taskPackage) {
      if (taskPackage.spec_sha256 && taskPackage.spec_sha256 !== specRes.specSha) {
        console.error(`[GATE] Task Package 绑定的 spec_sha256 与实际 Spec 哈希不匹配 (Exit 24)`);
        process.exit(RC.SIGNATURE_INVALID);
      }
      if (taskPackage.scope_sha && taskPackage.scope_sha !== specRes.computedScopeSha) {
        console.error(`[GATE] Task Package 绑定的 scope_sha 与 Spec 计算哈希不匹配 (Exit 24)`);
        process.exit(RC.SIGNATURE_INVALID);
      }
    }
  }

  // 4. 推导参数

  const lane = taskPackage ? taskPackage.lane : (options.lane || 'L1');
  const baseSha = taskPackage ? taskPackage.base_sha : options.base;
  const currentHead = execFileSync('git', ['--no-optional-locks', 'rev-parse', 'HEAD'], { cwd, encoding: 'utf8' }).trim();
  const commitOid = taskPackage?.commit_oid || options.commit || currentHead;

  if (!baseSha) {
    console.error('[GATE] 缺失 base_sha 参数 (Exit 34)');
    process.exit(RC.STALE_MAP);
  }

  // 断言 Commit 关系
  if (!assertCommitOid(baseSha, commitOid, cwd)) {
    process.exit(RC.STALE_LEASE_OR_INTEGRITY);
  }

  // 断言 commit_oid 校验：
  // 若为当前活跃任务（lane !== 'L0-A'），commit_oid 必须等于当前分支 HEAD；
  // 对于历史前序任务（如已完结的 L0-A / T00），断言 commit_oid 必须是当前 HEAD 的祖先或等于 HEAD
  if (taskPackage && taskPackage.commit_oid) {
    if (taskPackage.commit_oid !== currentHead) {
      try {
        execFileSync('git', ['--no-optional-locks', 'merge-base', '--is-ancestor', taskPackage.commit_oid, currentHead], { cwd, stdio: 'ignore' });
        let isActive = false;
        try {
          const st = JSON.parse(fs.readFileSync(path.join(cwd, '.c06', 'wizard_state.json'), 'utf8'));
          if (st.active_task_id && taskPackage.task_id === st.active_task_id) isActive = true;
        } catch (_) {}
        if (isActive) {
          console.error(`[GATE] 活跃任务包绑定的 commit_oid (${taskPackage.commit_oid}) 必须等于当前分支 HEAD (${currentHead}) (Exit 33)`);
          process.exit(RC.STALE_LEASE_OR_INTEGRITY);
        }
      } catch (e) {
        console.error(`[GATE] 任务包绑定的 commit_oid (${taskPackage.commit_oid}) 既非当前分支 HEAD (${currentHead}) 亦非有效历史祖先 (Exit 33)`);
        process.exit(RC.STALE_LEASE_OR_INTEGRITY);
      }
    }
  }

  // 5. 提取改动文件
  const diffRes = getChangedFiles(baseSha, commitOid, cwd);
  if (!diffRes.ok) {
    process.exit(RC.OUT_OF_SCOPE_OR_DIRTY);
  }
  const changedFiles = diffRes.changes;

  // 6. L0 快车道度量、敏感词与扩展名检查
  if (lane === 'L0-A' || lane === 'L0-B') {
    const l0Res = assertL0MetricsAndKeywords(baseSha, commitOid, lane, cwd, taskPackage);
    if (!l0Res.pass) {
      console.error(`[GATE] L0 快车道断言未通过: ${l0Res.reason}`);
      process.exit(l0Res.code);
    }
  }

  // 7. 禁区与范围白名单检查 (基于 Task Package 或 Spec)
  const effectivePackage = taskPackage || (options.spec ? {
    owned_paths: ['src/pages/**', 'src/components/**', 'Design_Spec*.md'],
    forbidden_paths: CORE_FORBIDDEN_FAST_TRACK
  } : null);

  if (effectivePackage) {
    const scopeRes = assertScopeAndForbidden(changedFiles, effectivePackage, lane, cwd);
    if (!scopeRes.pass) {
      process.exit(scopeRes.code);
    }
  }

  // 7. 在所有门禁断言 100% 成功通过后，单一事务原子提交消费 Nonce (Fail-Closed: 批次提交与回滚机制)
  const noncesToCommit = [];
  if (taskPackage && taskPackage.nonce) {
    noncesToCommit.push({ role: 'commander', nonce: taskPackage.nonce, iat: taskPackage.iat });
  }
  if (specUserAuth && specUserAuth.nonce) {
    noncesToCommit.push({ role: 'user', nonce: specUserAuth.nonce, iat: specUserAuth.iat });
  }
  // 满足规范 Gate 零磁盘写入原则：仅在显式传入 --commit-nonces 时原子消费 Nonce
  if (process.argv.includes('--commit-nonces') && noncesToCommit.length > 0) {
    c06Crypto.atomicBatchRecordNonces(noncesToCommit, cwd);
  }

  console.log(`[GATE] scope-check.js 门禁断言全部通过 (Exit 0)，改动文件数: ${changedFiles.length}`);
  process.exit(RC.OK);
}

/**
 * 自检套件 (--self-test)
 */
function selfTest() {
  console.log('--- scope-check.js v3.9.0-Industrial 自检运行 ---');
  let failures = 0;

  function assert(name, condition) {
    if (condition) {
      console.log(`  PASS: ${name}`);
    } else {
      console.error(`  FAIL: ${name}`);
      failures++;
    }
  }

  // 1. matchGlob 测试
  assert('中段 **/src/core/** 匹配根路径', matchGlob('src/core/index.ts', '**/src/core/**'));
  assert('中段 **/src/core/** 匹配嵌套路径', matchGlob('apps/web/src/core/utils.ts', '**/src/core/**'));
  assert('中段 **/src/services/** 匹配', matchGlob('src/services/api.ts', '**/src/services/**'));
  assert('前缀 **/package.json 匹配根', matchGlob('package.json', '**/package.json'));
  assert('前缀 **/package.json 匹配嵌套', matchGlob('apps/api/package.json', '**/package.json'));
  assert('后缀 scripts/** 匹配', matchGlob('scripts/deploy.sh', 'scripts/**'));
  assert('后缀 scripts/** 排除非 scripts', !matchGlob('src/scripts/a.ts', 'scripts/**'));
  assert('精确路径匹配', matchGlob('pnpm-lock.yaml', 'pnpm-lock.yaml'));

  // 2. 敏感词正向/反向测试
  const kwRegex = new RegExp('\\b(' + SENSITIVE_AUTH_KEYWORDS.join('|') + ')\\b', 'i');
  assert('检出 auth 敏感词', kwRegex.test('const auth = req.headers.authorization;'));
  assert('检出 token 敏感词', kwRegex.test('const token = generateToken();'));
  assert('检出 password 敏感词', kwRegex.test('if (password !== hash) return;'));
  assert('排除普通单词 authentic', !kwRegex.test('const authentic = true;'));
  assert('排除普通单词 author', !kwRegex.test('const author = "Lin";'));

  // 3. 词法安全测试
  assert('正常路径词法安全', assertPathLexicalSafety('src/components/Button.tsx', process.cwd()));
  assert('ADS 冒号拦截', !assertPathLexicalSafety('src/file.ts:hidden', process.cwd()));
  assert('保留设备名拦截', !assertPathLexicalSafety('nul.txt', process.cwd()));
  assert('Windows 尾随点拦截', !assertPathLexicalSafety('src/core./file.ts', process.cwd()));
  assert('Windows 尾随空格拦截', !assertPathLexicalSafety('src/file.ts ', process.cwd()));

  // 4. L0-B 扩展名白名单测试
  assert('L0-B 允许 .css', L0_B_ALLOWED_EXTENSIONS.has('.css'));
  assert('L0-B 允许 .json', L0_B_ALLOWED_EXTENSIONS.has('.json'));
  assert('L0-B 允许 .svg', L0_B_ALLOWED_EXTENSIONS.has('.svg'));
  assert('L0-B 严禁 .ts', !L0_B_ALLOWED_EXTENSIONS.has('.ts'));
  assert('L0-B 严禁 .tsx', !L0_B_ALLOWED_EXTENSIONS.has('.tsx'));
  assert('L0-B 严禁 .js', !L0_B_ALLOWED_EXTENSIONS.has('.js'));

  // 5. 重命名双端检测
  const mockTaskPackage = {
    owned_paths: ['src/components/**'],
    forbidden_paths: ['src/core/**']
  };
  const renameEscape = [{ status: 'R100', oldPath: 'src/core/secret.ts', path: 'src/components/secret.ts' }];
  const renameRes = assertScopeAndForbidden(renameEscape, mockTaskPackage, 'L1', process.cwd());
  assert('重命名旧路径命中禁区即拦截', renameRes.pass === false && renameRes.code === RC.FORBIDDEN_ZONE);

  console.log(`自检完成: ${failures === 0 ? '全部通过' : failures + ' 项失败'}`);
  return failures === 0 ? 0 : 2;
}

if (process.argv.includes('--self-test')) {
  process.exit(selfTest());
} else if (require.main === module) {
  runCLI();
}

module.exports = {
  RC,
  CORE_FORBIDDEN_FAST_TRACK,
  SENSITIVE_AUTH_KEYWORDS,
  L0_B_ALLOWED_EXTENSIONS,
  matchGlob,
  normalizePath,
  assertCleanWorktree,
  assertCommitOid,
  getChangedFiles,
  assertL0MetricsAndKeywords,
  assertScopeAndForbidden,
  assertPathLexicalSafety,
  verifySpecScope,
  selfTest
};
