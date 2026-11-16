const fs = require('fs');
const path = require('path');
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

function takeScreenshot(htmlPath, outImagePath, width = 1280, height = 800) {
  return new Promise((resolve, reject) => {
    const edgePath = getEdgePath();
    if (!edgePath) {
      return reject(new Error('未在默认路径找到 Microsoft Edge 浏览器，请确认已安装 Edge。'));
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
      `--window-size=${width},${height}`,
      `--screenshot=${absOut}`,
      fileUrl
    ];

    execFile(edgePath, args, (error) => {
      if (error) {
        return reject(error);
      }
      if (fs.existsSync(absOut)) {
        resolve(absOut);
      } else {
        reject(new Error(`截图命令执行完毕，但输出文件未生成: ${absOut}`));
      }
    });
  });
}

// CLI 接口：node screenshot.js <htmlPath> <outImagePath> [width] [height]
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('用法: node screenshot.js <htmlPath> <outImagePath> [width] [height]');
    process.exit(1);
  }

  const [htmlPath, outPath, w, h] = args;
  takeScreenshot(htmlPath, outPath, w ? parseInt(w) : 1280, h ? parseInt(h) : 800)
    .then((saved) => {
      console.log(`[OK] 截图已成功生成: ${saved}`);
      process.exit(0);
    })
    .catch((err) => {
      console.error(`[ERROR] 截图失败: ${err.message}`);
      process.exit(1);
    });
}

module.exports = { takeScreenshot };
