"""Main application window."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QStatusBar,
)

from .constants import TREE_WIDTH, STYLE_PATH, BADGE_COLORS
from .colormaps import COLORMAP_NAMES
from .data_model import SeriesMeta, GroupedSeriesMeta
from .tree_panel import StudyTreeWidget
from .quad_view import QuadView
from .view_cell import ViewCell


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vidi")
        self.resize(1400, 900)

        self._build_ui()
        self._connect_signals()
        self._load_stylesheet()
        self._inject_tc_panel()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ── Toolbar ────────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(44)

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(COLORMAP_NAMES)
        self._cmap_combo.setCurrentText("Gray")

        cmap_lbl = QLabel("Colormap")
        cmap_lbl.setStyleSheet("color: #6c7086;")

        self._wc_spin = QDoubleSpinBox()
        self._wc_spin.setRange(-100000, 100000)
        self._wc_spin.setValue(2048)
        self._wc_spin.setPrefix("C: ")
        self._wc_spin.setDecimals(1)
        self._wc_spin.setSingleStep(10)
        self._wc_spin.setFixedWidth(110)

        self._ww_spin = QDoubleSpinBox()
        self._ww_spin.setRange(1, 200000)
        self._ww_spin.setValue(4096)
        self._ww_spin.setPrefix("W: ")
        self._ww_spin.setDecimals(1)
        self._ww_spin.setSingleStep(10)
        self._ww_spin.setFixedWidth(110)

        reset_btn = QPushButton("Reset W/L")
        reset_btn.clicked.connect(self._reset_wl)

        self._type_badge = QLabel("")
        self._type_badge.setObjectName("typeLabel")
        self._type_badge.setMinimumWidth(50)

        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(12, 6, 12, 6)
        tb_lay.setSpacing(10)
        tb_lay.addWidget(cmap_lbl)
        tb_lay.addWidget(self._cmap_combo)
        tb_lay.addWidget(self._wc_spin)
        tb_lay.addWidget(self._ww_spin)
        tb_lay.addWidget(reset_btn)
        tb_lay.addStretch(1)
        tb_lay.addWidget(self._type_badge)

        # ── Tree + quad viewer splitter ────────────────────────────────────
        self._tree = StudyTreeWidget()
        self._quad = QuadView()

        self._tree.setMinimumWidth(200)
        self._tree.setMaximumWidth(450)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._quad)
        splitter.setSizes([TREE_WIDTH, 1100])
        splitter.setStretchFactor(1, 1)

        # ── Status bar ─────────────────────────────────────────────────────
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_series   = QLabel("No series selected")
        self._status_pixel    = QLabel("")
        self._status_progress = QLabel("")
        for lbl in (self._status_series, self._status_pixel):
            sb.addWidget(lbl)
            lbl.setObjectName("statusLabel")
        sb.addPermanentWidget(self._status_progress)
        self._status_progress.setObjectName("statusLabel")

        from .gpu import GPU
        if GPU.available:
            try:
                import cupy as cp
                dev_name = cp.cuda.runtime.getDeviceProperties(0)["name"].decode()
            except Exception:
                dev_name = "GPU"
            gpu_lbl = QLabel(f"⚡ {dev_name}")
            gpu_lbl.setStyleSheet("color:#a6e3a1; font-size:10px; padding:0 6px;")
            sb.addPermanentWidget(gpu_lbl)

        # ── Root layout ────────────────────────────────────────────────────
        central = QWidget()
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(toolbar)
        root_lay.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        # Tree → active cell load
        self._tree.series_selected.connect(self._on_series_selected)

        # Quad → toolbar sync
        self._quad.active_cell_changed.connect(self._on_active_cell_changed)
        self._quad.wl_changed.connect(self._on_viewer_wl)
        self._quad.pixel_hovered.connect(self._on_pixel_hovered)

        # Toolbar → quad
        self._cmap_combo.currentTextChanged.connect(self._quad.set_colormap)
        self._wc_spin.valueChanged.connect(self._on_toolbar_wl)
        self._ww_spin.valueChanged.connect(self._on_toolbar_wl)

    def _load_stylesheet(self) -> None:
        try:
            with open(STYLE_PATH) as f:
                self.setStyleSheet(f.read())
        except Exception:
            pass

    def _inject_tc_panel(self) -> None:
        panel = self._tree.tc_panel
        for cell in self._quad._cells:
            cell.set_tc_panel(panel)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_series_selected(self, meta) -> None:
        """Load into the currently active cell."""
        cell = self._quad.active_cell()
        cell.load_meta(meta)

        if isinstance(meta, GroupedSeriesMeta):
            self._status_series.setText(
                f"{meta.study_name}  /  {meta.group_name}  "
                f"(×{meta.n_timepoints} timepoints)"
            )
        else:
            self._status_series.setText(
                f"{meta.study_name}  /  {meta.series_name}  ({meta.n_files} files)"
            )

    def _on_active_cell_changed(self, cell: ViewCell) -> None:
        """Sync toolbar W/L spinboxes to the newly activated cell."""
        wc, ww = cell.current_wl()
        self._sync_wl_spins(wc, ww)
        sd = cell.series_data()
        if sd:
            self._show_type_badge(sd.series_type.value)
        else:
            self._type_badge.setText("")
        cell.refresh_tc_panel()

    def _on_viewer_wl(self, wc: float, ww: float) -> None:
        self._sync_wl_spins(wc, ww)

    def _sync_wl_spins(self, wc: float, ww: float) -> None:
        self._wc_spin.blockSignals(True)
        self._ww_spin.blockSignals(True)
        self._wc_spin.setValue(wc)
        self._ww_spin.setValue(ww)
        self._wc_spin.blockSignals(False)
        self._ww_spin.blockSignals(False)

    def _on_toolbar_wl(self) -> None:
        self._quad.set_wl(self._wc_spin.value(), self._ww_spin.value())

    def _on_pixel_hovered(self, x: int, y: int, val: float) -> None:
        self._status_pixel.setText(f"x={x}  y={y}  val={val:.0f}")

    def _reset_wl(self) -> None:
        self._quad.reset_wl()

    def _show_type_badge(self, type_str: str) -> None:
        color = BADGE_COLORS.get(type_str, "#cdd6f4")
        self._type_badge.setText(type_str)
        self._type_badge.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 11px;"
            f"padding: 2px 8px; border-radius: 4px;"
            f"background: {color}22;"
        )

    def closeEvent(self, event) -> None:
        self._quad.cancel_all()
        super().closeEvent(event)
