"""2×2 grid of ViewCell widgets with fullscreen toggle."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter

from .view_cell import ViewCell


class QuadView(QWidget):
    """Four-panel DICOM viewer with active-cell tracking and fullscreen toggle.

    Layout (nested QSplitters):
        QuadView
          └── _splitter_v (Vertical)
                ├── _splitter_top (Horizontal)  ← cells[0], cells[1]
                └── _splitter_bot (Horizontal)  ← cells[2], cells[3]

    Fullscreen: hide 3 cells + collapse their splitter halves so the selected
    cell fills the entire QuadView area.
    """

    active_cell_changed = pyqtSignal(object)    # ViewCell
    wl_changed          = pyqtSignal(float, float)
    pixel_hovered       = pyqtSignal(int, int, float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._cells: list[ViewCell] = [ViewCell(i) for i in range(4)]
        self._active:     ViewCell  = self._cells[0]
        self._fs_cell:    ViewCell | None = None  # fullscreen cell (None = grid view)
        self._saved_v_sizes:   list[int] = []
        self._saved_top_sizes: list[int] = []
        self._saved_bot_sizes: list[int] = []

        self._splitter_top = QSplitter(Qt.Horizontal)
        self._splitter_top.setObjectName("quadSplitterH")
        self._splitter_top.setChildrenCollapsible(False)
        self._splitter_top.addWidget(self._cells[0])
        self._splitter_top.addWidget(self._cells[1])

        self._splitter_bot = QSplitter(Qt.Horizontal)
        self._splitter_bot.setObjectName("quadSplitterH")
        self._splitter_bot.setChildrenCollapsible(False)
        self._splitter_bot.addWidget(self._cells[2])
        self._splitter_bot.addWidget(self._cells[3])

        self._splitter_v = QSplitter(Qt.Vertical)
        self._splitter_v.setObjectName("quadSplitterV")
        self._splitter_v.setChildrenCollapsible(False)
        self._splitter_v.addWidget(self._splitter_top)
        self._splitter_v.addWidget(self._splitter_bot)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._splitter_v)

        for cell in self._cells:
            cell.activated.connect(lambda c=cell: self._on_activated(c))
            cell.wl_changed.connect(self._on_cell_wl)
            cell.pixel_hovered.connect(self.pixel_hovered)
            cell.double_clicked.connect(lambda c=cell: self._toggle_fullscreen(c))

        self._set_active(self._cells[0])

    # ── Public API ─────────────────────────────────────────────────────────

    def active_cell(self) -> ViewCell:
        return self._active

    def cell_at(self, idx: int) -> ViewCell:
        return self._cells[idx]

    def set_wl(self, wc: float, ww: float) -> None:
        self._active.set_wl(wc, ww)

    def set_colormap(self, name: str) -> None:
        for c in self._cells:
            c.set_colormap(name)

    def reset_wl(self) -> None:
        self._active.reset_wl()

    def cancel_all(self) -> None:
        for c in self._cells:
            c._loader.cancel()

    def is_fullscreen(self) -> bool:
        return self._fs_cell is not None

    # ── Active cell ────────────────────────────────────────────────────────

    def _on_activated(self, cell: ViewCell) -> None:
        if cell is not self._active:
            self._set_active(cell)

    def _set_active(self, cell: ViewCell) -> None:
        if self._active is not cell:
            self._active.set_active(False)
        self._active = cell
        cell.set_active(True)
        self.active_cell_changed.emit(cell)
        wc, ww = cell.current_wl()
        self.wl_changed.emit(wc, ww)

    def _on_cell_wl(self, wc: float, ww: float) -> None:
        if self.sender() is self._active:
            self.wl_changed.emit(wc, ww)

    # ── Fullscreen toggle ──────────────────────────────────────────────────

    def _toggle_fullscreen(self, cell: ViewCell) -> None:
        if self._fs_cell is None:
            self._enter_fullscreen(cell)
        else:
            self._exit_fullscreen()

    def _enter_fullscreen(self, cell: ViewCell) -> None:
        self._fs_cell = cell
        # Save current splitter sizes so we can restore them
        self._saved_v_sizes   = self._splitter_v.sizes()
        self._saved_top_sizes = self._splitter_top.sizes()
        self._saved_bot_sizes = self._splitter_bot.sizes()

        row = 0 if cell in (self._cells[0], self._cells[1]) else 1
        col = 0 if cell in (self._cells[0], self._cells[2]) else 1

        # Hide all cells that are not the target
        for c in self._cells:
            if c is not cell:
                c.setVisible(False)

        # Collapse the opposite row in the vertical splitter
        total_v = sum(self._splitter_v.sizes())
        self._splitter_v.setSizes(
            [total_v, 0] if row == 0 else [0, total_v]
        )

        # Collapse the opposite column in the relevant horizontal splitter
        target_h = self._splitter_top if row == 0 else self._splitter_bot
        total_h = sum(target_h.sizes())
        target_h.setSizes(
            [total_h, 0] if col == 0 else [0, total_h]
        )

        self._set_active(cell)

    def _exit_fullscreen(self) -> None:
        for c in self._cells:
            c.setVisible(True)

        # Restore saved sizes (or equal split if none saved)
        if self._saved_v_sizes:
            self._splitter_v.setSizes(self._saved_v_sizes)
            self._splitter_top.setSizes(self._saved_top_sizes)
            self._splitter_bot.setSizes(self._saved_bot_sizes)
        else:
            h = max(1, self._splitter_v.height() // 2)
            w_t = max(1, self._splitter_top.width() // 2)
            w_b = max(1, self._splitter_bot.width() // 2)
            self._splitter_v.setSizes([h, h])
            self._splitter_top.setSizes([w_t, w_t])
            self._splitter_bot.setSizes([w_b, w_b])

        self._fs_cell = None
