import numpy as np


def _gray() -> np.ndarray:
    t = np.arange(256, dtype=np.uint8)
    return np.stack([t, t, t], axis=1)


def _bone() -> np.ndarray:
    # warm grey-blue: bone window used in radiology
    t = np.linspace(0, 1, 256)
    r = np.clip(t * 1.0,        0, 1)
    g = np.clip(t * 1.0,        0, 1)
    b = np.clip(t * 1.0 + 0.08, 0, 1)
    return (np.stack([r, g, b], axis=1) * 255).astype(np.uint8)


def _hot() -> np.ndarray:
    t = np.linspace(0, 1, 256)
    r = np.clip(t * 3.0,       0, 1)
    g = np.clip(t * 3.0 - 1.0, 0, 1)
    b = np.clip(t * 3.0 - 2.0, 0, 1)
    return (np.stack([r, g, b], axis=1) * 255).astype(np.uint8)


def _viridis() -> np.ndarray:
    # Viridis control points (R, G, B) at t = 0, 0.25, 0.5, 0.75, 1.0
    ctrl = np.array([
        [0.267, 0.005, 0.329],
        [0.229, 0.322, 0.545],
        [0.128, 0.566, 0.551],
        [0.369, 0.789, 0.383],
        [0.993, 0.906, 0.144],
    ], dtype=np.float32)
    t = np.linspace(0, 1, 256)
    idx = t * (len(ctrl) - 1)
    lo = np.floor(idx).astype(int).clip(0, len(ctrl) - 2)
    frac = (idx - lo)[:, None]
    rgb = ctrl[lo] * (1 - frac) + ctrl[lo + 1] * frac
    return (rgb * 255).astype(np.uint8)


COLORMAPS: dict[str, np.ndarray] = {
    "Gray":    _gray(),
    "Bone":    _bone(),
    "Hot":     _hot(),
    "Viridis": _viridis(),
}

COLORMAP_NAMES = list(COLORMAPS.keys())
