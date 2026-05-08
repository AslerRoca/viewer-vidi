"""2D time-series (cine) display with playback controls."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QDoubleSpinBox,
)

from .image_canvas import ImageCanvas
from .data_model import SeriesData
from .constants import DEFAULT_FPS, MAX_FPS


class ImageView2DT(QWidget):
    wl_changed    = pyqtSignal(float, float)
    pixel_hovered = pyqtSignal(int, int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._array: np.ndarray | None = None
        self._n_frames = 0
        self._current  = 0

        self._canvas = ImageCanvas(self)
        self._canvas.wl_changed.connect(self.wl_changed)
        self._canvas.pixel_hovered.connect(self.pixel_hovered)

        # playback controls
        self._play_btn  = QPushButton("▶")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.setCheckable(True)
        self._play_btn.toggled.connect(self._on_play_toggled)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.valueChanged.connect(self._on_slider)

        self._frame_lbl = QLabel("0 / 0")
        self._frame_lbl.setMinimumWidth(60)

        self._fps_spin = QDoubleSpinBox()
        self._fps_spin.setRange(0.5, MAX_FPS)
        self._fps_spin.setValue(DEFAULT_FPS)
        self._fps_spin.setSuffix(" fps")
        self._fps_spin.valueChanged.connect(self._update_timer_interval)
        self._fps_spin.setFixedWidth(80)

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(8, 4, 8, 4)
        ctrl_row.addWidget(self._play_btn)
        ctrl_row.addWidget(self._slider, 1)
        ctrl_row.addWidget(self._frame_lbl)
        ctrl_row.addWidget(QLabel("FPS"))
        ctrl_row.addWidget(self._fps_spin)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._canvas, 1)
        lay.addLayout(ctrl_row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._update_timer_interval()

    # ── Public API ─────────────────────────────────────────────────────────

    def load(self, series_data: SeriesData, array: np.ndarray) -> None:
        # array: (T, H, W)
        self._stop_playback()
        self._array = array
        self._n_frames = array.shape[0]
        self._current  = 0
        self._slider.setMaximum(max(0, self._n_frames - 1))
        self._slider.setValue(0)
        self._canvas.set_wl(series_data.window_center, series_data.window_width)
        self._show_frame(0)

    def set_wl(self, wc: float, ww: float) -> None:
        self._canvas.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        self._canvas.set_colormap(name)

    # ── Internals ──────────────────────────────────────────────────────────

    def _show_frame(self, idx: int) -> None:
        if self._array is None:
            return
        self._current = idx
        self._canvas.set_image(self._array[idx])
        self._frame_lbl.setText(f"{idx + 1} / {self._n_frames}")

    def _on_slider(self, value: int) -> None:
        self._show_frame(value)

    def _on_play_toggled(self, playing: bool) -> None:
        if playing:
            self._play_btn.setText("⏸")
            self._timer.start()
        else:
            self._play_btn.setText("▶")
            self._timer.stop()

    def _advance(self) -> None:
        if self._n_frames == 0:
            return
        nxt = (self._current + 1) % self._n_frames
        self._slider.setValue(nxt)

    def _update_timer_interval(self) -> None:
        fps = max(0.5, self._fps_spin.value())
        self._timer.setInterval(int(1000 / fps))

    def _stop_playback(self) -> None:
        self._timer.stop()
        self._play_btn.setChecked(False)
        self._play_btn.setText("▶")
