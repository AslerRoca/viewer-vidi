"""Module-level drag payload for tree-to-cell drag and drop.

Using a module-level variable sidesteps Qt MIME serialization.
Only one drag can be in-flight at a time (GUI thread guarantee).
"""
from __future__ import annotations

_payload = None

MIME_TYPE = "application/x-dicom-series"

# Every drag from the study tree also names the dragged paths (for the Reports
# panel). A private type on purpose: with file URLs a drop outside the viewer
# would make the file manager copy the dragged folder.
PATHS_MIME_TYPE = "application/x-vidi-paths"


def encode_paths(paths) -> bytes:
    return "\0".join(paths).encode("utf-8")


def decode_paths(mime) -> list[str]:
    """Paths of a drag from the study tree; [] for any other drag."""
    raw = bytes(mime.data(PATHS_MIME_TYPE)).decode("utf-8", "replace")
    return [p for p in raw.split("\0") if p]


def set_payload(meta) -> None:
    global _payload
    _payload = meta


def get_payload():
    return _payload


def clear_payload() -> None:
    global _payload
    _payload = None
