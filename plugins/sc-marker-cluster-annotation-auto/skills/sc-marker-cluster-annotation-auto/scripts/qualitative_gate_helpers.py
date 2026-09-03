#!/usr/bin/env python3
"""Per-gene metrics and explicit biological gates used by the qualitative core."""

import csv
import json
from pathlib import Path
from statistics import median

CORE_VERSION = "3.1.2"
_LOCAL_CONFIG = Path(__file__).resolve().parent / "annotation-evidence-config.v1.json"
_VENDORED_CONFIG = Path(__file__).resolve().parent.parent / "references" / "annotation-evidence-config.v1.json"
DEFAULT_CONFIG = _LOCAL_CONFIG if _LOCAL_CONFIG.is_file() else _VENDORED_CONFIG

def _snapshot_metadata():
    vendored = Path(__file__).resolve().parent.parent / 'references' / 'annotation-evidence-core.snapshot.json'
    if vendored.is_file():
        return json.loads(vendored.read_text(encoding='utf-8'))
    version = Path(__file__).resolve().parent / 'VERSION.json'
    return json.loads(version.read_text(encoding='utf-8')) if version.is_file() else {'core_version': CORE_VERSION}


def _norm(value):
    return str(value).strip().upper()


def _mad(values):
    if not values:
        return 0.0
    center = median(values)
    return median([abs(value - center) for value in values])


def _alias(headers, names, required=True):
    lookup = {_norm(value): index for index, value in enumerate(headers)}
    for name in names:
        if _norm(name) in lookup:
            return lookup[_norm(name)]
    if required:
        raise ValueError(f'Missing required column; expected one of {names}')
    return None


def load_gene_map(path):
    if not path:
        return {}
    with Path(path).open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle, delimiter='\t')
        headers = next(reader)
        source_i = _alias(headers, ['source_gene', 'gene', 'original_gene'])
        target_i = _alias(headers, ['canonical_gene', 'target_gene', 'ortholog_gene'])
        mapping = {}
        for row in reader:
            if row and row[source_i] and row[target_i]:
                mapping[_norm(row[source_i])] = _norm(row[target_i])
    return mapping


def canonical_gene(gene, mapping):
    normalized = _norm(gene)
    return mapping.get(normalized, normalized)


def load_ratio_table(path, expected_clusters, mapping, expected_genes=None, require_complete=False):
    if not path:
        return None
    values = {str(cluster): {} for cluster in expected_clusters}
    with Path(path).open('r', encoding='utf-8-sig', newline='') as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = '\t' if '\t' in sample.splitlines()[0] else ','
        reader = csv.reader(handle, delimiter=delimiter)
        headers = next(reader)
        gene_i = _alias(headers, ['gene', 'GeneName', 'feature', 'features'])
        cluster_i = _alias(headers, ['group', 'cluster', 'Target_Cluster', 'seurat_clusters'])
        ratio_i = _alias(headers, ['expr_ratio', 'detection_ratio', 'pct', 'pct.1', 'pct1'])
        mean_i = _alias(headers, ['mean_expr', 'average_expression', 'mean'], required=False)
        norm_i = _alias(headers, ['norm_expr', 'normalized_expression', 'scaled_expression'], required=False)
        for row in reader:
            if not row or not row[gene_i]:
                continue
            cluster = str(row[cluster_i]).strip()
            if cluster not in values:
                continue
            gene = canonical_gene(row[gene_i], mapping)
            ratio = float(row[ratio_i] or 0.0)
            if ratio > 1.0 and ratio <= 100.0:
                ratio /= 100.0
            if ratio < 0.0 or ratio > 1.0:
                raise ValueError(f'Detection ratio must be within 0-1 or 0-100: cluster={cluster}, gene={gene}, value={ratio}')
            if gene in values[cluster]:
                raise ValueError(f'Duplicate gene-cluster ratio row: cluster={cluster}, gene={gene}')
            values[cluster][gene] = {'ratio': ratio, 'mean': None if mean_i is None or row[mean_i] in (None, '', 'NA') else float(row[mean_i]), 'norm': None if norm_i is None or row[norm_i] in (None, '', 'NA') else float(row[norm_i])}
    missing = [cluster for cluster, genes in values.items() if not genes]
    if missing:
        raise ValueError(f'Ratio table lacks rows for clusters: {missing}')
    if require_complete:
        expected = {canonical_gene(gene, mapping) for gene in expected_genes or [] if str(gene).strip()}
        if not expected:
            raise ValueError('Strict full-ratio validation requires the average-expression gene universe; the input evidence did not provide average_gene_names')
        missing_genes = {cluster: sorted(expected - set(genes)) for cluster, genes in values.items() if expected - set(genes)}
        if missing_genes:
            preview = {cluster: genes[:20] for cluster, genes in missing_genes.items()}
            raise ValueError(f'Strict full-ratio table is incomplete for the average-expression gene universe: {preview}')
    return values


