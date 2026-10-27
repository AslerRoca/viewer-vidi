"""Workspace annotation dock: job list, drawing tools and export settings.

Drives the segment / crop-ROI workflow over a Workspace (workspace.py):
items load one at a time into the active panel, the dock's tool buttons
switch that panel's canvas into brush / polygon / rectangle mode, and
Save writes the products through annotation_export.py into
<workspace>/<output dir>/<format>/.
"""
from __future__ import annotations

import os
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QListWidget, QSpinBox, QCheckBox, QLineEdit,
    QFileDialog, QMessageBox, QInputDialog, QButtonGroup,
)

from .annotation_export import ExportInput, ExportOptions, export_item
from .constants import DATA_ROOT
from .data_model import SeriesType
from .tree_panel import _make_series_meta
from .workspace import (
    DEFAULT_OUT_DIR, FILES_SEP, STATUS_DELETED, STATUS_SAVED, Workspace,
    build_workspace, manifest_source, parse_list_file, probe_workspace,
    read_manifest, remove_manifest_row, scan_images, write_manifest_row,
)

# (button label, canvas mode, tooltip)
_TOOLS = (
    ("W/L",     "drag",  "Left-drag adjusts window/level; no annotation"),
    ("Brush",   "paint", "Paint the mask (tick Erase to remove)"),
    ("Polygon", "poly",  "Click vertices; double-click or Enter fills the polygon,\n"
                         "right-click drops the last vertex, Esc cancels"),
    ("Rect",    "rect",  "Drag the crop rectangle (ROI). Drag again to replace it"),
)
_ANNOTATION_MODES = ("paint", "poly", "rect")


