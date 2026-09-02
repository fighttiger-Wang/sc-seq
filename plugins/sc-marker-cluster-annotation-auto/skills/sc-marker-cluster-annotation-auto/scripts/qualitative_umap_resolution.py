#!/usr/bin/env python3
"""Shared UMAP-triggered identity reassessment without numeric scoring."""

from __future__ import annotations

import json
import re


PLOT_LABEL = re.compile(r"^[A-Za-z0-9_]+$")
IDENTITY_ACTIONS = {"retain", "reject_and_reassign"}
RELATION_ALIASES = {"uncertain": "indeterminate"}


def normalize_relation(value):
    text = str(value or "").strip().lower()
    return RELATION_ALIASES.get(text, text)


def _as_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, dict):
        return [value]
    text = str(value).strip()
    if text.startswith(("[", "{")):
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if parsed is not None:
            return _as_list(parsed)
    return [item.strip() for item in re.split(r"[;,；、]", text) if item.strip()]


def _labels(value):
    labels = []
    for item in _as_list(value):
        if isinstance(item, dict):
            label = item.get("stable_id") or item.get("label") or item.get("celltype_en") or item.get("program")
        else:
            label = item
        text = str(label or "").strip()
        if text and PLOT_LABEL.fullmatch(text):
            labels.append(text)
    return labels


def _marker_genes(value):
    genes = []
    for item in _as_list(value):
        if isinstance(item, dict):
            gene = item.get("gene") or item.get("Gene") or item.get("GeneName")
        else:
            gene = re.split(r"[\s(]", str(item).strip(), maxsplit=1)[0]
        text = str(gene or "").strip().upper()
        if text and re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", text):
            genes.append(text)
    return list(dict.fromkeys(genes))


def _available_marker_genes(record, evidence, cluster):
    genes = []
    profile = (evidence or {}).get("cluster_profiles", {}).get(str(cluster), {})
    for key in ("top_markers", "top_informative_markers"):
        genes.extend(_marker_genes(profile.get(key, [])))
    for key in (
        "supporting_markers", "key_markers", "conflicting_markers",
        "supporting_marker_evidence", "conflicting_marker_evidence",
    ):
        genes.extend(_marker_genes(record.get(key)))
    return set(genes)


def _candidate_labels(record, evidence, cluster):
    candidates = []
    for key in ("candidate_labels", "competing_programs", "possible_components"):
        candidates.extend(_labels(record.get(key)))
    decision = (evidence or {}).get("qualitative_annotation_evidence", {}).get(str(cluster), {})
    for key in ("candidate_labels", "competing_programs", "possible_components"):
        candidates.extend(_labels(decision.get(key)))
    return set(candidates)


