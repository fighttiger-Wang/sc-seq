#!/usr/bin/env python3
"""Validate structured, all-cluster UMAP topology review records."""

import json
from pathlib import Path


RELATIONS = {"concordant", "conflict", "indeterminate"}
RESEARCH_STATUSES = {"not_required", "pending", "resolved", "reused"}
SAME_LABEL_TOPOLOGIES = {"adjacent", "disconnected", "not_applicable"}
SEPARATION_EXPLANATIONS = {"state_dominant", "sample_effect", "trajectory_boundary", "none"}
CONFLICT_RESOLUTION_BASES = {
    "cell_level_coexpression", "sample_metadata", "trajectory_metric",
    "reference_mapping", "quantitative_qc", "literature_only", "none",
}


def load_umap_audit(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_cluster_entries(audit):
    entries = audit.get("clusters", {})
    if isinstance(entries, dict):
        return {str(cluster): value for cluster, value in entries.items()}, []
    if isinstance(entries, list):
        normalized = {}
        duplicates = []
        for item in entries:
            cluster = str(item.get("cluster_id", ""))
            if cluster in normalized:
                duplicates.append(cluster)
            normalized[cluster] = item
        return normalized, duplicates
    raise ValueError("UMAP audit clusters must be an object or list")


def _record_context(records):
    context = {}
    for record in records or []:
        cluster = str(record.get("cluster_id", ""))
        label = str(record.get("stable_id") or record.get("canonical_subtype") or record.get("celltype_en") or "")
        states = record.get("state_list", [])
        if isinstance(states, str):
            try:
                decoded = json.loads(states)
            except (json.JSONDecodeError, TypeError):
                decoded = None
            states = decoded if isinstance(decoded, list) else [
                item.strip() for item in states.replace(",", ";").split(";") if item.strip()
            ]
        primary_state = str(record.get("primary_state") or "").strip()
        if primary_state and primary_state not in states:
            states = [primary_state] + list(states)
        context[cluster] = {
            "label": label,
            "states": [str(item) for item in states],
            "label_basis": str(record.get("label_basis") or "").strip(),
        }
    return context


def validate_umap_audit(audit, expected_clusters, formal=False, records=None):
    expected = [str(cluster) for cluster in expected_clusters]
    entries, duplicates = _normalize_cluster_entries(audit)
    record_context = _record_context(records)
    label_groups = {}
    for cluster, item in record_context.items():
        if item["label"]:
            label_groups.setdefault(item["label"], []).append(cluster)
    errors = []
    if duplicates:
        errors.append(f"Duplicate UMAP audit clusters: {sorted(set(duplicates))}")
    missing = [cluster for cluster in expected if cluster not in entries]
    extra = sorted(cluster for cluster in entries if cluster not in set(expected))
    if missing:
        errors.append(f"Missing UMAP audit clusters: {missing}")
    if extra:
        errors.append(f"Unexpected UMAP audit clusters: {extra}")

    conflict_clusters = []
    pending_clusters = []
    for cluster in expected:
        if cluster not in entries:
            continue
        item = entries[cluster]
        relation = str(item.get("marker_umap_relation", ""))
        research_status = str(item.get("research_status", ""))
        same_label_clusters = [str(value) for value in item.get("same_label_clusters", [])]
        same_label_topology = str(item.get("same_label_topology", ""))
        separation_explanation = str(item.get("separation_explanation", ""))
        separation_evidence = str(item.get("separation_evidence", "")).strip()
        conflict_resolution_basis = str(item.get("conflict_resolution_basis", "none"))
        if item.get("reviewed") is not True:
            errors.append(f"Cluster {cluster} UMAP audit requires reviewed=true")
        if not str(item.get("topology_summary", "")).strip():
            errors.append(f"Cluster {cluster} UMAP audit lacks topology_summary")
        if not isinstance(item.get("nearest_clusters", []), list):
            errors.append(f"Cluster {cluster} nearest_clusters must be a list")
        if relation not in RELATIONS:
            errors.append(f"Cluster {cluster} invalid marker_umap_relation: {relation}")
        if research_status not in RESEARCH_STATUSES:
            errors.append(f"Cluster {cluster} invalid research_status: {research_status}")
        if same_label_topology not in SAME_LABEL_TOPOLOGIES:
            errors.append(f"Cluster {cluster} invalid same_label_topology: {same_label_topology}")
        if separation_explanation not in SEPARATION_EXPLANATIONS:
            errors.append(f"Cluster {cluster} invalid separation_explanation: {separation_explanation}")
        if conflict_resolution_basis not in CONFLICT_RESOLUTION_BASES:
            errors.append(f"Cluster {cluster} invalid conflict_resolution_basis: {conflict_resolution_basis}")

        if record_context:
            label = record_context.get(cluster, {}).get("label", "")
            label_basis = record_context.get(cluster, {}).get("label_basis", "")
            expected_peers = sorted(
                (peer for peer in label_groups.get(label, []) if peer != cluster), key=str
            )
            if sorted(same_label_clusters, key=str) != expected_peers:
                errors.append(
                    f"Cluster {cluster} same_label_clusters does not match final label {label}: "
                    f"expected {expected_peers}, observed {sorted(same_label_clusters, key=str)}"
                )
            if not expected_peers and same_label_topology != "not_applicable":
                errors.append(f"Cluster {cluster} unique final label requires same_label_topology=not_applicable")
            if expected_peers and same_label_topology == "not_applicable":
                errors.append(f"Cluster {cluster} repeated final label requires adjacent/disconnected topology review")
            if label_basis in {"validated_external_candidate", "researched_branch_fallback"}:
                nearest_labels = {
                    record_context.get(str(peer), {}).get("label", "")
                    for peer in item.get("nearest_clusters", [])
                }
                nearest_supports_label = bool(label and label in nearest_labels)
                concrete_resolution = bool(
                    research_status in {"resolved", "reused"}
                    and conflict_resolution_basis not in {"none", "literature_only"}
                    and item.get("evidence_ids")
                )
                if relation == "concordant" and not nearest_supports_label and not concrete_resolution:
                    errors.append(
                        f"Cluster {cluster} {label_basis} cannot use plain concordant UMAP audit when no nearest "
                        f"cluster shares final identity {label}; provide resolved current-case evidence or mark a conflict"
                    )

        if same_label_topology == "disconnected":
            if separation_explanation == "none":
                if relation != "conflict":
                    errors.append(
                        f"Cluster {cluster} disconnected same-label island without explanation must be marker/UMAP conflict"
                    )
                if item.get("research_required") is not True:
                    errors.append(
                        f"Cluster {cluster} unexplained disconnected same-label island requires research_required=true"
                    )
            else:
                if not separation_evidence:
                    errors.append(
                        f"Cluster {cluster} disconnected same-label explanation lacks separation_evidence"
                    )
                if separation_explanation == "state_dominant" and record_context:
                    group = [cluster] + same_label_clusters
                    states = {
                        state.lower()
                        for peer in group
                        for state in record_context.get(peer, {}).get("states", [])
                    }
                    evidence_lower = separation_evidence.lower()
                    if not states or not any(state in evidence_lower for state in states):
                        errors.append(
                            f"Cluster {cluster} state_dominant separation lacks a recorded state named in separation_evidence"
                        )
        elif separation_explanation != "none":
            errors.append(
                f"Cluster {cluster} separation_explanation must be none unless same_label_topology=disconnected"
            )
        if relation == "conflict":
            conflict_clusters.append(cluster)
            if item.get("research_required") is not True:
                errors.append(f"Cluster {cluster} marker/UMAP conflict requires research_required=true")
            if not str(item.get("conflict_reason", "")).strip():
                errors.append(f"Cluster {cluster} marker/UMAP conflict lacks conflict_reason")
            if research_status not in {"resolved", "reused"}:
                pending_clusters.append(cluster)
                if formal:
                    errors.append(
                        f"Cluster {cluster} marker/UMAP conflict research is not resolved or reused"
                    )
            if formal and research_status in {"resolved", "reused"} and not item.get("evidence_ids"):
                errors.append(f"Cluster {cluster} resolved/reused conflict lacks evidence_ids")
            if formal and research_status in {"resolved", "reused"}:
                if conflict_resolution_basis in {"none", "literature_only"}:
                    errors.append(
                        f"Cluster {cluster} marker/UMAP conflict cannot be resolved by literature alone; "
                        "provide cell-level, sample, trajectory, reference-mapping, or quantitative-QC evidence"
                    )
        elif item.get("research_required") is True and research_status == "pending":
            pending_clusters.append(cluster)
            if formal:
                errors.append(f"Cluster {cluster} UMAP-triggered research remains pending")

    if errors:
        raise ValueError("\n".join(errors))
    return {
        "entries": entries,
        "reviewed_clusters": expected,
        "conflict_clusters": conflict_clusters,
        "research_pending_clusters": pending_clusters,
        "all_clusters_reviewed": True,
    }


def apply_umap_audit(records, validated):
    entries = validated["entries"]
    for record in records:
        item = entries[str(record.get("cluster_id", ""))]
        record["umap_review_status"] = "reviewed"
        record["umap_neighbors"] = item.get("nearest_clusters", [])
        record["umap_topology"] = item.get("topology_summary", "")
        record["umap_marker_concordance"] = item.get("marker_umap_relation", "")
        record["umap_review_action"] = item.get("review_action", "")
        record["umap_research_status"] = item.get("research_status", "")
        record["umap_evidence_ids"] = item.get("evidence_ids", [])
        record["umap_same_label_clusters"] = item.get("same_label_clusters", [])
        record["umap_same_label_topology"] = item.get("same_label_topology", "")
        record["umap_separation_explanation"] = item.get("separation_explanation", "")
        record["umap_separation_evidence"] = item.get("separation_evidence", "")
        record["umap_conflict_resolution_basis"] = item.get("conflict_resolution_basis", "none")
        if item.get("same_label_topology") == "disconnected":
            record["auto_merge_allowed"] = False
            record["manual_review"] = True
