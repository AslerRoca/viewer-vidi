"""Bring an output directory written by an older viewer-vidi up to what the
viewer writes today, without reopening its items. Everything is derived from
manifest.csv (the rectangles are in it) and the source films. Two steps,
each asked for by its switch:

  --default-window   Films whose default window now comes from their VOI LUT
                     (no WindowCenter / WindowWidth in the header) used to
                     open with a guess, so their PNG / JPEG were saved with a
                     window set by hand, film by film. Their PNG / JPEG image
                     and crop are rendered again with the default window,
                     Invert off — one rule for all of them. The files that
                     are replaced are moved to <output dir>/replaced-<time>/
                     first. The row gets wc, ww, wl_default = 1, invert = 0.
                     NIfTI files are not touched (see repair_mono1.py).

  --rect-masks       Every saved row with a rectangle gets <stem>_rect_mask
                     (the rectangle as a mask on the whole image) in each of
                     its formats, as the viewer now writes it when Mask is
                     ticked. Nothing existing is changed.

    python tools/update_exports.py <output dir> --default-window --rect-masks
    python tools/update_exports.py <output dir> --default-window --rect-masks --apply

Without --apply nothing is written: the counts say what would happen. A
second run finds nothing left to do. Rows of volume slices (a 'view' in the
manifest) are left alone. Run it with the viewer's Python environment.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
import types
from collections import Counter
from datetime import datetime

import numpy as np

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if "viewer_vidi" not in sys.modules:        # same registration as run.py (dash in the dir name)
    _pkg = types.ModuleType("viewer_vidi")
    _pkg.__path__ = [_SRC]
    _pkg.__package__ = "viewer_vidi"
    _pkg.__file__ = os.path.join(_SRC, "__init__.py")
    sys.modules["viewer_vidi"] = _pkg
    importlib.util.spec_from_file_location("viewer_vidi", _pkg.__file__).loader.exec_module(_pkg)

from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item   # noqa: E402
from viewer_vidi.data_model import acq_plane_info                                   # noqa: E402
from viewer_vidi.dicom_sniff import list_dicom_files                                # noqa: E402
from viewer_vidi.windowing import apply_rescale, wl_from_dicom                      # noqa: E402
from viewer_vidi.workspace import (                                                 # noqa: E402
    FILES_SEP, MANIFEST_NAME, STATUS_SAVED, read_manifest, write_manifest_row,
)

_EIGHT_BIT = ("png", "jpeg")


def _files(row: dict) -> list[str]:
    cell = row.get("files", "")         # ';'-separated; older rows used spaces
    return [f for f in cell.split(FILES_SEP if FILES_SEP in cell else " ") if f]


def _product(rel: str) -> tuple[str, str]:
    """(format folder, product suffix) of a manifest 'files' entry."""
    name = os.path.basename(rel)
    for ext in (".nii.gz", ".png", ".jpg"):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break
    suffix = next((s for s in ("_roi_mask", "_rect_mask", "_mask", "_image", "_roi")
                   if name.endswith(s)), "")
    return rel.replace("\\", "/").split("/")[0], suffix


def _rect(row: dict):
    try:
        return tuple(int(row[k]) for k in ("x0", "y0", "x1", "y1"))
    except (KeyError, ValueError):
        return None


def _source_file(source: str, root: str) -> str | None:
    path = source if os.path.isabs(source) else os.path.join(root, source)
    if os.path.isdir(path):
        files = list_dicom_files(path)
        return files[0] if files else None
    return path if os.path.isfile(path) else None


def _header(row: dict, root: str):
    """pydicom header of the row's source film, or None."""
    import pydicom
    src = _source_file(row.get("source", ""), root)
    if src is None:
        return None, None
    try:
        return src, pydicom.dcmread(src, stop_before_pixels=True)
    except Exception:
        return src, None


def _shape(path: str) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size[1], im.size[0]


