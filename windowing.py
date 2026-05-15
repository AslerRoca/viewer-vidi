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


def wl_from_dicom(ds) -> tuple[float | None, float | None]:
    """Extract WindowCenter / WindowWidth from a pydicom dataset.

    Returns (None, None) if the tags are absent.
    """
    wc = ds.get("WindowCenter")
    ww = ds.get("WindowWidth")
    if wc is None or ww is None:
        return None, None
    if hasattr(wc, "__len__"):
        wc = float(wc[0])
    else:
        wc = float(wc)
    if hasattr(ww, "__len__"):
        ww = float(ww[0])
    else:
        ww = float(ww)
    return wc, max(1.0, ww)


def apply_rescale(raw: np.ndarray, ds) -> np.ndarray:
    """Apply RescaleSlope / RescaleIntercept and return float32."""
    arr = raw.astype(np.float32)
    slope     = float(getattr(ds, "RescaleSlope",     1.0) or 1.0)
    intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
    if slope != 1.0 or intercept != 0.0:
        arr = arr * slope + intercept
    return arr
