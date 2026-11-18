const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// RFC 8785 Canonical JSON Serialization (JCS)
function canonicalJCS(obj) {
  if (obj === undefined) {
    return undefined;
  }
  if (obj === null || typeof obj === 'boolean') {
    return JSON.stringify(obj);
  }
  if (typeof obj === 'string') {
    if (/(?:[^\uD800-\uDBFF]|^)[\uDC00-\uDFFF]|[\uD800-\uDBFF](?![\uDC00-\uDFFF])/.test(obj)) {
      throw new TypeError('RFC 8785 prohibits lone surrogate code points in strings');
    }
    return JSON.stringify(obj);
  }
  if (typeof obj === 'number') {
    if (!Number.isFinite(obj)) {
      throw new TypeError('RFC 8785 does not permit NaN or Infinity');
    }
    return JSON.stringify(obj);
  }
  if (Array.isArray(obj)) {
    const items = obj.map(item => {
      const res = canonicalJCS(item);
      return res === undefined ? 'null' : res;
    });
    return '[' + items.join(',') + ']';
  }
  if (typeof obj === 'object') {
    const keys = Object.keys(obj).sort();
    const parts = [];
    for (const k of keys) {
      if (/(?:[^\uD800-\uDBFF]|^)[\uDC00-\uDFFF]|[\uD800-\uDBFF](?![\uDC00-\uDFFF])/.test(k)) {
        throw new TypeError('RFC 8785 prohibits lone surrogate code points in object keys');
      }
      const val = canonicalJCS(obj[k]);
      if (val !== undefined) {
        parts.push(JSON.stringify(k) + ':' + val);
      }
    }
    return '{' + parts.join(',') + '}';
  }
  return JSON.stringify(obj);
}

function sha256(data) {
  const hash = crypto.createHash('sha256');
  if (typeof data === 'string') {
    hash.update(Buffer.from(data, 'utf8'));
  } else {
    hash.update(data);
  }
  return 'sha256:' + hash.digest('hex');
}

// Convert OpenSSH Ed25519 pubkey to standard Node.js KeyObject
function parseOpenSshEd25519(pubContent) {
  const parts = pubContent.trim().split(/\s+/);
  const b64 = parts.length > 1 ? parts[1] : parts[0];
  const buf = Buffer.from(b64, 'base64');
  const rawPub = buf.slice(buf.length - 32);
  const spkiPrefix = Buffer.from('302a300506032b6570032100', 'hex');
  const der = Buffer.concat([spkiPrefix, rawPub]);
  return crypto.createPublicKey({ key: der, format: 'der', type: 'spki' });
}

// Hardcoded trusted pin public keys (OpenSSH base64 payload)
const TRUSTED_PINS = {
  commander: 'AAAAC3NzaC1lZDI1NTE5AAAAIKKq0+FSVDWXFIfIBLEwvCvqLdwZVy9roqK7NQgDIqs6',
  gate: 'AAAAC3NzaC1lZDI1NTE5AAAAIG5eZz5I8+FxZpVlcK65uyHO45DjvqtaTwVz+yvKtP/V',
  reviewer: 'AAAAC3NzaC1lZDI1NTE5AAAAIHUP4q3eVJImIoLQkkDQ8JkRuXwxJXWxm6PLjgA27zDA',
  static_analyzer: 'AAAAC3NzaC1lZDI1NTE5AAAAIGiDV1ow8kWMRSMf0REUjjXlG6XNKxxr+mPkjNI/tjfE',
  user: 'AAAAC3NzaC1lZDI1NTE5AAAAINrNaBgGX1APd/6PH/5gHEtK8IBj0fcYblCaPLQAuA6e'
};

