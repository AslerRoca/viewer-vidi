"""3D volumetric MPR display (acquisition plane + 2 reformats)."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QSlider, QLabel, QSizePolicy,
)

from .image_canvas import ImageCanvas
from .data_model import SeriesData


class _PlaneView(QWidget):
    """One MPR plane: label + canvas + vertical slice slider."""

    slice_changed = pyqtSignal(int)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.canvas = ImageCanvas(self)

        self._lbl = QLabel(label)
        self._lbl.setObjectName("planeLabel")
        self._lbl.setAlignment(Qt.AlignCenter)

        self._slider = QSlider(Qt.Vertical)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self.slice_changed)
        self._slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self.canvas, 1)
        row.addWidget(self._slider)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        lay.addWidget(self._lbl)
        lay.addLayout(row, 1)

    def set_label(self, text: str) -> None:
        self._lbl.setText(text)

    def set_range(self, n: int) -> None:
        self._slider.setMaximum(max(0, n - 1))
        self._slider.setValue(n // 2)

    def set_value(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)

    def value(self) -> int:
        return self._slider.value()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        step = -1 if delta > 0 else 1
        self._slider.setValue(self._slider.value() + step)


class ImageView3D(QWidget):
    """3-plane MPR viewer for S3D volumes."""

    wl_changed    = pyqtSignal(float, float)
    pixel_hovered = pyqtSignal(int, int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vol: np.ndarray | None = None  # (Z, H, W) float32
        self._sd:  SeriesData | None = None

        self._pv0 = _PlaneView("ACQ",  self)   # acquisition plane
        self._pv1 = _PlaneView("MPR1", self)   # first reformat
        self._pv2 = _PlaneView("MPR2", self)   # second reformat

        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.wl_changed.connect(self._on_wl_changed)
            pv.canvas.pixel_hovered.connect(self.pixel_hovered)

        self._pv0.slice_changed.connect(self._on_s0)
        self._pv1.slice_changed.connect(self._on_s1)
        self._pv2.slice_changed.connect(self._on_s2)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self._pv0, 1)
        lay.addWidget(self._pv1, 1)
        lay.addWidget(self._pv2, 1)

    # ── Public API ─────────────────────────────────────────────────────────

    def load(self, series_data: SeriesData, array: np.ndarray) -> None:
        self._vol = array
        self._sd  = series_data

        labels = series_data.panel_labels
        self._pv0.set_label(labels[0])
        self._pv1.set_label(labels[1])
        self._pv2.set_label(labels[2])

        n_z, n_h, n_w = array.shape
        self._pv0.set_range(n_z)
        self._pv1.set_range(n_h)
        self._pv2.set_range(n_w)

        wc, ww = series_data.window_center, series_data.window_width
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_wl(wc, ww)

        self._render_all()

    def set_wl(self, wc: float, ww: float) -> None:
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_colormap(name)

    # ── Slice handlers ─────────────────────────────────────────────────────

    def _on_s0(self, z: int) -> None:
        if self._vol is None:
            return
        self._pv0.canvas.set_image(self._acq_slice(z), 1.0)

    def _on_s1(self, y: int) -> None:
        if self._vol is None:
            return
        sl, asp = self._reformat1(y)
        self._pv1.canvas.set_image(sl, asp)

    def _on_s2(self, x: int) -> None:
        if self._vol is None:
            return
        sl, asp = self._reformat2(x)
        self._pv2.canvas.set_image(sl, asp)

    def _on_wl_changed(self, wc: float, ww: float) -> None:
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_wl(wc, ww)
        self.wl_changed.emit(wc, ww)

    # ── Slice extraction with orientation correction ────────────────────────

    def _acq_slice(self, z: int) -> np.ndarray:
        """Acquisition-plane slice with optional flip."""
        sl = self._vol[z, :, :]
        if self._sd and self._sd.flip_acq_rows:
            sl = np.flipud(sl)
        if self._sd and self._sd.flip_acq_cols:
            sl = np.fliplr(sl)
        return sl

    def _reformat1(self, y: int) -> tuple[np.ndarray, float]:
        """vol[:,y,:] with Z-axis flip and correct aspect ratio."""
        sl = self._vol[:, y, :]   # (Z, W)
        if self._sd and self._sd.flip_reformat:
            sl = np.flipud(sl)
        asp = self._reformat1_aspect()
        return sl, asp

    def _reformat2(self, x: int) -> tuple[np.ndarray, float]:
        """vol[:,:,x] with Z-axis flip and correct aspect ratio."""
        sl = self._vol[:, :, x]   # (Z, H)
        if self._sd and self._sd.flip_reformat:
            sl = np.flipud(sl)
        asp = self._reformat2_aspect()
        return sl, asp

    def _reformat1_aspect(self) -> float:
        if self._sd is None:
            return 1.0
        dz = self._sd.slice_spacing or 1.0
        dx = self._sd.pixel_spacing[1] or 1.0
        return dz / dx

    def _reformat2_aspect(self) -> float:
        if self._sd is None:
            return 1.0
        dz = self._sd.slice_spacing or 1.0
        dy = self._sd.pixel_spacing[0] or 1.0
        return dz / dy

    def _render_all(self) -> None:
        if self._vol is None:
            return
        z = self._pv0.value()
        y = self._pv1.value()
        x = self._pv2.value()
        self._pv0.canvas.set_image(self._acq_slice(z), 1.0)
        sl1, asp1 = self._reformat1(y)
        sl2, asp2 = self._reformat2(x)
        self._pv1.canvas.set_image(sl1, asp1)
        self._pv2.canvas.set_image(sl2, asp2)
