#!/usr/bin/env python3
"""Shared, transactional case registry and knowledge promotion for annotation skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_POLICY = HERE / "policy.v1.json"
DEFAULT_CANONICAL_KB = HERE.parent / "sc-annotation-evidence-core" / "knowledge-base" / "cell-annotation-knowledge-base.v2.json"


def discover_workspace_root():
    configured = os.environ.get("CODEX_SHARED_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "skill-pack.json").is_file():
            return parent.parent
    raise RuntimeError(
        "Shared workspace could not be resolved. Run Install-PersonalSkillMarketplace.ps1 "
        "or set CODEX_SHARED_WORKSPACE_ROOT."
    )


DEFAULT_STORE = discover_workspace_root() / ".sc-annotation-knowledge"
SCHEMA_VERSION = 1


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def parse_version(value):
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)", str(value or ""))
    return tuple(int(item) for item in match.groups()) if match else (0, 0, 0)


def split_tokens(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[;,|]", str(value or "")) if item.strip()]


def marker_tokens(value):
    ignored = {"CELL", "PROGRAM", "HIGH", "LOW", "ABSENT", "MARKER", "MARKERS", "AND", "OR"}
    result = []
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9-]{1,20}\b", str(value or "")):
        gene = token.upper()
        if gene not in ignored and gene not in result:
            result.append(gene)
    return result


def literature_keys(record):
    text = str(record.get("literature_source", ""))
    keys = set()
    keys.update("PMID:" + item for item in re.findall(r"PMID\s*[:：]?\s*(\d+)", text, re.I))
    keys.update("DOI:" + item.lower().rstrip(".,;)") for item in re.findall(r"10\.\d{4,9}/[^\s;，]+", text, re.I))
    details = record.get("literature_details", [])
    if isinstance(details, dict):
        details = [details]
    normalized = []
    for item in details if isinstance(details, list) else []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("pmid") or item.get("doi") or item.get("url") or "").strip()
        if key:
            if item.get("pmid"):
                key = "PMID:" + str(item["pmid"])
            elif item.get("doi"):
                key = "DOI:" + str(item["doi"]).lower()
            keys.add(key)
            normalized.append({**item, "source_key": key})
    return sorted(keys), normalized


def project_key(path):
    name = Path(path).name.lower()
    name = re.sub(r"(?:revision|rev|version|ver|v)[_-]?\d+", "", name)
    name = re.sub(r"20\d{6}(?:\d{6})?", "", name)
    name = re.sub(r"[_-]+", "_", name).strip("_")
    return name or Path(path).name.lower()


def infer_skill(qa):
    source = str(qa.get("annotation_evidence_policy", {}).get("knowledge_base_source", ""))
    for name in ("sc-major-celltype-annotation-auto", "sc-marker-cluster-annotation-auto"):
        match = re.search(re.escape(name) + r"[\\/]+([^\\/]+)", source)
        if match:
            return name, match.group(1)
    return "", ""


def connect(store):
    store.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(store / "annotation_cases.sqlite3", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cases(
          id INTEGER PRIMARY KEY, case_uuid TEXT NOT NULL UNIQUE, case_key TEXT NOT NULL UNIQUE,
          dataset_fingerprint TEXT NOT NULL, project_key TEXT NOT NULL, project_path TEXT NOT NULL,
          project_path_hash TEXT NOT NULL, skill_name TEXT NOT NULL, skill_version TEXT NOT NULL,
          annotation_level TEXT NOT NULL, parent_population TEXT, species TEXT, tissue TEXT,
          qa_path TEXT NOT NULL, records_path TEXT NOT NULL, evidence_path TEXT,
          qa_sha256 TEXT NOT NULL, records_sha256 TEXT NOT NULL, evidence_sha256 TEXT,
          registered_at TEXT NOT NULL, snapshot_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cases_dataset ON cases(dataset_fingerprint);
        CREATE TABLE IF NOT EXISTS observations(
          id INTEGER PRIMARY KEY, case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
          identity_id TEXT NOT NULL, label_basis TEXT, node_kind TEXT, risk_class TEXT NOT NULL,
          eligible_for_promotion INTEGER NOT NULL, cluster_count INTEGER NOT NULL,
          supporting_markers_json TEXT NOT NULL, conflicting_markers_json TEXT NOT NULL,
          parent_path_json TEXT NOT NULL, tissue_scope_json TEXT NOT NULL,
          panel_species TEXT, direct_species_evidence INTEGER NOT NULL,
          marker_observation_complete INTEGER NOT NULL, confidence TEXT,
          source_record_json TEXT NOT NULL, UNIQUE(case_id, identity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_obs_identity ON observations(identity_id);
        CREATE TABLE IF NOT EXISTS literature(
          id INTEGER PRIMARY KEY, observation_id INTEGER NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
          source_key TEXT NOT NULL, metadata_complete INTEGER NOT NULL, metadata_json TEXT NOT NULL,
          UNIQUE(observation_id, source_key)
        );
        CREATE TABLE IF NOT EXISTS identity_status(
          identity_id TEXT PRIMARY KEY, stage TEXT NOT NULL, risk_class TEXT NOT NULL,
          independent_cases INTEGER NOT NULL, independent_projects INTEGER NOT NULL,
          literature_sources INTEGER NOT NULL, target_species_cases INTEGER NOT NULL,
          core_marker_consistency REAL NOT NULL, blockers_json TEXT NOT NULL,
          summary_json TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, event_time TEXT NOT NULL, event_type TEXT NOT NULL,
          case_uuid TEXT, identity_id TEXT, payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS publications(
          id INTEGER PRIMARY KEY, identity_id TEXT NOT NULL, from_version TEXT NOT NULL,
          to_version TEXT NOT NULL, published_at TEXT NOT NULL, report_path TEXT NOT NULL,
          snapshot_path TEXT NOT NULL, payload_json TEXT NOT NULL
        );
        """
    )
    conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    conn.commit()