def _validate_runtime_snapshot(config, knowledge_base):
    """Reject mixed core/config/knowledge-base snapshots before scoring."""
    snapshot = _snapshot_metadata()
    expected = {'core_version': CORE_VERSION, 'config_version': str(config.get('config_version', '')), 'knowledge_base_version': str(config.get('knowledge_base_version', ''))}
    mismatches = {key: {'runtime': value, 'snapshot': str(snapshot.get(key, ''))} for key, value in expected.items() if snapshot.get(key) and str(snapshot.get(key)) != value}
    kb_version = str(knowledge_base.get('knowledge_base_version', ''))
    if kb_version and expected['knowledge_base_version'] and (kb_version != expected['knowledge_base_version']):
        mismatches['knowledge_base_runtime'] = {'runtime': kb_version, 'config': expected['knowledge_base_version']}
    if mismatches:
        raise RuntimeError(f'Annotation runtime snapshot mismatch; do not evaluate with mixed versions: {mismatches}')
    return snapshot


def marker_ratio_table(evidence, mapping):
    values = {str(cluster): {} for cluster in evidence['clusters']}
    for cluster in evidence['clusters']:
        for record in evidence['cluster_profiles'][str(cluster)].get('top_markers', []):
            gene = canonical_gene(record['gene'], mapping)
            values[str(cluster)][gene] = {'ratio': float(record.get('pct1', 0.0)), 'background': float(record.get('pct2', 0.0)), 'log2FC': float(record.get('log2FC', 0.0))}
    return values


def gene_metric(gene, cluster, values, clusters, thresholds, full_ratio):
    current = values.get(str(cluster), {}).get(gene)
    if current is None:
        if full_ratio:
            return {'gene': gene, 'p_in': 0.0, 'p_background': 0.0, 'delta': 0.0, 'robust_z': 0.0, 'detected': False, 'strong': False, 'review': False, 'log2FC': None}
        return None
    p_in = float(current.get('ratio', 0.0))
    if full_ratio:
        background_values = [float(values[str(other)][gene]['ratio']) for other in clusters if str(other) != str(cluster) and gene in values.get(str(other), {})]
        background = median(background_values) if background_values else 0.0
        spread = 1.4826 * _mad(background_values)
        robust_z = (p_in - background) / max(spread, 0.05)
    else:
        background = float(current.get('background', 0.0))
        spread = 0.0
        robust_z = (p_in - background) / 0.1
    delta = p_in - background
    adaptive_primary = background + thresholds['primary_robust_z'] * max(spread, 0.02) if full_ratio else thresholds['primary_detection_floor']
    primary_threshold = max(thresholds['primary_detection_floor'], adaptive_primary)
    return {'gene': gene, 'p_in': round(p_in, 4), 'p_background': round(background, 4), 'delta': round(delta, 4), 'robust_z': round(robust_z, 3), 'detected': p_in >= thresholds['minimum_detection_floor'], 'strong': p_in >= primary_threshold and (delta >= thresholds['minimum_detection_delta'] or robust_z >= thresholds['primary_robust_z']), 'review': p_in >= thresholds['rival_review_floor'] and (delta >= thresholds['minimum_detection_delta'] / 2 or robust_z >= thresholds['rival_robust_z']), 'log2FC': current.get('log2FC')}


def load_cell_evidence(path):
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Cell evidence must be a JSON object keyed by cluster')
    return {str(key): value for key, value in data.items()}


def _program_hits(cluster, values, marker_floors):
    hits = []
    for gene, floor in marker_floors.items():
        ratio = float(values.get(cluster, {}).get(_norm(gene), {}).get('ratio', 0.0))
        if ratio >= float(floor):
            hits.append({'gene': _norm(gene), 'ratio': round(ratio, 4), 'floor': float(floor)})
    return hits


def _program_detection_profile(cluster, values, marker_floors):
    """Summarize all marker prevalences, including values below hit floors."""
    ratios = {_norm(gene): round(float(values.get(cluster, {}).get(_norm(gene), {}).get('ratio', 0.0)), 4) for gene in marker_floors}
    hits = _program_hits(cluster, values, marker_floors)
    return {'marker_ratios': ratios, 'marker_hits': hits, 'hit_count': len(hits), 'mean_detection': round(sum(ratios.values()) / len(ratios), 4) if ratios else 0.0}


