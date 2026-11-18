/**
 * C02 · UI视觉设计 v1.3.0 官方标准工具链: CAD 工程蓝图与 PPT 多环节评审生成器
 * 
 * 功能:
 * 1. 接收各环节的工程图纸配置 (包含左侧 Exploded View、右侧 Plan View、底部规范参数表与评审决策点)
 * 2. 依托 Chrome Headless 渲染 1920x1080 (16:9) 工业制图标准的极清蓝图 PNG
 * 3. 依托 pptxgenjs 自动编译为宽屏 PowerPoint 演示文稿 (.pptx)
 * 4. 在每页右下角自动注入原生可编辑、打字批注的交互卡片，供用户逐页审查反馈
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 共享 CAD 制图基类样式 (白底工程制图风格、精细标线、尺寸公差、虚线槽位)
const CAD_BASE_CSS = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px;
    height: 1080px;
    background: #FFFFFF;
    font-family: 'Segoe UI', -apple-system, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;
    color: #1A202C;
    position: relative;
    overflow: hidden;
    padding: 36px 48px;
  }
  .blueprint-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 2px solid #1E293B;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }
  .header-main h1 {
    font-size: 27px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #0F172A;
    text-transform: uppercase;
  }
  .header-main .sub {
    font-size: 13px;
    font-family: 'Consolas', 'Courier New', monospace;
    color: #475569;
    letter-spacing: 0.5px;
    margin-top: 4px;
  }
  .header-meta {
    text-align: right;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    color: #475569;
    line-height: 1.5;
  }
  .header-meta b { color: #0F172A; }
  .blueprint-body {
    display: grid;
    grid-template-columns: 820px 980px;
    gap: 24px;
    height: 824px;
  }
  .panel-card {
    border: 1.5px solid #CBD5E1;
    border-radius: 8px;
    background: #FFFFFF;
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 18px;
  }
  .panel-title {
    font-family: 'Consolas', monospace;
    font-size: 13px;
    font-weight: bold;
    color: #1E293B;
    letter-spacing: 0.8px;
    border-bottom: 1px dashed #94A3B8;
    padding-bottom: 8px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
  }
  .panel-title span { font-size: 11px; color: #64748B; }
  .dim-text {
    font-family: 'Consolas', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #1E293B;
  }
  .slot-box {
    border: 1.5px dashed #475569;
    background: #F8FAFC;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    font-weight: 600;
    color: #334155;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .slot-box.fill { background: #F1F5F9; }
  .slot-box.highlight { border-color: #2563EB; color: #1D4ED8; background: #EFF6FF; }
  .slot-box.accent { border-color: #D97706; color: #B45309; background: #FFFBEB; }
  .spec-table-container {
    margin-top: auto;
    border-top: 1px solid #E2E8F0;
    padding-top: 10px;
  }
  .spec-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10.5px;
  }
  .spec-table th {
    background: #F1F5F9;
    color: #1E293B;
    text-align: left;
    padding: 6px 8px;
    font-weight: 700;
    border: 1px solid #CBD5E1;
  }
  .spec-table td {
    padding: 6px 8px;
    border: 1px solid #E2E8F0;
    color: #334155;
    background: #FFFFFF;
  }
  .spec-table tr:nth-child(even) td { background: #F8FAFC; }
  .review-hint {
    margin-top: 6px;
    background: #FFFBEB;
    border-left: 3px solid #D97706;
    padding: 5px 10px;
    font-size: 10.5px;
    color: #92400E;
    font-family: 'Segoe UI', sans-serif;
  }
`;

/**
 * 寻找 Chrome 可执行程序路径
 */
function findChrome() {
  const commonPaths = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    process.env.CHROME_BIN,
    process.env.PUPPETEER_EXECUTABLE_PATH
  ];
  for (const p of commonPaths) {
    if (p && fs.existsSync(p)) return p;
  }
  return 'chrome';
}

