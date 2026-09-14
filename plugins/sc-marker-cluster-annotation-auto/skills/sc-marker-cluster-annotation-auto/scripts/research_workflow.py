#!/usr/bin/env python3
"""Open-world research triggers and auditable evidence admission.

The annotation core may nominate a fallback from the registered ontology, but
formal binding is blocked whenever the current evidence indicates a knowledge
gap, context mismatch, unresolved boundary, expert escalation, or an active
calibration requirement.  Literature expands the candidate set; it never
creates an identity without current-case multi-gene support.
"""

from __future__ import annotations

import hashlib
import json
import csv
from datetime import date, datetime, timezone
from pathlib import Path


SKILL_ID = "sc-marker-cluster-annotation-auto"
SCHEMA_VERSION = "1.0.0"
PASS_STATES = {"通过", "pass", "passed"}
SOURCE_FIELDS = {
    "title", "doi_or_pmid_or_url", "retrieval_date", "species", "tissue",
    "supported_program", "exclusions", "adoption_or_rejection_reason",
}


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value):
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plugin_version(start):
    for parent in [Path(start).resolve(), *Path(start).resolve().parents]:
        manifest = parent / ".codex-plugin" / "plugin.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return str(data.get("version", "unknown")).split("+", 1)[0]
    return "unknown"


def load_calibration_policy(path):
    policy_path = Path(path).resolve()
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    counter = data.get("counters", {}).get(SKILL_ID, {})
    return data, {
        "policy_path": str(policy_path),
        "policy_sha256": sha256_file(policy_path),
        "policy_version": str(data.get("version", "")),
        "required_online_verification_uses": int(counter.get("required_online_verification_uses", 0)),
    }


def _load_state(path):
    state_path = Path(path).resolve()
    if not state_path.exists():
        return {"schema_version": SCHEMA_VERSION, "completed_uses": {}}
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("completed_uses", {}), dict):
        raise ValueError(f"Invalid calibration state: {state_path}")
    return data


def calibration_context(evidence, policy_path, state_path, runtime_version):
    policy, details = load_calibration_policy(policy_path)
    evidence_policy = evidence.get("annotation_evidence_policy", {})
    release_components = {
        "skill_version": runtime_version,
        "calibration_policy_version": details["policy_version"],
        "core_version": evidence_policy.get("core_version", ""),
        "config_version": evidence_policy.get("config_version", ""),
        "knowledge_base_version": evidence_policy.get("knowledge_base_version", ""),
    }
    release_key = sha256_json(release_components)
    state = _load_state(state_path)
    completed = int(state.get("completed_uses", {}).get(release_key, 0))
    required_uses = details["required_online_verification_uses"]
    use_number = completed + 1
    return {
        **details,
        "release_key": release_key,
        "release_components": release_components,
        "state_path": str(Path(state_path).resolve()),
        "completed_uses_before_run": completed,
        "use_number": use_number,
        "online_verification_required": use_number <= required_uses,
        "policy_retrieve_when": list(policy.get("after_calibration", {}).get("retrieve_when", [])),
    }


def _genes(value):
    result = []
    if value in (None, ""):
        return result
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    for item in value:
        if isinstance(item, dict):
            gene = item.get("gene") or item.get("Gene") or item.get("GeneName")
        else:
            gene = str(item).split(" ", 1)[0].split("(", 1)[0]
        text = str(gene or "").strip().upper()
        if text and text not in result:
            result.append(text)
    return result


def available_case_genes(evidence, cluster):
    genes = []
    profile = evidence.get("cluster_profiles", {}).get(str(cluster), {})
    for key in ("top_markers", "top_informative_markers"):
        genes.extend(_genes(profile.get(key, [])))
    decision = evidence.get("qualitative_annotation_evidence", {}).get(str(cluster), {})
    genes.extend(_genes(decision.get("supporting_markers", [])))
    for candidate in decision.get("candidate_program_audits", []) or []:
        genes.extend(_genes(candidate.get("supporting_core", [])))
        genes.extend(_genes(candidate.get("supporting_supportive", [])))
    return list(dict.fromkeys(genes))