def _borderline_program_hit(cluster, values, gene, floor, minimum_fraction):
    ratio = float(values.get(cluster, {}).get(_norm(gene), {}).get('ratio', 0.0))
    near_floor = float(floor) * float(minimum_fraction)
    if near_floor <= ratio < float(floor):
        return {'gene': _norm(gene), 'ratio': round(ratio, 4), 'floor': float(floor), 'near_floor': round(near_floor, 4), 'floor_fraction': float(minimum_fraction)}
    return {}


def _myeloid_boundary_audit(config, cluster, values, full_ratio, cell_evidence=None):
    """Audit program-level myeloid boundaries that isolated markers cannot resolve."""
    rules = config.get('myeloid_boundary_rules', {})
    if not full_ratio or not rules:
        return {'assessed': False, 'reason': 'requires_full_cluster_ratio'}
    neutrophil_rule = rules.get('neutrophil_vs_monocyte', {})
    monocyte_hits = _program_hits(cluster, values, neutrophil_rule.get('monocyte_program', {}).get('markers', {}))
    monocyte_minimum = int(neutrophil_rule.get('monocyte_program', {}).get('minimum_markers', 4))
    commitment_hits = _program_hits(cluster, values, neutrophil_rule.get('neutrophil_commitment', {}).get('markers', {}))
    commitment_minimum = int(neutrophil_rule.get('neutrophil_commitment', {}).get('minimum_markers', 2))
    alternatives = []
    for program in neutrophil_rule.get('neutrophil_program_alternatives', []):
        required_hits = _program_hits(cluster, values, program.get('required_markers', {}))
        program_hits = _program_hits(cluster, values, program.get('markers', {}))
        required_passed = len(required_hits) == len(program.get('required_markers', {}))
        passed = required_passed and len(program_hits) >= int(program.get('minimum_markers', 1))
        alternatives.append({'program_id': program.get('program_id', ''), 'passed': passed, 'required_hits': required_hits, 'marker_hits': program_hits, 'minimum_markers': int(program.get('minimum_markers', 1))})
    alternative_commitment_rule = neutrophil_rule.get('alternative_program_can_complete_commitment', {})
    alternative_commitment_hits = _program_hits(cluster, values, alternative_commitment_rule.get('required_anchor_markers', {}))
    alternative_commitment_passed = bool(alternative_commitment_rule.get('enabled', False) and len(alternative_commitment_hits) >= int(alternative_commitment_rule.get('minimum_required_anchors', 1)) and any((item['passed'] for item in alternatives)))
    neutrophil_commitment_passed = bool(len(commitment_hits) >= commitment_minimum or alternative_commitment_passed)
    neutrophil_program_passed = neutrophil_commitment_passed and any((item['passed'] for item in alternatives))
    immature_neutrophil_program_passed = any((item['program_id'] == 'early_granule_neutrophil' and item['passed'] for item in alternatives))
    monocyte_program_passed = len(monocyte_hits) >= monocyte_minimum
    borderline_rule = neutrophil_rule.get('borderline_activated_neutrophil', {})
    borderline_anchor_hits = _program_hits(cluster, values, borderline_rule.get('required_anchor_markers', {}))
    borderline_gene = str(borderline_rule.get('borderline_marker', '')).strip()
    commitment_markers = neutrophil_rule.get('neutrophil_commitment', {}).get('markers', {})
    borderline_hit = _borderline_program_hit(cluster, values, borderline_gene, commitment_markers.get(borderline_gene, 1.0), borderline_rule.get('borderline_floor_fraction', 0.75)) if borderline_gene else {}
    borderline_program = next((item for item in alternatives if item['program_id'] == borderline_rule.get('program_id', '')), {})
    borderline_activated_neutrophil_candidate = bool(borderline_rule and len(borderline_anchor_hits) == len(borderline_rule.get('required_anchor_markers', {})) and borderline_hit and (len(borderline_program.get('marker_hits', [])) >= int(borderline_rule.get('minimum_program_markers', 2))) and (not borderline_rule.get('requires_monocyte_program_absent', True) or not monocyte_program_passed))
    dc_identity_programs = {}
    for identity, program in rules.get('dc_identity_programs', {}).items():
        hits = _program_hits(cluster, values, program.get('markers', {}))
        minimum = int(program.get('minimum_markers', 2))
        relative = [
            metric for gene in program.get('markers', {})
            if (metric := gene_metric(gene, cluster, values, list(values), config.get('thresholds', {}), full_ratio)) is not None
            if metric.get('review')
        ]
        strong_relative = [metric for metric in relative if metric.get('strong')]
        minimum_relative = int(program.get('minimum_relative_markers', minimum))
        minimum_strong = int(program.get('minimum_strong_markers', 1))
        passed = bool(len(hits) >= minimum and len(relative) >= minimum_relative and len(strong_relative) >= minimum_strong)
        dc_identity_programs[identity] = {'passed': passed, 'marker_hits': hits, 'relative_marker_hits': relative, 'strong_relative_marker_hits': strong_relative, 'minimum_markers': minimum, 'minimum_relative_markers': minimum_relative, 'minimum_strong_markers': minimum_strong}
    dc_like_rule = rules.get('dc_like_activation', {})
    dc_like_hits = _program_hits(cluster, values, dc_like_rule.get('markers', {}))
    dc_like_activation = {'passed': len(dc_like_hits) >= int(dc_like_rule.get('minimum_markers', 2)), 'marker_hits': dc_like_hits, 'minimum_markers': int(dc_like_rule.get('minimum_markers', 2)), 'interpretation': 'state_support_only_not_DC_identity'}
    dc_rule = rules.get('dc3_vs_monocyte', {})
    apc_rule = dc_rule.get('apc_program', {})
    dc_specific_rule = dc_rule.get('dc_specific_program', {})
    monocyte_specific_rule = dc_rule.get('monocyte_specific_program', dc_rule.get('monocyte_program', {}))
    pan_myeloid_rule = dc_rule.get('pan_myeloid_support', {})
    apc_profile = _program_detection_profile(cluster, values, apc_rule.get('markers', {}))
    dc_specific_profile = _program_detection_profile(cluster, values, dc_specific_rule.get('markers', {}))
    monocyte_specific_profile = _program_detection_profile(cluster, values, monocyte_specific_rule.get('markers', {}))
    pan_myeloid_profile = _program_detection_profile(cluster, values, pan_myeloid_rule.get('markers', {}))
    macrophage_rule = dc_rule.get('macrophage_exclusion', {})
    macrophage_profile = _program_detection_profile(cluster, values, macrophage_rule.get('markers', {}))
    apc_hits = apc_profile['marker_hits']
    dc_hits = dc_specific_profile['marker_hits']
    dc_monocyte_hits = monocyte_specific_profile['marker_hits']
    thresholds = config.get('thresholds', {})
    dc_specific_review_hits = [
        metric for gene in dc_specific_rule.get('markers', {})
        if (metric := gene_metric(gene, cluster, values, list(values), thresholds, full_ratio)) is not None
        if metric.get('review')
    ]
    monocyte_specific_review_hits = [
        metric for gene in monocyte_specific_rule.get('markers', {})
        if (metric := gene_metric(gene, cluster, values, list(values), thresholds, full_ratio)) is not None
        if metric.get('review')
    ]
    monocyte_specific_minimum = int(monocyte_specific_rule.get('minimum_markers', 3))
    two_marker_rule = monocyte_specific_rule.get('two_marker_competitive_exception', {})
    dc_mean = float(dc_specific_profile['mean_detection'])
    monocyte_mean = float(monocyte_specific_profile['mean_detection'])
    macrophage_mean = float(macrophage_profile['mean_detection'])
    macrophage_competing = bool(len(macrophage_profile['marker_hits']) >= int(macrophage_rule.get('minimum_markers', 3)) and macrophage_mean >= float(macrophage_rule.get('minimum_mean_detection', 0.35)) and (macrophage_mean >= dc_mean * float(macrophage_rule.get('minimum_ratio_to_dc_specific', 1.0))))
    two_marker_competitive = bool(len(dc_monocyte_hits) >= int(two_marker_rule.get('minimum_markers', 2)) and monocyte_mean >= float(two_marker_rule.get('minimum_mean_detection', 0.25)) and (monocyte_mean >= dc_mean * float(two_marker_rule.get('minimum_ratio_to_dc', 0.8))))
    monocyte_specific_competitive = bool(len(dc_monocyte_hits) >= monocyte_specific_minimum or two_marker_competitive)
    dominance_rule = dc_rule.get('cdc2_dominance_review', {})
    cdc2_dominant = bool(len(dc_hits) >= int(dominance_rule.get('minimum_dc_specific_markers', 3)) and len(dc_monocyte_hits) <= int(dominance_rule.get('maximum_monocyte_specific_markers', 2)) and (dc_mean >= monocyte_mean * float(dominance_rule.get('minimum_dominance_ratio', 1.5))) and (dc_mean - monocyte_mean >= float(dominance_rule.get('minimum_absolute_margin', 0.2))))
    minimum_dc_review = int(dc_specific_rule.get('minimum_relative_markers', 2))
    minimum_monocyte_review = int(monocyte_specific_rule.get('minimum_relative_markers', 2))
    dc3_candidate = bool(len(apc_hits) >= int(apc_rule.get('minimum_markers', 3)) and len(dc_hits) >= int(dc_specific_rule.get('minimum_markers', 2)) and len(dc_specific_review_hits) >= minimum_dc_review and monocyte_specific_competitive and len(monocyte_specific_review_hits) >= minimum_monocyte_review and (not macrophage_competing))
    if dc3_candidate:
        boundary_reason = 'coherent_dc_and_monocyte_specific_programs'
    elif cdc2_dominant:
        boundary_reason = 'cdc2_dominant_over_weak_monocyte_background'
    elif macrophage_competing:
        boundary_reason = 'macrophage_program_dominates_dc3_competitor'
    elif len(apc_hits) < int(apc_rule.get('minimum_markers', 3)):
        boundary_reason = 'apc_program_incomplete'
    elif len(dc_hits) < int(dc_specific_rule.get('minimum_markers', 2)):
        boundary_reason = 'dc_specific_program_incomplete'
    else:
        boundary_reason = 'monocyte_specific_program_not_competitive'
    validation = (cell_evidence or {}).get('identity_boundary_validation', {})
    cell_level_validated = bool(validation.get('rule_id') == dc_rule.get('rule_id') and validation.get('coexpression_validated') is True and str(validation.get('method', '')).strip())
    return {'assessed': True, 'neutrophil_vs_monocyte': {'rule_id': neutrophil_rule.get('rule_id', ''), 'monocyte_program_passed': monocyte_program_passed, 'monocyte_hits': monocyte_hits, 'neutrophil_commitment_passed': neutrophil_commitment_passed, 'neutrophil_commitment_hits': commitment_hits, 'alternative_commitment_passed': alternative_commitment_passed, 'alternative_commitment_hits': alternative_commitment_hits, 'neutrophil_program_passed': neutrophil_program_passed, 'immature_neutrophil_program_passed': immature_neutrophil_program_passed, 'borderline_activated_neutrophil_candidate': borderline_activated_neutrophil_candidate, 'borderline_anchor_hits': borderline_anchor_hits, 'borderline_commitment_hit': borderline_hit, 'neutrophil_program_alternatives': alternatives, 'neutrophil_blocked_by_monocyte': bool(monocyte_program_passed and neutrophil_commitment_passed and (not neutrophil_program_passed))}, 'dc_identity_programs': dc_identity_programs, 'dc_like_activation': dc_like_activation, 'dc3_vs_monocyte': {'rule_id': dc_rule.get('rule_id', ''), 'dc3_boundary_candidate': dc3_candidate, 'apc_hits': apc_hits, 'dc_specific_hits': dc_hits, 'dc_specific_review_hits': dc_specific_review_hits, 'monocyte_hits': dc_monocyte_hits, 'monocyte_specific_hits': dc_monocyte_hits, 'monocyte_specific_review_hits': monocyte_specific_review_hits, 'pan_myeloid_hits': pan_myeloid_profile['marker_hits'], 'macrophage_hits': macrophage_profile['marker_hits'], 'apc_program_mean': apc_profile['mean_detection'], 'cdc2_program_mean': dc_specific_profile['mean_detection'], 'monocyte_specific_program_mean': monocyte_specific_profile['mean_detection'], 'pan_myeloid_program_mean': pan_myeloid_profile['mean_detection'], 'macrophage_program_mean': macrophage_mean, 'monocyte_specific_competitive': monocyte_specific_competitive, 'two_marker_competitive_exception': two_marker_competitive, 'macrophage_competing': macrophage_competing, 'dc3_blocked_by_macrophage': macrophage_competing, 'cdc2_dominant': cdc2_dominant, 'boundary_reason': boundary_reason, 'cell_level_validated': cell_level_validated, 'validation_method': str(validation.get('method', ''))}}


