"""Reports panel: browse and read text reports next to the images.

Opens a report source (reports.py: a folder of .txt / .rtf files, or CSV / TSV
tables with one report per row), lists the reports with a filter, and shows
the selected one formatted by its layout — sections, sub-headings, bullet
lists and 'key: value' lines. Read-only: nothing is written anywhere.
"""
from __future__ import annotations

import csv
import html
import os
from bisect import bisect_left

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QLineEdit, QTextBrowser, QSplitter, QFileDialog,
)

from . import drag_state
from .constants import DATA_ROOT
from .reports import ReportEntry, ReportError, load_report, parse_report, scan_reports

_ACCENT = "#89b4fa"     # section headings
_KEY = "#a6adc8"        # labels and field names
_DIM = "#6c7086"
_PRE = "white-space:pre-wrap;"      # keep tabs and runs of spaces of the source


def report_html(text: str, fields=()) -> str:
    """Report text (+ header fields of a table row) as Qt rich text."""
    esc = html.escape
    out = []
    rows = [(k, v) for k, v in fields if v]
    if rows:
        out.append('<table cellspacing="0" cellpadding="1">')
        out += [f'<tr><td style="color:{_DIM};">{esc(k)}&nbsp;&nbsp;&nbsp;</td>'
                f'<td>{esc(v)}</td></tr>' for k, v in rows]
        out.append("</table><hr>")

    blocks = parse_report(text)
    if not blocks:
        out.append(f'<p style="color:{_DIM};">(empty report)</p>')
    in_list = False
    for b, block in enumerate(blocks):
        for i, (kind, a, value) in enumerate(block):
            top = 10 if i == 0 and b > 0 else 0      # blank line of the source
            if in_list and kind != "bullet":
                out.append("</ul>")
                in_list = False
            if kind == "bullet":
                if not in_list:
                    out.append(f'<ul style="margin-top:{top}px; margin-bottom:0px; '
                               '-qt-list-indent:1;">')
                    in_list = True
                out.append(f'<li style="margin-bottom:2px; {_PRE}">{esc(a)}</li>')
            elif kind == "rule":
                out.append(("<hr>" if out else "")
                           + f'<p style="color:{_DIM}; font-weight:bold;">{esc(a)}</p>')
            elif kind == "section":
                out.append(f'<p style="margin-top:{16 if out else 0}px; margin-bottom:4px; '
                           f'color:{_ACCENT}; font-weight:bold;">{esc(a)}</p>')
            elif kind == "sub":
                out.append(f'<p style="margin-top:{top}px; margin-bottom:2px; '
                           f'font-weight:bold;">{esc(a)}</p>')
            elif kind == "label":
                out.append(f'<p style="margin-top:{top}px; margin-bottom:2px; '
                           f'color:{_KEY}; font-weight:bold;">{esc(a)}</p>')
            elif kind == "field":
                out.append(f'<p style="margin-top:{top}px; margin-bottom:2px; {_PRE}">'
                           f'<span style="color:{_KEY}; font-weight:bold;">{esc(a)}:</span> '
                           f'{esc(value)}</p>')
            else:
                out.append(f'<p style="margin-top:{top}px; margin-bottom:2px; {_PRE}">'
                           f'{esc(a)}</p>')
    if in_list:
        out.append("</ul>")
    return "".join(out)


class _ScanWorker(QThread):
    """Indexes a report source off the GUI thread (a CSV export can be
    hundreds of MB). Signals carry the worker so a superseded scan is ignored."""

    progress = pyqtSignal(object, str)           # worker, text
    scanned = pyqtSignal(object, list, list)     # worker, entries, notes

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            entries, notes = scan_reports(self._path,
                                          lambda text: self.progress.emit(self, text),
                                          lambda: self._cancelled)
        except Exception as exc:    # an exception escaping run() would abort the viewer
            entries, notes = [], [str(exc)]
        if not self._cancelled:
            self.scanned.emit(self, entries, notes)