def ratio_supported_genes(evidence, cluster, requested_genes, minimum_ratio=0.05):
    """Verify requested genes against the original long-form detection table."""
    source = str(evidence.get("source_paths", {}).get("expression_ratio_table", "")).strip()
    path = Path(source) if source else None
    requested = {str(gene).strip().upper() for gene in requested_genes if str(gene).strip()}
    if not path or not path.is_file() or not requested:
        return set()
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    supported = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fields = {str(name).strip().lower(): name for name in (reader.fieldnames or [])}
        gene_field = fields.get("gene") or fields.get("genename")
        group_field = fields.get("group") or fields.get("cluster") or fields.get("seurat_clusters")
        ratio_field = fields.get("expr_ratio") or fields.get("detection_ratio") or fields.get("pct.1")
        if not gene_field or not group_field or not ratio_field:
            return set()
        for row in reader:
            gene = str(row.get(gene_field, "")).strip().upper()
            if gene not in requested or str(row.get(group_field, "")).strip() != str(cluster):
                continue
            try:
                ratio = float(row.get(ratio_field, 0) or 0)
            except (TypeError, ValueError):
                continue
            if ratio >= minimum_ratio:
                supported.add(gene)
                if supported == requested:
                    break
    return supported


def _candidate_summary(decision):
    rows = []
    for candidate in decision.get("candidate_program_audits", []) or []:
        rows.append({
            "label": candidate.get("label", ""),
            "program_gate": candidate.get("program_gate", ""),
            "parent_lineage_gate": candidate.get("parent_lineage_gate", ""),
            "tissue_scope_match": candidate.get("tissue_scope_match", True),
            "supporting_core": _genes(candidate.get("supporting_core", [])),
            "supporting_supportive": _genes(candidate.get("supporting_supportive", [])),
            "conflicting_markers": _genes(candidate.get("conflicting_markers", [])),
            "missing_core_markers": _genes(candidate.get("missing_core_markers", [])),
        })
    return rows


def _trigger_reasons(decision, calibration, force_research=False, expert_reasons=None):
    reasons = []
    candidates = decision.get("candidate_program_audits", []) or []
    primary = next(
        (item for item in candidates if item.get("label") == decision.get("primary_program")),
        {},
    )
    if calibration.get("online_verification_required"):
        reasons.append("calibration_verification")
    if candidates and not any(str(item.get("program_gate", "")) in PASS_STATES for item in candidates):
        reasons.append("knowledge_base_gap")
    if primary.get("tissue_scope_match") is False:
        reasons.append("species_or_tissue_conflict")
    auto_binding_eligible = [
        item for item in candidates
        if item.get("tissue_scope_match", True) is not False
        and str(item.get("parent_lineage_gate", "")) not in {"不通过", "fail", "failed"}
    ]
    if candidates and not auto_binding_eligible:
        reasons.append("no_auto_binding_eligible_candidate")
    arbitration = decision.get("identity_arbitration", []) or []
    if decision.get("qualitative_gates", {}).get("sibling_competition") == "未确定" or any(
        str(item.get("resolution", "")).startswith("unresolved") for item in arbitration if isinstance(item, dict)
    ):
        reasons.append("unresolved_competing_programs")
    if decision.get("off_parent_detected"):
        reasons.append("off_parent_coherent_program")
    if force_research:
        reasons.append("expert_escalation")
    for reason in expert_reasons or []:
        text = str(reason).strip()
        if text:
            reasons.append(f"expert_reason:{text}")
    return list(dict.fromkeys(reasons))


def build_research_requests(evidence, calibration, force_research=False, expert_reasons=None):
    metadata = evidence.get("confirmed_metadata", {})
    requests = []
    for cluster in evidence.get("clusters", []):
        cluster = str(cluster)
        decision = evidence.get("qualitative_annotation_evidence", {}).get(cluster, {})
        reasons = _trigger_reasons(decision, calibration, force_research, expert_reasons)
        decision["research_required"] = bool(reasons)
        decision["research_trigger_reasons"] = reasons
        decision["research_status"] = "pending" if reasons else "not_required"
        decision["formal_identity_binding_allowed"] = not reasons
        if not reasons:
            continue
        candidates = _candidate_summary(decision)
        known_program_genes = {
            gene
            for candidate in candidates
            for key in ("supporting_core", "supporting_supportive", "conflicting_markers", "missing_core_markers")
            for gene in candidate.get(key, [])
        }
        case_genes = available_case_genes(evidence, cluster)
        unexplained = [gene for gene in case_genes if gene not in known_program_genes][:15]
        request = {
            "request_id": f"cluster-{cluster}",
            "cluster_id": cluster,
            "trigger_reasons": reasons,
            "species": metadata.get("species", ""),
            "tissue": metadata.get("tissue", ""),
            "parent_population": metadata.get("parent_population", ""),
            "sample_context": metadata.get("sample_context", {}),
            "fallback_identity_not_formally_bound": decision.get("stable_id", ""),
            "candidate_programs": candidates,
            "current_case_genes": case_genes[:40],
            "unexplained_enriched_genes": unexplained,
            "query_requirements": [
                "Search by species, organ/tissue, disease/development context, and the coherent multi-gene program.",
                "Compare the proposed identity against its nearest sibling identities and explicit exclusions.",
                "Return at least two independent sources and document both adopted and rejected candidates.",
            ],
        }
        requests.append(request)
        decision["research_request_id"] = request["request_id"]
    stable_payload = {
        "schema_version": SCHEMA_VERSION,
        "skill_id": SKILL_ID,
        "calibration": calibration,
        "requests": requests,
    }
    document = {
        **stable_payload,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_sha256": sha256_json(stable_payload),
    }
    return document