function loadPublicKey(role, projectRoot = process.cwd()) {
  const expectedB64 = TRUSTED_PINS[role];
  if (!expectedB64) {
    throw new Error(`Unknown role for pin resolution: ${role}`);
  }

  const candidates = [
    path.join(projectRoot, '.c06', 'pins', `${role}.pub`),
    path.join(os.homedir(), '.c06', 'pins', `${role}.pub`),
    path.join(__dirname, '..', '..', '..', '.c06', 'pins', `${role}.pub`)
  ];

  for (const p of candidates) {
    if (fs.existsSync(p)) {
      try {
        const content = fs.readFileSync(p, 'utf8').trim();
        const parts = content.split(/\s+/);
        const actualB64 = parts.length > 1 ? parts[1] : parts[0];
        // Enforce pin anchor comparison (Defense against Pin substitution)
        if (actualB64 !== expectedB64) {
          console.error(`[CRYPTO SECURITY ALERT] Pin mismatch for role ${role} in ${p}! Expected ${expectedB64}, got ${actualB64}`);
          process.exit(33);
        }
        return parseOpenSshEd25519(content);
      } catch (e) {
        if (e.code === 'ERR_ASSERTION' || e.message.includes('Pin mismatch')) throw e;
      }
    }
  }

  // Fallback to built-in trusted pin if file not present
  return parseOpenSshEd25519('ssh-ed25519 ' + expectedB64);
}

function verifyEd25519(payload, signatureStr, roleOrKey, projectRoot = process.cwd()) {
  if (!signatureStr || typeof signatureStr !== 'string') return false;
  let rawSig = signatureStr.trim();
  if (rawSig.startsWith('sig:ed25519:')) {
    rawSig = rawSig.slice('sig:ed25519:'.length);
  }

  let sigBuf;
  if (/^[0-9a-fA-F]{128}$/.test(rawSig)) {
    sigBuf = Buffer.from(rawSig, 'hex');
  } else {
    try {
      sigBuf = Buffer.from(rawSig, 'base64');
    } catch (_) {
      return false;
    }
  }

  if (sigBuf.length !== 64) return false;

  let keyObj = null;
  if (typeof roleOrKey === 'string') {
    keyObj = loadPublicKey(roleOrKey, projectRoot);
  } else if (roleOrKey && typeof roleOrKey === 'object') {
    keyObj = roleOrKey;
  }

  if (!keyObj) return false;

  const msgStr = typeof payload === 'string' ? payload : canonicalJCS(payload);
  const msgBuf = Buffer.from(msgStr, 'utf8');

  try {
    return crypto.verify(null, msgBuf, keyObj, sigBuf);
  } catch (e) {
    return false;
  }
}

function isNonceConsumed(nonce, projectRoot = process.cwd()) {
  if (!nonce) return true;
  const p = path.join(projectRoot, '.c06', 'consumed_nonces.jsonl');
  if (!fs.existsSync(p)) return false;
  try {
    const raw = fs.readFileSync(p, 'utf8');
    const lines = raw.split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      const item = JSON.parse(line);
      if (!item || typeof item !== 'object' || typeof item.nonce !== 'string' || item.nonce.length === 0) {
        console.error('[CRYPTO ALERT] 发现结构破损的 Nonce 记录，Fail-Closed 拦截！');
        return true;
      }
      if (item.nonce === nonce) return true;
    }
  } catch (err) {
    // 账本读取或解析失败，Fail-Closed 拒绝以防重放
    console.error(`[CRYPTO ALERT] consumed_nonces.jsonl 读取或解析异常: ${err.message}`);
    return true;
  }
  return false;
}

function recordNonce(role, nonce, iat, projectRoot = process.cwd()) {
  if (!nonce) return;
  const p = path.join(projectRoot, '.c06', 'consumed_nonces.jsonl');
  const dir = path.dirname(p);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const entry = {
    role: role || 'unknown',
    nonce: nonce,
    iat: iat || Math.floor(Date.now() / 1000),
    consumed_at: Math.floor(Date.now() / 1000)
  };
  fs.appendFileSync(p, JSON.stringify(entry) + '\n', 'utf8');
}