def ensure_store(store, canonical_kb=DEFAULT_CANONICAL_KB):
    store = Path(store)
    conn = connect(store)
    init_schema(conn)
    current = store / "published" / "current" / "cell-annotation-knowledge-base.v2.json"
    if not current.is_file():
        baseline = load_json(canonical_kb)
        atomic_json(current, baseline)
        baseline_version = str(baseline.get("knowledge_base_version") or "baseline")
        baseline_snapshot = store / "published" / "versions" / baseline_version / current.name
        if not baseline_snapshot.is_file():
            atomic_json(baseline_snapshot, baseline)
        atomic_json(current.with_name("publication-manifest.json"), {
            "status": "baseline", "knowledge_base_version": baseline.get("knowledge_base_version"),
            "published_at": now_utc(), "sha256": sha256_file(current), "source": str(Path(canonical_kb).resolve()),
            "snapshot": str(baseline_snapshot)
        })
    else:
        active = load_json(current)
        active_version = str(active.get("knowledge_base_version") or "baseline")
        active_snapshot = store / "published" / "versions" / active_version / current.name
        if not active_snapshot.is_file():
            atomic_json(active_snapshot, active)
        manifest_path = current.with_name("publication-manifest.json")
        manifest = load_json(manifest_path) if manifest_path.is_file() else {}
        if not manifest.get("snapshot"):
            manifest["snapshot"] = str(active_snapshot)
            atomic_json(manifest_path, manifest)
    return conn


def metadata_from(qa, evidence):
    policy = qa.get("annotation_evidence_policy", {})
    confirmed = (evidence or {}).get("confirmed_metadata", {})
    return {
        "species": confirmed.get("species") or policy.get("species") or "",
        "tissue": confirmed.get("tissue") or policy.get("tissue") or "",
        "annotation_level": confirmed.get("annotation_level") or ("subcluster" if "hierarchy_depth_policy" in qa else "major"),
        "parent_population": confirmed.get("parent_population") or "",
        "parent_kind": confirmed.get("parent_kind") or "",
    }


def dataset_fingerprint(project_dir, records, qa, evidence, meta):
    paths = (evidence or {}).get("source_paths", {})
    file_hashes = []
    for key in ("cell_avg_exp", "marker_table", "expression_ratio_table", "umap"):
        candidate = Path(str(paths.get(key, "")))
        if candidate.is_file():
            file_hashes.append((key, sha256_file(candidate)))
    if file_hashes:
        basis = {"species": meta["species"], "files": file_hashes}
    else:
        basis = {
            "species": meta["species"], "tissue": meta["tissue"], "project": project_key(project_dir),
            "clusters": sorted(str(item.get("cluster_id", "")) for item in records),
            "record_count": qa.get("record_count", len(records))
        }
    return stable_hash(basis)


