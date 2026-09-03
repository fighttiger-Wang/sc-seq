#!/usr/bin/env python3
"""Build the standardized qualitative major-celltype annotation workbook."""

import sys
from pathlib import Path


SKILL_NAME = "sc-major-celltype-annotation-auto"
SKILL_VERSION = "0.3.3"


def _load_shared():
    local = Path(__file__).resolve().parent
    if (local / "qualitative_annotation_workbook.py").is_file():
        if str(local) not in sys.path:
            sys.path.insert(0, str(local))
        import qualitative_annotation_workbook as module  # noqa: WPS433
        return module
    for parent in Path(__file__).resolve().parents:
        shared = parent / "shared" / "sc-annotation-evidence-core"
        if (shared / "qualitative_annotation_workbook.py").is_file():
            if str(shared) not in sys.path:
                sys.path.insert(0, str(shared))
            import qualitative_annotation_workbook as module  # noqa: WPS433
            return module
    raise RuntimeError("Shared qualitative annotation workbook module not found")


_SHARED = _load_shared()
cluster_sort_key = _SHARED.cluster_sort_key
normalize_final_label = _SHARED.normalize_final_label
inject_qualitative_evidence = _SHARED.inject_qualitative_evidence
inject_deterministic_evidence = inject_qualitative_evidence


def validate(records, clusters, evidence):
    normalized = _SHARED.normalize_records(records, evidence)
    records[:] = normalized
    return _SHARED.validate(records, clusters, evidence, annotation_level="major")


def main():
    return _SHARED.cli_main("major", SKILL_NAME, SKILL_VERSION)


if __name__ == "__main__":
    main()
