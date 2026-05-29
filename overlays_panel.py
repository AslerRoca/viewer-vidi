"""Overlays panel — per-panel mask overlay controls, synced to the active cell."""
from __future__ import annotations

from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QSlider, QScrollArea,
)


class OverlaysPanel(QWidget):
    """Lists the active cell's mask overlays with visibility / opacity / mode /
    remove controls. Stateless beyond a reference to the active ViewCell — it
    rebuilds its rows from `cell.overlays()` whenever asked to refresh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cell = None

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        title = QLabel("Mask overlays")
        title.setStyleSheet("color:#cdd6f4; font-weight:bold;")
        root.addWidget(title)

        self._empty = QLabel("No masks for the active panel.")
        self._empty.setStyleSheet("color:#6c7086; font-size:11px;")
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)

        self._rows_host = QWidget()
        self._rows_lay = QVBoxLayout(self._rows_host)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(6)
        self._rows_lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._rows_host)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(scroll, 1)

    # ── Public API ───────────────────────────────────────────────────────────

    def set_cell(self, cell) -> None:
        self._cell = cell
        self.refresh()

    def refresh(self) -> None:
        # Clear existing rows (keep the trailing stretch).
        while self._rows_lay.count() > 1:
            item = self._rows_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        overlays = self._cell.overlays() if self._cell is not None else []
        self._empty.setVisible(not overlays)

        for idx, ov in enumerate(overlays):
            self._rows_lay.insertWidget(self._rows_lay.count() - 1,
                                        self._make_row(idx, ov))

    # ── Row construction ───────────────────────────────────────────────────────

    def _make_row(self, idx: int, ov) -> QWidget:
        row = QWidget()
        lay = QVBoxLayout(row)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(4)

        chk = QCheckBox(ov.name)
        chk.setChecked(ov.visible)
        chk.toggled.connect(partial(self._on_visible, idx))
        top.addWidget(chk, 1)

        outline = QPushButton("Outline")
        outline.setCheckable(True)
        outline.setChecked(ov.mode == "outline")
        outline.setFixedWidth(64)
        outline.setToolTip("Toggle filled vs. contour-only rendering")
        outline.toggled.connect(partial(self._on_mode, idx))
        top.addWidget(outline)

        remove = QPushButton("×")
        remove.setFixedWidth(24)
        remove.setToolTip("Remove this overlay")
        remove.clicked.connect(partial(self._on_remove, idx))
        top.addWidget(remove)

        lay.addLayout(top)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(int(round(ov.opacity * 100)))
        slider.setToolTip("Overlay opacity")
        slider.valueChanged.connect(partial(self._on_opacity, idx))
        lay.addWidget(slider)

        return row

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_visible(self, idx: int, checked: bool) -> None:
        if self._cell is not None:
            self._cell.set_overlay_visible(idx, checked)

    def _on_mode(self, idx: int, checked: bool) -> None:
        if self._cell is not None:
            self._cell.set_overlay_mode(idx, "outline" if checked else "fill")

    def _on_opacity(self, idx: int, value: int) -> None:
        if self._cell is not None:
            self._cell.set_overlay_opacity(idx, value / 100.0)

    def _on_remove(self, idx: int) -> None:
        if self._cell is not None:
            self._cell.remove_overlay(idx)   # triggers overlays_changed → refresh