def _validate_source(source, cluster, index):
    if not isinstance(source, dict):
        raise ValueError(f"Cluster {cluster} source {index} must be an object")
    missing = sorted(field for field in SOURCE_FIELDS if not str(source.get(field, "")).strip())
    if missing:
        raise ValueError(f"Cluster {cluster} source {index} missing fields: {missing}")
    identifier = str(source.get("doi_or_pmid_or_url", "")).strip().lower()
    return identifier


def validate_and_apply_research_evidence(evidence, requests, research_path):
    path = Path(research_path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("request_sha256") != requests.get("request_sha256"):
        raise ValueError("Research evidence request_sha256 does not match the current research request")
    resolutions = payload.get("resolutions", {})
    source_library = payload.get("source_library", {})
    if not isinstance(resolutions, dict):
        raise ValueError("Research evidence resolutions must be an object keyed by cluster")
    request_by_cluster = {str(item["cluster_id"]): item for item in requests.get("requests", [])}
    normalized = {}
    external = []
    for cluster, request in request_by_cluster.items():
        resolution = resolutions.get(cluster)
        if not isinstance(resolution, dict):
            raise ValueError(f"Research evidence missing required cluster {cluster}")
        status = str(resolution.get("status", "")).strip()
        if status not in {"resolved", "reused"}:
            raise ValueError(f"Cluster {cluster} research status must be resolved or reused for formal binding")
        query = str(resolution.get("query", "")).strip()
        retrieval_date = str(resolution.get("retrieval_date", "")).strip()
        rationale = str(resolution.get("adoption_or_rejection_rationale", "")).strip()
        candidate = str(resolution.get("candidate_label", "")).strip()
        label_basis = str(resolution.get("label_basis", "")).strip()
        exclusions = resolution.get("exclusions", [])
        if not query or not retrieval_date or not rationale or not candidate:
            raise ValueError(f"Cluster {cluster} research resolution lacks query/date/candidate/rationale")
        if not isinstance(exclusions, list) or not any(str(item).strip() for item in exclusions):
            raise ValueError(f"Cluster {cluster} research resolution requires explicit exclusions")
        sources = resolution.get("sources", [])
        if not sources and resolution.get("source_ids"):
            sources = [source_library.get(str(source_id)) for source_id in resolution.get("source_ids", [])]
        if not isinstance(sources, list) or len(sources) < 2:
            raise ValueError(f"Cluster {cluster} requires at least two independent research sources")
        identifiers = [_validate_source(source, cluster, index) for index, source in enumerate(sources, 1)]
        if len(set(identifiers)) < 2:
            raise ValueError(f"Cluster {cluster} research sources are not independent")
        markers = _genes(resolution.get("current_case_support_markers", []))
        available = set(available_case_genes(evidence, cluster))
        ratio_supported = ratio_supported_genes(evidence, cluster, markers)
        verified_markers = set(markers) & (available | ratio_supported)
        if len(markers) < 2 or len(verified_markers) < 2:
            raise ValueError(
                f"Cluster {cluster} requires at least two current-case supporting markers present in the evidence"
            )
        registered = {str(item.get("label", "")) for item in request.get("candidate_programs", [])}
        expected_basis = "researched_registered_candidate" if candidate in registered else "validated_external_candidate"
        if label_basis != expected_basis:
            raise ValueError(
                f"Cluster {cluster} candidate {candidate} requires label_basis={expected_basis}, observed {label_basis}"
            )
        normalized_resolution = {
            **resolution,
            "status": status,
            "candidate_label": candidate,
            "label_basis": label_basis,
            "current_case_support_markers": markers,
            "ratio_verified_support_markers": sorted(ratio_supported),
            "source_evidence_ids": identifiers,
        }
        normalized[cluster] = normalized_resolution
        if label_basis == "validated_external_candidate":
            external.append({
                "cluster_id": cluster,
                "candidate_label": candidate,
                "current_case_support_markers": markers,
                "sources": sources,
                "adoption_or_rejection_rationale": rationale,
            })
    normalized_document = {
        "schema_version": SCHEMA_VERSION,
        "request_sha256": requests["request_sha256"],
        "source_path": str(path),
        "source_sha256": sha256_file(path),
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolutions": normalized,
    }
    artifact_sha = sha256_json(normalized_document)
    normalized_document["research_artifact_sha256"] = artifact_sha
    for cluster, resolution in normalized.items():
        decision = evidence["qualitative_annotation_evidence"][cluster]
        fallback_identity = str(decision.get("stable_id", "")).strip()
        decision.update({
            "pre_research_fallback_identity": fallback_identity,
            "stable_id": resolution["candidate_label"],
            "suggested_identity": resolution["candidate_label"],
            "research_status": resolution["status"],
            "research_selected_identity": resolution["candidate_label"],
            "research_label_basis": resolution["label_basis"],
            "research_artifact_sha256": artifact_sha,
            "research_evidence_ids": resolution["source_evidence_ids"],
            "formal_identity_binding_allowed": True,
        })
    return normalized_document, external


def apply_research_stage(
    evidence, calibration_policy_path, calibration_state_path, runtime_version,
    research_evidence_path=None, force_research=False, expert_reasons=None,
):
    calibration = calibration_context(
        evidence, calibration_policy_path, calibration_state_path, runtime_version
    )
    requests = build_research_requests(
        evidence, calibration, force_research=force_research, expert_reasons=expert_reasons
    )
    normalized = None
    external = []
    if requests["requests"] and research_evidence_path:
        normalized, external = validate_and_apply_research_evidence(
            evidence, requests, research_evidence_path
        )
    elif research_evidence_path and not requests["requests"]:
        raise ValueError("Research evidence was supplied but the current run has no research trigger")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "calibration": calibration,
        "request_sha256": requests["request_sha256"],
        "required_clusters": [item["cluster_id"] for item in requests["requests"]],
        "resolved_clusters": sorted(normalized.get("resolutions", {})) if normalized else [],
        "formal_delivery_blocked": bool(requests["requests"] and not normalized),
        "research_artifact_sha256": normalized.get("research_artifact_sha256", "") if normalized else "",
    }
    evidence.setdefault("annotation_evidence_policy", {})["open_world_research"] = summary
    return requests, normalized, external