def validate_identity_resolution(item, record, evidence=None, formal=False):
    """Return validation errors for one UMAP identity action."""
    errors = []
    cluster = str(record.get("cluster_id", ""))
    current = str(
        record.get("provisional_stable_id") or record.get("stable_id") or record.get("canonical_subtype")
        or record.get("celltype_en") or record.get("display_label") or ""
    ).strip()
    relation = normalize_relation(item.get("marker_umap_relation"))
    action = str(item.get("identity_action", "")).strip()

    if formal and action not in IDENTITY_ACTIONS:
        errors.append(f"Cluster {cluster} formal UMAP audit requires identity_action=retain/reject_and_reassign")
        return errors
    if action and action not in IDENTITY_ACTIONS:
        errors.append(f"Cluster {cluster} invalid identity_action: {action}")
        return errors
    if not action:
        return errors
    if relation != "conflict" and action != "retain":
        errors.append(f"Cluster {cluster} can reject an identity only when marker_umap_relation=conflict")

    provisional = str(item.get("provisional_label", "")).strip()
    resolved = str(item.get("resolved_label", "")).strip()
    if formal and not provisional:
        errors.append(f"Cluster {cluster} formal UMAP audit requires provisional_label")
    if formal and not resolved:
        errors.append(f"Cluster {cluster} formal UMAP audit requires resolved_label")
    if action == "retain" and not provisional:
        provisional = current
    if action == "retain" and not resolved:
        resolved = current
    if action == "reject_and_reassign":
        if provisional != current:
            errors.append(
                f"Cluster {cluster} provisional_label must match the pre-UMAP identity {current}: {provisional}"
            )
        if not PLOT_LABEL.fullmatch(resolved):
            errors.append(f"Cluster {cluster} resolved_label violates [A-Za-z0-9_]+: {resolved}")
        if resolved == provisional:
            errors.append(f"Cluster {cluster} reject_and_reassign must change the identity")
        candidates = _candidate_labels(record, evidence, cluster)
        if resolved not in candidates:
            errors.append(
                f"Cluster {cluster} resolved_label {resolved} is not an existing marker-supported sibling candidate: "
                f"{sorted(candidates)}"
            )
        parent = str((evidence or {}).get("confirmed_metadata", {}).get("parent_population", "")).strip()
        normalized_parent = re.sub(r"[^A-Za-z0-9_]+", "_", parent).strip("_")
        if normalized_parent and resolved.lower() == normalized_parent.lower():
            errors.append(f"Cluster {cluster} UMAP reassessment cannot retreat to the supplied parent {parent}")
        if not str(item.get("resolved_label_cn", "")).strip():
            errors.append(f"Cluster {cluster} reject_and_reassign requires resolved_label_cn")

    if relation == "conflict":
        rationale = str(item.get("reassessment_rationale", "")).strip()
        genes = _marker_genes(item.get("reassessment_marker_support"))
        if not rationale:
            errors.append(f"Cluster {cluster} marker/UMAP conflict lacks reassessment_rationale")
        if len(genes) < 2:
            errors.append(f"Cluster {cluster} marker/UMAP conflict requires a coherent multi-gene reassessment_marker_support")
        available = _available_marker_genes(record, evidence, cluster)
        if available and len(set(genes) & available) < 2:
            errors.append(
                f"Cluster {cluster} reassessment Marker support is not present in current-case evidence: {genes}"
            )
        if action == "retain" and provisional and provisional != current:
            errors.append(f"Cluster {cluster} retain provisional_label does not match current identity {current}")
        if action == "retain" and resolved and resolved != current:
            errors.append(f"Cluster {cluster} retain resolved_label must remain {current}")
    return errors


def effective_label(record, item):
    current = str(
        record.get("stable_id") or record.get("canonical_subtype")
        or record.get("celltype_en") or record.get("display_label") or ""
    ).strip()
    if str(item.get("identity_action", "")).strip() == "reject_and_reassign":
        return str(item.get("resolved_label", "")).strip() or current
    return current


def apply_identity_resolution(record, item):
    """Apply a validated reassignment and preserve the rejected identity for audit."""
    relation = normalize_relation(item.get("marker_umap_relation"))
    item["marker_umap_relation"] = relation
    record["umap_identity_action"] = str(item.get("identity_action", "")).strip()
    if record["umap_identity_action"] != "reject_and_reassign":
        return record

    provisional = str(item.get("provisional_label", "")).strip()
    resolved = str(item.get("resolved_label", "")).strip()
    old_markers = record.get("supporting_markers") or record.get("key_markers") or ""
    new_markers = item.get("reassessment_marker_support", [])
    rationale = str(item.get("reassessment_rationale", "")).strip()
    record.update({
        "provisional_stable_id": provisional,
        "umap_rejected_identity": provisional,
        "stable_id": resolved,
        "canonical_subtype": resolved,
        "celltype_en": resolved,
        "display_label": resolved,
        "celltype_cn": str(item.get("resolved_label_cn", "")).strip(),
        "supporting_markers": new_markers,
        "key_markers": new_markers,
        "umap_reassessment_rationale": rationale,
    })
    if old_markers:
        record["provisional_supporting_markers"] = old_markers
        if not record.get("conflicting_markers"):
            record["conflicting_markers"] = old_markers
    existing = str(record.get("rationale") or record.get("decision_rationale") or "").strip()
    record["rationale"] = "；".join(part for part in (existing, f"UMAP整合复核：{rationale}") if part)
    return record
