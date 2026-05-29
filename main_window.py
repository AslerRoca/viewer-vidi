"""Main application window."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QStatusBar, QShortcut,
    QInputDialog, QMessageBox, QDockWidget,
)

from .constants import TREE_WIDTH, STYLE_PATH, BADGE_COLORS
from .colormaps import COLORMAP_NAMES
from .data_model import SeriesMeta, GroupedSeriesMeta
from .tree_panel import StudyTreeWidget
from .quad_view import QuadView
from .view_cell import ViewCell
from .overlays_panel import OverlaysPanel
from . import presets as wl_presets


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

        preset_lbl = QLabel("Preset")
        preset_lbl.setStyleSheet("color: #6c7086;")

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumContentsLength(12)
        self._preset_combo.setToolTip(
            "Apply a Window/Level preset to the active panel."
        )
        self._rebuild_preset_combo()

        self._preset_save_btn = QPushButton("+")
        self._preset_save_btn.setFixedWidth(24)
        self._preset_save_btn.setToolTip("Save current C/W as a new preset")
        self._preset_delete_btn = QPushButton("−")
        self._preset_delete_btn.setFixedWidth(24)
        self._preset_delete_btn.setToolTip("Delete the selected custom preset")
        self._preset_delete_btn.setEnabled(False)

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

        self._hu_offset_spin = QDoubleSpinBox()
        self._hu_offset_spin.setRange(-100000, 100000)
        self._hu_offset_spin.setValue(0)
        self._hu_offset_spin.setPrefix("HU offset: ")
        self._hu_offset_spin.setDecimals(0)
        self._hu_offset_spin.setSingleStep(1024)
        self._hu_offset_spin.setFixedWidth(150)
        self._hu_offset_spin.setToolTip(
            "Additive offset applied to MetaImage (.mhd/.mha) volumes that lost "
            "their DICOM RescaleIntercept during conversion. Set e.g. -4096 to map "
            "stored values back to Hounsfield units, then W/L presets work."
        )

        self._type_badge = QLabel("")
        self._type_badge.setObjectName("typeLabel")
        self._type_badge.setMinimumWidth(50)

        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(12, 6, 12, 6)
        tb_lay.setSpacing(10)
        tb_lay.addWidget(cmap_lbl)
        tb_lay.addWidget(self._cmap_combo)
        tb_lay.addWidget(preset_lbl)
        tb_lay.addWidget(self._preset_combo)
        tb_lay.addWidget(self._preset_save_btn)
        tb_lay.addWidget(self._preset_delete_btn)
        tb_lay.addWidget(self._wc_spin)
        tb_lay.addWidget(self._ww_spin)
        tb_lay.addWidget(reset_btn)
        tb_lay.addWidget(self._hu_offset_spin)
        tb_lay.addStretch(1)
        tb_lay.addWidget(self._type_badge)

        # ── Tree + quad viewer splitter ────────────────────────────────────
        self._tree = StudyTreeWidget()
        self._quad = QuadView()

        self._tree.setMinimumWidth(200)
        self._tree.setMaximumWidth(450)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(self._quad)
        self._splitter.setSizes([TREE_WIDTH, 1100])
        self._splitter.setStretchFactor(1, 1)
        self._tree_width = TREE_WIDTH

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
        root_lay.addWidget(self._splitter, 1)
        self.setCentralWidget(central)

        # ── Overlays dock (mask controls for the active panel) ──────────────
        self._overlays_panel = OverlaysPanel()
        dock = QDockWidget("Overlays", self)
        dock.setObjectName("overlaysDock")
        dock.setWidget(self._overlays_panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._overlays_dock = dock

    def _connect_signals(self) -> None:
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(self._toggle_sidebar)

        # Tree → active cell load
        self._tree.series_selected.connect(self._on_series_selected)

        # Quad → toolbar sync
        self._quad.active_cell_changed.connect(self._on_active_cell_changed)
        self._quad.wl_changed.connect(self._on_viewer_wl)
        self._quad.pixel_hovered.connect(self._on_pixel_hovered)

        # Per-cell overlay + status signals
        for cell in self._quad._cells:
            cell.overlays_changed.connect(self._on_overlays_changed)
            cell.status_message.connect(self._on_status_message)
        self._overlays_panel.set_cell(self._quad.active_cell())

        # Toolbar → quad
        self._cmap_combo.currentTextChanged.connect(self._quad.set_colormap)
        self._wc_spin.valueChanged.connect(self._on_toolbar_wl)
        self._ww_spin.valueChanged.connect(self._on_toolbar_wl)
        self._preset_combo.activated.connect(self._on_preset_selected)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_index_changed)
        self._preset_save_btn.clicked.connect(self._on_preset_save)
        self._preset_delete_btn.clicked.connect(self._on_preset_delete)
        self._hu_offset_spin.valueChanged.connect(self._quad.set_hu_offset)

    def _load_stylesheet(self) -> None:
        try:
            import os as _os
            with open(STYLE_PATH) as f:
                css = f.read()
            style_dir = _os.path.dirname(_os.path.abspath(STYLE_PATH))
            css = css.replace("{STYLE_DIR}", style_dir)
            self.setStyleSheet(css)
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
        self._overlays_panel.set_cell(cell)

    def _on_overlays_changed(self) -> None:
        sender = self.sender()
        if sender is self._quad.active_cell():
            self._overlays_panel.refresh()

    def _on_status_message(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 6000)

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

    # ── W/L presets ───────────────────────────────────────────────────────

    def _rebuild_preset_combo(self) -> None:
        """Populate the preset combo with built-ins followed by user-saved presets.

        Items carry (wc, ww, is_custom) in their userData; selection starts at
        -1 so picking the first item still fires `activated`.
        """
        cb = self._preset_combo
        cb.blockSignals(True)
        cb.clear()
        for name, wc, ww in wl_presets.BUILTIN_PRESETS:
            cb.addItem(name, (float(wc), float(ww), False))
        custom = wl_presets.load_custom_presets()
        if custom:
            cb.insertSeparator(cb.count())
            for name, wc, ww in custom:
                cb.addItem(name, (float(wc), float(ww), True))
        cb.setCurrentIndex(-1)
        cb.blockSignals(False)
        if hasattr(self, "_preset_delete_btn"):
            self._preset_delete_btn.setEnabled(False)

    def _on_preset_selected(self, idx: int) -> None:
        data = self._preset_combo.itemData(idx)
        if not data:
            return
        wc, ww, _is_custom = data
        self._sync_wl_spins(wc, ww)
        self._quad.set_wl(wc, ww)

    def _on_preset_index_changed(self, idx: int) -> None:
        data = self._preset_combo.itemData(idx)
        self._preset_delete_btn.setEnabled(bool(data) and bool(data[2]))

    def _on_preset_save(self) -> None:
        wc = self._wc_spin.value()
        ww = self._ww_spin.value()
        name, ok = QInputDialog.getText(
            self, "Save W/L preset",
            f"Name for preset (C={wc:.0f}, W={ww:.0f}):",
        )
        name = name.strip()
        if not (ok and name):
            return
        builtin_names = {n for n, *_ in wl_presets.BUILTIN_PRESETS}
        if name in builtin_names:
            QMessageBox.information(
                self, "Save W/L preset",
                f"\"{name}\" is a built-in preset name. Pick a different name.",
            )
            return
        custom = [p for p in wl_presets.load_custom_presets() if p[0] != name]
        custom.append((name, float(wc), float(ww)))
        wl_presets.save_custom_presets(custom)
        self._rebuild_preset_combo()
        new_idx = self._preset_combo.findText(name)
        if new_idx >= 0:
            self._preset_combo.setCurrentIndex(new_idx)

    def _on_preset_delete(self) -> None:
        idx = self._preset_combo.currentIndex()
        data = self._preset_combo.itemData(idx)
        if not data or not data[2]:
            return
        name = self._preset_combo.currentText()
        custom = [p for p in wl_presets.load_custom_presets() if p[0] != name]
        wl_presets.save_custom_presets(custom)
        self._rebuild_preset_combo()

    def _show_type_badge(self, type_str: str) -> None:
        color = BADGE_COLORS.get(type_str, "#cdd6f4")
        self._type_badge.setText(type_str)
        self._type_badge.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 11px;"
            f"padding: 2px 8px; border-radius: 4px;"
            f"background: {color}22;"
        )

    def _toggle_sidebar(self) -> None:
        if self._tree.isVisible():
            self._tree_width = self._splitter.sizes()[0] or self._tree_width
            self._tree.hide()
        else:
            self._tree.show()
            total = sum(self._splitter.sizes())
            self._splitter.setSizes([self._tree_width, total - self._tree_width])

    def closeEvent(self, event) -> None:
        self._quad.cancel_all()
        super().closeEvent(event)
