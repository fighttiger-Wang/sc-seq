#!/usr/bin/env python3
"""Load and project the approved multi-tissue annotation knowledge base."""

import json
import os
import re
from pathlib import Path


KNOWLEDGE_BASE_VERSION = "2.0.0"
_LOCAL_KB = Path(__file__).resolve().parent / "knowledge-base" / "cell-annotation-knowledge-base.v2.json"
_VENDORED_KB = Path(__file__).resolve().parent.parent / "references" / "cell-annotation-knowledge-base.v2.json"


def _discover_workspace_root():
    configured = os.environ.get("CODEX_SHARED_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "skill-pack.json").is_file():
            return parent.parent
    return None


_WORKSPACE_ROOT = _discover_workspace_root()
_SHARED_RUNTIME_KB = (
    _WORKSPACE_ROOT / ".sc-annotation-knowledge" / "published" / "current" / "cell-annotation-knowledge-base.v2.json"
    if _WORKSPACE_ROOT else Path("__missing_shared_annotation_knowledge_base__")
)
_ENV_KB = Path(os.environ["SC_ANNOTATION_KB_PATH"]).resolve() if os.environ.get("SC_ANNOTATION_KB_PATH") else None
DEFAULT_KNOWLEDGE_BASE = (
    _ENV_KB if _ENV_KB and _ENV_KB.is_file()
    else (_LOCAL_KB if _LOCAL_KB.is_file()
          else (_SHARED_RUNTIME_KB if _SHARED_RUNTIME_KB.is_file() else _VENDORED_KB))
)

_NON_GENE_TOKENS = {
    "ABSENT", "ACTIVATION", "ADDITIONAL", "ALONE", "AND", "CAN", "CELL", "COHERENT",
    "CONTEXT", "CYCLING", "DROPOUT", "GENES", "HIGH", "INCLUDING", "LINEAGE", "LOW",
    "MARKER", "MARKERS", "NOT", "ONLY", "OR", "PLUS", "PROGRAM", "REQUIRE", "STATE",
    "TISSUE", "WITHOUT",
}


def _split_list(value):
    return [item.strip() for item in re.split(r"[;,]", str(value or "")) if item.strip()]


def _marker_genes(value):
    genes = []
    for item in _split_list(value):
        for token in re.findall(r"\b[A-Z][A-Z0-9-]{1,15}\b", item.upper()):
            if token not in _NON_GENE_TOKENS and token not in genes:
                genes.append(token)
    return genes


def _required_core_count(rule, core_count):
    match = re.search(r">=\s*(\d+)", str(rule or ""))
    if match:
        return min(int(match.group(1)), max(core_count, 1))
    if re.search(r"\bplus\b|\band\b|combination|coherent", str(rule or ""), re.I):
        return min(2, max(core_count, 1))
    return min(3, max(core_count, 1))


def load_knowledge_base(path=None):
    source = Path(path or DEFAULT_KNOWLEDGE_BASE)
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("schema_version") != KNOWLEDGE_BASE_VERSION:
        raise ValueError(f"Unsupported annotation knowledge-base version: {data.get('schema_version')}")
    data["_source_path"] = str(source.resolve())
    return data


def _norm_species(species):
    value = str(species or "Human").strip().lower()
    if value in {"human", "homo sapiens", "人", "人类"}:
        return "Human"
    if value in {"mouse", "mus musculus", "mice", "小鼠", "鼠"}:
        return "Mouse"
    return str(species).strip().title()


def _norm_tissue_token(value):
    return re.sub(r"[\s_-]+", "_", str(value or "").strip().lower())


def _expanded_tissue_tokens(value):
    tokens = set()
    for item in _split_list(value):
        normalized = _norm_tissue_token(item)
        if not normalized:
            continue
        tokens.add(normalized)
        tokens.update(part for part in normalized.split("_") if part)
    if tokens & {"cancer", "carcinoma", "neoplasm", "tumour", "tumor"}:
        tokens.add("tumor")
    if tokens & {"ovarian", "ovary"}:
        tokens.update({"ovarian", "ovary"})
    return tokens


def _active_modules(kb, tissue):
    tissue_tokens = _expanded_tissue_tokens(tissue)
    active = []
    for module in kb.get("tissue_modules", []):
        scopes = {_norm_tissue_token(item) for item in _split_list(module.get("tissues"))}
        if module.get("module_id") == "core_multi_tissue" or bool(scopes & tissue_tokens):
            active.append(module)
    return active


def _tissue_scope_matches(scope, tissue):
    scopes = {_norm_tissue_token(item) for item in _split_list(scope)}
    if not scopes or scopes & {"all", "multi_tissue", "multitissue", "pan_tissue"}:
        return True
    tissue_tokens = _expanded_tissue_tokens(tissue)
    if not tissue_tokens:
        return False
    # ``tissue`` is an ontology-wide scope used by circulating immune cells
    # that can infiltrate any named solid tissue.  Treating it as a literal
    # tissue name incorrectly removed monocyte/neutrophil panels from organs
    # such as aorta before evidence scoring even started.
    if "tissue" in scopes:
        return True
    aliases = {
        "bone_marrow": {"bone_marrow", "marrow"},
        "peripheral_blood": {"peripheral_blood", "blood"},
        "blood": {"blood", "peripheral_blood"},
        "colon": {"colon", "intestine", "large_intestine"},
        "intestine": {"intestine", "small_intestine", "colon"},
    }
    accepted = set()
    for tissue_token in tissue_tokens:
        accepted.update(aliases.get(tissue_token, {tissue_token}))
    return bool(scopes & accepted)


def build_runtime_config(kb, species="Human", tissue="", annotation_level="subcluster", parent_population="", parent_kind="unknown"):
    species = _norm_species(species)
    nodes = {row["cell_id"]: row for row in kb.get("ontology", []) if row.get("cell_id")}
    active_modules = _active_modules(kb, tissue)
    allowed_major = {
        item
        for module in active_modules
        for item in _split_list(module.get("allowed_major_outputs"))
        if item.lower() != "none"
    }
    active_roots = {
        item
        for module in active_modules
        for item in _split_list(module.get("enabled_roots"))
        if item.lower() != "all"
    }

    def ancestors(cell_id):
        lineage = []
        seen = set()
        current = cell_id
        while current and current not in seen:
            seen.add(current)
            lineage.append(current)
            current = nodes.get(current, {}).get("parent_id", "")
        return lineage

    def major_label(cell_id):
        lineage = ancestors(cell_id)
        for candidate in lineage:
            if candidate in allowed_major:
                return candidate
        for candidate in lineage:
            if str(nodes.get(candidate, {}).get("major_output_allowed")) == "Yes":
                return candidate
        return lineage[-1] if lineage else cell_id

    parent = str(parent_population or "").strip()
    parent_aliases = {
        alias.get("alias", "").lower(): alias.get("maps_to") or alias.get("cell_id")
        for alias in kb.get("aliases", [])
    }
    parent_id = parent if parent in nodes else parent_aliases.get(parent.lower(), "")
    if not parent_id and parent:
        # Parent inputs often use a branch token (for example, ``T_NK``)
        # rather than the ontology node's canonical ``*_lineage`` ID.  Resolve
        # that token only when it maps unambiguously to a lineage root.
        branch_matches = [
            cell_id for cell_id, node in nodes.items()
            if str(node.get("branch", "")).strip().lower() == parent.lower()
            and str(cell_id).lower().endswith("_lineage")
        ]
        if len(branch_matches) == 1:
            parent_id = branch_matches[0]
    restrict_to_parent = annotation_level == "subcluster" and parent_kind == "lineage" and parent_id in nodes

    approved_rows = [row for row in kb.get("marker_panels", []) if row.get("approval_status") == "Approve"]
    exact_rows = [row for row in approved_rows if _norm_species(row.get("target_species")) == species]
    panel_rows = exact_rows or [row for row in approved_rows if _norm_species(row.get("target_species")) == "Human"]
    species_panel_mode = "exact" if exact_rows else "cross_species_human_fallback"

    panels = {}
    provenance = {}
    for row in panel_rows:
        cell_id = row.get("cell_id")
        if cell_id not in nodes:
            continue
        node = nodes[cell_id]
        if node.get("proposed_status") != "Approve":
            continue
        if annotation_level == "subcluster" and node.get("subcluster_output_allowed") != "Yes":
            continue
        lineage = ancestors(cell_id)
        within_parent_scope = not restrict_to_parent or parent_id in lineage or cell_id == parent_id
        tissue_scope_match = _tissue_scope_matches(nodes[cell_id].get("tissue_scope"), tissue)
        # A confirmed lineage parent is a strong prior, not permission to hide
        # contaminants.  Keep every tissue-relevant off-parent panel as an
        # audit sentinel when full expression ratios are available.  Retain
        # noncanonical-tissue panels only inside the confirmed parent branch.
        if (
            not tissue_scope_match
            and cell_id not in allowed_major
            and (not restrict_to_parent or not within_parent_scope)
        ):
            continue
        if annotation_level == "major" and active_roots:
            # Keep core immune/vascular/stromal lineages and tissue-module descendants.
            if not any(root in lineage for root in active_roots) and not any(
                root in lineage for root in (
                    "Immune_cell", "Endothelial_cell", "Stromal_cell",
                    "Epithelial_cell", "Hematopoietic_nonimmune",
                )
            ):
                continue
        core = _marker_genes(row.get("core_markers"))
        if not core:
            continue
        panels[cell_id] = {
            "core": core,
            "supportive": _marker_genes(row.get("supportive_markers")),
            "negative": _marker_genes(row.get("exclusion_markers")),
            "confounders": row.get("confounders", ""),
            "decision_rule": row.get("decision_rule", ""),
            "required_core_markers": _required_core_count(row.get("decision_rule"), len(core)),
        }
        boundary = kb.get("identity_boundary_rules", {}).get(cell_id, {})
        if boundary:
            panels[cell_id].update(boundary)
        provenance[cell_id] = {
            "stable_id": cell_id,
            "parent_path": list(reversed(lineage)),
            "major_label": major_label(cell_id),
            "target_species": species,
            "panel_species": row.get("panel_species", species),
            "cross_species_inference": (
                species_panel_mode != "exact"
                or str(row.get("cross_species_inference", "No")).lower() == "yes"
            ),
            "evidence_ids": _split_list(row.get("evidence_ids")),
            "evidence_gate": row.get("evidence_gate", ""),
            "developmental_stage": nodes.get(cell_id, {}).get("developmental_stage", ""),
            "node_kind": nodes.get(cell_id, {}).get("node_kind", "identity"),
            "tissue_scope": _split_list(nodes.get(cell_id, {}).get("tissue_scope", "")),
            "tissue_scope_match": tissue_scope_match,
            "tissue_context_review": not tissue_scope_match,
            "tissue_module": [module.get("module_id") for module in active_modules if any(root in lineage for root in _split_list(module.get("enabled_roots")))],
            "within_parent_scope": within_parent_scope,
            "off_parent_audit": bool(restrict_to_parent and not within_parent_scope),
        }

    state_priority = {}
    for row in kb.get("state_rules", []):
        if row.get("approval_status") == "Approve":
            state_priority[row.get("scope")] = {
                "allowed": _split_list(row.get("allowed_states")),
                "priority": [item.strip() for item in str(row.get("priority_order", "")).split(">") if item.strip()],
                "max_display_states": int(row.get("max_display_states") or 1),
                "display_grammar": row.get("display_grammar") or "<Identity>",
            }

    source_by_id = {
        row.get("source_id"): row
        for row in kb.get("evidence_sources", [])
        if row.get("source_id")
    }
    selected_evidence_ids = {
        evidence_id
        for item in provenance.values()
        for evidence_id in item.get("evidence_ids", [])
    }

    return {
        "knowledge_base_version": kb.get("knowledge_base_version", kb["schema_version"]),
        "knowledge_base_source": kb["_source_path"],
        "species": species,
        "species_panel_mode": species_panel_mode,
        "tissue": tissue,
        "annotation_level": annotation_level,
        "parent_population": parent_population,
        "parent_kind": parent_kind,
        "resolved_parent_id": parent_id,
        "restrict_to_parent": restrict_to_parent,
        "identity_panels": panels,
        "panel_provenance": provenance,
        "evidence_source_registry": {
            evidence_id: source_by_id[evidence_id]
            for evidence_id in sorted(selected_evidence_ids)
            if evidence_id in source_by_id
        },
        "major_label_map": {cell_id: info["major_label"] for cell_id, info in provenance.items()},
        "broad_groups": {cell_id: (nodes.get(cell_id, {}).get("branch") or major_label(cell_id)) for cell_id in panels},
        "state_priority_rules": state_priority,
        "active_tissue_modules": [module.get("module_id") for module in active_modules],
        "legacy_migration": kb.get("legacy_migration", []),
        "ontology_parent_map": {cell_id: row.get("parent_id", "") for cell_id, row in nodes.items()},
        "ontology_node_kind": {cell_id: row.get("node_kind", "identity") for cell_id, row in nodes.items()},
        "ontology_developmental_stage": {cell_id: row.get("developmental_stage", "") for cell_id, row in nodes.items()},
    }
