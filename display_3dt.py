"""3D time-series (4D) MPR display with playback controls."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QSlider, QLabel, QPushButton, QDoubleSpinBox,
)

from .data_model import SeriesData
from .constants import DEFAULT_FPS, MAX_FPS
from .display_3d import _PlaneView


class ImageView3DT(QWidget):
    """4D viewer: 3-plane MPR + time slider + playback."""

    wl_changed    = pyqtSignal(float, float)
    pixel_hovered = pyqtSignal(int, int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vol:          np.ndarray | None = None  # (T, Z, H, W)
        self._sd:           SeriesData | None = None
        self._n_t           = 0
        self._cur_t         = 0
        self._loaded_mask:  np.ndarray | None = None

        self._pv0 = _PlaneView("ACQ",  self)
        self._pv1 = _PlaneView("MPR1", self)
        self._pv2 = _PlaneView("MPR2", self)

        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.wl_changed.connect(self._on_wl_changed)
            pv.canvas.pixel_hovered.connect(self.pixel_hovered)
            pv.canvas.setFocusPolicy(Qt.ClickFocus)
            pv.canvas.installEventFilter(self)

        self._pv0.slice_changed.connect(self._on_s0)
        self._pv1.slice_changed.connect(self._on_s1)
        self._pv2.slice_changed.connect(self._on_s2)

        planes_row = QHBoxLayout()
        planes_row.setContentsMargins(0, 0, 0, 0)
        planes_row.setSpacing(2)
        planes_row.addWidget(self._pv0, 1)
        planes_row.addWidget(self._pv1, 1)
        planes_row.addWidget(self._pv2, 1)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.setCheckable(True)
        self._play_btn.toggled.connect(self._on_play_toggled)

        self._time_slider = QSlider(Qt.Horizontal)
        self._time_slider.setMinimum(0)
        self._time_slider.valueChanged.connect(self._on_time_slider)

        self._time_lbl = QLabel("t=0/0")
        self._time_lbl.setMinimumWidth(60)

        self._fps_spin = QDoubleSpinBox()
        self._fps_spin.setRange(0.5, MAX_FPS)
        self._fps_spin.setValue(DEFAULT_FPS)
        self._fps_spin.setSuffix(" fps")
        self._fps_spin.valueChanged.connect(self._update_interval)
        self._fps_spin.setFixedWidth(80)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(8, 4, 8, 4)
        time_row.addWidget(self._play_btn)
        time_row.addWidget(self._time_slider, 1)
        time_row.addWidget(self._time_lbl)
        time_row.addWidget(QLabel("FPS"))
        time_row.addWidget(self._fps_spin)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addLayout(planes_row, 1)
        lay.addLayout(time_row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._update_interval()

    # ── Public API ─────────────────────────────────────────────────────────

    def load(self, series_data: SeriesData, array: np.ndarray) -> None:
        self._stop_playback()
        self._vol   = array
        self._sd    = series_data
        self._n_t   = array.shape[0]
        self._cur_t = 0
        self._loaded_mask = np.ones(self._n_t, bool)

        labels = series_data.panel_labels
        self._pv0.set_label(labels[0])
        self._pv1.set_label(labels[1])
        self._pv2.set_label(labels[2])

        n_z, n_h, n_w = array.shape[1], array.shape[2], array.shape[3]
        self._pv0.set_range(n_z)
        self._pv1.set_range(n_h)
        self._pv2.set_range(n_w)

        self._time_slider.setMaximum(max(0, self._n_t - 1))
        self._time_slider.setValue(0)
        self._time_lbl.setText(f"t=1/{self._n_t}")

        wc, ww = series_data.window_center, series_data.window_width
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_wl(wc, ww)

        self._render_all()

    def update_timepoint(self, t: int, full_array: np.ndarray) -> None:
        self._vol = full_array
        if self._loaded_mask is None or len(self._loaded_mask) != full_array.shape[0]:
            self._loaded_mask = np.zeros(full_array.shape[0], bool)
        self._loaded_mask[t] = True
        if t == self._cur_t:
            self._render_all()

    def set_wl(self, wc: float, ww: float) -> None:
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_colormap(name)

    # ── Slice / time handlers ───────────────────────────────────────────────

    def _on_s0(self, z: int) -> None:
        if self._vol is None:
            return
        self._pv0.canvas.set_image(self._acq_slice(self._cur_t, z), 1.0)

    def _on_s1(self, y: int) -> None:
        if self._vol is None:
            return
        sl, asp = self._reformat1(self._cur_t, y)
        self._pv1.canvas.set_image(sl, asp)

    def _on_s2(self, x: int) -> None:
        if self._vol is None:
            return
        sl, asp = self._reformat2(self._cur_t, x)
        self._pv2.canvas.set_image(sl, asp)

    def _on_time_slider(self, t: int) -> None:
        self._cur_t = t
        self._time_lbl.setText(f"t={t+1}/{self._n_t}")
        self._render_all()

    def _on_wl_changed(self, wc: float, ww: float) -> None:
        for pv in (self._pv0, self._pv1, self._pv2):
            pv.canvas.set_wl(wc, ww)
        self.wl_changed.emit(wc, ww)

    # ── Playback ────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        canvases = (self._pv0.canvas, self._pv1.canvas, self._pv2.canvas)
        if obj in canvases and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space:
                self._play_btn.toggle()
                return True
        return super().eventFilter(obj, event)

    def _on_play_toggled(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")
        if playing:
            self._timer.start()
        else:
            self._timer.stop()

    def _advance(self) -> None:
        if self._n_t == 0:
            return
        nxt = (self._cur_t + 1) % self._n_t
        if self._loaded_mask is not None and not self._loaded_mask[nxt]:
            return
        self._time_slider.setValue(nxt)

    def _update_interval(self) -> None:
        self._timer.setInterval(int(1000 / max(0.5, self._fps_spin.value())))

    def _stop_playback(self) -> None:
        self._timer.stop()
        self._play_btn.setChecked(False)
        self._play_btn.setText("▶")

    # ── Slice extraction with orientation correction ────────────────────────

    def _acq_slice(self, t: int, z: int) -> np.ndarray:
        sl = self._vol[t, z, :, :]
        if self._sd and self._sd.flip_acq_rows:
            sl = np.flipud(sl)
        if self._sd and self._sd.flip_acq_cols:
            sl = np.fliplr(sl)
        return sl

    def _reformat1(self, t: int, y: int) -> tuple[np.ndarray, float]:
        sl = self._vol[t, :, y, :]
        if self._sd and self._sd.flip_reformat:
            sl = np.flipud(sl)
        asp = self._r1_aspect()
        return sl, asp

    def _reformat2(self, t: int, x: int) -> tuple[np.ndarray, float]:
        sl = self._vol[t, :, :, x]
        if self._sd and self._sd.flip_reformat:
            sl = np.flipud(sl)
        asp = self._r2_aspect()
        return sl, asp

    def _r1_aspect(self) -> float:
        if self._sd is None:
            return 1.0
        dz = self._sd.slice_spacing or 1.0
        dx = self._sd.pixel_spacing[1] or 1.0
        return dz / dx

    def _r2_aspect(self) -> float:
        if self._sd is None:
            return 1.0
        dz = self._sd.slice_spacing or 1.0
        dy = self._sd.pixel_spacing[0] or 1.0
        return dz / dy

    def _render_all(self) -> None:
        if self._vol is None:
            return
        t = self._cur_t
        self._pv0.canvas.set_image(self._acq_slice(t, self._pv0.value()), 1.0)
        sl1, asp1 = self._reformat1(t, self._pv1.value())
        sl2, asp2 = self._reformat2(t, self._pv2.value())
        self._pv1.canvas.set_image(sl1, asp1)
        self._pv2.canvas.set_image(sl2, asp2)