def _absolute_program_gate(label, config, cluster, values, full_ratio):
    """Validate a configured leaf program without cluster-relative enrichment.

    Repeated canonical identities can be abundant in one subset, so every member may
    have weak median/MAD specificity even when the absolute identity program is intact.
    This gate remains conservative by requiring core, supportive, and parent-lineage
    anchors together with explicit incompatible-program exclusions.
    """
    rule = next((item for item in config.get('absolute_program_rules', []) if item.get('label') == label), None)
    if not full_ratio or not rule:
        return {'rule_id': '', 'assessed': False, 'passed': False, 'required': False}

    def detected(key, floor_key, default_floor):
        return _detected_branch_anchors(cluster, values, rule.get(key, []), float(rule.get(floor_key, default_floor)))
    core = detected('core_anchors', 'core_detection_floor', 0.25)
    supportive = detected('supportive_anchors', 'supportive_detection_floor', 0.1)
    parent = detected('parent_anchors', 'parent_detection_floor', 0.1)
    forbidden_hits = []
    for forbidden in rule.get('forbidden_programs', []):
        genes = forbidden.get('anchors', [])
        anchors = _detected_branch_anchors(cluster, values, genes, float(forbidden.get('detection_floor', 0.1)))
        minimum_dataset_fraction = forbidden.get('minimum_dataset_fraction')
        dataset_fractions = {}
        if minimum_dataset_fraction is not None:
            relative_anchors = []
            for gene in anchors:
                current = float(values.get(str(cluster), {}).get(gene, {}).get('ratio', 0.0))
                peak = max((float(profile.get(gene, {}).get('ratio', 0.0)) for profile in values.values()), default=0.0)
                fraction = current / peak if peak > 0 else 0.0
                dataset_fractions[gene] = round(fraction, 4)
                if fraction >= float(minimum_dataset_fraction):
                    relative_anchors.append(gene)
            anchors = relative_anchors
        if len(anchors) >= int(forbidden.get('minimum_anchors', 1)):
            hit = {'program': forbidden.get('program', 'forbidden'), 'anchors': anchors}
            if minimum_dataset_fraction is not None:
                hit['minimum_dataset_fraction'] = float(minimum_dataset_fraction)
                hit['dataset_fractions'] = dataset_fractions
            forbidden_hits.append(hit)
    passed = bool(len(core) >= int(rule.get('minimum_core_anchors', 2)) and len(supportive) >= int(rule.get('minimum_supportive_anchors', 1)) and (len(parent) >= int(rule.get('minimum_parent_anchors', 2))) and (not forbidden_hits))
    return {'rule_id': rule.get('rule_id', ''), 'assessed': True, 'passed': passed, 'required': bool(rule.get('required', False)), 'core_anchors': core, 'supportive_anchors': supportive, 'parent_anchors': parent, 'forbidden_program_hits': forbidden_hits, 'coherence_basis': 'absolute_program_with_lineage_and_exclusion_gates'}