def group_observations(records, meta):
    grouped = defaultdict(list)
    for record in records:
        identity = str(record.get("stable_id") or record.get("canonical_subtype") or record.get("fine_type") or record.get("celltype_en") or "").strip()
        if identity:
            grouped[identity].append(record)
    observations = []
    for identity, items in grouped.items():
        clean_items = [
            row for row in items
            if not bool(row.get("mixed_or_doublet") or row.get("mixed_population") or row.get("suspected_doublet"))
        ]
        evidence_items = clean_items or items
        supporting, conflicting, parent_paths, scopes, literature = set(), set(), [], set(), {}
        for item in evidence_items:
            supporting.update(marker_tokens(item.get("supporting_markers")))
            conflicting.update(marker_tokens(item.get("conflicting_markers")))
            path = item.get("parent_path", [])
            if isinstance(path, list) and path:
                parent_paths.append(tuple(str(part) for part in path))
            scopes.update(split_tokens(item.get("tissue_scope", [])))
            keys, details = literature_keys(item)
            detail_by_key = {detail["source_key"]: detail for detail in details}
            for key in keys:
                literature[key] = detail_by_key.get(key, {"source_key": key})
        exemplar = max(evidence_items, key=lambda row: float(row.get("quality_score") or 0))
        mixed_only = not clean_items
        node_kind = str(exemplar.get("ontology_node_kind") or "identity")
        external = any(str(row.get("label_basis")) == "validated_external_candidate" for row in items)
        rare = external or bool(scopes) or any("validated_external" in str(row.get("tissue_module", "")) for row in items)
        eligible = identity != "Cell" and not mixed_only and node_kind not in {"state", "disease_role_or_state", "mixed_population", "doublet"}
        complete = all(bool(row.get("marker_observation_complete")) and isinstance(row.get("evaluated_markers"), dict) for row in evidence_items)
        observations.append({
            "identity_id": identity, "label_basis": str(exemplar.get("label_basis", "")),
            "node_kind": node_kind, "risk_class": "rare_or_context_specific" if rare else "normal",
            "eligible": int(eligible), "cluster_count": len(evidence_items), "supporting": sorted(supporting),
            "conflicting": sorted(conflicting), "parent_path": list(Counter(parent_paths).most_common(1)[0][0]) if parent_paths else [],
            "tissue_scope": sorted(scopes), "panel_species": str(exemplar.get("panel_species") or meta["species"]),
            "direct_species": int(not bool(exemplar.get("cross_species_inference"))), "complete": int(complete),
            "confidence": str(exemplar.get("confidence", "")), "exemplar": exemplar,
            "literature": literature
        })
    return observations


