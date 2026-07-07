"""Content-based DICOM detection for extensionless files (DICOMDIR/CD-style exports)."""
from __future__ import annotations

import os

# Catalogue indexes carry the DICM magic but hold no image data.
_INDEX_NAMES = frozenset({"dicomdir"})


def has_dicm_magic(path: str) -> bool:
    """True if *path* has the DICM preamble magic at byte offset 128."""
    try:
        with open(path, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except OSError:
        return False


def maybe_dicom_name(name: str) -> bool:
    """Extensionless, non-index filenames are candidates for magic sniffing."""
    nl = name.lower()
    return "." not in nl and nl not in _INDEX_NAMES


def is_dicom_file(path: str) -> bool:
    """True for .dcm files, or extensionless files with the DICM magic
    (scanner CD/DVD exports named e.g. DICOM/26070517/54450000/42217791)."""
    name = os.path.basename(path)
    if name.lower().endswith(".dcm"):
        return True
    return maybe_dicom_name(name) and os.path.isfile(path) and has_dicm_magic(path)


def list_dicom_files(directory: str, files: "list[str] | None" = None) -> list[str]:
    """Sorted full paths of DICOM files in *directory* (non-recursive).

    .dcm files match by name. Extensionless files are included when the first
    one sniffs as DICOM — export series dirs are homogeneous, so one 132-byte
    read decides for the whole directory instead of one read per file.
    """
    if files is None:
        try:
            files = os.listdir(directory)
        except OSError:
            return []
    dcm = [f for f in files if f.lower().endswith(".dcm")]
    if not dcm:
        extless = sorted(
            f for f in files
            if maybe_dicom_name(f) and os.path.isfile(os.path.join(directory, f))
        )
        if extless and has_dicm_magic(os.path.join(directory, extless[0])):
            dcm = extless
    return sorted(os.path.join(directory, f) for f in dcm)
