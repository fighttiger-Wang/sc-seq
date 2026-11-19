#!/usr/bin/env node
/**
 * screenshot.js — C06 无头截图与 L1 运行时零异常门禁探针 (v5.0.0 Vibe-Agile)
 *
 * 用法：
 *   node screenshot.js <htmlPath> <outImagePath> [width] [height]
 *   node screenshot.js <htmlPath> --stdout-base64 [width] [height]
 *
 * 退出码契约：
 *   0  = 成功生成截图且控制台零致命异常
 *   40 = L1 Runtime Error: 页面存在未捕获严重控制台异常或 UnhandledPromiseRejection
 *   41 = L1 Resource / Timeout: 渲染超时、资源缺失或截图文件未生成
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFile } = require('child_process');

// 自动寻找 Edge 浏览器可执行文件路径
function getEdgePath() {
  const candidates = [
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Microsoft\\Edge\\Application\\msedge.exe')
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

/**
 * 执行无头截图并进行 L1 运行时控制台零异常核验 (Runtime Zero-Error Probe)
 */
function takeScreenshot(htmlPath, outImagePath, width = 1280, height = 800) {
  return new Promise((resolve, reject) => {
    const edgePath = getEdgePath();
    if (!edgePath) {
      const err = new Error('未在默认路径找到 Microsoft Edge 浏览器，请确认已安装 Edge。');
      err.code = 41;
      return reject(err);
    }

    const absHtml = path.resolve(htmlPath);
    const absOut = path.resolve(outImagePath);
    const fileUrl = 'file:///' + absHtml.replace(/\\/g, '/');

    // 确保输出目录存在
    const outDir = path.dirname(absOut);
    if (!fs.existsSync(outDir)) {
      fs.mkdirSync(outDir, { recursive: true });
    }

    const args = [
      '--headless=new',
      '--disable-gpu',
      '--no-sandbox',
      '--hide-scrollbars',
      '--enable-logging=stderr',
      '--log-level=0',
      '--virtual-time-budget=2000',
      `--window-size=${width},${height}`,
      `--screenshot=${absOut}`,
      fileUrl
    ];

    execFile(edgePath, args, (error, stdout, stderr) => {
      // 检查 stderr 中是否存在致命未捕获 JS 异常（L1 运行时拦截：全量未捕获异常与 Promise 拒绝）
      const errLogs = (stderr || '') + (stdout || '');
      const fatalErrors = [];
      const lines = errLogs.split('\n');
      for (const line of lines) {
        if (/(?:Uncaught\s+|UnhandledPromiseRejection|Unhandled\s+promise\s+rejection|CONSOLE\(\d+\)\]\s+"Error:)/i.test(line)) {
          fatalErrors.push(line.trim());
        }
      }

      if (fatalErrors.length > 0) {
        if (fs.existsSync(absOut)) {
          try { fs.unlinkSync(absOut); } catch (_) {}
        }
        const err = new Error(`[L1 运行时拦截 Exit 40] 页面存在未捕获的严重控制台异常:\n${fatalErrors.join('\n')}`);
        err.code = 40;
        return reject(err);
      }

      if (error && !fs.existsSync(absOut)) {
        const err = new Error(`[L1 截图失败 Exit 41] ${error.message}`);
        err.code = 41;
        return reject(err);
      }

      if (fs.existsSync(absOut)) {
        resolve({
          path: absOut,
          hasWarnings: /Console message/i.test(errLogs)
        });
      } else {
        const err = new Error(`[L1 资源缺失 Exit 41] 截图命令执行完毕，但输出文件未生成: ${absOut}`);
        err.code = 41;
        reject(err);
      }
    });
  });
}

// CLI 接口
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('用法: node screenshot.js <htmlPath> <outImagePath|--stdout-base64> [width] [height]');
    process.exit(1);
  }

  const htmlPath = args[0];
  const isBase64Mode = args[1] === '--stdout-base64';
  const outPath = isBase64Mode
    ? path.join(os.tmpdir(), `c06-shot-${Date.now()}-${Math.random().toString(36).slice(2)}.png`)
    : args[1];
  const w = args[2] ? parseInt(args[2], 10) : 1280;
  const h = args[3] ? parseInt(args[3], 10) : 800;

  takeScreenshot(htmlPath, outPath, w, h)
    .then((res) => {
      if (isBase64Mode) {
        try {
          const buf = fs.readFileSync(res.path);
          const b64 = buf.toString('base64');
          fs.unlinkSync(res.path); // 确保零磁盘残留
          console.log(`data:image/png;base64,${b64}`);
        } catch (e) {
          console.error(`[ERROR] 读取临时截图失败: ${e.message}`);
          process.exit(41);
        }
      } else {
        console.log(`[OK] 截图已成功生成 (L1 运行时零异常通过): ${res.path}`);
      }
      process.exit(0);
    })
    .catch((err) => {
      if (isBase64Mode && fs.existsSync(outPath)) {
        try { fs.unlinkSync(outPath); } catch (_) {}
      }
      console.error(`[ERROR] 截图或运行时核验失败 (Exit ${err.code || 41}): ${err.message}`);
      process.exit(err.code || 41);
    });
}

module.exports = { takeScreenshot };