def register_case(store, records_path, qa_path, evidence_path=None, project_dir=None, skill_name=None, skill_version=None, policy_path=DEFAULT_POLICY):
    policy = load_json(policy_path)
    store = Path(store)
    conn = ensure_store(store)
    records_path, qa_path = Path(records_path).resolve(), Path(qa_path).resolve()
    project_dir = Path(project_dir or records_path.parent).resolve()
    evidence_path = Path(evidence_path).resolve() if evidence_path and Path(evidence_path).is_file() else None
    qa, records = load_json(qa_path), load_json(records_path)
    evidence = load_json(evidence_path) if evidence_path else {}
    if qa.get("status") != "pass":
        raise ValueError("Case registration requires QA status=pass")
    inferred_name, inferred_version = infer_skill(qa)
    skill_name, skill_version = skill_name or inferred_name, skill_version or inferred_version
    minimum = policy["eligible_skills"].get(skill_name)
    if not minimum or parse_version(skill_version) < parse_version(minimum):
        raise ValueError(f"Ineligible skill/version: {skill_name} {skill_version}; minimum={minimum}")
    meta = metadata_from(qa, evidence)
    fingerprint = dataset_fingerprint(project_dir, records, qa, evidence, meta)
    case_key = stable_hash({"dataset": fingerprint, "level": meta["annotation_level"], "parent": meta["parent_population"], "skill": skill_name})
    case_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "sc-annotation-case:" + case_key))
    observations = group_observations(records, meta)
    snapshot = {
        "case_uuid": case_uuid, "dataset_fingerprint": fingerprint, "project_key": project_key(project_dir),
        "skill_name": skill_name, "skill_version": skill_version, **meta,
        "qa_sha256": sha256_file(qa_path), "records_sha256": sha256_file(records_path),
        "evidence_sha256": sha256_file(evidence_path) if evidence_path else "",
        "observation_count": len(observations), "registered_at": now_utc()
    }
    with conn:
        existing = conn.execute("SELECT case_uuid FROM cases WHERE case_key=?", (case_key,)).fetchone()
        if existing:
            conn.execute("INSERT INTO events(event_time,event_type,case_uuid,payload_json) VALUES(?,?,?,?)", (now_utc(), "duplicate_case_ignored", existing[0], json.dumps(snapshot, ensure_ascii=False)))
            result = {"status": "duplicate", "case_uuid": existing[0], "observation_count": len(observations)}
        else:
            cursor = conn.execute(
                """INSERT INTO cases(case_uuid,case_key,dataset_fingerprint,project_key,project_path,project_path_hash,
                skill_name,skill_version,annotation_level,parent_population,species,tissue,qa_path,records_path,evidence_path,
                qa_sha256,records_sha256,evidence_sha256,registered_at,snapshot_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (case_uuid, case_key, fingerprint, snapshot["project_key"], str(project_dir), stable_hash(str(project_dir)), skill_name,
                 skill_version, meta["annotation_level"], meta["parent_population"], meta["species"], meta["tissue"], str(qa_path),
                 str(records_path), str(evidence_path or ""), snapshot["qa_sha256"], snapshot["records_sha256"], snapshot["evidence_sha256"],
                 snapshot["registered_at"], json.dumps(snapshot, ensure_ascii=False))
            )
            case_id = cursor.lastrowid
            for obs in observations:
                cursor = conn.execute(
                    """INSERT INTO observations(case_id,identity_id,label_basis,node_kind,risk_class,eligible_for_promotion,cluster_count,
                    supporting_markers_json,conflicting_markers_json,parent_path_json,tissue_scope_json,panel_species,direct_species_evidence,
                    marker_observation_complete,confidence,source_record_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (case_id, obs["identity_id"], obs["label_basis"], obs["node_kind"], obs["risk_class"], obs["eligible"], obs["cluster_count"],
                     json.dumps(obs["supporting"]), json.dumps(obs["conflicting"]), json.dumps(obs["parent_path"]), json.dumps(obs["tissue_scope"]),
                     obs["panel_species"], obs["direct_species"], obs["complete"], obs["confidence"], json.dumps(obs["exemplar"], ensure_ascii=False))
                )
                for key, detail in obs["literature"].items():
                    complete = int(bool(detail.get("title")) and bool(detail.get("doi") or detail.get("pmid")) and bool(detail.get("species")) and bool(detail.get("tissue")))
                    conn.execute("INSERT INTO literature(observation_id,source_key,metadata_complete,metadata_json) VALUES(?,?,?,?)", (cursor.lastrowid, key, complete, json.dumps(detail, ensure_ascii=False)))
            conn.execute("INSERT INTO events(event_time,event_type,case_uuid,payload_json) VALUES(?,?,?,?)", (now_utc(), "case_registered", case_uuid, json.dumps(snapshot, ensure_ascii=False)))
            result = {"status": "registered", "case_uuid": case_uuid, "observation_count": len(observations)}
    evaluation = evaluate_all(conn, store, policy)
    result["evaluation"] = evaluation
    conn.close()
    return result


def approved_ids(store):
    kb = load_json(Path(store) / "published" / "current" / "cell-annotation-knowledge-base.v2.json")
    return {row.get("cell_id") for row in kb.get("ontology", []) if row.get("proposed_status") == "Approve" or row.get("approval_status") == "Approve"}, kb


def identity_summary(conn, identity, policy, existing):
    rows = conn.execute(
        """SELECT o.*,c.dataset_fingerprint,c.project_key,c.species,c.tissue,c.annotation_level
        FROM observations o JOIN cases c ON c.id=o.case_id WHERE o.identity_id=? AND o.eligible_for_promotion=1""", (identity,)
    ).fetchall()
    datasets = {row["dataset_fingerprint"] for row in rows}
    projects = {row["project_key"] for row in rows}
    literature = conn.execute("SELECT DISTINCT l.source_key,l.metadata_complete FROM literature l JOIN observations o ON o.id=l.observation_id WHERE o.identity_id=?", (identity,)).fetchall()
    genes = Counter()
    for row in rows:
        genes.update(set(json.loads(row["supporting_markers_json"])))
    frequencies = {gene: count / max(len(datasets), 1) for gene, count in genes.items()}
    complete_rows = [row for row in rows if row["marker_observation_complete"]]
    complete_datasets = {row["dataset_fingerprint"] for row in complete_rows}
    marker_stats_by_species = {}
    for species in sorted({row["species"] for row in complete_rows if row["species"]}):
        species_rows = [row for row in complete_rows if row["species"] == species]
        species_datasets = {row["dataset_fingerprint"] for row in species_rows}
        support_counts, conflict_counts = Counter(), Counter()
        for row in species_rows:
            support_counts.update(set(json.loads(row["supporting_markers_json"])))
            conflict_counts.update(set(json.loads(row["conflicting_markers_json"])))
        marker_stats_by_species[species] = {
            "case_count": len(species_datasets),
            "support_frequency": {gene: count / max(len(species_datasets), 1) for gene, count in support_counts.items()},
            "conflict_frequency": {gene: count / max(len(species_datasets), 1) for gene, count in conflict_counts.items()},
        }
    core = sorted(gene for gene, freq in frequencies.items() if freq >= 0.8)
    consistency = min(1.0, len(core) / 2) if rows else 0.0
    risk = "rare_or_context_specific" if any(row["risk_class"] == "rare_or_context_specific" for row in rows) else "normal"
    rules = policy["rare_or_context_specific_identity" if risk.startswith("rare") else "normal_identity"]
    complete_lit = sum(1 for row in literature if row["metadata_complete"])
    direct_cases = len({row["dataset_fingerprint"] for row in rows if row["direct_species_evidence"]})
    blockers = []
    if len(datasets) < rules["approval_cases"]: blockers.append(f"independent_cases<{rules['approval_cases']}")
    if len(projects) < rules["minimum_project_sources"]: blockers.append(f"independent_projects<{rules['minimum_project_sources']}")
    if len(literature) < rules["minimum_literature_sources"]: blockers.append(f"literature_sources<{rules['minimum_literature_sources']}")
    if policy["publication"]["require_complete_literature_metadata"] and complete_lit < rules["minimum_literature_sources"]: blockers.append("literature_metadata_incomplete")
    if consistency < rules["minimum_core_marker_consistency"]: blockers.append("core_marker_consistency_below_threshold")
    if risk.startswith("rare") and direct_cases < rules["minimum_target_species_cases"]: blockers.append(f"target_species_cases<{rules['minimum_target_species_cases']}")
    if identity in existing:
        stage = "approved"
    elif len(datasets) >= rules["supported_cases"]:
        stage = "supported_candidate"
    elif len(datasets) >= rules["candidate_cases"]:
        stage = "candidate"
    else:
        stage = "observed"
    return {
        "identity_id": identity, "stage": stage, "risk_class": risk, "independent_cases": len(datasets),
        "independent_projects": len(projects), "literature_sources": len(literature), "complete_literature_sources": complete_lit,
        "target_species_cases": direct_cases, "core_marker_consistency": consistency, "core_markers": core,
        "supportive_markers": sorted(gene for gene, freq in frequencies.items() if 0.5 <= freq < 0.8),
        "complete_marker_cases": len(complete_datasets), "marker_stats_by_species": marker_stats_by_species,
        "blockers": blockers, "eligible_for_auto_publication": identity not in existing and not blockers,
        "eligible_for_marker_update": identity in existing and len(complete_datasets) >= rules["approval_cases"] and len(projects) >= rules["minimum_project_sources"],
    }


def evaluate_all(conn, store, policy):
    existing, _ = approved_ids(store)
    identities = [row[0] for row in conn.execute("SELECT DISTINCT identity_id FROM observations ORDER BY identity_id")]
    promoted = []
    summaries = []
    for identity in identities:
        summary = identity_summary(conn, identity, policy, existing)
        summaries.append(summary)
        with conn:
            conn.execute(
                """INSERT INTO identity_status(identity_id,stage,risk_class,independent_cases,independent_projects,literature_sources,
                target_species_cases,core_marker_consistency,blockers_json,summary_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(identity_id) DO UPDATE SET stage=excluded.stage,risk_class=excluded.risk_class,
                independent_cases=excluded.independent_cases,independent_projects=excluded.independent_projects,
                literature_sources=excluded.literature_sources,target_species_cases=excluded.target_species_cases,
                core_marker_consistency=excluded.core_marker_consistency,blockers_json=excluded.blockers_json,
                summary_json=excluded.summary_json,updated_at=excluded.updated_at""",
                (identity, summary["stage"], summary["risk_class"], summary["independent_cases"], summary["independent_projects"],
                 summary["literature_sources"], summary["target_species_cases"], summary["core_marker_consistency"],
                 json.dumps(summary["blockers"]), json.dumps(summary, ensure_ascii=False), now_utc())
            )
        if summary["eligible_for_auto_publication"]:
            publication = publish_identity(conn, Path(store), policy, summary)
            if publication.get("status") == "published":
                promoted.append(publication)
                existing.add(identity)
        elif summary["eligible_for_marker_update"]:
            publication = publish_marker_update(conn, Path(store), policy, summary)
            if publication.get("status") == "published":
                promoted.append(publication)
    return {"identity_count": len(summaries), "promoted": promoted, "summaries": summaries}


def next_patch(version):
    major, minor, patch = parse_version(version)
    return f"{major}.{minor}.{patch + 1}"


def apply_empirical_marker_updates(kb, summary, policy):
    identity = summary["identity_id"]
    changed = []
    core_cutoff = policy["publication"]["marker_core_frequency"]
    supportive_cutoff = policy["publication"]["marker_supportive_frequency"]
    for species, stats in summary.get("marker_stats_by_species", {}).items():
        panels = [row for row in kb.get("marker_panels", []) if row.get("cell_id") == identity and row.get("target_species") == species and row.get("approval_status") == "Approve"]
        for panel in panels:
            core = split_tokens(panel.get("core_markers"))
            supportive = split_tokens(panel.get("supportive_markers"))
            deprecated = split_tokens(panel.get("deprecated_markers"))
            additions = sorted(gene for gene, freq in stats["support_frequency"].items() if freq >= supportive_cutoff and gene not in core and gene not in supportive)
            downweighted = sorted(gene for gene, freq in stats["conflict_frequency"].items() if freq >= core_cutoff and gene in core)
            if additions:
                supportive.extend(additions)
            for gene in downweighted:
                core.remove(gene)
                if gene not in supportive:
                    supportive.append(gene)
                if gene not in deprecated:
                    deprecated.append(gene)
            if additions or downweighted:
                panel["core_markers"] = ";".join(core)
                panel["supportive_markers"] = ";".join(supportive)
                panel["deprecated_markers"] = ";".join(deprecated)
                panel["empirical_update_note"] = f"Auto-updated from {stats['case_count']} complete independent datasets; no marker was hard-deleted"
                changed.append({"species": species, "supportive_added": additions, "core_downweighted": downweighted})
    return changed


def publish_marker_update(conn, store, policy, summary):
    identity = summary["identity_id"]
    current = store / "published" / "current" / "cell-annotation-knowledge-base.v2.json"
    kb = load_json(current)
    changes = apply_empirical_marker_updates(kb, summary, policy)
    if not changes:
        return {"status": "unchanged", "identity_id": identity}
    old_version = kb.get("knowledge_base_version", "0.0.0")
    new_version = next_patch(old_version)
    kb["knowledge_base_version"] = new_version
    kb["approved_at"] = datetime.now().date().isoformat()
    candidate_dir = store / "staging" / f"kb-{new_version}-{identity}-marker-update"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / current.name
    atomic_json(candidate, kb)
    regression = publication_regression(conn, candidate, store)
    if regression["status"] != "pass":
        return {"status": "blocked", "identity_id": identity, "reason": "historical_regression_failed", "regression": regression}
    version_dir = store / "published" / "versions" / new_version
    version_dir.mkdir(parents=True, exist_ok=False)
    snapshot = version_dir / current.name
    atomic_json(snapshot, kb)
    shutil.copyfile(snapshot, current)
    report = version_dir / "变更报告.md"
    report.write_text(
        f"# 细胞注释 Marker 规则自动更新\n\n- 身份：`{identity}`\n- 版本：`{old_version}` → `{new_version}`\n"
        f"- 完整独立数据集：{summary['complete_marker_cases']}\n- 调整：`{json.dumps(changes, ensure_ascii=False)}`\n"
        "- 删除策略：未永久删除任何 Marker；冲突核心 Marker 仅降权并保留在 deprecated_markers。\n- 历史回归：通过\n",
        encoding="utf-8"
    )
    manifest = {"status": "published", "change_type": "marker_update", "identity_id": identity, "from_version": old_version,
                "knowledge_base_version": new_version, "published_at": now_utc(), "sha256": sha256_file(current),
                "snapshot": str(snapshot), "report": str(report), "changes": changes, "regression": regression}
    atomic_json(current.with_name("publication-manifest.json"), manifest)
    with conn:
        conn.execute("INSERT INTO publications(identity_id,from_version,to_version,published_at,report_path,snapshot_path,payload_json) VALUES(?,?,?,?,?,?,?)",
                     (identity, old_version, new_version, manifest["published_at"], str(report), str(snapshot), json.dumps(manifest, ensure_ascii=False)))
        conn.execute("INSERT INTO events(event_time,event_type,identity_id,payload_json) VALUES(?,?,?,?)", (now_utc(), "marker_rules_published", identity, json.dumps(manifest, ensure_ascii=False)))
    return manifest


def publish_identity(conn, store, policy, summary):
    identity = summary["identity_id"]
    current = store / "published" / "current" / "cell-annotation-knowledge-base.v2.json"
    kb = load_json(current)
    rows = conn.execute("SELECT o.*,c.species,c.tissue,c.annotation_level FROM observations o JOIN cases c ON c.id=o.case_id WHERE o.identity_id=? AND o.eligible_for_promotion=1", (identity,)).fetchall()
    paths = [json.loads(row["parent_path_json"]) for row in rows if json.loads(row["parent_path_json"])]
    parent_path = list(Counter(tuple(path) for path in paths).most_common(1)[0][0]) if paths else []
    parent = parent_path[-2] if len(parent_path) >= 2 and parent_path[-1] == identity else (parent_path[-1] if parent_path else "")
    known = {row.get("cell_id") for row in kb.get("ontology", [])}
    if not parent or parent not in known:
        return {"status": "blocked", "identity_id": identity, "reason": "approved_parent_missing"}
    species = Counter(row["species"] for row in rows if row["species"]).most_common(1)[0][0]
    tissues = sorted({row["tissue"] for row in rows if row["tissue"]})
    literature = conn.execute("SELECT DISTINCT l.source_key,l.metadata_json FROM literature l JOIN observations o ON o.id=l.observation_id WHERE o.identity_id=? AND l.metadata_complete=1", (identity,)).fetchall()
    source_ids = []
    existing_source_ids = {row.get("source_id") for row in kb.get("evidence_sources", [])}
    for index, source in enumerate(literature, 1):
        meta = json.loads(source["metadata_json"])
        source_id = "AUTO_" + hashlib.sha1(source["source_key"].encode()).hexdigest()[:10].upper()
        source_ids.append(source_id)
        if source_id not in existing_source_ids:
            kb["evidence_sources"].append({
                "source_id": source_id, "short_name": meta.get("title", source["source_key"]),
                "source_type": meta.get("source_type", "peer_reviewed_literature"), "title": meta.get("title", ""),
                "year": meta.get("year", ""), "journal": meta.get("journal", ""), "doi": meta.get("doi", ""),
                "pmid": meta.get("pmid", ""), "url_or_path": meta.get("url", ""),
                "relevance": f"Auto-promoted evidence for {identity}; species={meta.get('species','')}; tissue={meta.get('tissue','')}",
                "authority_gate": "Yes"
            })
    major_seen = any(row["annotation_level"] == "major" for row in rows)
    sub_seen = any(row["annotation_level"] == "subcluster" for row in rows)
    kb["ontology"].append({
        "cell_id": identity, "name_en": identity, "name_cn": "", "parent_id": parent,
        "branch": next((item.get("branch") for item in kb["ontology"] if item.get("cell_id") == parent), parent),
        "node_kind": "identity", "tissue_scope": ";".join(tissues) or "multi_tissue",
        "major_output_allowed": "Yes" if major_seen else "No", "subcluster_output_allowed": "Yes" if sub_seen else "No",
        "external_ontology_id": "", "ontology_lookup_name": identity.replace("_", " ").lower(), "aliases": "",
        "evidence_ids": ";".join(source_ids), "evidence_gate": "Meets_auto_case_regression",
        "proposed_status": "Approve", "review_note": f"Automatically promoted from {summary['independent_cases']} independent datasets"
    })
    for target_species in sorted({row["species"] for row in rows if row["species"]}):
        kb["marker_panels"].append({
            "cell_id": identity, "target_species": target_species, "panel_species": target_species,
            "cross_species_inference": "No", "core_markers": ";".join(summary["core_markers"]),
            "supportive_markers": ";".join(summary["supportive_markers"]), "exclusion_markers": "",
            "confounders": "See registered competing-lineage evidence snapshots",
            "decision_rule": "Require a coherent multi-marker program and absence of registered hard competing-lineage conflicts",
            "evidence_ids": ";".join(source_ids), "evidence_gate": "Meets_auto_case_regression", "approval_status": "Approve"
        })
    old_version = kb.get("knowledge_base_version", "0.0.0")
    new_version = next_patch(old_version)
    kb["knowledge_base_version"] = new_version
    kb["approved_at"] = datetime.now().date().isoformat()
    candidate_dir = store / "staging" / f"kb-{new_version}-{identity}"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "cell-annotation-knowledge-base.v2.json"
    atomic_json(candidate, kb)
    regression = publication_regression(conn, candidate, store)
    if regression["status"] != "pass":
        return {"status": "blocked", "identity_id": identity, "reason": "historical_regression_failed", "regression": regression}
    version_dir = store / "published" / "versions" / new_version
    version_dir.mkdir(parents=True, exist_ok=False)
    snapshot = version_dir / candidate.name
    shutil.copyfile(candidate, snapshot)
    current.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(candidate, current)
    report = version_dir / "变更报告.md"
    report.write_text(
        f"# 细胞注释知识库自动升级\n\n- 新增身份：`{identity}`\n- 版本：`{old_version}` → `{new_version}`\n"
        f"- 独立数据集：{summary['independent_cases']}\n- 独立项目来源：{summary['independent_projects']}\n"
        f"- 文献来源：{summary['literature_sources']}\n- 核心 Marker：{';'.join(summary['core_markers'])}\n"
        f"- 历史案例回归：通过\n- 回滚：将 `published/versions/{old_version}` 的快照重新发布为 current。\n",
        encoding="utf-8"
    )
    manifest = {"status": "published", "identity_id": identity, "from_version": old_version, "knowledge_base_version": new_version,
                "published_at": now_utc(), "sha256": sha256_file(current), "snapshot": str(snapshot), "report": str(report), "regression": regression}
    atomic_json(current.with_name("publication-manifest.json"), manifest)
    with conn:
        conn.execute("INSERT INTO publications(identity_id,from_version,to_version,published_at,report_path,snapshot_path,payload_json) VALUES(?,?,?,?,?,?,?)",
                     (identity, old_version, new_version, manifest["published_at"], str(report), str(snapshot), json.dumps(manifest, ensure_ascii=False)))
        conn.execute("INSERT INTO events(event_time,event_type,identity_id,payload_json) VALUES(?,?,?,?)", (now_utc(), "knowledge_published", identity, json.dumps(manifest, ensure_ascii=False)))
    return manifest


def historical_regression(conn, kb):
    ontology = {row.get("cell_id") for row in kb.get("ontology", [])}
    panels = {row.get("cell_id") for row in kb.get("marker_panels", []) if row.get("approval_status") == "Approve"}
    failures = []
    for row in conn.execute("SELECT DISTINCT identity_id FROM observations WHERE eligible_for_promotion=1"):
        identity = row[0]
        if identity in ontology and identity not in panels:
            failures.append({"identity_id": identity, "reason": "approved_identity_without_marker_panel"})
    return {"status": "fail" if failures else "pass", "registered_identity_count": conn.execute("SELECT COUNT(DISTINCT identity_id) FROM observations").fetchone()[0], "failures": failures}


def publication_regression(conn, candidate_path, store):
    kb = load_json(candidate_path)
    internal = historical_regression(conn, kb)
    if internal["status"] != "pass":
        return {"status": "fail", "internal": internal, "registered": {"status": "not_run"}}
    marketplace = HERE.parents[1]
    runner = marketplace / "plugins" / "sc-marker-cluster-annotation-auto" / "skills" / "sc-marker-cluster-annotation-auto" / "tests" / "run_registered_regressions.py"
    if not runner.is_file():
        return {"status": "fail", "internal": internal, "registered": {"status": "missing", "runner": str(runner)}}
    work_dir = Path(store) / "regression-runs" / (datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    env = dict(os.environ)
    env["SC_ANNOTATION_KB_PATH"] = str(Path(candidate_path).resolve())
    completed = subprocess.run(
        [sys.executable, str(runner), "--work-dir", str(work_dir)],
        text=True, capture_output=True, env=env
    )
    report_path = work_dir / "registered_regression_report.json"
    registered = load_json(report_path) if report_path.is_file() else {
        "status": "fail", "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]
    }
    return {
        "status": "pass" if registered.get("status") == "pass" and completed.returncode == 0 else "fail",
        "internal": internal, "registered": registered, "report_path": str(report_path)
    }


def scan_outputs(store, outputs_root, policy_path=DEFAULT_POLICY):
    policy = load_json(policy_path)
    outputs_root = Path(outputs_root).resolve()
    excluded = [re.compile(item, re.I) for item in policy["scan_excluded_name_patterns"]]
    candidates = []
    for qa_path in outputs_root.rglob("*.qa.json"):
        relative_parts = qa_path.relative_to(outputs_root).parts
        if not relative_parts or any(pattern.search(relative_parts[0]) for pattern in excluded):
            continue
        project_dir = outputs_root / relative_parts[0]
        records_path = qa_path.parent / "annotation_records.json"
        if not records_path.is_file():
            continue
        try:
            qa = load_json(qa_path)
            skill_name, skill_version = infer_skill(qa)
            minimum = policy["eligible_skills"].get(skill_name)
            if qa.get("status") != "pass" or not minimum or parse_version(skill_version) < parse_version(minimum):
                continue
            evidence_path = qa_path.parent / "annotation_evidence_pack.json"
            candidates.append({"qa": qa_path, "records": records_path, "evidence": evidence_path if evidence_path.is_file() else None,
                               "project": project_dir, "skill": skill_name, "version": skill_version, "mtime": qa_path.stat().st_mtime,
                               "group": (project_key(project_dir), skill_name)})
        except Exception:
            continue
    latest = {}
    for item in candidates:
        if item["group"] not in latest or item["mtime"] > latest[item["group"]]["mtime"]:
            latest[item["group"]] = item
    results = []
    for item in sorted(latest.values(), key=lambda value: value["mtime"]):
        try:
            results.append(register_case(store, item["records"], item["qa"], item["evidence"], item["project"], item["skill"], item["version"], policy_path))
        except Exception as exc:
            results.append({"status": "failed", "project": str(item["project"]), "error": str(exc)})
    return {"status": "complete", "eligible_projects": len(latest), "results": results}


def status(store):
    conn = ensure_store(Path(store))
    result = {
        "store": str(Path(store).resolve()),
        "case_count": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
        "observation_count": conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
        "identity_count": conn.execute("SELECT COUNT(DISTINCT identity_id) FROM observations").fetchone()[0],
        "stages": {row[0]: row[1] for row in conn.execute("SELECT stage,COUNT(*) FROM identity_status GROUP BY stage")},
        "current_knowledge_base": load_json(Path(store) / "published" / "current" / "publication-manifest.json"),
    }
    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store-root", default=str(DEFAULT_STORE))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    register = sub.add_parser("register")
    register.add_argument("--records", required=True); register.add_argument("--qa", required=True)
    register.add_argument("--evidence"); register.add_argument("--project-dir")
    register.add_argument("--skill-name"); register.add_argument("--skill-version")
    scan = sub.add_parser("scan"); scan.add_argument("--outputs-root", required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "init":
        conn = ensure_store(Path(args.store_root)); conn.close(); result = status(args.store_root)
    elif args.command == "register":
        result = register_case(args.store_root, args.records, args.qa, args.evidence, args.project_dir, args.skill_name, args.skill_version, args.policy)
    elif args.command == "scan":
        result = scan_outputs(args.store_root, args.outputs_root, args.policy)
    else:
        result = status(args.store_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
