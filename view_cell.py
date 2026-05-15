"""Single panel cell for the 4-panel quad view."""
from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QDoubleSpinBox,
    QSizePolicy, QStackedWidget,
)

from .image_canvas import ImageCanvas
from .loader import LoaderWorker
from .data_model import SeriesData, SeriesType
from .constants import DEFAULT_FPS, MAX_FPS
from . import drag_state


# (acq_plane, view_mode) → which array axis to cut through
# 'z' = vol[z,:,:]  (acquisition plane)
# 'y' = vol[:,y,:]  (reformat — uses flip_reformat + r1 aspect)
# 'x' = vol[:,:,x]  (reformat — uses flip_reformat + r2 aspect)
_AXIS = {
    ("AXIAL",    "AXIAL"):    "z",
    ("AXIAL",    "CORONAL"):  "y",
    ("AXIAL",    "SAGITTAL"): "x",
    ("CORONAL",  "CORONAL"):  "z",
    ("CORONAL",  "AXIAL"):    "y",
    ("CORONAL",  "SAGITTAL"): "x",
    ("SAGITTAL", "SAGITTAL"): "z",
    ("SAGITTAL", "AXIAL"):    "y",
    ("SAGITTAL", "CORONAL"):  "x",
    ("OBLIQUE",  "AXIAL"):    "z",
    ("OBLIQUE",  "CORONAL"):  "y",
    ("OBLIQUE",  "SAGITTAL"): "x",
}

_VIEWS = ("AXIAL", "CORONAL", "SAGITTAL")


