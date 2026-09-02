#!/usr/bin/env python3
"""Public import for qualitative annotation override validation."""

import sys
from pathlib import Path


for parent in Path(__file__).resolve().parents:
    shared = parent / "shared" / "sc-annotation-evidence-core"
    if (shared / "qualitative_override_policy.py").is_file():
        if str(shared) not in sys.path:
            sys.path.insert(0, str(shared))
        from qualitative_override_policy import validate_identity_override  # noqa: E402,F401
        break
else:
    from qualitative_override_policy import validate_identity_override  # noqa: F401

__all__ = ["validate_identity_override"]
