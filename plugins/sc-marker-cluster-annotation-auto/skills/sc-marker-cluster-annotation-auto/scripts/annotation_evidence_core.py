#!/usr/bin/env python3
"""Public entrypoint for the score-free qualitative annotation evidence core."""

from qualitative_evidence_core import enrich_evidence

CORE_VERSION = "3.1.2"

__all__ = ["CORE_VERSION", "enrich_evidence"]
