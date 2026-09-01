#!/usr/bin/env python3
"""Single entry point for average-expression XLSX/TSV/CSV preflight."""

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook


def normalize_average(source: Path, output_dir: Path) -> Path:
    if source.suffix.lower() == ".xlsx":
        return source
    if source.suffix.lower() not in {".tsv", ".csv"}:
        raise ValueError("Average expression must be .xlsx, .tsv, or .csv")
    delimiter = "\t" if source.suffix.lower() == ".tsv" else ","
    normalized_dir = output_dir / "normalized_input"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    destination = normalized_dir / "cell_avg_exp.xlsx"
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Sheet1")
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle, delimiter=delimiter):
            sheet.append(row)
    workbook.save(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--avg", required=True)
    parser.add_argument("--markers", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--species", required=True)
    parser.add_argument("--tissue", required=True)
    parser.add_argument("--experimental-system", default="")
    parser.add_argument("--context-source", action="append", default=[])
    parser.add_argument("--annotation-level", choices=["major"], required=True)
    parser.add_argument("--parent-population", required=True)
    parser.add_argument("--parent-kind", choices=["auto", "lineage", "state", "mixed", "unknown"], default="auto")
    parser.add_argument("--ratios")
    parser.add_argument("--gene-map")
    parser.add_argument("--cell-evidence")
    parser.add_argument("--umap")
    parser.add_argument("--evidence-config")
    parser.add_argument("--knowledge-base")
    parser.add_argument("--project-prior")
    parser.add_argument("--project-major-label", action="append", default=[])
    parser.add_argument("--context-json")
    parser.add_argument("--annotation-constraints")
    parser.add_argument("--exclude-label", action="append", default=[])
    parser.add_argument("--exclude-marker", action="append", default=[])
    parser.add_argument("--allow-partial-ratios", action="store_true")
    parser.add_argument("--top-n", type=int, default=60)
    parser.add_argument("--informative-n", type=int, default=25)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    avg = normalize_average(Path(args.avg).resolve(), output_dir)
    prepare = Path(__file__).with_name("prepare_annotation.py")
    command = [
        sys.executable, str(prepare),
        "--avg", str(avg), "--markers", str(Path(args.markers).resolve()),
        "--output-dir", str(output_dir), "--workspace-root", args.workspace_root,
        "--species", args.species, "--tissue", args.tissue,
        "--experimental-system", args.experimental_system,
        "--annotation-level", args.annotation_level,
        "--parent-population", args.parent_population,
        "--parent-kind", args.parent_kind,
        "--top-n", str(args.top_n), "--informative-n", str(args.informative_n),
    ]
    for source in args.context_source:
        command.extend(["--context-source", source])
    for label in args.project_major_label:
        command.extend(["--project-major-label", label])
    if args.context_json:
        command.extend(["--context-json", args.context_json])
    if args.annotation_constraints:
        command.extend(["--annotation-constraints", args.annotation_constraints])
    for label in args.exclude_label:
        command.extend(["--exclude-label", label])
    for marker in args.exclude_marker:
        command.extend(["--exclude-marker", marker])
    if args.allow_partial_ratios:
        command.append("--allow-partial-ratios")
    for flag, value in (
        ("--ratios", args.ratios),
        ("--gene-map", args.gene_map),
        ("--cell-evidence", args.cell_evidence),
        ("--umap", args.umap),
        ("--evidence-config", args.evidence_config),
        ("--knowledge-base", args.knowledge_base),
        ("--project-prior", args.project_prior),
    ):
        if value:
            command.extend([flag, value])
    completed = subprocess.run(command, check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