class ViewCell(QWidget):
    """One panel in the 2×2 quad viewer.

    Owns its own LoaderWorker — fully independent from other cells.
    """
    activated      = pyqtSignal()          # user interacted → make this the active cell
    wl_changed     = pyqtSignal(float, float)
    pixel_hovered  = pyqtSignal(int, int, float)
    double_clicked = pyqtSignal()          # request fullscreen toggle

    def __init__(self, cell_index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("viewCell")
        self._idx  = cell_index
        self._active = False

        # Data state
        self._sd:           SeriesData | None = None
        self._vol:          np.ndarray | None = None
        self._loaded_mask:  np.ndarray | None = None
        self._view_mode:    str  = "AXIAL"
        self._cur_z:        int  = 0
        self._cur_y:        int  = 0
        self._cur_x:        int  = 0
        self._cur_t:        int  = 0
        self._playing:      bool = False

        self._tc_window    = None   # TimeCourseWindow (floating) or embedded panel
        self._tc_panel_ref = None   # injected shared embedded panel (set by MainWindow)

        self._loader = LoaderWorker()
        self._loader.headers_ready.connect(self._on_headers_ready)
        self._loader.pixels_ready.connect(self._on_pixels_ready)
        self._loader.load_complete.connect(self._on_load_complete)
        self._loader.progress.connect(self._on_progress)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_time)

        self._build_ui()
        self._set_state_empty()
        self.setAcceptDrops(True)
        self._canvas.installEventFilter(self)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Header bar ─────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("cellHeader")
        self._header.setFixedHeight(26)

        self._ax_btn  = self._make_view_btn("AX")
        self._cor_btn = self._make_view_btn("COR")
        self._sag_btn = self._make_view_btn("SAG")
        self._ax_btn.setChecked(True)

        self._ax_btn.clicked.connect(lambda: self._set_view("AXIAL"))
        self._cor_btn.clicked.connect(lambda: self._set_view("CORONAL"))
        self._sag_btn.clicked.connect(lambda: self._set_view("SAGITTAL"))

        # W/L mode toggle: "W/L" (drag) vs "ROI" (region select)
        self._roi_btn = QPushButton("ROI")
        self._roi_btn.setObjectName("roiModeBtn")
        self._roi_btn.setCheckable(True)
        self._roi_btn.setToolTip("ROI W/L: drag a rectangle to set W/L from region")
        self._roi_btn.toggled.connect(self._on_roi_mode_toggled)

        self._tc_btn = QPushButton("TC")
        self._tc_btn.setObjectName("roiModeBtn")
        self._tc_btn.setCheckable(True)
        self._tc_btn.setToolTip("Time course: click to place points, plot intensity vs time")
        self._tc_btn.setVisible(False)
        self._tc_btn.toggled.connect(self._on_tc_mode_toggled)

        self._roi_tc_btn = QPushButton("ROI-TC")
        self._roi_tc_btn.setObjectName("roiModeBtn")
        self._roi_tc_btn.setCheckable(True)
        self._roi_tc_btn.setToolTip("ROI time course: draw a rectangle, plot mean intensity vs time")
        self._roi_tc_btn.setVisible(False)
        self._roi_tc_btn.toggled.connect(self._on_roi_tc_mode_toggled)

        self._series_lbl = QLabel("")
        self._series_lbl.setObjectName("cellSeriesLabel")
        self._series_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        h_lay = QHBoxLayout(self._header)
        h_lay.setContentsMargins(4, 2, 4, 2)
        h_lay.setSpacing(3)
        h_lay.addWidget(self._ax_btn)
        h_lay.addWidget(self._cor_btn)
        h_lay.addWidget(self._sag_btn)
        h_lay.addWidget(self._roi_btn)
        h_lay.addWidget(self._tc_btn)
        h_lay.addWidget(self._roi_tc_btn)
        h_lay.addStretch(1)
        h_lay.addWidget(self._series_lbl)

        # ── Canvas + vertical slice slider ─────────────────────────────────
        self._canvas = ImageCanvas(self)
        self._canvas.setFocusPolicy(Qt.ClickFocus)
        self._canvas.wl_changed.connect(self._on_canvas_wl)
        self._canvas.pixel_hovered.connect(self.pixel_hovered)
        self._canvas.tc_points_changed.connect(self._on_tc_points_changed)
        self._canvas.roi_tc_polys_changed.connect(self._on_roi_tc_changed)

        self._slice_slider = QSlider(Qt.Vertical)
        self._slice_slider.setMinimum(0)
        self._slice_slider.setMaximum(0)
        self._slice_slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._slice_slider.setFixedWidth(18)
        self._slice_slider.valueChanged.connect(self._on_slice_changed)

        self._drop_lbl = QLabel("Drop series here")
        self._drop_lbl.setObjectName("dropLabel")
        self._drop_lbl.setAlignment(Qt.AlignCenter)

        canvas_row = QHBoxLayout()
        canvas_row.setContentsMargins(0, 0, 0, 0)
        canvas_row.setSpacing(2)
        canvas_row.addWidget(self._canvas, 1)
        canvas_row.addWidget(self._slice_slider)

        canvas_wrap = QStackedWidget()
        self._canvas_widget = QWidget()
        self._canvas_widget.setLayout(canvas_row)
        canvas_wrap.addWidget(self._drop_lbl)     # page 0: empty
        canvas_wrap.addWidget(self._canvas_widget) # page 1: loaded
        self._canvas_stack = canvas_wrap

        # ── Bottom time bar ─────────────────────────────────────────────────
        self._bottom_bar = QWidget()
        self._bottom_bar.setObjectName("cellHeader")
        self._bottom_bar.setFixedHeight(30)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.setCheckable(True)
        self._play_btn.setFixedSize(24, 24)
        self._play_btn.toggled.connect(self._on_play_toggled)

        self._time_slider = QSlider(Qt.Horizontal)
        self._time_slider.setMinimum(0)
        self._time_slider.valueChanged.connect(self._on_time_changed)

        self._time_lbl = QLabel("t=0/0")
        self._time_lbl.setObjectName("cellSeriesLabel")
        self._time_lbl.setMinimumWidth(48)

        self._fps_spin = QDoubleSpinBox()
        self._fps_spin.setRange(0.5, MAX_FPS)
        self._fps_spin.setValue(DEFAULT_FPS)
        self._fps_spin.setSuffix("fps")
        self._fps_spin.setDecimals(0)
        self._fps_spin.setFixedWidth(64)
        self._fps_spin.valueChanged.connect(self._update_timer_interval)

        t_lay = QHBoxLayout(self._bottom_bar)
        t_lay.setContentsMargins(4, 3, 4, 3)
        t_lay.setSpacing(4)
        t_lay.addWidget(self._play_btn)
        t_lay.addWidget(self._time_slider, 1)
        t_lay.addWidget(self._time_lbl)
        t_lay.addWidget(self._fps_spin)

        # ── Root layout ─────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(0)
        root.addWidget(self._header)
        root.addWidget(self._canvas_stack, 1)
        root.addWidget(self._bottom_bar)

    def _make_view_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("viewModeBtn")
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        return btn

    # ── Public API ─────────────────────────────────────────────────────────

    def load_meta(self, meta) -> None:
        self._stop_playback()
        self._loader.cancel()
        self._sd   = None
        self._vol  = None
        self._loaded_mask = None
        self._cur_z = self._cur_y = self._cur_x = self._cur_t = 0

        # Reset interaction modes
        self._roi_btn.blockSignals(True)
        self._roi_btn.setChecked(False)
        self._roi_btn.blockSignals(False)
        self._tc_btn.blockSignals(True)
        self._tc_btn.setChecked(False)
        self._tc_btn.setVisible(False)
        self._tc_btn.blockSignals(False)
        self._roi_tc_btn.blockSignals(True)
        self._roi_tc_btn.setChecked(False)
        self._roi_tc_btn.setVisible(False)
        self._roi_tc_btn.blockSignals(False)
        self._canvas.set_wl_mode("drag")
        self._canvas.clear_tc_points()
        self._canvas.clear_roi_tc_polys()
        if self._tc_window is not None:
            self._tc_window.clear_roi_data()
            self._tc_window.hide()

        name = getattr(meta, "series_name", None) or getattr(meta, "group_name", "")
        self._series_lbl.setText(self._truncate(name, 28))
        self._canvas_stack.setCurrentIndex(1)
        self._canvas.set_image(None)
        self._set_controls_visible(False, False)
        self._loader.request_load(meta)

    def set_wl(self, wc: float, ww: float) -> None:
        self._canvas.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        self._canvas.set_colormap(name)

    def current_wl(self) -> tuple[float, float]:
        return self._canvas.wl()

    def series_data(self) -> SeriesData | None:
        return self._sd

    def reset_wl(self) -> None:
        if self._sd:
            self._canvas.set_wl(self._sd.window_center, self._sd.window_width)

    def set_active(self, active: bool) -> None:
        self._active = active
        # Dynamic QSS property for border colour
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)

    # ── Loader slots ───────────────────────────────────────────────────────

    def _on_headers_ready(self, sd: SeriesData) -> None:
        self._sd = sd
        st = sd.series_type
        is_3d  = st in (SeriesType.S3D, SeriesType.S3DT)
        is_time = st in (SeriesType.S2DT, SeriesType.S3DT)
        self._tc_btn.setVisible(is_time)
        self._roi_tc_btn.setVisible(is_time)
        self._set_controls_visible(is_3d, is_time)

        if is_3d:
            # Default view = acquisition plane
            self._view_mode = sd.acq_plane if sd.acq_plane in _VIEWS else "AXIAL"
            self._update_view_buttons()
        else:
            self._view_mode = "AXIAL"  # unused for 2D

        self._canvas.set_wl(sd.window_center, sd.window_width)

    def _on_pixels_ready(self, t: int, array: np.ndarray) -> None:
        if self._sd is None:
            return
        st = self._sd.series_type

        if st == SeriesType.S3DT:
            self._vol = array
            if self._loaded_mask is None:
                self._loaded_mask = np.zeros(array.shape[0], bool)
            self._loaded_mask[t] = True
            if t == 0:
                # Set slider ranges now that we know the volume shape
                n_t, n_z, n_h, n_w = array.shape
                self._setup_3d_sliders(n_z, n_h, n_w)
                self._time_slider.setMaximum(max(0, n_t - 1))
                self._time_lbl.setText(f"t=1/{n_t}")
                self._canvas.set_wl(self._sd.window_center, self._sd.window_width)
            if t == self._cur_t:
                self._render()

        elif st == SeriesType.S3D:
            self._vol = array
            n_z, n_h, n_w = array.shape
            self._setup_3d_sliders(n_z, n_h, n_w)
            self._canvas.set_wl(self._sd.window_center, self._sd.window_width)
            self._render()

        elif st == SeriesType.S2DT:
            self._vol = array
            n_t = array.shape[0]
            self._time_slider.setMaximum(max(0, n_t - 1))
            self._time_lbl.setText(f"t=1/{n_t}")
            self._canvas.set_wl(self._sd.window_center, self._sd.window_width)
            self._render()

        elif st in (SeriesType.S2D, SeriesType.MULTI):
            self._vol = array
            self._canvas.set_wl(self._sd.window_center, self._sd.window_width)
            self._render()

    def _on_load_complete(self) -> None:
        pass

    def _on_progress(self, loaded: int, total: int) -> None:
        self._canvas.set_label(f"{loaded}/{total}")

    # ── Rendering ──────────────────────────────────────────────────────────

    def _render(self) -> None:
        if self._vol is None or self._sd is None:
            return
        sl, asp = self._extract_slice()
        self._canvas.set_image(sl, asp, reset_view=False)
        self._canvas.set_label("")

    def _extract_slice(self) -> tuple[np.ndarray, float]:
        sd  = self._sd
        vol = self._vol
        st  = sd.series_type

        if st == SeriesType.S2D:
            return self._apply_flip(vol, acq=True), 1.0

        if st == SeriesType.MULTI:
            idx = min(self._cur_z, vol.shape[0] - 1)
            return self._apply_flip(vol[idx], acq=True), 1.0

        if st == SeriesType.S2DT:
            t = min(self._cur_t, vol.shape[0] - 1)
            return self._apply_flip(vol[t], acq=True), 1.0

        # 3D or 3D-T
        vol3 = vol if st == SeriesType.S3D else vol[min(self._cur_t, vol.shape[0]-1)]

        acq  = sd.acq_plane if sd.acq_plane in _VIEWS else "AXIAL"
        axis = _AXIS.get((acq, self._view_mode), "z")

        n_z, n_h, n_w = vol3.shape
        if axis == "z":
            z = min(self._cur_z, n_z - 1)
            sl = self._apply_flip(vol3[z], acq=True)
            asp = 1.0
        elif axis == "y":
            y = min(self._cur_y, n_h - 1)
            sl = vol3[:, y, :]
            if sd.flip_reformat:
                sl = np.flipud(sl)
            dz = sd.slice_spacing or 1.0
            dx = sd.pixel_spacing[1] or 1.0
            asp = dz / dx
        else:  # "x"
            x = min(self._cur_x, n_w - 1)
            sl = vol3[:, :, x]
            if sd.flip_reformat:
                sl = np.flipud(sl)
            dz = sd.slice_spacing or 1.0
            dy = sd.pixel_spacing[0] or 1.0
            asp = dz / dy

        return sl, asp

    def _apply_flip(self, sl: np.ndarray, acq: bool = False) -> np.ndarray:
        if acq and self._sd:
            if self._sd.flip_acq_rows:
                sl = np.flipud(sl)
            if self._sd.flip_acq_cols:
                sl = np.fliplr(sl)
        return sl

    # ── Slice / time navigation ────────────────────────────────────────────

    def _on_slice_changed(self, value: int) -> None:
        acq  = (self._sd.acq_plane if self._sd and self._sd.acq_plane in _VIEWS else "AXIAL")
        axis = _AXIS.get((acq, self._view_mode), "z")
        if axis == "z":
            self._cur_z = value
        elif axis == "y":
            self._cur_y = value
        else:
            self._cur_x = value
        self._render()
        if self._tc_window is not None and self._tc_window.isVisible():
            self._tc_window.update_slice(self._cur_z, self._cur_y, self._cur_x)

    def _on_time_changed(self, value: int) -> None:
        self._cur_t = value
        if self._sd:
            n_t = self._sd.n_timepoints
            self._time_lbl.setText(f"t={value+1}/{n_t}")
        # Check if this timepoint is loaded (for streaming 3DT)
        if self._loaded_mask is not None and not self._loaded_mask[value]:
            return
        self._render()

    # ── W/L / ROI / TC mode toggles ───────────────────────────────────────

    def _on_roi_mode_toggled(self, checked: bool) -> None:
        if checked:
            self._tc_btn.blockSignals(True)
            self._tc_btn.setChecked(False)
            self._tc_btn.blockSignals(False)
            self._roi_tc_btn.blockSignals(True)
            self._roi_tc_btn.setChecked(False)
            self._roi_tc_btn.blockSignals(False)
            if self._tc_window is not None:
                self._tc_window.hide()
            self._canvas.set_wl_mode("roi")
        else:
            self._canvas.set_wl_mode("drag")

    def _on_tc_mode_toggled(self, checked: bool) -> None:
        if checked:
            self._roi_btn.blockSignals(True)
            self._roi_btn.setChecked(False)
            self._roi_btn.blockSignals(False)
            self._roi_tc_btn.blockSignals(True)
            self._roi_tc_btn.setChecked(False)
            self._roi_tc_btn.blockSignals(False)
            self._canvas.set_wl_mode("tc")
            self._ensure_tc_window()
        else:
            self._canvas.set_wl_mode("drag")
            if self._tc_window is not None:
                self._tc_window.hide()

    def _on_roi_tc_mode_toggled(self, checked: bool) -> None:
        if checked:
            self._roi_btn.blockSignals(True)
            self._roi_btn.setChecked(False)
            self._roi_btn.blockSignals(False)
            self._tc_btn.blockSignals(True)
            self._tc_btn.setChecked(False)
            self._tc_btn.blockSignals(False)
            self._canvas.set_wl_mode("roi_tc")
            self._ensure_tc_window()
        else:
            self._canvas.set_wl_mode("drag")
            self._canvas.clear_roi_tc_polys()
            if self._tc_window is not None:
                self._tc_window.clear_roi_data()
                self._tc_window.hide()

    def _on_roi_tc_changed(self, polys: list) -> None:
        """Canvas emits this when a freehand polygon is added or removed."""
        if self._tc_window is None or not self._tc_window.isVisible():
            return
        if self._vol is None or self._sd is None:
            return
        acq = self._sd.acq_plane if self._sd.acq_plane in _VIEWS else "AXIAL"
        self._tc_window.set_geometry_info(
            self._view_mode, acq,
            self._cur_z, self._cur_y, self._cur_x,
            self._sd.flip_acq_rows, self._sd.flip_reformat,
        )
        self._tc_window.update_roi_polys(self._vol, self._sd.series_type, polys)

    def set_tc_panel(self, panel) -> None:
        """Inject the shared embedded TC panel from MainWindow."""
        self._tc_panel_ref = panel

    def is_tc_active(self) -> bool:
        return self._tc_btn.isChecked()

    def refresh_tc_panel(self) -> None:
        """Called when this cell becomes the active cell — sync panel visibility."""
        panel = self._tc_panel_ref
        if panel is None:
            return
        if self.is_tc_active():
            panel.setVisible(True)
            self._on_tc_points_changed(self._canvas.tc_points())
        else:
            panel.setVisible(False)

    def _clear_all_tc(self) -> None:
        self._canvas.clear_tc_points()
        self._canvas.clear_roi_tc_polys()

    def _ensure_tc_window(self) -> None:
        if self._tc_panel_ref is not None:
            w = self._tc_panel_ref
            if self._tc_window is not w:
                # Re-wire clear_requested to this cell's canvas
                try:
                    w.clear_requested.disconnect()
                except TypeError:
                    pass
                w.clear_requested.connect(self._clear_all_tc)
                self._tc_window = w
            w.set_series_name(self._series_lbl.text())
            w.setVisible(True)
        else:
            # Fallback: floating window
            if self._tc_window is None:
                from .time_course_window import TimeCourseWindow
                self._tc_window = TimeCourseWindow()
                self._tc_window.clear_requested.connect(self._clear_all_tc)
                self._tc_window.window_closed.connect(self._on_tc_window_closed)
            self._tc_window.set_series_name(self._series_lbl.text())
            mw = self.window()
            if mw is not None:
                geo = mw.geometry()
                self._tc_window.move(geo.right() + 20, geo.top())
            self._tc_window.show()
            self._tc_window.raise_()

    def _on_tc_window_closed(self) -> None:
        self._tc_btn.blockSignals(True)
        self._tc_btn.setChecked(False)
        self._tc_btn.blockSignals(False)
        self._canvas.set_wl_mode("drag")

    def _on_tc_points_changed(self, points: list) -> None:
        if self._tc_window is None or not self._tc_window.isVisible():
            return
        if self._vol is None or self._sd is None:
            return
        acq = self._sd.acq_plane if self._sd.acq_plane in _VIEWS else "AXIAL"
        self._tc_window.set_geometry_info(
            self._view_mode, acq,
            self._cur_z, self._cur_y, self._cur_x,
            self._sd.flip_acq_rows, self._sd.flip_reformat,
        )
        self._tc_window.update_data(self._vol, self._sd.series_type, points)

    # ── View mode ──────────────────────────────────────────────────────────

    def _set_view(self, mode: str) -> None:
        if mode == self._view_mode:
            return
        self._view_mode = mode
        # Reset the slice slider to midpoint of the new axis range
        if self._vol is not None and self._sd is not None:
            st = self._sd.series_type
            if st in (SeriesType.S3D, SeriesType.S3DT):
                vol3 = self._vol if st == SeriesType.S3D else self._vol[0]
                n_z, n_h, n_w = vol3.shape
                acq  = self._sd.acq_plane if self._sd.acq_plane in _VIEWS else "AXIAL"
                axis = _AXIS.get((acq, mode), "z")
                if axis == "z":
                    depth = n_z
                elif axis == "y":
                    depth = n_h
                else:
                    depth = n_w
                self._slice_slider.blockSignals(True)
                self._slice_slider.setMaximum(max(0, depth - 1))
                self._slice_slider.setValue(depth // 2)
                self._slice_slider.blockSignals(False)
                if axis == "z":
                    self._cur_z = depth // 2
                elif axis == "y":
                    self._cur_y = depth // 2
                else:
                    self._cur_x = depth // 2
        self._render()
        if self._tc_window is not None and self._tc_window.isVisible():
            self._on_tc_points_changed(self._canvas.tc_points())

    def _update_view_buttons(self) -> None:
        v = self._view_mode
        self._ax_btn.blockSignals(True)
        self._cor_btn.blockSignals(True)
        self._sag_btn.blockSignals(True)
        self._ax_btn.setChecked(v == "AXIAL")
        self._cor_btn.setChecked(v == "CORONAL")
        self._sag_btn.setChecked(v == "SAGITTAL")
        self._ax_btn.blockSignals(False)
        self._cor_btn.blockSignals(False)
        self._sag_btn.blockSignals(False)

    # ── Playback ───────────────────────────────────────────────────────────

    def _on_play_toggled(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")
        if playing:
            self._update_timer_interval()
            self._timer.start()
        else:
            self._timer.stop()

    def _advance_time(self) -> None:
        if self._sd is None:
            return
        n_t = self._sd.n_timepoints
        if n_t <= 1:
            return
        nxt = (self._cur_t + 1) % n_t
        if self._loaded_mask is not None and not self._loaded_mask[nxt]:
            return
        self._time_slider.setValue(nxt)

    def _update_timer_interval(self) -> None:
        fps = max(0.5, self._fps_spin.value())
        self._timer.setInterval(int(1000 / fps))

    def _stop_playback(self) -> None:
        self._timer.stop()
        self._play_btn.blockSignals(True)
        self._play_btn.setChecked(False)
        self._play_btn.setText("▶")
        self._play_btn.blockSignals(False)

    # ── Helper: set up slice slider ranges ─────────────────────────────────

    def _setup_3d_sliders(self, n_z: int, n_h: int, n_w: int) -> None:
        acq  = self._sd.acq_plane if self._sd and self._sd.acq_plane in _VIEWS else "AXIAL"
        axis = _AXIS.get((acq, self._view_mode), "z")
        if axis == "z":
            depth = n_z
        elif axis == "y":
            depth = n_h
        else:
            depth = n_w
        self._slice_slider.blockSignals(True)
        self._slice_slider.setMaximum(max(0, depth - 1))
        mid = depth // 2
        self._slice_slider.setValue(mid)
        self._slice_slider.blockSignals(False)
        # Set mid as current index
        if axis == "z":
            self._cur_z = mid
        elif axis == "y":
            self._cur_y = mid
        else:
            self._cur_x = mid

    # ── Wheel scroll on canvas → slice ─────────────────────────────────────

    def _scroll_slice(self, delta: int) -> None:
        step = -1 if delta > 0 else 1
        v = self._slice_slider.value() + step
        v = max(self._slice_slider.minimum(), min(self._slice_slider.maximum(), v))
        self._slice_slider.setValue(v)

    def _scroll_time(self, delta: int) -> None:
        if self._sd is None:
            return
        step = -1 if delta > 0 else 1
        v = self._time_slider.value() + step
        v = max(self._time_slider.minimum(), min(self._time_slider.maximum(), v))
        self._time_slider.setValue(v)

    # ── Visibility helpers ─────────────────────────────────────────────────

    def _set_controls_visible(self, show_slice: bool, show_time: bool) -> None:
        self._ax_btn.setVisible(show_slice)
        self._cor_btn.setVisible(show_slice)
        self._sag_btn.setVisible(show_slice)
        self._slice_slider.setVisible(show_slice)
        self._bottom_bar.setVisible(show_time)

    def _set_state_empty(self) -> None:
        self._canvas_stack.setCurrentIndex(0)
        self._series_lbl.setText("")
        self._set_controls_visible(False, False)

    # ── Canvas W/L relay ───────────────────────────────────────────────────

    def _on_canvas_wl(self, wc: float, ww: float) -> None:
        self.activated.emit()
        self.wl_changed.emit(wc, ww)

    # ── Drag and drop ──────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(drag_state.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        meta = drag_state.get_payload()
        drag_state.clear_payload()
        if meta is not None:
            self.load_meta(meta)
            self.activated.emit()
        event.acceptProposedAction()

    # ── Mouse events ───────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        self.activated.emit()
        super().mousePressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._canvas:
            t = event.type()
            if t == QEvent.MouseButtonPress:
                self.activated.emit()
            elif t == QEvent.KeyPress:
                if event.key() == Qt.Key_Space and self._bottom_bar.isVisible():
                    self._play_btn.toggle()
                    return True
            elif t == QEvent.MouseButtonDblClick:
                self.double_clicked.emit()
                return True   # consume: prevent W/L drag start on dbl-click
            elif t == QEvent.Wheel:
                modifiers = event.modifiers()
                delta = event.angleDelta().y()
                if modifiers & Qt.ControlModifier:
                    self._canvas.zoom_wheel(delta)
                elif modifiers & Qt.ShiftModifier:
                    self._scroll_time(delta)
                else:
                    self._scroll_slice(delta)
                return True
        return super().eventFilter(obj, event)

    # ── Utilities ──────────────────────────────────────────────────────────

    @staticmethod
    def _truncate(text: str, n: int) -> str:
        return text if len(text) <= n else text[:n-1] + "…"