class ReportPanel(QWidget):
    """Source buttons, filterable report list, report view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[ReportEntry] = []
        self._haystack: list[str] = []      # lower-cased label + header values per entry
        self._visible: list[int] = []       # rows passing the filter, ascending
        self._source = ""
        self._worker: _ScanWorker | None = None     # set while a scan is pending
        self._start_dir = DATA_ROOT
        self._build_ui()
        self.setAcceptDrops(True)       # a folder or file dragged from the study list

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        row = QHBoxLayout()
        self._open_dir_btn = QPushButton("Open folder…")
        self._open_dir_btn.setToolTip(
            "Every .txt / .rtf file of the folder is one report; every row of its\n"
            ".csv / .tsv files is one report. Subfolders are not searched.")
        self._open_dir_btn.clicked.connect(self._open_dir)
        self._open_file_btn = QPushButton("Open file…")
        self._open_file_btn.setToolTip("One report file, or one table with a report per row")
        self._open_file_btn.clicked.connect(self._open_file)
        row.addWidget(self._open_dir_btn)
        row.addWidget(self._open_file_btn)
        lay.addLayout(row)

        self._src_lbl = QLabel("No reports open — use the buttons, or drag a folder or file "
                               "here from the study list.")
        self._src_lbl.setObjectName("dockDim")
        self._src_lbl.setWordWrap(True)
        lay.addWidget(self._src_lbl)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter — ID, date, any header value")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(lambda _t: self._apply_filter())
        lay.addWidget(self._filter)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.currentRowChanged.connect(self._show)
        self._view = QTextBrowser()
        self._view.setObjectName("reportView")
        self._view.setOpenLinks(False)
        self._view.document().setIndentWidth(20)        # bullet indent; Qt's default is 40
        split = QSplitter(Qt.Vertical)
        split.addWidget(self._list)
        split.addWidget(self._view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        split.setChildrenCollapsible(False)
        lay.addWidget(split, 1)

        nav = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Prev")
        self._prev_btn.clicked.connect(lambda: self._step(-1))
        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(lambda: self._step(+1))
        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("dockDim")
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._next_btn)
        nav.addStretch(1)
        nav.addWidget(self._count_lbl)
        lay.addLayout(nav)

        self.setMinimumWidth(320)
        self._update_nav()

    # ── Public (MainWindow) ────────────────────────────────────────────────

    def set_start_dir(self, path: str) -> None:
        self._start_dir = path

    def open_source(self, path: str) -> None:
        """Index a folder or file in the background and list its reports."""
        self._stop_scan()
        self._set_entries([])
        self._source = path
        self._src_lbl.setText(f"Indexing {self._source_name()} …")
        self._src_lbl.setToolTip(path)
        self._worker = _ScanWorker(path)
        self._worker.progress.connect(self._on_progress)
        self._worker.scanned.connect(self._on_scanned)
        self._worker.start()

    def shutdown(self) -> None:
        """Stop a running scan (the window is closing)."""
        self._stop_scan()

    # ── Opening ────────────────────────────────────────────────────────────

    def _open_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select report folder", self._start_dir)
        if path:
            self._start_dir = path
            self.open_source(path)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select report file", self._start_dir,
            "Reports (*.txt *.rtf *.csv *.tsv);;All files (*)")
        if path:
            self._start_dir = os.path.dirname(path)
            self.open_source(path)

    def dragEnterEvent(self, event) -> None:
        if len(drag_state.decode_paths(event.mimeData())) == 1:
            event.acceptProposedAction()
        else:               # not from the study list, or several items at once
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = drag_state.decode_paths(event.mimeData())
        if len(paths) == 1:
            self.open_source(paths[0])
            event.acceptProposedAction()

    def _source_name(self) -> str:
        return os.path.basename(self._source.rstrip("/\\")) or self._source

    def _stop_scan(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait()     # the scan checks the flag per file and per row
            self._worker = None

    def _on_progress(self, worker, text: str) -> None:
        if worker is self._worker:
            self._src_lbl.setText(f"Indexing {text} …")

    def _on_scanned(self, worker, entries: list, notes: list) -> None:
        if worker is not self._worker:
            return
        worker.wait()           # run() is returning; never drop a thread that still runs
        self._worker = None
        name = self._source_name()
        if entries:
            text = f"{name} — {len(entries):,} report{'s' if len(entries) != 1 else ''}"
        else:
            text = (f"No reports found in {name} (.txt, .rtf, .csv, .tsv; "
                    "subfolders are not searched).")
        self._src_lbl.setText("\n".join([text, *notes]))
        self._set_entries(entries)

    def _set_entries(self, entries: list) -> None:
        self._entries = entries
        self._haystack = [" ".join((e.label, *(v for _, v in e.fields))).lower()
                          for e in entries]
        self._list.blockSignals(True)
        self._list.clear()
        self._list.addItems([e.label for e in entries])
        self._list.blockSignals(False)
        self._view.clear()
        self._apply_filter()

    # ── List, filter, navigation ───────────────────────────────────────────

    def _apply_filter(self) -> None:
        """Show the rows containing every word of the filter (case-insensitive);
        keep the current report if it still matches, else go to the first match."""
        terms = self._filter.text().lower().split()
        self._visible = [i for i, hay in enumerate(self._haystack)
                         if all(t in hay for t in terms)]
        shown = set(self._visible)
        for i in range(self._list.count()):
            self._list.setRowHidden(i, i not in shown)
        if self._list.currentRow() not in shown:
            self._list.setCurrentRow(self._visible[0] if self._visible else -1)
        self._update_nav()

    def _step(self, delta: int) -> None:
        k = bisect_left(self._visible, self._list.currentRow()) + delta
        if 0 <= k < len(self._visible):
            self._list.setCurrentRow(self._visible[k])

    def _show(self, row: int) -> None:
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            try:
                self._view.setHtml(report_html(load_report(entry), entry.fields))
            except (ReportError, OSError, csv.Error) as exc:
                self._view.setPlainText(f"This report cannot be shown.\n\n{exc}")
        else:
            self._view.clear()
        self._update_nav()

    def _update_nav(self) -> None:
        row = self._list.currentRow()
        k = bisect_left(self._visible, row)
        on_row = k < len(self._visible) and self._visible[k] == row
        self._prev_btn.setEnabled(on_row and k > 0)
        self._next_btn.setEnabled(on_row and k < len(self._visible) - 1)
        if not self._entries:
            self._count_lbl.setText("")
            return
        text = f"{k + 1 if on_row else 0:,} / {len(self._visible):,}"
        if len(self._visible) != len(self._entries):
            text += f" of {len(self._entries):,}"
        self._count_lbl.setText(text)
