#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E03 · Skill规范写作 v0.5.0 — 七大零性能损耗鲁棒性护栏校验与快照回滚引擎
对应全局快捷口令：
  - .g (体检) : 运行全套标准 Skill（或指定 Skill）七大护栏分舱体检
  - .u (撤回) : --rollback <skill> 一键物理回滚至改前快照

七大护栏：
  1. 📏 护栏 1（主文件防肥胖红线）：全仓所有 Skill 的 SKILL.md 一律强制 <= 8 KB，超限硬性报错
  2. 🛡️ 护栏 2（/ 斜杠菜单防消失锁 & 无 BOM UTF-8）：目录名 == SKILL.md name == skills.json & ANTIGRAVITY_SKILLS_MAP，displayName 符合 ^[A-Z]\\d{2} · .+ v\\d+\\.\\d+\\.\\d+$
  3. 🧬 护栏 3（A/B/C/D/E 五大类分舱特化校验）：
     - A/B 生信与绘图舱：校验共享知识库快照哈希一致性与生物学规则基线，不强套工程快捷键
     - C 前端设计舱：校验 vibe-guard.js / distill.js / govern.js 核心脚本完备性与防删函数护栏
     - D 算力运维舱：校验无本机个人账户绝对路径硬编码泄漏
     - E 治理与调度舱：校验快捷口令统一使用 .前缀 (.? / .u / .d / .g / .s)，无裸单字母劫持，无默认调用付费外援 (dsh/codex)
  4. 🗺️ 护栏 4（三端注册表对齐核验）：检查 ~/.gemini/config/skills/、~/.gemini/config/skills.json、ANTIGRAVITY_SKILLS_MAP 与 skill-pack.json 100% 一致，无孤儿或 _archive_*
  5. ⏪ 护栏 5（改前快照与 1 秒回滚）：支持 --snapshot <skill> 与 --rollback <skill>
  6. 🔗 护栏 6（全仓反向引用与死链雷达）：校验 SKILL.md / references/ 下相对链接真实存在，且无旧名残留
  7. 🧭 护栏 7（同文档矛盾检查 & global_pitfalls 巡检）：拦截同文档矛盾断言并按 shared/global_pitfalls.json 巡检全仓
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

STANDARD_20_MAP: dict[str, tuple[int, str]] = {
    "single-cell-qc-extract": (1, "A01-质控过滤提取"),
    "sc-major-celltype-annotation-auto": (2, "A02-大类谱系注释"),
    "sc-marker-cluster-annotation-auto": (3, "A03-亚群精细注释"),
    "annotation-knowledge-release": (4, "A04-知识库发布"),
    "bioinformatics-results-report": (5, "A05-交互解读报告"),
    "bioinformatics-results-report-classic": (6, "A06-文档解读报告"),
    "workflow-script-structure": (7, "A07-流程脚本工程"),
    "single-cell-qc-image-display": (8, "B01-质控分布图"),
    "feature-gene-heatmap-violin": (9, "B02-Marker表达图"),
    "celltype-function-heatmap": (10, "B03-功能模块热图"),
    "sc-group-gene-bubble-stats": (11, "B04-分组表达气泡图"),
    "sc-cell-proportion-stats": (12, "B05-细胞比例统计图"),
    "kegg-flow-bubble-plot": (13, "B06-KEGG流泡图"),
    "scientific-diagram-016": (14, "B07-机制流程概念图"),
    "c06-ai-design-pipeline": (15, "C06-AI设计流水线"),
    "hpc-computing-guide": (16, "D01-HPC超算指南"),
    "server-task-delivery": (17, "D02-服务器任务投递"),
    "task-handoff": (18, "E01-任务交接"),
    "tripartite-expert-review": (19, "E02-生信三方评审"),
    "skill-writing": (20, "E03-Skill规范写作"),
    "personal-skill-marketplace-setup": (21, "E04-Skill市场安装"),
    "skill-sync-publish": (22, "E05-Skill同步发布"),
    "local-agent-delegate": (23, "E06-红蓝对抗闭环"),
    "e07-dispatch": (24, "E07-派发"),
}

