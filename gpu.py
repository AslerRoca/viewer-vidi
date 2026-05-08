"""Optional GPU acceleration via CuPy (CUDA). Falls back silently to CPU numpy."""
from __future__ import annotations

import numpy as np


class _Backend:
    """Thin wrapper that keeps the rest of the code GPU-library-agnostic."""

    def __init__(self):
        self.available  = False
        self.backend    = "cpu"
        self._cp        = None
        self._cmap_cache: dict[int, object] = {}   # id(cmap_np) → gpu array
        self._try_cupy()

    def _try_cupy(self) -> None:
        try:
            import cupy as cp
            # Trigger an actual CUDA call to confirm a device exists.
            cp.zeros(1, dtype=cp.float32)
            self._cp        = cp
            self.available  = True
            self.backend    = "cupy"
        except Exception:
            pass

    # ── array helpers ──────────────────────────────────────────────────────

    def to_device(self, arr: np.ndarray):
        """Upload a numpy array to GPU (no-op on CPU backend)."""
        if self.available:
            return self._cp.asarray(arr)
        return arr

    def to_numpy(self, arr) -> np.ndarray:
        """Download a GPU array back to CPU numpy (no-op if already numpy)."""
        if self.available and isinstance(arr, self._cp.ndarray):
            return self._cp.asnumpy(arr)
        return np.asarray(arr)

    def cmap_on_device(self, cmap: np.ndarray):
        """Return a GPU-resident copy of *cmap*, cached by identity."""
        if not self.available:
            return cmap
        key = id(cmap)
        if key not in self._cmap_cache:
            self._cmap_cache[key] = self._cp.asarray(cmap)
        return self._cmap_cache[key]

    def is_gpu_array(self, arr) -> bool:
        return self.available and isinstance(arr, self._cp.ndarray)

    def __repr__(self) -> str:
        return f"<GPU backend={self.backend}>"


GPU = _Backend()