class AnnotationDock(QDockWidget):
    """Right-hand dock: Workspace (items + navigation), Tools, Export."""

    def __init__(self, quad, parent=None):
        super().__init__("Workspace", parent)
        self.setObjectName("annotationDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._quad = quad
        self._ws: Workspace | None = None
        self._index: int = -1
        self._start_dir = DATA_ROOT
        self._build_ui()
        for cell in quad.cells():
            cell.canvas().annotation_changed.connect(self._refresh_stats)
            cell.load_failed.connect(lambda msg, c=cell: self._on_load_failed(c, msg))

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # ── Workspace: open buttons, summary, item list, navigation ────────
        ws_box = QGroupBox("Workspace")
        g = QVBoxLayout(ws_box)
        row = QHBoxLayout()
        self._open_dir_btn = QPushButton("Open directory…")
        self._open_dir_btn.setToolTip(
            "Image mode: every DICOM / NIfTI / image file below the directory is one item.\n"
            "If the directory holds a list file instead, list mode is offered.")
        self._open_dir_btn.clicked.connect(self._open_dir)
        self._open_list_btn = QPushButton("Open list…")
        self._open_list_btn.setToolTip(
            "List mode: a .txt/.lst/.csv/.tsv file with one image path per line\n"
            "(absolute, or relative to the list). Its directory becomes the workspace.")
        self._open_list_btn.clicked.connect(self._open_list)
        row.addWidget(self._open_dir_btn)
        row.addWidget(self._open_list_btn)
        g.addLayout(row)

        self._ws_lbl = QLabel("No workspace open.")
        self._ws_lbl.setObjectName("dockDim")
        self._ws_lbl.setWordWrap(True)
        g.addWidget(self._ws_lbl)

        self._list = QListWidget()
        self._list.setToolTip("Double-click an item to load it into the active panel")
        self._list.itemDoubleClicked.connect(
            lambda it: self._load_index(self._list.row(it)))
        g.addWidget(self._list, 1)

        nav = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Prev")
        self._prev_btn.clicked.connect(lambda: self._step(-1))
        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(lambda: self._step(+1))
        self._del_btn = QPushButton("Delete")
        self._del_btn.setObjectName("deleteBtn")
        self._del_btn.setToolTip(
            "Mark the current image as wrong (Delete key; also Backspace). The file is kept;\n"
            "the mark is recorded in manifest.csv. Press again to restore.")
        self._del_btn.clicked.connect(self.toggle_delete)
        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("dockDim")
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._next_btn)
        nav.addWidget(self._del_btn)
        nav.addStretch(1)
        nav.addWidget(self._count_lbl)
        g.addLayout(nav)

        # ── Tools ──────────────────────────────────────────────────────────
        tool_box = QGroupBox("Tools")
        t = QVBoxLayout(tool_box)
        row = QHBoxLayout()
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_btns: dict[str, QPushButton] = {}
        for label, mode, tip in _TOOLS:
            b = QPushButton(label)
            b.setObjectName("toolBtn")
            b.setCheckable(True)
            b.setToolTip(tip)
            self._tool_group.addButton(b)
            self._tool_btns[mode] = b
            row.addWidget(b)
        self._tool_btns["paint"].setChecked(True)
        self._tool_group.buttonClicked.connect(lambda _b: self._apply_tool())
        t.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Brush px"))
        self._brush_spin = QSpinBox()
        self._brush_spin.setRange(1, 500)
        self._brush_spin.setValue(20)
        self._brush_spin.setToolTip("Brush radius in image pixels")
        self._brush_spin.valueChanged.connect(lambda _v: self._apply_brush())
        self._erase_chk = QCheckBox("Erase")
        self._erase_chk.setToolTip("Brush and polygon remove from the mask instead of adding")
        self._erase_chk.toggled.connect(lambda _c: self._apply_brush())
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setToolTip("Undo the last stroke / polygon / clear (Ctrl+Z)")
        self._undo_btn.clicked.connect(self.undo)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear the mask and drop the rectangle")
        self._clear_btn.clicked.connect(self._clear)
        row.addWidget(self._brush_spin)
        row.addWidget(self._erase_chk)
        row.addStretch(1)
        row.addWidget(self._undo_btn)
        row.addWidget(self._clear_btn)
        t.addLayout(row)

        self._stats_lbl = QLabel("mask 0 px · no rectangle")
        self._stats_lbl.setObjectName("dockDim")
        t.addWidget(self._stats_lbl)

        # ── Export ─────────────────────────────────────────────────────────
        ex_box = QGroupBox("Export")
        e = QGridLayout(ex_box)
        e.setColumnStretch(1, 1)

        e.addWidget(QLabel("Formats"), 0, 0)
        self._fmt_chk = {"png": QCheckBox("PNG"), "jpeg": QCheckBox("JPEG"),
                         "nifti": QCheckBox("NIfTI")}
        self._fmt_chk["png"].setChecked(True)
        self._fmt_chk["png"].setToolTip("8-bit, current window/level applied; masks 0/255")
        self._fmt_chk["jpeg"].setToolTip("8-bit lossy (quality 95); masks 0/255 — PNG is safer for masks")
        self._fmt_chk["nifti"].setToolTip("Raw float32 values and pixel spacing; masks uint8 0/1 (.nii.gz)")
        fr = QHBoxLayout()
        for chk in self._fmt_chk.values():
            fr.addWidget(chk)
        fr.addStretch(1)
        e.addLayout(fr, 0, 1)

        e.addWidget(QLabel("Content"), 1, 0)
        self._mask_chk = QCheckBox("Mask")
        self._mask_chk.setChecked(True)
        self._mask_chk.setToolTip("<stem>_mask — the painted segmentation (plus <stem>_roi_mask inside a rectangle)")
        self._crop_chk = QCheckBox("Crop")
        self._crop_chk.setChecked(True)
        self._crop_chk.setToolTip("<stem>_roi — the rectangle cut out of the image")
        self._image_chk = QCheckBox("Original")
        self._image_chk.setToolTip("<stem>_image — the whole displayed image")
        cr = QHBoxLayout()
        cr.addWidget(self._mask_chk)
        cr.addWidget(self._crop_chk)
        cr.addWidget(self._image_chk)
        cr.addStretch(1)
        e.addLayout(cr, 1, 1)

        e.addWidget(QLabel("Output dir"), 2, 0)
        self._out_edit = QLineEdit(DEFAULT_OUT_DIR)
        self._out_edit.setToolTip("Created inside the workspace; one subdirectory per format")
        e.addWidget(self._out_edit, 2, 1)

        sr = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(lambda: self._save(advance=False))
        self._save_next_btn = QPushButton("Save && Next")
        self._save_next_btn.setToolTip("Save this item and load the next one (Ctrl+S)")
        self._save_next_btn.clicked.connect(self.save_and_next)
        sr.addStretch(1)
        sr.addWidget(self._save_btn)
        sr.addWidget(self._save_next_btn)
        e.addLayout(sr, 3, 0, 1, 2)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("dockDim")
        self._status_lbl.setWordWrap(True)
        e.addWidget(self._status_lbl, 4, 0, 1, 2)

        lay.addWidget(ws_box, 1)
        lay.addWidget(tool_box)
        lay.addWidget(ex_box)
        self.setWidget(body)
        self.setMinimumWidth(320)
        self._update_nav()

    # ── Public (MainWindow) ────────────────────────────────────────────────

    def workspace(self) -> Workspace | None:
        return self._ws

    def set_start_dir(self, path: str) -> None:
        self._start_dir = path

    def on_active_cell_changed(self, _cell) -> None:
        """Tools follow the active panel while the dock is open."""
        if self.isVisible():
            self._apply_tool()
            self._refresh_stats()

    def save_and_next(self) -> None:
        if self.isVisible():          # Ctrl+S means nothing while the dock is closed
            self._save(advance=True)

    def toggle_delete(self) -> None:
        """Mark the current image as wrong, or restore it (button / Delete key).

        The file stays on disk. A deleted mark is a manifest row with
        status 'deleted' (so it survives reopening and the other device);
        products of an earlier save of the item are removed. Restoring drops
        the row, so the item is pending again. The item stays on screen so a
        second press undoes the first."""
        ws = self._ws
        if not self.isVisible() or ws is None or not (0 <= self._index < len(ws.items)):
            return
        item = ws.items[self._index]
        ws.out_dir_name = self._out_name()
        try:
            if item.deleted:
                remove_manifest_row(ws.manifest_path, item.stem)
                item.deleted = False
                self._status_lbl.setText(f"Restored {item.stem} — pending again.")
            else:
                previous = read_manifest(ws.manifest_path).get(item.stem, {})
                removed = self._remove_products(ws, _split_files(previous.get("files", "")))
                write_manifest_row(ws.manifest_path, dict(
                    stem=item.stem, source=manifest_source(item.path, ws.root),
                    status=STATUS_DELETED,
                    saved_at=datetime.now().isoformat(timespec="seconds")))
                item.deleted = True
                item.done = False
                self._status_lbl.setText(
                    f"Marked {item.stem} as deleted (wrong picture)."
                    + (f" Removed {removed} earlier output file(s)." if removed else "")
                    + " Press Delete again to restore.")
        except Exception as exc:   # manifest not writable
            QMessageBox.warning(self, "Manifest not updated",
                                f"Could not record the change in manifest.csv:\n{exc}")
            return
        self._refresh_item(self._index)
        self._update_nav()

    def _remove_products(self, ws: Workspace, rel_files) -> int:
        """Delete product files of an item (paths relative to the output dir)."""
        n = 0
        base = os.path.normpath(ws.out_dir)
        for rel in rel_files:
            fp = os.path.normpath(os.path.join(base, rel))
            if fp.startswith(base + os.sep) and os.path.isfile(fp):
                try:
                    os.remove(fp)
                    n += 1
                except OSError:
                    pass
        return n

    def undo(self) -> None:
        if not self.isVisible():
            return
        if not self._canvas().undo_annotation():
            self._status_lbl.setText("Nothing to undo.")

    # Opening/closing the dock switches the annotation tools on/off so the
    # ordinary W/L drag is untouched when the dock is hidden.
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_tool()
        self._refresh_stats()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        for cell in self._quad.cells():
            if cell.canvas().wl_mode() in _ANNOTATION_MODES:
                cell.canvas().set_wl_mode("drag")

    # ── Workspace opening ──────────────────────────────────────────────────

    def _out_name(self) -> str:
        """A plain directory name inside the workspace — paths, '.' and '..'
        are rejected (they would write outside or make exports reappear as
        items) and fall back to the default."""
        name = self._out_edit.text().strip()
        if (not name or name in (".", "..") or "/" in name or "\\" in name
                or os.sep in name):
            if name:
                self._status_lbl.setText(
                    f"Output dir must be a plain folder name — using '{DEFAULT_OUT_DIR}'.")
            name = DEFAULT_OUT_DIR
            self._out_edit.setText(name)
        return name

    def _open_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select workspace directory",
                                                self._start_dir)
        if not path:
            return
        out_name = self._out_name()
        images, lists = probe_workspace(path, out_name)

        if images and lists:
            box = QMessageBox(self)
            box.setWindowTitle("Workspace mode")
            box.setText(f"{os.path.basename(path)} holds {len(images)} image files "
                        f"and {len(lists)} list file(s).\nWhich should define the job?")
            img_btn = box.addButton(f"Image mode ({len(images)} files)", QMessageBox.AcceptRole)
            lst_btn = box.addButton("List mode", QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec_()
            if box.clickedButton() is img_btn:
                self._set_workspace(build_workspace(path, "image", images, out_name))
            elif box.clickedButton() is lst_btn:
                self._open_list_in(path, lists, out_name)
            return
        if lists:
            self._open_list_in(path, lists, out_name)
            return
        if images:
            self._set_workspace(build_workspace(path, "image", images, out_name))
            return
        QMessageBox.information(
            self, "Empty workspace",
            "No DICOM / NIfTI / image files and no list files (.txt/.lst/.csv/.tsv) "
            f"with existing paths found in\n{path}")

    def _open_list_in(self, root: str, lists: list[str], out_name: str) -> None:
        if len(lists) == 1:
            lf = lists[0]
        else:
            names = [os.path.basename(p) for p in lists]
            name, ok = QInputDialog.getItem(self, "Choose list", "List file:", names, 0, False)
            if not ok:
                return
            lf = lists[names.index(name)]
        self._set_workspace(build_workspace(root, "list", parse_list_file(lf),
                                            out_name, list_file=lf))

    def _open_list(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Select image list", self._start_dir,
            "Lists (*.txt *.lst *.csv *.tsv);;All files (*)")
        if not f:
            return
        paths = parse_list_file(f)
        if not any(os.path.isfile(p) for p in paths):
            QMessageBox.warning(self, "Empty list", f"No existing image paths found in\n{f}")
            return
        self._set_workspace(build_workspace(os.path.dirname(os.path.abspath(f)), "list",
                                            paths, self._out_name(), list_file=f))

    def _set_workspace(self, ws: Workspace) -> None:
        self._ws = ws
        self._index = -1
        self._list.clear()
        for i, it in enumerate(ws.items):
            self._list.addItem(self._item_text(it))
            self._refresh_item(i)
        src = (f"list {os.path.basename(ws.list_file)}" if ws.mode == "list"
               else "image directory")
        txt = (f"{ws.root}\n{ws.mode.upper()} mode · {src} · "
               f"{len(ws.items)} items, {ws.n_done} done")
        if ws.missing:
            txt += f" · {len(ws.missing)} listed path(s) not found"
        if ws.manifest_warning:
            txt += f"\n⚠ {ws.manifest_warning}"
        if (ws.mode == "image" and os.path.isdir(ws.out_dir)
                and not os.path.isfile(ws.manifest_path) and scan_images(ws.out_dir)):
            txt += (f"\n⚠ '{ws.out_dir_name}' is the output dir — the images inside it "
                    "are not job items; pick another Output dir name to annotate them")
        self._ws_lbl.setText(txt)
        self._ws_lbl.setToolTip("\n".join(ws.missing) if ws.missing else ws.root)
        self._status_lbl.setText("")
        self._update_nav()
        if ws.items:
            first_pending = next((i for i, it in enumerate(ws.items)
                                  if not it.done and not it.deleted), 0)
            self._load_index(first_pending)

    @staticmethod
    def _item_text(it) -> str:
        mark = "⊘ " if it.deleted else ("✗ " if it.error else ("✓ " if it.done else "○ "))
        return mark + it.stem

    def _refresh_item(self, i: int) -> None:
        """Sync one list row (text + strike-through for deleted) with its Item."""
        it = self._ws.items[i]
        row = self._list.item(i)
        row.setText(self._item_text(it))
        f = row.font()
        f.setStrikeOut(it.deleted)
        row.setFont(f)

    # ── Navigation ─────────────────────────────────────────────────────────

    def _load_index(self, i: int) -> None:
        ws = self._ws
        if ws is None or not (0 <= i < len(ws.items)):
            return
        item = ws.items[i]
        self._index = i               # always move, so Next/Prev never get stuck
        self._list.setCurrentRow(i)
        meta = _make_series_meta(item.path)
        if meta is None:
            item.error = "not a readable image / series"
            self._refresh_item(i)
            self._status_lbl.setText(f"Cannot open {item.path}")
            self._update_nav()
            return
        item.error = ""
        self._refresh_item(i)
        cell = self._quad.active_cell()
        cell.load_meta(meta)          # resets the canvas mode → re-apply the tool
        self._apply_tool(cell)
        self._update_nav()
        self._refresh_stats()

    def _on_load_failed(self, cell, msg: str) -> None:
        """A panel's loader reported an error; flag the item it was showing."""
        ws = self._ws
        if ws is None or cell is not self._quad.active_cell() or self._index < 0:
            return
        item = ws.items[self._index]
        item.error = msg
        self._refresh_item(self._index)
        self._status_lbl.setText(f"Load failed: {msg}")

    def _step(self, delta: int) -> None:
        if self._ws is not None:
            self._load_index(self._index + delta)

    def _update_nav(self) -> None:
        ws = self._ws
        n = len(ws.items) if ws else 0
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(0 <= self._index < n - 1)
        current = ws.items[self._index] if ws and 0 <= self._index < n else None
        self._del_btn.setEnabled(current is not None)
        self._del_btn.setText("Restore" if current is not None and current.deleted else "Delete")
        self._del_btn.setProperty("restore", bool(current is not None and current.deleted))
        self._del_btn.style().unpolish(self._del_btn)
        self._del_btn.style().polish(self._del_btn)
        if ws:
            txt = f"{self._index + 1}/{n} · {ws.n_done} done"
            if ws.n_deleted:
                txt += f" · {ws.n_deleted} deleted"
            self._count_lbl.setText(txt)
        else:
            self._count_lbl.setText("")

    # ── Tools ──────────────────────────────────────────────────────────────

    def _canvas(self):
        return self._quad.active_cell().canvas()

    def _current_tool(self) -> str:
        return next(m for m, b in self._tool_btns.items() if b.isChecked())

    def _apply_tool(self, cell=None) -> None:
        cell = cell or self._quad.active_cell()
        canvas = cell.canvas()
        if self._current_tool() != "drag":
            cell.reset_mode_buttons()   # the panel's ROI/TC toggles no longer own the mode
        canvas.set_wl_mode(self._current_tool())
        canvas.set_brush(self._brush_spin.value(), self._erase_chk.isChecked())

    def _apply_brush(self) -> None:
        self._canvas().set_brush(self._brush_spin.value(), self._erase_chk.isChecked())

    def _clear(self) -> None:
        self._canvas().clear_annotations()

    def _refresh_stats(self) -> None:
        canvas = self._canvas()
        n = canvas.mask_pixels()
        rect = canvas.crop_rect()
        rs = (f"rect ({rect[0]}, {rect[1]}) → ({rect[2]}, {rect[3]}), "
              f"{rect[2] - rect[0]}×{rect[3] - rect[1]} px") if rect else "no rectangle"
        self._stats_lbl.setText(f"mask {n:,} px · {rs}")

    # ── Saving ─────────────────────────────────────────────────────────────

    def _save(self, advance: bool) -> None:
        ws = self._ws
        if ws is None or self._index < 0:
            self._status_lbl.setText("Open a workspace first.")
            return
        item = ws.items[self._index]
        cell = self._quad.active_cell()
        canvas = cell.canvas()
        sd = cell.series_data()
        pixels = canvas.displayed_pixels()
        if cell.load_error_text():
            self._status_lbl.setText(f"Cannot save: load failed ({cell.load_error_text()}).")
            return
        if sd is None or pixels is None:
            self._status_lbl.setText("Image still loading — try again in a moment."
                                     if cell.is_loading() else
                                     "No image in the active panel.")
            return
        if os.path.realpath(sd.meta.series_dir) != os.path.realpath(item.path):
            QMessageBox.warning(
                self, "Panel mismatch",
                f"The active panel shows\n{sd.meta.series_dir}\n\nbut the current item is\n"
                f"{item.path}\n\nDouble-click the item in the list to load it, then save.")
            return
        if (sd.series_type in (SeriesType.S2D, SeriesType.S2DT, SeriesType.MULTI)
                and pixels.shape != (sd.rows, sd.cols)):
            self._status_lbl.setText("Panel is still updating — try again in a moment.")
            return
        formats = tuple(f for f, chk in self._fmt_chk.items() if chk.isChecked())
        if not formats:
            self._status_lbl.setText("Tick at least one format (PNG / JPEG / NIfTI).")
            return

        ws.out_dir_name = self._out_name()
        wc, ww = canvas.wl()
        rect = canvas.crop_rect()
        inp = ExportInput(stem=item.stem, pixels=pixels, wc=wc, ww=ww,
                          invert=canvas.invert(), mask=canvas.mask(), rect=rect,
                          spacing=cell.display_spacing())
        opts = ExportOptions(formats=formats,
                             save_mask=self._mask_chk.isChecked(),
                             save_crop=self._crop_chk.isChecked(),
                             save_image=self._image_chk.isChecked())
        previous = read_manifest(ws.manifest_path).get(item.stem, {})
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            written = export_item(ws.out_dir, inp, opts)
        except Exception as exc:   # disk full, permissions, missing writer …
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        if not written:
            self._status_lbl.setText(
                "Nothing to save: draw a mask or a rectangle, or tick Original.")
            return

        # Products of an earlier save of this item that were not rewritten
        # would contradict the new manifest row — remove them.
        stale = [f for f in _split_files(previous.get("files", "")) if f not in written]
        for rel in stale:
            fp = os.path.normpath(os.path.join(ws.out_dir, rel))
            if fp.startswith(os.path.normpath(ws.out_dir) + os.sep) and os.path.isfile(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass

        x0, y0, x1, y1 = rect if rect else ("", "", "", "")
        try:
            backup = write_manifest_row(ws.manifest_path, dict(
                stem=item.stem, source=manifest_source(item.path, ws.root),
                status=STATUS_SAVED,
                saved_at=datetime.now().isoformat(timespec="seconds"),
                view=cell.display_view(), mask_pixels=canvas.mask_pixels(),
                x0=x0, y0=y0, x1=x1, y1=y1,
                formats=" ".join(formats), files=FILES_SEP.join(written)))
        except Exception as exc:   # read-only dir, manifest.csv is a folder, …
            QMessageBox.warning(
                self, "Manifest not updated",
                f"{len(written)} file(s) were written to {ws.out_dir_name}/, but "
                f"manifest.csv could not be updated:\n{exc}\n\nThe item stays pending.")
            return
        item.done = True
        item.deleted = False          # saving a deleted item restores it
        self._refresh_item(self._index)
        note = f" · old manifest moved to {os.path.basename(backup)}" if backup else ""
        self._status_lbl.setText(
            f"Saved {len(written)} file(s) → {ws.out_dir_name}/ ({', '.join(formats)})"
            + (f", removed {len(stale)} stale" if stale else "") + note)
        self._update_nav()
        if advance and self._index < len(ws.items) - 1:
            self._load_index(self._index + 1)


def _split_files(value: str) -> list[str]:
    """Entries of a manifest 'files' cell (';'-separated; older rows used spaces)."""
    if not value:
        return []
    sep = FILES_SEP if FILES_SEP in value else " "
    return [v for v in value.split(sep) if v]