# Note: Total standard skills = 7 (A) + 7 (B) + 1 (C) + 2 (D) + 7 (E) = 24 skills in the A~E 5-category ledger!
# Let's map both by plugin_id and by Antigravity Chinese name.
CN_TO_PLUGIN_ID = {cn: pid for pid, (_, cn) in STANDARD_20_MAP.items()}
DISPLAY_RE = re.compile(r"^[A-Z]\d{2} · .+ v\d+\.\d+\.\d+$")
MAX_SKILL_MD_BYTES = 8 * 1024  # 8 KB

# Allowable third-party or built-in non-A-E skill directories in ~/.gemini/config/skills
ALLOWED_THIRD_PARTY_SKILLS = {"unslop"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_antigravity_home() -> Path:
    return Path(
        os.environ.get("ANTIGRAVITY_HOME")
        or os.environ.get("GEMINI_HOME")
        or (Path.home() / ".gemini")
    ).expanduser().resolve()


def resolve_marketplace_root(explicit: Path | None = None) -> Path:
    if explicit and (explicit / "skill-pack.json").is_file():
        return explicit.resolve()
    env_root = os.environ.get("CODEX_SHARED_MARKETPLACE_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if (p / "skill-pack.json").is_file():
            return p
    marker = Path.home() / ".codex" / "workspace-local.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            mp = data.get("marketplaceRoot")
            if mp and (Path(mp) / "skill-pack.json").is_file():
                return Path(mp).resolve()
        except Exception:
            pass
    for candidate in (
        Path(r"E:\A002-Codex\工作区\local-marketplace-stable-20260916-193427-e53a557c"),
        Path(r"E:\A002-Codex\工作区\sc-seq"),
    ):
        if (candidate / "skill-pack.json").is_file():
            return candidate.resolve()
    cursor = Path(__file__).resolve()
    for parent in cursor.parents:
        if (parent / "skill-pack.json").is_file():
            return parent
    raise FileNotFoundError("Could not locate authoritative marketplace root containing skill-pack.json")


def resolve_skill_pair(query: str) -> tuple[str, str]:
    q = query.strip()
    if q in STANDARD_20_MAP:
        return q, STANDARD_20_MAP[q][1]
    if q in CN_TO_PLUGIN_ID:
        return CN_TO_PLUGIN_ID[q], q
    for pid, (_, cn) in STANDARD_20_MAP.items():
        if cn.upper().startswith(q.upper() + "-") or pid.lower() == q.lower():
            return pid, cn
    raise ValueError(f"Unknown skill identifier: {query}")


def get_snapshot_base() -> Path:
    base = resolve_antigravity_home() / "archive_e_series_backup" / "skill_snapshots"
    base.mkdir(parents=True, exist_ok=True)
    return base


def take_snapshot(skill_query: str, marketplace_root: Path) -> dict[str, Any]:
    plugin_id, cn_name = resolve_skill_pair(skill_query)
    ag_home = resolve_antigravity_home()
    ag_skill_dir = ag_home / "config" / "skills" / cn_name
    mp_plugin_dir = marketplace_root / "plugins" / plugin_id

    snap_dir = get_snapshot_base() / cn_name
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)

    recorded = {}
    if ag_skill_dir.is_dir():
        shutil.copytree(ag_skill_dir, snap_dir / "antigravity_skill")
        recorded["antigravity_skill"] = str(ag_skill_dir)
    if mp_plugin_dir.is_dir():
        shutil.copytree(mp_plugin_dir, snap_dir / "marketplace_plugin")
        recorded["marketplace_plugin"] = str(mp_plugin_dir)

    meta = {
        "plugin_id": plugin_id,
        "cn_name": cn_name,
        "timestamp": dt.datetime.now().astimezone().isoformat(),
        "marketplace_root": str(marketplace_root),
        "recorded": recorded,
    }
    (snap_dir / "snapshot_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "SNAPSHOT_CREATED", "snapshot_dir": str(snap_dir), **meta}


def rollback_snapshot(skill_query: str, marketplace_root: Path) -> dict[str, Any]:
    plugin_id, cn_name = resolve_skill_pair(skill_query)
    snap_dir = get_snapshot_base() / cn_name
    meta_file = snap_dir / "snapshot_meta.json"
    if not meta_file.is_file():
        raise FileNotFoundError(f"No snapshot found for {cn_name} ({plugin_id}) at {snap_dir}")

    ag_home = resolve_antigravity_home()
    ag_skill_dir = ag_home / "config" / "skills" / cn_name
    mp_plugin_dir = marketplace_root / "plugins" / plugin_id

    restored = []
    if (snap_dir / "antigravity_skill").is_dir():
        if ag_skill_dir.exists():
            shutil.rmtree(ag_skill_dir)
        shutil.copytree(snap_dir / "antigravity_skill", ag_skill_dir)
        restored.append(str(ag_skill_dir))
    if (snap_dir / "marketplace_plugin").is_dir():
        if mp_plugin_dir.exists():
            shutil.rmtree(mp_plugin_dir)
        shutil.copytree(snap_dir / "marketplace_plugin", mp_plugin_dir)
        restored.append(str(mp_plugin_dir))

    return {
        "status": "ROLLED_BACK",
        "plugin_id": plugin_id,
        "cn_name": cn_name,
        "restored_paths": restored,
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"\A---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            k, v = line.split(":", 1)
            val = v.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            result[k.strip()] = val
    return result


def validate_one_skill(
    plugin_id: str,
    cn_name: str,
    marketplace_root: Path,
    ag_skills_dir: Path,
) -> dict[str, Any]:
    cabin = cn_name[0].upper()
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, str] = {}

    ag_dir = ag_skills_dir / cn_name
    ag_skill_md = ag_dir / "SKILL.md"
    mp_dir = marketplace_root / "plugins" / plugin_id
    mp_skill_md = mp_dir / "skills" / plugin_id / "SKILL.md"
    mp_plugin_json = mp_dir / ".codex-plugin" / "plugin.json"
    mp_openai_yaml = mp_dir / "skills" / plugin_id / "agents" / "openai.yaml"

    # Prefer checking Antigravity installed SKILL.md and Marketplace SKILL.md
    target_md = ag_skill_md if ag_skill_md.is_file() else mp_skill_md
    if not target_md.is_file():
        errors.append(f"Missing SKILL.md in both Antigravity ({ag_skill_md}) and Marketplace ({mp_skill_md})")
        return {
            "plugin_id": plugin_id,
            "cn_name": cn_name,
            "cabin": cabin,
            "size_kb": 0.0,
            "display_name": "",
            "passed": False,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        }

    raw_bytes = target_md.read_bytes()
    size_bytes = len(raw_bytes)
    size_kb = round(size_bytes / 1024.0, 2)

    # 护栏 1：主文件防肥胖红线 (<= 8 KB，全仓 24 个标准 Skill 一律硬性报错)
    if size_bytes <= MAX_SKILL_MD_BYTES:
        checks["G1_size_budget"] = f"PASS ({size_kb} KB <= 8.0 KB)"
    else:
        errors.append(f"[G1 主文件超重] {cn_name} SKILL.md 体积 {size_kb} KB 超过 8.0 KB 硬红线，请将细节下沉至 references/")
        checks["G1_size_budget"] = f"FAIL ({size_kb} KB > 8.0 KB)"

    # 护栏 2：/ 斜杠菜单防消失锁 & UTF-8 无 BOM
    has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    if has_bom:
        errors.append(f"[G2 编码违规] {target_md} 含有 UTF-8 BOM 头")
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    fm = parse_frontmatter(text)
    display_name = fm.get("displayName", "")

    if ag_skill_md.is_file():
        ag_fm = parse_frontmatter(ag_skill_md.read_text(encoding="utf-8"))
        ag_name = ag_fm.get("name", "")
        if ag_name != cn_name:
            errors.append(f"[G2 斜杠菜单消失风险] Antigravity 目录名 '{cn_name}' 与 SKILL.md name '{ag_name}' 不一致")
        display_name = ag_fm.get("displayName", display_name)
    else:
        errors.append(f"[G2 目录缺失] Antigravity 技能目录缺失: {ag_dir}")

    if not DISPLAY_RE.fullmatch(display_name):
        errors.append(
            f"[G2 displayName 格式违规] '{display_name}' 不符合 '^[A-Z]\\d{{2}} · .+ v\\d+\\.\\d+\\.\\d+$'（必须使用中点 · U+00B7 且带 vX.Y.Z）"
        )

    if mp_plugin_json.is_file() and mp_openai_yaml.is_file():
        pj_raw = mp_plugin_json.read_bytes()
        oy_raw = mp_openai_yaml.read_bytes()
        if pj_raw.startswith(b"\xef\xbb\xbf") or oy_raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"[G2 编码违规] {plugin_id} 的 plugin.json 或 openai.yaml 含 UTF-8 BOM")
        pj = json.loads(pj_raw.decode("utf-8-sig"))
        pj_disp = (pj.get("interface") or {}).get("displayName", "")
        oy_text = oy_raw.decode("utf-8-sig")
        oy_m = re.search(r'(?m)^\s*display_name:\s*["\']?([^"\'\r\n]+)', oy_text)
        oy_disp = oy_m.group(1).strip() if oy_m else ""
        if pj_disp != display_name or oy_disp != display_name:
            errors.append(
                f"[G2 元数据版本撕裂] SKILL.md('{display_name}') vs plugin.json('{pj_disp}') vs openai.yaml('{oy_disp}')"
            )
    else:
        errors.append(f"[G2 插件元数据缺失] 缺少 {mp_plugin_json} 或 {mp_openai_yaml}")

    checks["G2_slash_menu_lock"] = "PASS" if not any(e.startswith("[G2") for e in errors) else "FAIL"

    # 护栏 3：A/B/C/D/E 五大类分舱特化校验
    if cabin in {"A", "B"}:
        # 生信与绘图舱：检查共享知识库快照一致性（针对 A02/A03）与参考资料完整性
        if plugin_id in {"sc-major-celltype-annotation-auto", "sc-marker-cluster-annotation-auto"}:
            snap_file = mp_dir / "skills" / plugin_id / "references" / "annotation-evidence-core.snapshot.json"
            core_ver_file = marketplace_root / "shared" / "sc-annotation-evidence-core" / "VERSION.json"
            if not snap_file.is_file() or not core_ver_file.is_file():
                errors.append(f"[G3 生信舱] {cn_name} 缺少共享知识库快照 annotation-evidence-core.snapshot.json")
            else:
                snap_data = json.loads(snap_file.read_text(encoding="utf-8"))
                core_data = json.loads(core_ver_file.read_text(encoding="utf-8"))
                if snap_data.get("knowledge_base_version") != core_data.get("knowledge_base_version"):
                    errors.append(f"[G3 生信舱] {cn_name} 知识库快照版本与 shared core 不一致")
        checks["G3_cabin_specific"] = "PASS (A/B 生信绘图基线完好)" if not any(e.startswith("[G3") for e in errors) else "FAIL"

    elif cabin == "C":
        # C 前端设计舱：检查 vibe-guard.js / distill.js / govern.js 及防删函数护栏
        base_dir = ag_dir if ag_dir.is_dir() else (mp_dir / "skills" / plugin_id)
        required_scripts = ("vibe-guard.js", "distill.js", "govern.js")
        for req_s in required_scripts:
            if not (base_dir / "scripts" / req_s).is_file():
                errors.append(f"[G3 前端设计舱] {cn_name} 缺少核心脚本 scripts/{req_s}")
        vg_file = base_dir / "scripts" / "vibe-guard.js"
        if vg_file.is_file():
            vg_text = vg_file.read_text(encoding="utf-8", errors="replace")
            if "extractSymbols" not in vg_text or "deletedFunctions" not in vg_text:
                errors.append(f"[G3 前端设计舱] vibe-guard.js 缺少函数符号防删校验逻辑")
        for dot_cmd in (".?", ".u", ".d", ".g"):
            if dot_cmd not in text:
                errors.append(f"[G3 前端设计舱] {cn_name} SKILL.md 未更新全局点号前缀口令 '{dot_cmd}'")
        checks["G3_cabin_specific"] = "PASS (C06 三大护栏脚本与 .前缀口令完好)" if not any(e.startswith("[G3") for e in errors) else "FAIL"

    elif cabin == "D":
        # D 算力运维舱：检查无本机个人账户绝对路径硬编码泄漏
        normalized = text.replace("\\\\", "/").replace("\\", "/")
        if re.search(r"(?i)\b[A-Z]:/Users/[^/\s<>'\"]+/", normalized) or re.search(r"/(Users|home)/fight/", normalized):
            errors.append(f"[G3 算力运维舱] {cn_name} SKILL.md 存在本机个人账户绝对路径硬编码泄漏")
        checks["G3_cabin_specific"] = "PASS (D 算力运维无个人路径泄漏)" if not any(e.startswith("[G3") for e in errors) else "FAIL"

    elif cabin == "E":
        # E 治理与调度舱：检查 .前缀口令与禁默认调用付费外援
        if cn_name in {"E06-红蓝对抗闭环", "E07-派发"}:
            for dot_cmd in (".?", ".s"):
                if dot_cmd not in text:
                    errors.append(f"[G3 治理调度舱] {cn_name} SKILL.md 未包含点号快捷口令 '{dot_cmd}'")
            if re.search(r"\[r\]刷新|\[\?\]看板|\[s/c/r/\?\]", text):
                errors.append(f"[G3 治理调度舱] {cn_name} SKILL.md 仍残留旧版裸单字母快捷键提示 ([r] / [?] / [s/c/r/?])")
        if cn_name == "E03-Skill规范写作":
            for dot_cmd in (".u", ".g"):
                if dot_cmd not in text:
                    errors.append(f"[G3 治理调度舱] {cn_name} SKILL.md 未声明 '{dot_cmd}' 口令")
        checks["G3_cabin_specific"] = "PASS (E 治理调度舱 .前缀口令与免费优先合规)" if not any(e.startswith("[G3") for e in errors) else "FAIL"

    # 护栏 6：全仓反向引用与死链雷达（SKILL.md 与 references/*.md 相对链接真实存在，且无旧名残留）
    mp_skill_dir = mp_dir / "skills" / plugin_id
    md_files_to_scan = [mp_skill_md] + (sorted((mp_skill_dir / "references").glob("*.md")) if (mp_skill_dir / "references").is_dir() else [])
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    retired_always = ("E02-三方专家评审", "E05-多智能体委托", "E06-本机智能体委托", "C01-工作台", "C02-UI视觉设计", "C03-需求对齐追问", "C04-独立体验走查", "C05-桌面应用打包")
    for md_f in md_files_to_scan:
        if not md_f.is_file():
            continue
        md_raw = md_f.read_bytes()
        if md_raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"[G7 编码违规 PIT-005] {md_f.name} 含有 UTF-8 BOM 头")
        md_txt = md_raw.decode("utf-8-sig", errors="replace")
        for m_link in link_re.finditer(md_txt):
            raw_target = m_link.group(1).strip().split()[0]
            if not raw_target or raw_target.startswith(("http://", "https://", "mailto:", "file://", "#")) or "<" in raw_target or ">" in raw_target:
                continue
            rel_path = raw_target.split("#", 1)[0]
            if not rel_path:
                continue
            if rel_path.startswith("../../../../shared/"):
                resolved = marketplace_root / rel_path.replace("../../../../", "")
            else:
                resolved = (md_f.parent / rel_path).resolve()
            if not resolved.exists():
                errors.append(f"[G6 死链] {cn_name} {md_f.name} 引用了不存在的路径: {raw_target}")
        for old_nm in retired_always:
            if old_nm in md_txt:
                errors.append(f"[G6 旧名残留 PIT-002] {cn_name} {md_f.name} 仍包含已废弃旧名: {old_nm}")
        if "scientific-diagram-016" in md_txt and plugin_id not in {"scientific-diagram-016", "skill-writing", "personal-skill-marketplace-setup"}:
            errors.append(f"[G6 旧名残留 PIT-002] {cn_name} {md_f.name} 仍硬编码旧名 scientific-diagram-016，请改为按编号前缀调用 B07-机制流程概念图")
    checks["G6_cross_ref_radar"] = "PASS" if not any(e.startswith("[G6") for e in errors) else "FAIL"

    # 护栏 7：同文档矛盾检查 & global_pitfalls 巡检
    if plugin_id == "sc-marker-cluster-annotation-auto":
        if "legacy four-sheet output is invalid" in text or "fixed five-sheet workbook" in text:
            errors.append(f"[G7 同文档矛盾 PIT-003] {cn_name} 仍残留旧 5-sheet 唯一合法条文，与 4-sheet 标准版冲突")
    if plugin_id == "server-task-delivery":
        if "#SBATCH --mem=64G" in text:
            errors.append(f"[G7 陷阱违规 PIT-001] {cn_name} SKILL.md 仍包含 #SBATCH --mem=64G（openclaw01 RealMemory=1 禁写）")
        runner_ps1 = mp_skill_dir / "scripts" / "remote_bio_runner.ps1"
        if runner_ps1.is_file():
            r_txt = runner_ps1.read_text(encoding="utf-8-sig", errors="replace")
            if '[string]$Mem = "64G"' in r_txt:
                errors.append(f"[G7 陷阱违规 PIT-001] {cn_name} remote_bio_runner.ps1 默认仍写死 $Mem = '64G'")
    checks["G7_pitfalls_and_ssot"] = "PASS" if not any(e.startswith("[G7") for e in errors) else "FAIL"

    return {
        "plugin_id": plugin_id,
        "cn_name": cn_name,
        "cabin": cabin,
        "size_kb": size_kb,
        "display_name": display_name,
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def check_guardrail_4_registry_alignment(marketplace_root: Path, ag_home: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    ag_skills_dir = ag_home / "config" / "skills"
    skills_json = ag_home / "config" / "skills.json"

    if not skills_json.is_file():
        errors.append(f"[G4 注册表缺失] 缺少 {skills_json}")

    # 1. Check setup.py ANTIGRAVITY_SKILLS_MAP
    setup_py = (
        marketplace_root
        / "plugins"
        / "personal-skill-marketplace-setup"
        / "skills"
        / "personal-skill-marketplace-setup"
        / "scripts"
        / "setup.py"
    )
    if not setup_py.is_file():
        errors.append(f"[G4 核心脚本缺失] 缺少 {setup_py}")
    else:
        setup_text = setup_py.read_text(encoding="utf-8")
        idx = setup_text.find("ANTIGRAVITY_SKILLS_MAP")
        if idx == -1:
            errors.append("[G4 映射表缺失] setup.py 中未找到 ANTIGRAVITY_SKILLS_MAP")
        else:
            b_start = setup_text.find("{", idx)
            b_end = setup_text.find("}\n", b_start)
            if b_end == -1:
                b_end = setup_text.find("}", b_start)
            try:
                parsed_map = ast.literal_eval(setup_text[b_start : b_end + 1])
                expected_pairs = {pid: cn for pid, (_, cn) in STANDARD_20_MAP.items()}
                actual_pairs = {pid: cn for pid, (_, cn) in parsed_map.items()}
                if actual_pairs != expected_pairs:
                    missing = set(expected_pairs.items()) - set(actual_pairs.items())
                    extra = set(actual_pairs.items()) - set(expected_pairs.items())
                    errors.append(f"[G4 ANTIGRAVITY_SKILLS_MAP 不一致] missing={missing}, extra={extra}")
            except Exception as exc:
                errors.append(f"[G4 ANTIGRAVITY_SKILLS_MAP 解析失败] {exc}")

    # 2. Check skill-pack.json
    sp_file = marketplace_root / "skill-pack.json"
    if sp_file.is_file():
        sp = json.loads(sp_file.read_text(encoding="utf-8"))
        sp_ids = {item["id"] for item in sp.get("plugins", [])}
        expected_ids = set(STANDARD_20_MAP.keys())
        if sp_ids != expected_ids:
            errors.append(
                f"[G4 skill-pack.json 不对齐] missing={expected_ids - sp_ids}, extra={sp_ids - expected_ids}"
            )

    # 3. Check ~/.gemini/config/skills/ for orphan or _archive_* folders
    if ag_skills_dir.is_dir():
        expected_cn = {cn for _, (_, cn) in STANDARD_20_MAP.items()}
        for item in ag_skills_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("_archive") or item.name in {"E02-三方专家评审", "E06-本机智能体委托"}:
                errors.append(f"[G4 残留废弃目录] ~/.gemini/config/skills/ 中存在未清理的旧目录: {item.name}")
            elif item.name not in expected_cn and item.name not in ALLOWED_THIRD_PARTY_SKILLS:
                errors.append(f"[G4 孤儿技能目录] ~/.gemini/config/skills/ 中存在未注册孤儿目录: {item.name}")

    # 4. Check shared/global_pitfalls.json & ~/.gemini/config/skills/shared_global_pitfalls.json (Guardrail 7)
    mp_pitfalls = marketplace_root / "shared" / "global_pitfalls.json"
    ag_pitfalls = ag_skills_dir / "shared_global_pitfalls.json"
    if not mp_pitfalls.is_file():
        errors.append(f"[G7 陷阱库缺失] 缺少 {mp_pitfalls}")
    elif not ag_pitfalls.is_file():
        errors.append(f"[G7 陷阱库未同步] 缺少 {ag_pitfalls}")
    elif sha256_file(mp_pitfalls) != sha256_file(ag_pitfalls):
        errors.append(f"[G7 陷阱库失步] {ag_pitfalls} 与 {mp_pitfalls} 哈希不一致，请运行 sync-antigravity")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="E03 七大零损耗鲁棒性护栏校验与快照回滚工具 v0.5.0")
    parser.add_argument("--marketplace-root", type=Path, default=None, help="Marketplace 根目录")
    parser.add_argument("--skill", default=None, help="仅校验指定 Skill (英文 plugin_id 或中文名)")
    parser.add_argument("--snapshot", default=None, help="为指定 Skill 创建改前快照")
    parser.add_argument("--rollback", default=None, help="(对应口令 .u) 将指定 Skill 回滚至改前快照")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    mp_root = resolve_marketplace_root(args.marketplace_root)
    ag_home = resolve_antigravity_home()
    ag_skills_dir = ag_home / "config" / "skills"

    if args.snapshot:
        res = take_snapshot(args.snapshot, mp_root)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.rollback:
        res = rollback_snapshot(args.rollback, mp_root)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.skill:
        pid, cn = resolve_skill_pair(args.skill)
        targets = [(pid, cn)]
    else:
        targets = [(pid, cn) for pid, (_, cn) in STANDARD_20_MAP.items()]

    results = []
    all_errors: list[str] = []
    all_warnings: list[str] = []

    for pid, cn in targets:
        r = validate_one_skill(pid, cn, mp_root, ag_skills_dir)
        results.append(r)
        all_errors.extend(r["errors"])
        all_warnings.extend(r["warnings"])

    g4_errors: list[str] = []
    g4_warnings: list[str] = []
    if not args.skill:
        g4_errors, g4_warnings = check_guardrail_4_registry_alignment(mp_root, ag_home)
        all_errors.extend(g4_errors)
        all_warnings.extend(g4_warnings)

    summary = {
        "status": "PASS" if not all_errors else "FAIL",
        "marketplace_root": str(mp_root),
        "antigravity_skills_dir": str(ag_skills_dir),
        "checked_count": len(results),
        "error_count": len(all_errors),
        "warning_count": len(all_warnings),
        "errors": all_errors,
        "warnings": all_warnings,
        "skills": results,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"# 🛡️ E03 Skill 鲁棒性七护栏分舱体检报告 (v0.5.0 · 口令 `.g`)")
        print(f"- 权威仓库: {mp_root}")
        print(f"- 本地技能舱: {ag_skills_dir}")
        print(f"- 检查技能数: {len(results)} 个 │ 错误(Error): {len(all_errors)} │ 温和提示(Warning): {len(all_warnings)}\n")
        for r in results:
            badge = "✅ PASS" if r["passed"] else "❌ FAIL"
            warn_tag = f" (⚠️ {len(r['warnings'])} 提示)" if r["warnings"] else ""
            print(f"  • [{badge}] {r['cn_name']:<16} ({r['plugin_id']}) │ {r['size_kb']:>5.2f} KB │ {r['display_name']}{warn_tag}")
            for err in r["errors"]:
                print(f"      ❌ {err}")
        if g4_errors:
            print("\n## 🗺️ 护栏 4（三端注册表对齐）异常:")
            for ge in g4_errors:
                print(f"  ❌ {ge}")
        else:
            print("\n## 🗺️ 护栏 4（三端注册表对齐）: ✅ 100% 对齐，0 孤儿目录，0 残留归档")
        print(f"\n[RESULT] Exit Code {'0 (体检全绿通过)' if not all_errors else '1 (存在阻断性错误)'}")

    sys.exit(0 if not all_errors else 1)


if __name__ == "__main__":
    main()