def _default_window(row, out_dir, root, backup_dir, apply, n) -> dict | None:
    """Re-render the 8-bit image products of one row; returns the row's new fields."""
    import pydicom
    if row.get("wl_default") == "1":
        n["window: already the default"] += 1
        return None
    src, ds = _header(row, root)
    if ds is None:
        n["window: source not found or not DICOM — left alone"] += 1
        return None
    if ds.get("WindowCenter") is not None or wl_from_dicom(ds)[0] is None:
        n["window: film has its own header window (or no LUT) — left alone"] += 1
        return None
    products = [f for f in _files(row) if _product(f)[0] in _EIGHT_BIT
                and _product(f)[1] in ("_image", "_roi") and os.path.isfile(os.path.join(out_dir, f))]
    if not products:
        n["window: LUT film without PNG / JPEG products"] += 1
        return None
    rect = _rect(row)
    for rel in products:                                # the new files must take the old ones' places exactly
        want = (int(ds.Rows), int(ds.Columns)) if _product(rel)[1] == "_image" else (
            (rect[3] - rect[1], rect[2] - rect[0]) if rect else None)
        if _shape(os.path.join(out_dir, rel)) != want:
            n["window: size of a saved product does not fit the film — left alone"] += 1
            return None
    n["window: LUT films to render again" if not apply else "window: LUT films rendered again"] += 1
    n["window: PNG / JPEG files" + (" replaced" if apply else " to replace")] += len(products)
    if not apply:
        return None

    full = pydicom.dcmread(src)
    vals = apply_rescale(full.pixel_array, full)
    iop = full.get("ImageOrientationPatient")           # the panel shows the slice with these flips
    info = acq_plane_info([float(v) for v in iop] if iop else [1, 0, 0, 0, 1, 0])
    if info["flip_acq_rows"]:
        vals = np.flipud(vals)
    if info["flip_acq_cols"]:
        vals = np.fliplr(vals)
    wc, ww = wl_from_dicom(full)
    for rel in products:
        dst = os.path.join(backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(os.path.join(out_dir, rel), dst)
    suffixes = {_product(f)[1] for f in products}
    written = export_item(
        out_dir, ExportInput(stem=row["stem"], pixels=vals, wc=wc, ww=ww, invert=False, rect=rect),
        ExportOptions(formats=tuple(f for f in _EIGHT_BIT if any(_product(p)[0] == f for p in products)),
                      save_mask=False, save_crop="_roi" in suffixes, save_image="_image" in suffixes))
    if sorted(written) != sorted(products):
        raise RuntimeError(f"{row['stem']}: wrote {sorted(written)}, expected {sorted(products)}")
    return dict(wc=round(wc, 2), ww=round(ww, 2), wl_default=1, invert=0)


def _rect_masks(row, out_dir, root, apply, n) -> dict | None:
    """Write the missing <stem>_rect_mask files of one row; returns the row's new fields."""
    rect = _rect(row)
    if rect is None:
        n["masks: row without a rectangle"] += 1
        return None
    files = _files(row)
    have = {_product(f)[0] for f in files if _product(f)[1] == "_rect_mask"}
    formats = tuple(f for f in row.get("formats", "").split() if f not in have)
    if not formats:
        n["masks: already there"] += 1
        return None
    src, ds = _header(row, root)
    if ds is None:
        n["masks: source not found or not DICOM — left alone"] += 1
        return None
    n["masks: rows to get one" if not apply else "masks: rows that got one"] += 1
    n["masks: files" + (" written" if apply else " to write")] += len(formats)
    if not apply:
        return None

    spacing = None
    for rel in files:       # the mask lies on the row's image: same pixel spacing as the NIfTI already there
        if _product(rel) == ("nifti", "_image") and os.path.isfile(os.path.join(out_dir, rel)):
            import nibabel as nib
            zooms = nib.load(os.path.join(out_dir, rel)).header.get_zooms()
            spacing = (float(zooms[1]), float(zooms[0]))
    if spacing is None:
        sp = ds.get("PixelSpacing") or ds.get("ImagerPixelSpacing")
        spacing = (float(sp[0]), float(sp[1])) if sp else (1.0, 1.0)
    blank = np.zeros((int(ds.Rows), int(ds.Columns)), dtype=np.float32)
    written = export_item(
        out_dir, ExportInput(stem=row["stem"], pixels=blank, wc=0.0, ww=1.0, rect=rect, spacing=spacing),
        ExportOptions(formats=formats, save_mask=True, save_crop=False, save_image=False))
    return dict(files=FILES_SEP.join(files + written))


def update(out_dir: str, default_window: bool = False, rect_masks: bool = False,
           apply: bool = False, out=print) -> Counter:
    """Walk the manifest of *out_dir*; returns the counts that are printed."""
    manifest = os.path.join(out_dir, MANIFEST_NAME)
    root = os.path.dirname(os.path.abspath(out_dir))
    backup_dir = os.path.join(out_dir, "replaced-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    rows = read_manifest(manifest)
    n = Counter(rows=len(rows))
    for stem in sorted(rows):
        row = rows[stem]
        if row.get("status") != STATUS_SAVED:
            n["not saved (deleted mark)"] += 1
            continue
        if row.get("view"):
            n["slice of a volume — left alone"] += 1
            continue
        new: dict = {}
        if default_window:
            new.update(_default_window(row, out_dir, root, backup_dir, apply, n) or {})
        if rect_masks:
            new.update(_rect_masks(row, out_dir, root, apply, n) or {})
        if new:
            write_manifest_row(manifest, {**row, **new})

    out(manifest)
    for key, count in n.items():
        out(f"  {count:>6}  {key}")
    if apply and os.path.isdir(backup_dir):
        out(f"Replaced files were moved to {backup_dir}")
    out("Applied." if apply else "Dry run — nothing was written. Add --apply to write.")
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out_dir", help="output directory holding manifest.csv (or the workspace above it)")
    ap.add_argument("--default-window", action="store_true",
                    help="render PNG / JPEG of VOI-LUT films again with the default window")
    ap.add_argument("--rect-masks", action="store_true", help="write the missing <stem>_rect_mask files")
    ap.add_argument("--apply", action="store_true", help="write (default: report only)")
    args = ap.parse_args(argv)
    if not (args.default_window or args.rect_masks):
        ap.error("choose at least one of --default-window, --rect-masks")
    out_dir = args.out_dir
    if not os.path.isfile(os.path.join(out_dir, MANIFEST_NAME)):
        nested = os.path.join(out_dir, "vidi_output")
        if not os.path.isfile(os.path.join(nested, MANIFEST_NAME)):
            print(f"No {MANIFEST_NAME} in {out_dir}", file=sys.stderr)
            return 2
        out_dir = nested
    update(out_dir, args.default_window, args.rect_masks, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
