#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mmap
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DSH_ROOT = Path("E:/A001-软件安装/deepseek/resources")
BJ_TZ = timezone(timedelta(hours=8))
MODEL_FIELDS = ("display_name", "name", "tier", "access_tier", "service_tier", "service_tiers",
                "quota_tier", "bucket", "quota_bucket", "visibility", "supported_in_api", "available_in_plans")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_policy():
    return read_json(SCRIPT_DIR / "routing_policy.json")


def tasks_dir():
    return Path(os.environ.get("E07_TASKS_DIR") or Path.home() / ".gemini/antigravity/scratch/e07_tasks")


def read_models(rows):
    if isinstance(rows, dict):
        rows = [dict(metadata, slug=slug) for slug, metadata in rows.items()]
    return {row if isinstance(row, str) else (row.get("slug") or row["id"]):
            {} if isinstance(row, str) else {key: row[key] for key in MODEL_FIELDS if key in row}
            for row in rows}


def read_codex_models():
    return read_models(read_json(Path.home() / ".codex/models_cache.json")["models"])


def resolve_codex_roles(policy, models):
    by_series = {}
    for slug, model in models.items():
        match = re.fullmatch(r"gpt-(\d+(?:\.\d+)*)-([a-z]+)", slug)
        if match and model.get("visibility", "list") == "list":
            version, series = match.groups()
            by_series.setdefault(series, []).append((tuple(map(int, version.split("."))), slug))
    resolved = {}
    for name, role in policy["roles"].items():
        if role["runner"] != "codex":
            continue
        chain = [slug for series in role["series_preference"]
                 for _, slug in sorted(by_series.get(series, []), reverse=True)]
        slug = chain[0] if chain else None
        resolved[name] = {**role, "slug": slug, "fallback_chain": chain,
                          "display_name": (models[slug].get("display_name") or slug) if slug else "不可用"}
    return resolved


def read_dsh_catalog():
    with (DSH_ROOT / "app.asar").open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as archive:
        match = re.search(rb'\bDEFAULT_MODELS\s*=\s*(\[\s*\{.{1,16384}?\}\s*\])', archive, re.S)
        rows = re.findall(rb'\bid:\s*"([^"]+)"\s*,\s*name:\s*"([^"]+)"', match[1]) if match else []
    if not rows:
        raise ValueError("DEFAULT_MODELS 未解析到模型")
    return {slug.decode(): {"display_name": name.decode()} for slug, name in rows}


def read_dsh_default():
    binary = os.environ.get("OIL_DELEGATE_DSH_BIN") or shutil.which("dsh") or str(DSH_ROOT / "runtime/cli/bin/dsh.cmd")
    result = subprocess.run([binary, "--profile", "headless", "--dump-config"],
                            capture_output=True, encoding="utf-8", timeout=15, check=True)
    blocks = re.split(r"(?m)^- id: ", result.stdout)
    block = next((block for block in blocks if block.startswith("agent-default-model\n")), "")
    values = dict(re.findall(r"(?m)^ +(provider|model): *['\"]?([\w.-]+)", block))
    if values.keys() != {"provider", "model"}:
        raise ValueError("headless 默认 provider/model 不完整")
    return values


def read_native_models(path):
    rows = read_json(path)
    return read_models(rows.get("models", rows) if isinstance(rows, dict) else rows)


def compare(previous, current):
    changes = []
    for source, models in current.items():
        if source not in previous:
            changes.append(f"{source}：建立基线（{len(models)} 条）")
            continue
        old = previous[source]
        for key in sorted(models.keys() - old.keys()):
            changes.append(f"{source}：新增 {key}")
        for key in sorted(old.keys() - models.keys()):
            changes.append(f"{source}：下架/移除 {key}")
        for key in sorted(old.keys() & models.keys()):
            if old[key] != models[key]:
                changes.append(f"{source}：{key} 变更 {old[key]} → {models[key]}")
    return changes


def save_snapshot(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.close()
            temporary.replace(path)
        finally:
            handle.close()
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="模型变化雷达")
    parser.add_argument("--native-models-json", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--quiet-if-unchanged", action="store_true")
    args = parser.parse_args(argv)
    policy = load_policy()
    snapshot = tasks_dir() / "radar_snapshot.json"
    today = datetime.now(BJ_TZ).date()
    errors = []
    previous = {}
    if snapshot.exists():
        try:
            previous = read_json(snapshot)["sources"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"基线不可读：{exc}")
    readers = {"codex": read_codex_models, "dsh_catalog": read_dsh_catalog, "dsh_headless": read_dsh_default}
    if args.native_models_json:
        readers["native"] = lambda: read_native_models(args.native_models_json)
    current = {}
    for name, reader in readers.items():
        try:
            current[name] = reader()
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            errors.append(f"{name} 读取失败：{exc}")
    roles = resolve_codex_roles(policy, current.get("codex", {}))
    if "codex" in current:
        current["codex_roles"] = {name: role["slug"] for name, role in roles.items()}
    warnings = []
    alerts = {}
    for notice in policy.get("retirement_notices", []):
        days = (date.fromisoformat(notice["retires_on"]) - today).days
        if days <= 14:
            state = "已过计划下线日期" if days < 0 else f"距计划下线 {days} 天"
            key = f"{notice['pattern']} ({notice['retires_on']})"
            warnings.append(f"{key}：{state}；替代：{notice['replacement_hint']}")
            alerts[key] = "past" if days < 0 else "upcoming"
    dsh = policy["dsh_defaults"]
    age = (today - date.fromisoformat(dsh["half_price_rule_verified_at"])).days
    if age > dsh["half_price_review_days"]:
        warnings.append(f"DeepSeek 半价规则已 {age} 天未复核；请先核实再报价。")
        alerts["DeepSeek 半价规则"] = dsh["half_price_rule_verified_at"]
    current["alerts"] = alerts
    changes = compare(previous, current)
    if not args.no_save:
        save_snapshot(snapshot, {"date": today.isoformat(), "sources": {**previous, **current}})
    if args.quiet_if_unchanged and not (changes or errors):
        return 0
    if args.json:
        print(json.dumps({"date": today.isoformat(), "changes": changes, "warnings": warnings,
                          "errors": errors, "roles": roles, "sources": current}, ensure_ascii=False, indent=2))
    else:
        print(f"《模型变化雷达简报》 {today}")
        print("Codex：" + " · ".join(f"{role['code']} {role['slug'] or '不可用'}" for role in roles.values()))
        if current.get("dsh_catalog"):
            print("DeepSeek 目录：" + " · ".join(current["dsh_catalog"]))
        if current.get("dsh_headless"):
            print("DeepSeek 默认：{provider} / {model}".format(**current["dsh_headless"]))
        for line in [*(changes or ["未检测到变化"]), *warnings, *errors]:
            print(f"- {line}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
