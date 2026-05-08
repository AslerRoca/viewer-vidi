"""Module-level drag payload for tree-to-cell drag and drop.

Using a module-level variable sidesteps Qt MIME serialization.
Only one drag can be in-flight at a time (GUI thread guarantee).
"""
from __future__ import annotations

_payload = None

MIME_TYPE = "application/x-dicom-series"


def set_payload(meta) -> None:
    global _payload
    _payload = meta


def get_payload():
    return _payload


def clear_payload() -> None:
    global _payload
    _payload = None