def _major_label(config, label):
    default = config.get('major_label_map', {}).get(label, label)
    vocabulary = {str(item).strip() for item in config.get('project_major_vocabulary', []) if str(item).strip()}
    if not vocabulary:
        return default
    if label in vocabulary:
        return label
    path = list(config.get('panel_provenance', {}).get(label, {}).get('parent_path', []))
    for candidate in reversed(path):
        if candidate in vocabulary:
            return candidate
    equivalences = config.get('project_major_vocabulary_policy', {}).get('identity_equivalences', {})
    for candidate in equivalences.get(label, []):
        if candidate in vocabulary:
            return candidate
    return default


def _identity_path(config, label):
    path = config.get('panel_provenance', {}).get(label, {}).get('parent_path', [])
    return list(path) if path else [label]


def normalize_user_constraints(constraints, clusters, mapping=None):
    """Normalize explicit per-run annotation constraints into an auditable contract."""
    raw = constraints if isinstance(constraints, dict) else {}
    cluster_ids = {str(cluster) for cluster in clusters}

    def values(*names):
        result = []
        for name in names:
            value = raw.get(name, [])
            if value is None:
                continue
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, (list, tuple, set)):
                raise ValueError(f'Annotation constraint {name} must be a list or string')
            result.extend((str(item).strip() for item in value if str(item).strip()))
        return result

    def unique(items, normalize=False):
        result, seen = ([], set())
        for item in items:
            key = _norm(item) if normalize else str(item).strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key if normalize else str(item).strip())
        return sorted(result)
    global_labels = unique(values('exclude_labels', 'excluded_labels'))
    global_markers = unique(values('conflict_markers', 'exclude_markers', 'blocked_positive_markers'), normalize=True)
    if mapping:
        global_markers = sorted({canonical_gene(gene, mapping) for gene in global_markers})
    raw_clusters = raw.get('clusters', raw.get('by_cluster', {})) or {}
    if not isinstance(raw_clusters, dict):
        raise ValueError('Annotation constraint clusters/by_cluster must be an object')
    by_cluster = {}
    for cluster, item in raw_clusters.items():
        cluster = str(cluster).strip()
        if cluster not in cluster_ids:
            raise ValueError(f'Annotation constraints reference an unknown cluster: {cluster}')
        if not isinstance(item, dict):
            raise ValueError(f'Annotation constraint for cluster {cluster} must be an object')
        raw_labels = item.get('exclude_labels', item.get('excluded_labels', [])) or []
        raw_markers = item.get('conflict_markers', item.get('exclude_markers', item.get('blocked_positive_markers', []))) or []
        if isinstance(raw_labels, str):
            raw_labels = [raw_labels]
        if isinstance(raw_markers, str):
            raw_markers = [raw_markers]
        labels = unique(raw_labels)
        markers = unique(raw_markers, normalize=True)
        if mapping:
            markers = sorted({canonical_gene(gene, mapping) for gene in markers})
        by_cluster[cluster] = {'exclude_labels': labels, 'conflict_markers': markers}
    return {'provided': bool(global_labels or global_markers or by_cluster), 'exclude_labels': global_labels, 'conflict_markers': global_markers, 'by_cluster': by_cluster, 'semantics': {'exclude_labels': 'Hard final-label exclusion; evidence remains visible and cannot be silently reassigned.', 'conflict_markers': 'Removed from positive identity/state scoring and retained as explicit conflict/contamination evidence.'}}


