#!/usr/bin/env python3
"""Run every registered regression suite in parallel and aggregate failures."""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
MARKETPLACE = SKILL.parents[3]
REGISTRY = Path(__file__).with_name("regression-registry.v1.json")


def run_suite(suite, work_root):
    script = MARKETPLACE / suite["script"]
    work_dir = work_root / suite["work_subdir"]
    work_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, str(script), "--work-dir", str(work_dir)],
        text=True,
        capture_output=True,
    )
    return {
        "id": suite["id"],
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work_root = Path(args.work_dir).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    suites = registry["suites"]
    results = []
    with ThreadPoolExecutor(max_workers=len(suites)) as executor:
        pending = {executor.submit(run_suite, suite, work_root): suite for suite in suites}
        for future in as_completed(pending):
            results.append(future.result())
    results.sort(key=lambda item: item["id"])
    failed = [item for item in results if item["returncode"] != 0]
    report = {
        "status": "fail" if failed else "pass",
        "registry": str(REGISTRY),
        "suite_count": len(suites),
        "all_registered_suites_ran": len(results) == len(suites),
        "results": results,
    }
    report_path = work_root / "registered_regression_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
