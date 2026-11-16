const fs = require('fs');
const path = require('path');

const KNOWLEDGE_PATH = path.join(__dirname, '..', 'knowledge', 'design_badcases.json');

function loadKnowledge() {
  if (!fs.existsSync(KNOWLEDGE_PATH)) {
    return { version: '1.0.0', updated_at: new Date().toISOString(), badcases: [] };
  }
  try {
    return JSON.parse(fs.readFileSync(KNOWLEDGE_PATH, 'utf-8'));
  } catch (e) {
    return { version: '1.0.0', updated_at: new Date().toISOString(), badcases: [] };
  }
}

function saveKnowledge(data) {
  data.updated_at = new Date().toISOString();
  fs.writeFileSync(KNOWLEDGE_PATH, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * 蒸馏并追加一条新经验
 */
function distillRule({ category, title, badcase, solution, rule }) {
  const db = loadKnowledge();
  
  // 查重：若已存在相同 title 则更新
  const existingIdx = db.badcases.findIndex(item => item.title === title);
  const entry = {
    id: existingIdx >= 0 ? db.badcases[existingIdx].id : `CASE-${String(db.badcases.length + 1).padStart(3, '0')}`,
    category: category || 'UI/UX 规范',
    title: title || '未命名体验缺陷',
    badcase: badcase || '',
    solution: solution || '',
    rule: rule || '',
    created_at: new Date().toISOString()
  };

  if (existingIdx >= 0) {
    db.badcases[existingIdx] = entry;
  } else {
    db.badcases.push(entry);
  }

  saveKnowledge(db);
  return entry;
}

// CLI 接口：node distill.js <category> <title> <badcase> <solution> <rule>
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length < 5) {
    console.error('用法: node distill.js <category> <title> <badcase> <solution> <rule>');
    process.exit(1);
  }

  const [category, title, badcase, solution, rule] = args;
  const entry = distillRule({ category, title, badcase, solution, rule });
  console.log(`[OK] 经验已成功蒸馏并沉淀入库: ${entry.id} - ${entry.title}`);
}

module.exports = { distillRule, loadKnowledge };