def _belongs_to_any(config, label, ancestors):
    path = set(_identity_path(config, label))
    return any((ancestor == label or ancestor in path for ancestor in ancestors))


def _detected_branch_anchors(cluster, values, genes, floor):
    cluster_values = values.get(str(cluster), {})
    return [gene for gene in genes if gene in cluster_values and float(cluster_values[gene].get('ratio', 0.0)) >= floor]


def _relative_branch_anchors(cluster, values, genes, floor, minimum_fraction):
    cluster_values = values.get(str(cluster), {})
    anchors = []
    fractions = {}
    for gene in genes:
        current = float(cluster_values.get(gene, {}).get('ratio', 0.0))
        peak = max((float(profile.get(gene, {}).get('ratio', 0.0)) for profile in values.values()), default=0.0)
        fraction = current / peak if peak > 0 else 0.0
        fractions[gene] = round(fraction, 4)
        if current >= floor and fraction >= minimum_fraction:
            anchors.append(gene)
    return (anchors, fractions)


def _identity_branch_gate(candidate, config, cluster, values, full_ratio):
    """Require lineage-defining CD4/CD8 anchors before accepting a branch-specific leaf."""
    matched = []
    for rule in config.get('identity_branch_gates', []):
        if not _belongs_to_any(config, candidate['label'], rule.get('ancestors', [])):
            continue
        floor = float(rule.get('anchor_detection_floor', 0.1))
        anchors = _detected_branch_anchors(cluster, values, rule.get('required_anchors', []), floor)
        minimum = int(rule.get('minimum_required_anchors', 1))
        forbidden_ceiling = float(rule.get('forbidden_detection_ceiling', 1.01))
        forbidden_anchors = _detected_branch_anchors(cluster, values, rule.get('forbidden_anchors', []), forbidden_ceiling)
        maximum_forbidden = int(rule.get('maximum_forbidden_anchors', len(rule.get('forbidden_anchors', []))))
        relative_floor = rule.get('relative_reference_min_fraction')
        relative_anchors = []
        relative_fractions = {}
        relative_minimum = int(rule.get('minimum_relative_anchors', minimum))
        if relative_floor is not None:
            relative_anchors, relative_fractions = _relative_branch_anchors(cluster, values, rule.get('required_anchors', []), floor, float(relative_floor))
        if full_ratio:
            assessed = True
            passed = len(anchors) >= minimum and len(forbidden_anchors) <= maximum_forbidden and (relative_floor is None or len(relative_anchors) >= relative_minimum)
        else:
            assessed = len(anchors) >= minimum
            passed = True
        matched.append({'rule_id': rule['rule_id'], 'assessed': assessed, 'passed': passed, 'required_anchors': list(rule.get('required_anchors', [])), 'detected_anchors': anchors, 'minimum_required_anchors': minimum, 'anchor_detection_floor': floor, 'forbidden_anchors': list(rule.get('forbidden_anchors', [])), 'detected_forbidden_anchors': forbidden_anchors, 'forbidden_detection_ceiling': forbidden_ceiling if rule.get('forbidden_anchors') else None, 'maximum_forbidden_anchors': maximum_forbidden if rule.get('forbidden_anchors') else 0, 'relative_reference_min_fraction': relative_floor, 'minimum_relative_anchors': relative_minimum if relative_floor is not None else 0, 'relative_reference_anchors': relative_anchors, 'relative_reference_fractions': relative_fractions, 'evidence_mode': 'full_ratio' if full_ratio else 'positive_markers_only'})
    if not matched:
        return {'rule_id': '', 'assessed': True, 'passed': True, 'required_anchors': [], 'detected_anchors': [], 'minimum_required_anchors': 0, 'anchor_detection_floor': None, 'evidence_mode': 'not_applicable'}
    failed = [item for item in matched if not item['passed']]
    if failed:
        return failed[0]
    assessed = [item for item in matched if item['assessed']]
    specific = [item for item in assessed if item['rule_id'] != 'REQUIRE_COHERENT_TCR_PROGRAM']
    if specific:
        return specific[0]
    return assessed[0] if assessed else matched[0]


