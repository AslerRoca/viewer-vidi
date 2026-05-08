"""Stacked viewer panel that routes to the correct display mode."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QStackedWidget, QLabel, QSizePolicy

from .data_model import SeriesData, SeriesType, VolumeData
from .display_2d  import ImageView2D
from .display_2dt import ImageView2DT
from .display_3d  import ImageView3D
from .display_3dt import ImageView3DT


_IDX_EMPTY = 0
_IDX_2D    = 1
_IDX_2DT   = 2
_IDX_3D    = 3
_IDX_3DT   = 4
_IDX_MULTI = 1   # multi-plane: reuse 2D slot for first panel


class ViewerPanel(QStackedWidget):
    wl_changed       = pyqtSignal(float, float)
    pixel_hovered    = pyqtSignal(int, int, float)
    series_type_ready = pyqtSignal(str)  # badge label

    def __init__(self, parent=None):
        super().__init__(parent)

        self._empty = QLabel("Select a series from the tree")
        self._empty.setObjectName("emptyLabel")
        from PyQt5.QtCore import Qt
        self._empty.setAlignment(Qt.AlignCenter)

        self._view2d   = ImageView2D(self)
        self._view2dt  = ImageView2DT(self)
        self._view3d   = ImageView3D(self)
        self._view3dt  = ImageView3DT(self)

        self.addWidget(self._empty)   # 0
        self.addWidget(self._view2d)  # 1
        self.addWidget(self._view2dt) # 2
        self.addWidget(self._view3d)  # 3
        self.addWidget(self._view3dt) # 4

        for view in (self._view2d, self._view2dt, self._view3d, self._view3dt):
            view.wl_changed.connect(self.wl_changed)
            view.pixel_hovered.connect(self.pixel_hovered)

        self._current_type: SeriesType | None = None

    # ── Called by MainWindow when loader signals ────────────────────────────

    def on_headers_ready(self, series_data: SeriesData) -> None:
        self._current_type = series_data.series_type
        self.series_type_ready.emit(series_data.series_type.value)

    def on_pixels_ready(self, t_idx: int, array: np.ndarray) -> None:
        st = self._current_type
        if st is None:
            return

        if st == SeriesType.S2D:
            self._view2d.load(self._current_sd, array)
            self.setCurrentIndex(_IDX_2D)

        elif st == SeriesType.S2DT:
            self._view2dt.load(self._current_sd, array)
            self.setCurrentIndex(_IDX_2DT)

        elif st == SeriesType.S3D:
            self._view3d.load(self._current_sd, array)
            self.setCurrentIndex(_IDX_3D)

        elif st == SeriesType.S3DT:
            if t_idx == 0:
                self._view3dt.load(self._current_sd, array)
                self.setCurrentIndex(_IDX_3DT)
            else:
                self._view3dt.update_timepoint(t_idx, array)

        elif st == SeriesType.MULTI:
            # Show first orientation as 2D; array is (G, H, W)
            self._view2d.load(self._current_sd, array[0])
            self.setCurrentIndex(_IDX_2D)

    def on_load_complete(self) -> None:
        pass  # could unlock controls here

    def set_series_data(self, sd: SeriesData) -> None:
        self._current_sd = sd

    # ── W/L and colormap passthrough ────────────────────────────────────────

    def set_wl(self, wc: float, ww: float) -> None:
        for view in (self._view2d, self._view2dt, self._view3d, self._view3dt):
            view.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        for view in (self._view2d, self._view2dt, self._view3d, self._view3dt):
            view.set_colormap(name)

    def show_empty(self) -> None:
        self.setCurrentIndex(_IDX_EMPTY)
        self._current_type = None
