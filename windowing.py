import numpy as np


def render_to_rgb(pixels, wc: float, ww: float, cmap: np.ndarray) -> np.ndarray:
    """Map a float32 (H, W) slice to uint8 RGB (H, W, 3).

    *pixels* may be a numpy or CuPy array; the result is always a CPU numpy
    array suitable for QImage. When pixels is GPU-resident the computation
    stays on the GPU; only the final RGB result is transferred back.
    """
    from .gpu import GPU
    lo    = wc - ww / 2.0
    scale = max(float(ww), 1e-6)

    if GPU.is_gpu_array(pixels):
        xp       = GPU._cp
        cmap_gpu = GPU.cmap_on_device(cmap)
        alpha    = xp.clip((pixels - lo) / scale, 0.0, 1.0)
        rgb_gpu  = cmap_gpu[(alpha * 255.0).astype(xp.uint8)]
        return GPU.to_numpy(xp.ascontiguousarray(rgb_gpu))

    # CPU path (numpy)
    alpha = np.clip((np.asarray(pixels, dtype=np.float32) - lo) / scale, 0.0, 1.0)
    return np.ascontiguousarray(cmap[(alpha * 255.0).astype(np.uint8)])


def wl_from_percentiles(pixels: np.ndarray) -> tuple[float, float]:
    """Compute sensible W/L from 2nd–98th percentile of a pixel array."""
    p2  = float(np.percentile(pixels, 2))
    p50 = float(np.percentile(pixels, 50))
    p98 = float(np.percentile(pixels, 98))
    wc = p50
    ww = max(1.0, p98 - p2)
    return wc, ww


def mono1_flip_sum(ds) -> float | None:
    """For a MONOCHROME1 dataset (high value = black): the constant S with
    which ``S - v`` turns a rescaled value into its MONOCHROME2 counterpart
    (high value = white). None for every other photometric interpretation.

    S comes from the header alone — the limits of the stored range
    (BitsStored, PixelRepresentation) passed through the rescale — so every
    film gets the same flip and a crop can be flipped without its full image.
    """
    if str(ds.get("PhotometricInterpretation", "") or "").strip().upper() != "MONOCHROME1":
        return None
    bits = int(ds.get("BitsStored", 0) or ds.get("BitsAllocated", 0) or 0)
    if bits <= 0:
        return None
    signed = int(ds.get("PixelRepresentation", 0) or 0) == 1
    lo_plus_hi = -1 if signed else (1 << bits) - 1
    slope     = float(getattr(ds, "RescaleSlope",     1.0) or 1.0)
    intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
    return slope * lo_plus_hi + 2.0 * intercept


def _voi_lut_range(ds) -> tuple[float | None, float | None]:
    """(centre, width) of the value range the first VOI LUT of *ds* maps, or
    (None, None). Films that describe their display by a lookup table instead
    of a window (some CR systems) get a straight window over the same range:
    the anatomy the maker meant to show, without the table's curve."""
    try:
        entries, first = (int(v) for v in ds.VOILUTSequence[0].LUTDescriptor[:2])
    except (AttributeError, IndexError, TypeError, ValueError):
        return None, None
    entries = entries or 65536            # the descriptor writes 65536 entries as 0
    return first + (entries - 1) / 2.0, float(entries)


def wl_from_dicom(ds) -> tuple[float | None, float | None]:
    """The default window of a pydicom dataset: WindowCenter / WindowWidth,
    else the range of its VOI LUT; mirrored for MONOCHROME1 so it fits the
    flipped values of apply_rescale().

    Returns (None, None) if the header gives neither.
    """
    wc = ds.get("WindowCenter")
    ww = ds.get("WindowWidth")
    if wc is None or ww is None:
        wc, ww = _voi_lut_range(ds)
        if wc is None:
            return None, None
    if hasattr(wc, "__len__"):
        wc = float(wc[0])
    else:
        wc = float(wc)
    if hasattr(ww, "__len__"):
        ww = float(ww[0])
    else:
        ww = float(ww)
    flip = mono1_flip_sum(ds)
    if flip is not None:
        wc = flip - wc
    return wc, max(1.0, ww)


def apply_rescale(raw: np.ndarray, ds) -> np.ndarray:
    """Stored values → the float32 values the viewer works with: RescaleSlope /
    RescaleIntercept applied, and MONOCHROME1 flipped (see mono1_flip_sum), so
    high = white for display, statistics and every export alike."""
    arr = raw.astype(np.float32)
    slope     = float(getattr(ds, "RescaleSlope",     1.0) or 1.0)
    intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
    if slope != 1.0 or intercept != 0.0:
        arr = arr * slope + intercept
    flip = mono1_flip_sum(ds)
    if flip is not None:
        arr = np.float32(flip) - arr
    return arr