def _program_profile(cluster, values, program):
    """Summarize cluster prevalence for a biological identity program."""
    floor = float(program.get('detection_floor', 0.1))
    genes = [_norm(gene) for gene in program.get('anchors', [])]
    ratios = {gene: float(values.get(str(cluster), {}).get(gene, {}).get('ratio', 0.0)) for gene in genes}
    detected = [gene for gene, ratio in ratios.items() if ratio >= floor]
    return {'anchors': genes, 'detected_anchors': detected, 'minimum_anchors': int(program.get('minimum_anchors', 2)), 'detection_floor': floor, 'ratios': {gene: round(ratio, 4) for gene, ratio in ratios.items()}, 'mean_detection': round(sum(ratios.values()) / len(ratios), 4) if ratios else 0.0, 'coherent': len(detected) >= int(program.get('minimum_anchors', 2))}


def _mutually_exclusive_program_gate(candidate, config, cluster, values, full_ratio):
    """Arbitrate identity-defining sibling programs before subtype scoring."""
    if not full_ratio:
        return {'rule_id': '', 'assessed': False, 'passed': True, 'reason': 'requires_full_cluster_ratio'}
    assessments = []
    for rule in config.get('mutually_exclusive_program_rules', []):
        sides = rule.get('sides', {})
        candidate_side = next((name for name, side in sides.items() if _belongs_to_any(config, candidate['label'], side.get('ancestors', []))), '')
        if not candidate_side:
            continue
        rival_side = next((name for name in sides if name != candidate_side), '')
        if not rival_side:
            continue
        own = _program_profile(cluster, values, sides[candidate_side])
        rival = _program_profile(cluster, values, sides[rival_side])
        own_mean = float(own['mean_detection'])
        rival_mean = float(rival['mean_detection'])
        ratio_threshold = float(rule.get('minimum_dominance_ratio', 1.25))
        margin_threshold = float(rule.get('minimum_absolute_margin', 0.1))
        rival_dominant = bool(rival['coherent'] and rival_mean >= own_mean * ratio_threshold and (rival_mean - own_mean >= margin_threshold))
        own_dominant = bool(own['coherent'] and own_mean >= rival_mean * ratio_threshold and (own_mean - rival_mean >= margin_threshold))
        unresolved_dual = bool(own['coherent'] and rival['coherent'] and (not own_dominant) and (not rival_dominant))
        assessments.append({'rule_id': rule.get('rule_id', ''), 'assessed': True, 'passed': bool(not rival_dominant), 'candidate_side': candidate_side, 'rival_side': rival_side, 'candidate_program': own, 'rival_program': rival, 'candidate_dominant': own_dominant, 'rival_dominant': rival_dominant, 'unresolved_dual_program': unresolved_dual, 'minimum_dominance_ratio': ratio_threshold, 'minimum_absolute_margin': margin_threshold, 'resolution': 'candidate_dominant' if own_dominant else 'rival_dominant' if rival_dominant else 'unresolved_requires_cell_level_validation' if unresolved_dual else 'candidate_program_incoherent', 'validation_ladder': rule.get('validation_ladder', []), 'biological_invariant': rule.get('biological_invariant', '')})
    if not assessments:
        return {'rule_id': '', 'assessed': True, 'passed': True, 'reason': 'not_applicable'}
    failed = [item for item in assessments if not item['passed']]
    unresolved = [item for item in assessments if item['unresolved_dual_program']]
    selected = dict((failed or unresolved or assessments)[0])
    selected['passed'] = all((item['passed'] for item in assessments))
    selected['all_applicable_rules_passed'] = selected['passed']
    selected['assessments'] = assessments
    return selected