function isKeyRevoked(keyId, projectRoot = process.cwd()) {
  const p = path.join(projectRoot, '.c06', 'pins', 'revocations.json');
  if (!fs.existsSync(p)) {
    // 缺少吊销清单，Fail-Closed
    return true;
  }
  try {
    const raw = fs.readFileSync(p, 'utf8');
    const data = JSON.parse(raw);
    if (!data || !data.signature) {
      return true;
    }
    const payload = { ...data };
    delete payload.signature;
    const valid = verifyEd25519(payload, data.signature, 'commander', projectRoot) || verifyEd25519(payload, data.signature, 'user', projectRoot);
    if (!valid) {
      console.error('[CRYPTO ALERT] 吊销清单 revocations.json 签名无效，Fail-Closed 拒绝所有密钥操作！');
      return true;
    }
    if (Array.isArray(data.revoked_keys) && data.revoked_keys.includes(keyId)) {
      return true;
    }
    return false;
  } catch (_) {
    return true;
  }
}

function atomicBatchRecordNonces(records, projectRoot = process.cwd()) {
  if (!Array.isArray(records) || records.length === 0) return true;
  const p = path.join(projectRoot, '.c06', 'consumed_nonces.jsonl');
  const dir = path.dirname(p);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const lockPath = path.join(dir, 'nonce.lock');
  let lockFd = null;
  const maxRetries = 20;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      lockFd = fs.openSync(lockPath, 'wx');
      break;
    } catch (e) {
      if (attempt === maxRetries - 1) throw new Error('[FAIL-CLOSED] 无法获取 Nonce 账本文件锁 (并发争用超时)');
      const sleepMs = 5 + Math.floor(Math.random() * 10);
      const start = Date.now();
      while (Date.now() - start < sleepMs) {}
    }
  }

  // 关键：一旦获取文件锁，立即进入 try/finally，确保任何异常（包括查重与语法错误）绝不泄漏锁
  try {
    const existingNonces = new Set();
    let originalContent = '';
    if (fs.existsSync(p)) {
      try {
        originalContent = fs.readFileSync(p, 'utf8');
        const lines = originalContent.split(/\r?\n/).filter(Boolean);
        for (const line of lines) {
          const item = JSON.parse(line);
          if (!item || typeof item !== 'object' || typeof item.nonce !== 'string' || item.nonce.length === 0) {
            throw new Error('发现结构破损或非字符串 Nonce 记录');
          }
          existingNonces.add(item.nonce);
        }
      } catch (err) {
        throw new Error(`[FAIL-CLOSED] 既有 Nonce 账本校验异常: ${err.message}`);
      }
    }

    const batchNonces = new Set();
    const now = Math.floor(Date.now() / 1000);
    const newLinesArr = [];
    for (const r of records) {
      if (!r.nonce || typeof r.nonce !== 'string' || r.nonce.length === 0) throw new Error('[FAIL-CLOSED] 尝试提交无效 Nonce');
      if (existingNonces.has(r.nonce) || batchNonces.has(r.nonce)) {
        throw new Error(`[REPLAY DETECTED] Nonce 重放拦截: ${r.nonce}`);
      }
      batchNonces.add(r.nonce);
      newLinesArr.push(JSON.stringify({
        role: r.role || 'unknown',
        nonce: r.nonce,
        iat: r.iat || now,
        consumed_at: now
      }) + '\n');
    }

    const newLines = newLinesArr.join('');
    const tmpPath = p + '.tmp.' + Date.now() + '.' + Math.random().toString(36).substring(2);
    try {
      fs.writeFileSync(tmpPath, originalContent + newLines, 'utf8');
      fs.renameSync(tmpPath, p);
      return true;
    } catch (err) {
      try { if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath); } catch (_) {}
      throw err;
    }
  } finally {
    if (lockFd !== null) {
      try { fs.closeSync(lockFd); } catch (_) {}
      try { fs.unlinkSync(lockPath); } catch (_) {}
    }
  }
}

module.exports = {
  canonicalJCS,
  sha256,
  loadPublicKey,
  verifyEd25519,
  isNonceConsumed,
  recordNonce,
  atomicBatchRecordNonces,
  isKeyRevoked,
  TRUSTED_PINS
};