/**
 * 加载 pptxgenjs 库 (兼容各种 node_modules 搜索路径)
 */
function loadPptxGen() {
  const searchPaths = [
    'pptxgenjs',
    path.join(__dirname, '..', 'node_modules', 'pptxgenjs'),
    'C:\\Users\\fight\\.gemini\\antigravity\\scratch\\node_modules\\pptxgenjs'
  ];
  for (const sp of searchPaths) {
    try {
      return require(sp);
    } catch (e) {}
  }
  throw new Error('pptxgenjs 未找到，请确保已安装依赖: npm install pptxgenjs');
}

/**
 * 核心对外构建函数
 * @param {Array} slideDefinitions 幻灯片配置数组
 * @param {string} outputDir 输出目标目录
 * @param {string} pptxFileName 输出 PPT 文件名
 */
async function buildReviewDeck(slideDefinitions, outputDir, pptxFileName = 'UI_Engineering_Spec.pptx') {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const chromePath = findChrome();
  const PptxGen = loadPptxGen();
  const pptx = new PptxGen();
  pptx.layout = 'LAYOUT_16x9';

  console.log(`[ReviewDeck] 开始渲染 ${slideDefinitions.length} 个环节的 CAD 工程蓝图...`);
  const renderedSlides = [];

  for (let i = 0; i < slideDefinitions.length; i++) {
    const s = slideDefinitions[i];
    const htmlPath = path.join(outputDir, `temp_${s.id}.html`);
    const pngPath = path.join(outputDir, `${s.id}.png`);

    fs.writeFileSync(htmlPath, s.html, 'utf8');

    const cmd = `"${chromePath}" --headless=new --screenshot="${pngPath}" --window-size=1920,1080 --virtual-time-budget=2000 "file:///${htmlPath.replace(/\\/g, '/')}"`;
    execSync(cmd, { stdio: 'pipe' });

    // 清理临时 html
    try { fs.unlinkSync(htmlPath); } catch (e) {}

    renderedSlides.push({
      id: s.id,
      title: s.title,
      pngPath: pngPath,
      isCover: s.isCover || false
    });
    console.log(`[ReviewDeck] [${i+1}/${slideDefinitions.length}] 蓝图渲染完成: ${s.id}.png`);
  }

  console.log(`[ReviewDeck] 正在装配 16:9 宽屏 PowerPoint 演示文稿...`);
  for (let i = 0; i < renderedSlides.length; i++) {
    const s = renderedSlides[i];
    const slideObj = pptx.addSlide();

    // 1. 全幅贴合蓝图图纸
    slideObj.addImage({
      path: s.pngPath,
      x: 0,
      y: 0,
      w: '100%',
      h: '100%'
    });

    // 2. 注入右下角用户原生交互批注文本框 (非封面页)
    if (!s.isCover && i < renderedSlides.length - 1) {
      slideObj.addShape(pptx.ShapeType.rect, {
        x: 9.8,
        y: 6.85,
        w: 3.3,
        h: 0.55,
        fill: { color: 'FEF3C7' },
        line: { color: 'D97706', width: 1.5, dashType: 'dash' }
      });

      slideObj.addText(`✎ 点击在此输入针对【${s.title}】的修改意见或反馈...`, {
        x: 9.85,
        y: 6.88,
        w: 3.2,
        h: 0.5,
        fontSize: 9.5,
        fontFace: 'Microsoft YaHei',
        color: '92400E',
        valign: 'middle'
      });
    }
  }

  const finalPptxPath = path.join(outputDir, pptxFileName);
  await pptx.writeFile({ fileName: finalPptxPath });
  console.log(`[ReviewDeck] 🎉 PPTX 评审手册已成功生成: ${finalPptxPath}`);
  return {
    pptxPath: finalPptxPath,
    slides: renderedSlides
  };
}

module.exports = {
  CAD_BASE_CSS,
  buildReviewDeck,
  findChrome
};
