"""Repair exports that were saved before viewer-vidi honoured MONOCHROME1.

Until then the viewer worked on the stored values of every film. For a film
stored as MONOCHROME1 (high value = black) that meant:

  NIfTI image / crop   stored values                -> a negative, always
  PNG / JPEG           what was on screen           -> right only if Invert was on

This script walks one output directory (the one holding manifest.csv) and,
for every saved row that carries no 'photometric' value yet, reads the HEADER
of the row's source file:

  MONOCHROME1  NIfTI image and crop are rewritten as  S - v  (the flip the
               viewer now applies at load, windowing.mono1_flip_sum); masks
               are not touched. 8-bit products are only CHECKED against the
               source and reported, never changed.
  otherwise    nothing to change.

The row then gets its 'photometric' value, and each rewritten NIfTI a note in
its header, so a second run changes nothing.

    python tools/repair_mono1.py <output dir>            dry run: report only
    python tools/repair_mono1.py <output dir> --apply    rewrite the files
    ... --list                                           also name the products

Run it with the viewer's Python environment.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import types
from collections import Counter

import numpy as np

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "viewer_vidi" not in sys.modules:        # same registration as run.py (dash in the dir name)
    _pkg = types.ModuleType("viewer_vidi")
    _pkg.__path__ = [_SRC]
    _pkg.__package__ = "viewer_vidi"
    _pkg.__file__ = os.path.join(_SRC, "__init__.py")
    sys.modules["viewer_vidi"] = _pkg
    importlib.util.spec_from_file_location("viewer_vidi", _pkg.__file__).loader.exec_module(_pkg)

from viewer_vidi.dicom_sniff import list_dicom_files          # noqa: E402
from viewer_vidi.windowing import mono1_flip_sum              # noqa: E402
from viewer_vidi.workspace import (                           # noqa: E402
    FILES_SEP, MANIFEST_NAME, STATUS_SAVED, read_manifest, write_manifest_row,
)

NOTE = b"vidi: MONOCHROME1 flipped"       # NIfTI header 'descrip' of a rewritten file
_IMAGE_SUFFIXES = ("_image", "_roi")      # products holding image values (not masks)


def _kind(rel: str) -> tuple[str, str]:
    """('nifti' | 'png' | 'jpeg' | '', product suffix) of a manifest 'files' entry."""
    fmt = rel.replace("\\", "/").split("/")[0]
    name = os.path.basename(rel)
    for ext in (".nii.gz", ".png", ".jpg"):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break
    suffix = next((s for s in ("_roi_mask", "_mask", "_image", "_roi") if name.endswith(s)), "")
    return (fmt if fmt in ("nifti", "png", "jpeg") else ""), suffix


def _source_file(source: str, root: str) -> str | None:
    """The DICOM file a manifest 'source' stands for (first file of a series dir)."""
    path = source if os.path.isabs(source) else os.path.join(root, source)
    if os.path.isdir(path):
        files = list_dicom_files(path)
        return files[0] if files else None
    return path if os.path.isfile(path) else None


def _flip_nifti(path: str, flip: float, apply: bool) -> str:
    """'flipped' | 'already' — rewrite one NIfTI as flip - v (atomically)."""
    import nibabel as nib
    img = nib.load(path)
    if NOTE in bytes(img.header["descrip"].tobytes()):
        return "already"
    if apply:
        data = np.float32(flip) - np.asarray(img.dataobj, dtype=np.float32)
        header = img.header.copy()
        header["descrip"] = NOTE
        tmp = path + ".tmp.nii.gz"
        nib.save(nib.Nifti1Image(data, img.affine, header), tmp)
        os.replace(tmp, path)
    return "flipped"


def _eight_bit_polarity(path: str, stored: np.ndarray, rect) -> str:
    """How an 8-bit product of a MONOCHROME1 film relates to the stored values:
    'right' (bright where the stored value is low — Invert was on), 'negative'
    (bright where it is high) or 'unclear'."""
    from PIL import Image
    with Image.open(path) as im:
        u8 = np.asarray(im.convert("L"), dtype=np.float32)
    ref = stored
    if rect is not None:
        x0, y0, x1, y1 = rect
        ref = stored[y0:y1, x0:x1]
    if u8.shape != ref.shape or u8.size < 4:
        return "unclear"
    step = max(1, min(u8.shape) // 256)
    a, b = u8[::step, ::step].ravel(), ref[::step, ::step].astype(np.float32).ravel()
    if a.std() == 0 or b.std() == 0:
        return "unclear"
    r = float(np.corrcoef(a, b)[0, 1])
    return "negative" if r > 0.2 else "right" if r < -0.2 else "unclear"


def repair(out_dir: str, apply: bool = False, listing: bool = False, out=print) -> Counter:
    """Walk the manifest of *out_dir*; returns the counts that are printed."""
    import pydicom
    manifest = os.path.join(out_dir, MANIFEST_NAME)
    root = os.path.dirname(os.path.abspath(out_dir))
    rows = read_manifest(manifest)
    n = Counter(rows=len(rows))
    named: list[str] = []

    for stem in sorted(rows):
        row = rows[stem]
        if row.get("status") != STATUS_SAVED:
            n["not saved (deleted mark)"] += 1
            continue
        if row.get("photometric"):
            n["already in the new convention"] += 1
            continue
        src = _source_file(row.get("source", ""), root)
        if src is None:
            n["source not found — left alone"] += 1
            continue
        try:
            ds = pydicom.dcmread(src, stop_before_pixels=True)
        except Exception:
            n["source is not DICOM — nothing to do"] += 1
            continue
        photometric = str(ds.get("PhotometricInterpretation", "") or "").strip()
        flip = mono1_flip_sum(ds)
        if flip is None:
            n["not MONOCHROME1 — nothing to change"] += 1
        else:
            n["MONOCHROME1 films"] += 1
            cell = row.get("files", "")     # ';'-separated; older rows used spaces
            stored = None
            for rel in (f for f in cell.split(FILES_SEP if FILES_SEP in cell else " ") if f):
                fmt, suffix = _kind(rel)
                path = os.path.join(out_dir, rel)
                if suffix not in _IMAGE_SUFFIXES or not os.path.isfile(path):
                    continue
                if fmt == "nifti":
                    state = _flip_nifti(path, flip, apply)
                    n[f"NIfTI {'rewritten' if apply else 'to rewrite'}" if state == "flipped"
                      else "NIfTI already rewritten"] += 1
                    if state == "flipped":
                        named.append(f"flip      {rel}")
                elif fmt in ("png", "jpeg"):
                    if stored is None:
                        stored = pydicom.dcmread(src).pixel_array
                    try:
                        rect = tuple(int(row[k]) for k in ("x0", "y0", "x1", "y1")) if suffix == "_roi" else None
                    except (KeyError, ValueError):
                        rect = None
                    verdict = _eight_bit_polarity(path, stored, rect)
                    n[f"8-bit products: {verdict}"] += 1
                    if verdict != "right":
                        named.append(f"{verdict:<9} {rel}")
        if apply:
            write_manifest_row(manifest, {**row, "photometric": photometric or "unknown"})

    out(f"{manifest}")
    for key, count in n.items():
        out(f"  {count:>6}  {key}")
    if listing:
        for line in named:
            out("  " + line)
    out("Applied." if apply else "Dry run — nothing was written. Add --apply to rewrite.")
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out_dir", help="output directory holding manifest.csv (or the workspace above it)")
    ap.add_argument("--apply", action="store_true", help="rewrite the files (default: report only)")
    ap.add_argument("--list", action="store_true", help="name every product that is rewritten or not right")
    args = ap.parse_args(argv)
    out_dir = args.out_dir
    if not os.path.isfile(os.path.join(out_dir, MANIFEST_NAME)):
        nested = os.path.join(out_dir, "vidi_output")
        if not os.path.isfile(os.path.join(nested, MANIFEST_NAME)):
            print(f"No {MANIFEST_NAME} in {out_dir}", file=sys.stderr)
            return 2
        out_dir = nested
    repair(out_dir, apply=args.apply, listing=args.list)
    return 0


if __name__ == "__main__":
    sys.exit(main())
