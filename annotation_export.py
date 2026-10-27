"""Write annotation products — mask, crop, full image — as PNG / JPEG / NIfTI.

Pure Python, no Qt. One call per item; each selected format gets its own
subdirectory under the output dir so mixed-format outputs never collide:

    <out_dir>/png/<stem>_mask.png      <out_dir>/nifti/<stem>_mask.nii.gz
    <out_dir>/png/<stem>_roi.png       <out_dir>/nifti/<stem>_roi.nii.gz
    <out_dir>/png/<stem>_image.png     ...

PNG/JPEG are 8-bit and get the viewer's current window/level (and invert)
applied, so the file matches what is on screen. NIfTI keeps the raw float32
values (after DICOM rescale) with pixel spacing in the affine; masks are
uint8 0/1 (0/255 in PNG/JPEG).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

FORMATS = ("png", "jpeg", "nifti")
_EXT = {"png": ".png", "jpeg": ".jpg", "nifti": ".nii.gz"}


@dataclass
class ExportOptions:
    formats: tuple[str, ...]        # subset of FORMATS, in output order
    save_mask: bool = True          # <stem>_mask (+ <stem>_roi_mask when a rect exists)
    save_crop: bool = True          # <stem>_roi — the rectangle cut from the image
    save_image: bool = False        # <stem>_image — the whole displayed slice


@dataclass
class ExportInput:
    stem: str
    pixels: np.ndarray                              # float32 (H, W) displayed slice
    wc: float
    ww: float
    invert: bool = False
    mask: np.ndarray | None = None                  # uint8 (H, W), 0/1
    rect: tuple[int, int, int, int] | None = None   # x0, y0, x1, y1 (x1/y1 exclusive)
    spacing: tuple[float, float] = (1.0, 1.0)       # (row_mm, col_mm)


def window_to_uint8(pixels: np.ndarray, wc: float, ww: float,
                    invert: bool = False) -> np.ndarray:
    """Apply window/level exactly like the canvas (windowing.render_to_rgb:
    clip, scale, truncate) so the file matches the screen pixel for pixel.
    NaN/inf pixels map to the window floor/ceiling instead of warning."""
    lo = wc - ww / 2.0
    px = np.nan_to_num(np.asarray(pixels, dtype=np.float32), nan=lo,
                       posinf=lo + ww, neginf=lo)
    alpha = np.clip((px - lo) / max(float(ww), 1e-6), 0.0, 1.0)
    u8 = (alpha * 255.0).astype(np.uint8)
    return (255 - u8) if invert else u8


def export_item(out_dir: str, inp: ExportInput, opts: ExportOptions) -> list[str]:
    """Write every requested product in every requested format.

    Returns the written paths relative to *out_dir* (empty if there was
    nothing to write, e.g. no mask drawn and no rectangle set).
    """
    if (not inp.stem or inp.stem in (".", "..") or "/" in inp.stem
            or "\\" in inp.stem or os.sep in inp.stem):
        raise ValueError(f"invalid stem {inp.stem!r}")
    products: list[tuple[str, np.ndarray, str, tuple[int, int]]] = []  # suffix, arr, kind, origin
    has_mask = opts.save_mask and inp.mask is not None and bool(inp.mask.any())
    rect = _clip_rect(inp.rect, inp.pixels.shape)
    has_rect = rect is not None

    if opts.save_image:
        products.append(("image", inp.pixels, "image", (0, 0)))
    if has_mask:
        products.append(("mask", inp.mask, "mask", (0, 0)))
    if has_rect:
        x0, y0, x1, y1 = rect
        if opts.save_crop:
            products.append(("roi", inp.pixels[y0:y1, x0:x1], "image", (x0, y0)))
        if has_mask:
            products.append(("roi_mask", inp.mask[y0:y1, x0:x1], "mask", (x0, y0)))

    if not products:
        return []

    written: list[str] = []
    for fmt in opts.formats:
        if fmt not in FORMATS:
            raise ValueError(f"unknown format {fmt!r}")
        sub = os.path.join(out_dir, fmt)
        os.makedirs(sub, exist_ok=True)
        for suffix, arr, kind, origin in products:
            fn = f"{inp.stem}_{suffix}{_EXT[fmt]}"
            _write(fmt, os.path.join(sub, fn), arr, kind, inp, origin)
            written.append(os.path.join(fmt, fn))
    return written


def _clip_rect(rect, shape) -> tuple[int, int, int, int] | None:
    """Clip (x0, y0, x1, y1) to the image; None when nothing is left."""
    if rect is None:
        return None
    h, w = shape[:2]
    x0, y0, x1, y1 = (int(v) for v in rect)
    x0, x1 = max(0, min(w, x0)), max(0, min(w, x1))
    y0, y1 = max(0, min(h, y0)), max(0, min(h, y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


# ── Writers ──────────────────────────────────────────────────────────────────

def _write(fmt: str, path: str, arr: np.ndarray, kind: str,
           inp: ExportInput, origin: tuple[int, int]) -> None:
    if fmt == "nifti":
        _write_nifti(path, arr, kind, inp.spacing, origin)
        return
    from PIL import Image
    if kind == "mask":
        u8 = (np.asarray(arr) > 0).astype(np.uint8) * 255
    else:
        u8 = window_to_uint8(arr, inp.wc, inp.ww, inp.invert)
    im = Image.fromarray(np.ascontiguousarray(u8), "L")
    if fmt == "jpeg":
        im.save(path, quality=95)
    else:
        im.save(path)


def _write_nifti(path: str, arr: np.ndarray, kind: str,
                 spacing: tuple[float, float], origin: tuple[int, int]) -> None:
    import nibabel as nib
    row_mm, col_mm = (spacing[0] or 1.0), (spacing[1] or 1.0)
    dtype = np.uint8 if kind == "mask" else np.float32
    # (H, W) row-major → (X, Y, 1) so x = columns, y = rows, as the loader expects.
    data = np.ascontiguousarray(np.asarray(arr).T)[:, :, np.newaxis].astype(dtype)
    affine = np.diag([col_mm, row_mm, 1.0, 1.0])
    affine[0, 3] = origin[0] * col_mm
    affine[1, 3] = origin[1] * row_mm
    img = nib.Nifti1Image(data, affine)
    img.header.set_xyzt_units("mm")
    nib.save(img, path)
