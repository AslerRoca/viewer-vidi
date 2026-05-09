"""Floating window showing intensity-vs-time for selected voxels."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
)

from .image_canvas import TC_COLORS
from .data_model import SeriesType

# matplotlib is imported lazily on first redraw so startup stays fast.
_MPL: bool | None = None   # None = not yet attempted

_BG    = "#1e1e2e"
_PANEL = "#12121e"
_TEXT  = "#cdd6f4"
_GRID  = "#2a2a3e"


class TimeCourseWindow(QWidget):
    """Matplotlib time-course plot — works as an embedded panel or a floating window.

    Pass ``embedded=True`` to get a plain QWidget suitable for embedding in a
    layout.  The default (``embedded=False``) retains the original floating
    window behaviour.

    Call update_data() whenever points or the volume change.
    The clear_requested signal fires when the user clicks "Clear" — the caller
    should call canvas.clear_tc_points() in response.
    """

    clear_requested = pyqtSignal()
    window_closed   = pyqtSignal()

    def __init__(self, parent=None, embedded: bool = False):
        if embedded:
            super().__init__(parent)
        else:
            super().__init__(parent, Qt.Window)
            self.setWindowTitle("Vidi — Time Course")
            self.resize(560, 360)
            self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._embedded = embedded

        self._vol:    np.ndarray | None = None
        self._stype:  SeriesType | None = None
        self._cur_z:  int = 0
        self._cur_y:  int = 0
        self._cur_x:  int = 0
        self._points: list[tuple[int, int]] = []   # display (col, row)
        self._flip_acq_rows: bool = False
        self._flip_reformat: bool = False
        self._view_mode: str = "AXIAL"
        self._acq_plane: str = "AXIAL"

        # ROI-TC state (freehand polygons)
        self._roi_tc_polys: list = []   # list of np.ndarray (N,2) image (x,y)

        # matplotlib canvas — created lazily on first _redraw call
        self._fig         = None
        self._ax          = None
        self._plot_canvas = None   # FigureCanvasQTAgg, added to _plot_area on demand

        # ── Controls ───────────────────────────────────────────────────────
        self._name_lbl = QLabel("")
        self._name_lbl.setStyleSheet("color:#6c7086; font-size:10px;")

        clear_btn = QPushButton("Clear points")
        clear_btn.setStyleSheet(
            "background:#2a2a3e; border:1px solid #45475a; border-radius:4px;"
            "color:#cdd6f4; padding:3px 10px; font-size:11px;"
        )
        clear_btn.clicked.connect(self._on_clear)

        hdr = QHBoxLayout()
        hdr.addWidget(self._name_lbl, 1)
        hdr.addWidget(clear_btn)

        # Placeholder container — matplotlib canvas is inserted here lazily
        self._plot_area = QWidget()
        self._plot_area.setStyleSheet(f"background:{_PANEL};")
        self._plot_area_lay = QVBoxLayout(self._plot_area)
        self._plot_area_lay.setContentsMargins(0, 0, 0, 0)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        lay.addLayout(hdr)
        lay.addWidget(self._plot_area, 1)

        self.setStyleSheet(f"background:{_BG};")

    # ── Public API ─────────────────────────────────────────────────────────

    def set_series_name(self, name: str) -> None:
        self._name_lbl.setText(name)

    def set_geometry_info(self, view_mode: str, acq_plane: str,
                          cur_z: int, cur_y: int, cur_x: int,
                          flip_acq_rows: bool, flip_reformat: bool) -> None:
        self._view_mode      = view_mode
        self._acq_plane      = acq_plane
        self._cur_z          = cur_z
        self._cur_y          = cur_y
        self._cur_x          = cur_x
        self._flip_acq_rows  = flip_acq_rows
        self._flip_reformat  = flip_reformat

    def update_data(self, vol: np.ndarray, stype: SeriesType,
                    points: list[tuple[int, int]]) -> None:
        """Recompute and redraw all time courses."""
        self._vol    = vol
        self._stype  = stype
        self._points = points
        self._redraw()

    def update_slice(self, cur_z: int, cur_y: int, cur_x: int) -> None:
        """Called when the slice position changes (3D-T only)."""
        self._cur_z = cur_z
        self._cur_y = cur_y
        self._cur_x = cur_x
        self._redraw()

    def update_roi_polys(self, vol: np.ndarray, stype: SeriesType,
                         polys: list) -> None:
        """Update the list of freehand ROI polygons and redraw."""
        self._vol          = vol
        self._stype        = stype
        self._roi_tc_polys = polys
        self._redraw()

    def clear_roi_data(self) -> None:
        self._roi_tc_polys = []
        self._redraw()

    # ── Internal ───────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if not self._embedded:
            self.window_closed.emit()
        event.accept()

    def _on_clear(self) -> None:
        self._points = []
        self._redraw()
        self.clear_requested.emit()

    def _style_ax(self) -> None:
        ax = self._ax
        ax.set_facecolor(_PANEL)
        for sp in ax.spines.values():
            sp.set_color(_GRID)
        ax.tick_params(colors=_TEXT, labelsize=8)
        ax.xaxis.label.set_color(_TEXT)
        ax.yaxis.label.set_color(_TEXT)
        ax.grid(True, color=_GRID, linewidth=0.5, linestyle="--")

    def _extract_curve(self, disp_x: int, disp_y: int) -> np.ndarray | None:
        """Extract the time-course for a display coordinate (col, row)."""
        vol   = self._vol
        stype = self._stype
        if vol is None or stype not in (SeriesType.S2DT, SeriesType.S3DT):
            return None

        if stype == SeriesType.S2DT:
            # vol: (T, H, W)
            T, H, W = vol.shape
            y = min(max(0, disp_y), H - 1)
            x = min(max(0, disp_x), W - 1)
            if self._flip_acq_rows:
                y = H - 1 - y
            return vol[:, y, x]

        # S3DT: vol (T, Z, H, W)
        T, n_z, n_h, n_w = vol.shape
        from .view_cell import _AXIS
        acq  = self._acq_plane if self._acq_plane in ("AXIAL","CORONAL","SAGITTAL") else "AXIAL"
        axis = _AXIS.get((acq, self._view_mode), "z")

        if axis == "z":
            z = min(max(0, self._cur_z), n_z - 1)
            y = min(max(0, disp_y), n_h - 1)
            x = min(max(0, disp_x), n_w - 1)
            if self._flip_acq_rows:
                y = n_h - 1 - y
        elif axis == "y":
            y = min(max(0, self._cur_y), n_h - 1)
            z = min(max(0, disp_y), n_z - 1)
            if self._flip_reformat:
                z = n_z - 1 - z
            x = min(max(0, disp_x), n_w - 1)
        else:  # "x"
            x = min(max(0, self._cur_x), n_w - 1)
            z = min(max(0, disp_y), n_z - 1)
            if self._flip_reformat:
                z = n_z - 1 - z
            y = min(max(0, disp_x), n_h - 1)

        return vol[:, z, y, x]

    def _extract_roi_curve(self, polygon: np.ndarray) -> "np.ndarray | None":
        """Compute mean intensity within a freehand polygon over each timepoint.

        *polygon* is (N, 2) float array of image (x, y) coordinates in display space.
        """
        vol   = self._vol
        stype = self._stype
        if vol is None or stype not in (SeriesType.S2DT, SeriesType.S3DT):
            return None
        try:
            from matplotlib.path import Path as MplPath
        except ImportError:
            return None

        mpl_path = MplPath(polygon)

        def _mask2d(H, W, flip_rows=False):
            Y, X = np.mgrid[0:H, 0:W]
            pts  = np.column_stack([X.ravel(), Y.ravel()])
            mask = mpl_path.contains_points(pts).reshape(H, W)
            if flip_rows:
                mask = mask[::-1, :]
            return mask

        if stype == SeriesType.S2DT:
            T, H, W = vol.shape
            mask = _mask2d(H, W, self._flip_acq_rows)
            if not mask.any():
                return None
            return vol[:, mask].mean(axis=1)

        # S3DT: vol (T, Z, H, W)
        T, n_z, n_h, n_w = vol.shape
        from .view_cell import _AXIS
        acq  = self._acq_plane if self._acq_plane in ("AXIAL","CORONAL","SAGITTAL") else "AXIAL"
        axis = _AXIS.get((acq, self._view_mode), "z")

        if axis == "z":
            z    = min(max(0, self._cur_z), n_z - 1)
            mask = _mask2d(n_h, n_w, self._flip_acq_rows)
            if not mask.any():
                return None
            return vol[:, z, mask].mean(axis=1)

        elif axis == "y":
            y    = min(max(0, self._cur_y), n_h - 1)
            # display rows=Z, cols=W
            mask = _mask2d(n_z, n_w, self._flip_reformat)
            if not mask.any():
                return None
            z_idx, x_idx = np.where(mask)
            return vol[:, z_idx, y, x_idx].mean(axis=1)

        else:  # "x"
            x    = min(max(0, self._cur_x), n_w - 1)
            # display rows=Z, cols=H
            mask = _mask2d(n_z, n_h, self._flip_reformat)
            if not mask.any():
                return None
            z_idx, y_idx = np.where(mask)
            return vol[:, z_idx, y_idx, x].mean(axis=1)

    def _ensure_canvas(self) -> bool:
        global _MPL
        if _MPL is False:
            return False
        if self._plot_canvas is not None:
            return True
        try:
            import warnings as _w
            with _w.catch_warnings():
                _w.simplefilter("ignore")
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
                from matplotlib.figure import Figure
            fig = Figure(facecolor=_PANEL, layout="tight")
            self._ax = fig.add_subplot(111)
            self._fig = fig
            self._plot_canvas = FigureCanvasQTAgg(fig)
            self._plot_canvas.setStyleSheet(f"background:{_PANEL};")
            self._plot_area_lay.addWidget(self._plot_canvas)
            _MPL = True
            return True
        except Exception:
            _MPL = False
            return False

    def _redraw(self) -> None:
        if not self._ensure_canvas():
            return
        self._ax.clear()
        self._style_ax()

        drawn = 0
        for i, (ix, iy) in enumerate(self._points):
            curve = self._extract_curve(ix, iy)
            if curve is None:
                continue
            color = TC_COLORS[i % len(TC_COLORS)]
            label = f"P{i+1} ({ix},{iy})"
            self._ax.plot(curve, color=color, linewidth=1.5, label=label)
            drawn += 1

        # Freehand ROI-TC curves (one per polygon)
        n_pts = len(self._points)
        for j, poly in enumerate(self._roi_tc_polys):
            curve = self._extract_roi_curve(poly)
            if curve is None:
                continue
            color = TC_COLORS[(n_pts + j) % len(TC_COLORS)]
            self._ax.plot(curve, color=color, linewidth=2.0, linestyle="--",
                          label=f"ROI-{j+1} ({len(poly)}pts)")
            drawn += 1

        if drawn:
            self._ax.set_xlabel("Timepoint", color=_TEXT, fontsize=8)
            self._ax.set_ylabel("Intensity",  color=_TEXT, fontsize=8)
            self._ax.legend(
                fontsize=7, facecolor=_PANEL, edgecolor=_GRID,
                labelcolor=_TEXT, loc="best", framealpha=0.8,
            )

        self._plot_canvas.draw()