def validate_formal_research_binding(records, evidence):
    errors = []
    decisions = evidence.get("qualitative_annotation_evidence", {})
    policy = evidence.get("annotation_evidence_policy", {}).get("open_world_research", {})
    artifact_sha = str(policy.get("research_artifact_sha256", "")).strip()
    records_by_cluster = {str(item.get("cluster_id", "")): item for item in records}
    for cluster, decision in decisions.items():
        if not decision.get("research_required"):
            continue
        if not decision.get("formal_identity_binding_allowed"):
            errors.append(f"Cluster {cluster} research is pending; formal identity binding is blocked")
            continue
        if not artifact_sha or decision.get("research_artifact_sha256") != artifact_sha:
            errors.append(f"Cluster {cluster} research artifact hash is missing or inconsistent")
        selected = str(decision.get("research_selected_identity", "")).strip()
        basis = str(decision.get("research_label_basis", "")).strip()
        record = records_by_cluster.get(str(cluster), {})
        observed = str(record.get("stable_id") or record.get("canonical_subtype") or record.get("celltype_en") or "").strip()
        if observed != selected:
            errors.append(
                f"Cluster {cluster} formal identity {observed} does not match researched identity {selected}"
            )
        if str(record.get("label_basis", "")).strip() != basis:
            errors.append(
                f"Cluster {cluster} formal label_basis must match research admission basis {basis}"
            )
    if errors:
        raise ValueError("\n".join(errors))
    return True


def complete_calibration_use(evidence):
    research = evidence.get("annotation_evidence_policy", {}).get("open_world_research", {})
    calibration = research.get("calibration", {})
    if not calibration or not calibration.get("online_verification_required"):
        return {"updated": False, "reason": "calibration_not_required"}
    if research.get("formal_delivery_blocked") or not research.get("research_artifact_sha256"):
        raise ValueError("Cannot complete calibration use before research-backed formal delivery")
    state_path = Path(calibration["state_path"]).resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = _load_state(state_path)
    release_key = calibration["release_key"]
    completed = int(state.get("completed_uses", {}).get(release_key, 0))
    use_number = int(calibration["use_number"])
    if completed < use_number:
        state.setdefault("completed_uses", {})[release_key] = use_number
        state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        state["skill_id"] = SKILL_ID
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"updated": True, "completed_use": use_number, "state_path": str(state_path)}
    return {"updated": False, "completed_use": completed, "state_path": str(state_path)}
