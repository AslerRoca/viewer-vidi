"""2D single-image display."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from .image_canvas import ImageCanvas
from .data_model import SeriesData


class ImageView2D(QWidget):
    wl_changed    = pyqtSignal(float, float)
    pixel_hovered = pyqtSignal(int, int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvas = ImageCanvas(self)
        self._canvas.wl_changed.connect(self.wl_changed)
        self._canvas.pixel_hovered.connect(self.pixel_hovered)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

    def load(self, series_data: SeriesData, array: np.ndarray) -> None:
        # array: (H, W)
        self._canvas.set_wl(series_data.window_center, series_data.window_width)
        self._canvas.set_image(array)

    def set_wl(self, wc: float, ww: float) -> None:
        self._canvas.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        self._canvas.set_colormap(name)
