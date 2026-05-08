"""Filesystem browser — VS Code-style hybrid tree (QFileSystemModel + smart proxy)."""
from __future__ import annotations

import os
import queue as _queue
import shutil
import threading as _threading
import concurrent.futures as _cf

from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QMimeData,
    QSortFilterProxyModel, QDir, QModelIndex,
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QSplitter,
    QPushButton, QLineEdit, QFileDialog, QMenu, QMessageBox,
    QFileSystemModel, QAbstractItemView,
)

from .data_model import SeriesMeta, GroupedSeriesMeta, SeriesType
from .constants import DATA_ROOT, BADGE_COLORS
from . import drag_state

_NIFTI_EXTS = (".nii.gz", ".nii")
_IMAGE_EXTS  = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"})


# ── Series-meta helpers ────────────────────────────────────────────────────────

def _make_series_meta(path: str) -> "SeriesMeta | GroupedSeriesMeta | None":
    if os.path.isfile(path):
        nl = path.lower()
        if any(nl.endswith(e) for e in _NIFTI_EXTS):
            return SeriesMeta(
                study_dir=os.path.dirname(path), series_dir=path,
                series_name=os.path.basename(path),
                study_name=os.path.basename(os.path.dirname(path)),
                n_files=1, file_format="nifti",
            )
        return None

    if not os.path.isdir(path):
        return None

    try:
        files = os.listdir(path)
    except OSError:
        return None

    dcm = [f for f in files if f.lower().endswith(".dcm")]
    if dcm:
        return SeriesMeta(
            study_dir=os.path.dirname(path), series_dir=path,
            series_name=os.path.basename(path),
            study_name=os.path.basename(os.path.dirname(path)),
            n_files=len(dcm), file_format="dicom",
        )

    nii = sorted(f for f in files if any(f.lower().endswith(e) for e in _NIFTI_EXTS))
    if nii:
        fp = os.path.join(path, nii[0])
        return SeriesMeta(
            study_dir=path, series_dir=fp, series_name=nii[0],
            study_name=os.path.basename(path), n_files=1, file_format="nifti",
        )

    imgs = [f for f in files if os.path.splitext(f.lower())[1] in _IMAGE_EXTS]
    if imgs:
        return SeriesMeta(
            study_dir=os.path.dirname(path), series_dir=path,
            series_name=os.path.basename(path),
            study_name=os.path.basename(os.path.dirname(path)),
            n_files=len(imgs), file_format="image",
        )

    return _make_grouped_meta(path)


def _make_grouped_meta(study_dir: str) -> "GroupedSeriesMeta | None":
    try:
        subdirs = sorted(
            d for d in os.listdir(study_dir)
            if os.path.isdir(os.path.join(study_dir, d))
        )
    except OSError:
        return None

    series_list = []
    study_name = os.path.basename(study_dir)
    for name in subdirs:
        sp = os.path.join(study_dir, name)
        try:
            n = sum(1 for f in os.listdir(sp) if f.lower().endswith(".dcm"))
        except OSError:
            n = 0
        if n:
            series_list.append(SeriesMeta(
                study_dir=study_dir,
                series_dir=sp,
                series_name=name,
                study_name=study_name,
                n_files=n,
                file_format="dicom",
            ))

    if not series_list:
        return None

    return GroupedSeriesMeta(
        study_dir=study_dir,
        study_name=study_name,
        group_name=study_name,
        series_dirs=series_list,
        n_timepoints=len(series_list),
    )


def _make_grouped_from_paths(paths: list) -> "GroupedSeriesMeta | None":
    series_list, study_dir = [], None
    for path in sorted(paths):
        if not os.path.isdir(path):
            continue
        try:
            n = sum(1 for f in os.listdir(path) if f.lower().endswith(".dcm"))
        except OSError:
            n = 0
        if n == 0:
            continue
        if study_dir is None:
            study_dir = os.path.dirname(path)
        series_list.append(SeriesMeta(
            study_dir=study_dir,
            series_dir=path,
            series_name=os.path.basename(path),
            study_name=os.path.basename(study_dir),
            n_files=n,
            file_format="dicom",
        ))

    if not series_list or study_dir is None:
        return None

    label = (f"{series_list[0].series_name} … {series_list[-1].series_name}"
             if len(series_list) > 1 else series_list[0].series_name)
    return GroupedSeriesMeta(
        study_dir=study_dir,
        study_name=os.path.basename(study_dir),
        group_name=label,
        series_dirs=series_list,
        n_timepoints=len(series_list),
    )


# ── Background directory classifier ───────────────────────────────────────────
#
# hasChildren / canFetchMore must never block the UI thread.
# We classify dirs in a small thread pool and push results into a thread-safe
# queue.  StudyTreeWidget drains that queue every 80 ms and calls
# invalidateFilter() so the proxy re-evaluates newly classified dirs.
# directoryLoaded pre-submits children of any dir QFileSystemModel just fetched.

_dir_type_cache : dict[str, str] = {}       # path → "dicom" | "image" | "dir"
_classify_lock   = _threading.Lock()
_classifying     : set[str] = set()
_result_queue    : "_queue.Queue[str]" = _queue.Queue()
_executor        = _cf.ThreadPoolExecutor(max_workers=3,
                                          thread_name_prefix="vidi-classify")


def _classify_dir_io(path: str) -> str:
    """Classify *path* by scanning its contents. Safe to call from any thread."""
    try:
        has_img = has_subdir = False
        with os.scandir(path) as it:
            for entry in it:
                nl = entry.name.lower()
                if nl.endswith(".dcm"):
                    return "dicom"
                if os.path.splitext(nl)[1] in _IMAGE_EXTS:
                    has_img = True
                elif entry.is_dir(follow_symlinks=False):
                    has_subdir = True
        return "image" if (has_img and not has_subdir) else "dir"
    except OSError:
        return "dir"


def _submit_classify(path: str) -> None:
    """Enqueue *path* for background classification if not already pending."""
    if not path or not os.path.isdir(path):
        return
    with _classify_lock:
        if path in _classifying or path in _dir_type_cache:
            return
        _classifying.add(path)

    def _worker():
        result = _classify_dir_io(path)
        with _classify_lock:
            _dir_type_cache[path] = result
            _classifying.discard(path)
        _result_queue.put(path)

    _executor.submit(_worker)


# ── Smart proxy ────────────────────────────────────────────────────────────────

class _SmartProxy(QSortFilterProxyModel):
    """Hides individual .dcm / image files; makes series leaf-dirs non-expandable.

    hasChildren and canFetchMore are cache-only — they never do I/O.
    Classification runs in the background pool; the tree self-corrects when
    invalidateFilter() is called after results arrive.
    """

    def filterAcceptsRow(self, src_row: int, src_parent) -> bool:
        idx  = self.sourceModel().index(src_row, 0, src_parent)
        path = self.sourceModel().filePath(idx)

        if path.lower().endswith(".dcm"):
            return False
        if os.path.isfile(path) and os.path.splitext(path.lower())[1] in _IMAGE_EXTS:
            return False

        rx = self.filterRegExp()
        if rx.isEmpty():
            return True
        name = self.sourceModel().data(idx) or ""
        if rx.indexIn(name) >= 0:
            return True
        return os.path.isdir(path)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        f = super().flags(index)
        if index.isValid():
            src  = self.mapToSource(index)
            path = self.sourceModel().filePath(src)
            if os.path.isdir(path):
                f |= Qt.ItemIsDragEnabled
        return f

    # ── Drag MIME ─────────────────────────────────────────────────────────
    # Qt calls mimeData() inside its own startDrag() → exec() chain.
    # We build the payload here so there is no second QDrag.exec_() call
    # (which would collide with Qt's active drag and cause the
    # "QDragManager::drag in possibly invalid state" warning).

    def mimeTypes(self):
        return [drag_state.MIME_TYPE]

    def supportedDragActions(self):
        return Qt.CopyAction

    def mimeData(self, indexes):
        paths, seen = [], set()
        for idx in indexes:
            if idx.column() != 0:
                continue
            src  = self.mapToSource(idx)
            path = self.sourceModel().filePath(src)
            if path and path not in seen:
                seen.add(path)
                paths.append(path)
        if not paths:
            return None
        meta = (_make_grouped_from_paths(paths) if len(paths) > 1 else None) \
               or _make_series_meta(paths[0])
        if meta is None:
            return None
        drag_state.set_payload(meta)
        mime = QMimeData()
        mime.setData(drag_state.MIME_TYPE, b"1")
        return mime

    def _is_leaf_dir(self, path: str) -> bool:
        return _dir_type_cache.get(path) in ("dicom", "image")

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return super().hasChildren(parent)
        src  = self.mapToSource(parent)
        path = self.sourceModel().filePath(src)
        if self._is_leaf_dir(path):
            return False
        return super().hasChildren(parent)

    def canFetchMore(self, parent: QModelIndex) -> bool:
        if not parent.isValid():
            return super().canFetchMore(parent)
        src  = self.mapToSource(parent)
        path = self.sourceModel().filePath(src)
        if self._is_leaf_dir(path):
            return False
        return super().canFetchMore(parent)


# ── Tree view ─────────────────────────────────────────────────────────────────

class _FileTree(QTreeView):
    """QTreeView that delegates drag entirely to Qt.

    · setDragEnabled(True) activates Qt's built-in delayed-selection logic:
      clicking an already-selected item inside a multi-selection does NOT clear
      the selection until mouse-release (pressedAlreadySelected mechanism).
    · _SmartProxy.mimeData() builds our payload and returns our MIME type so
      ViewCell.dragEnterEvent accepts the drop.
    · startDrag() override only clears the drag_state payload after exec()
      in case the drag was cancelled without a drop.
    """

    def __init__(self, fs_model: QFileSystemModel, proxy: _SmartProxy, parent=None):
        super().__init__(parent)
        self._fs    = fs_model
        self._proxy = proxy
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)

    def startDrag(self, supported_actions: Qt.DropActions) -> None:
        super().startDrag(supported_actions)   # builds MIME via mimeData(), runs exec()
        drag_state.clear_payload()             # no-op if drop succeeded; cleans up if cancelled


# ── Main widget ───────────────────────────────────────────────────────────────

class StudyTreeWidget(QWidget):
    """Left-panel VS Code-style filesystem browser with background classification."""

    series_selected = pyqtSignal(object)   # SeriesMeta | GroupedSeriesMeta
    root_changed    = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_root = DATA_ROOT

        # ── Filesystem model ───────────────────────────────────────────────
        self._fs = QFileSystemModel()
        self._fs.setRootPath(self._data_root)
        self._fs.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self._proxy = _SmartProxy(self)
        self._proxy.setSourceModel(self._fs)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(0)

        # ── Tree view ──────────────────────────────────────────────────────
        self._tree = _FileTree(self._fs, self._proxy, self)
        self._tree.setModel(self._proxy)
        self._set_root(self._data_root)
        for col in range(1, self._fs.columnCount()):
            self._tree.hideColumn(col)
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setAnimated(False)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tree.doubleClicked.connect(self._on_double_clicked)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

        # ── Background classification refresh ──────────────────────────────
        # QFileSystemModel emits directoryLoaded when it fetches a dir's
        # children.  We submit background classification for those children so
        # expand-triangles disappear without blocking the UI thread.
        self._fs.directoryLoaded.connect(self._on_dir_loaded)

        self._classify_timer = QTimer(self)
        self._classify_timer.setInterval(80)
        self._classify_timer.timeout.connect(self._drain_classify_results)
        self._classify_timer.start()

        # ── Controls ───────────────────────────────────────────────────────
        self._dir_btn = QPushButton("📁  Change directory")
        self._dir_btn.setStyleSheet(
            "color:#6c7086; font-size:11px; text-align:left;"
            "background:transparent; border:none; padding:2px 4px;"
        )
        self._dir_btn.setToolTip(self._data_root)
        self._dir_btn.clicked.connect(self._pick_directory)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter…")
        self._search.textChanged.connect(
            lambda t: self._proxy.setFilterFixedString(t.strip())
        )

        # ── Embedded TC panel ──────────────────────────────────────────────
        from .time_course_window import TimeCourseWindow
        self._tc_panel = TimeCourseWindow(parent=self, embedded=True)
        self._tc_panel.setVisible(False)
        self._tc_panel.setMinimumHeight(100)

        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(self._tc_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setChildrenCollapsible(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._dir_btn)
        lay.addWidget(self._search)
        lay.addWidget(self._splitter, 1)

    @property
    def tc_panel(self):
        return self._tc_panel

    # ── Background classifier callbacks ────────────────────────────────────

    def _on_dir_loaded(self, path: str) -> None:
        """QFileSystemModel just fetched *path*'s children — pre-classify them."""
        src_idx = self._fs.index(path)
        n = self._fs.rowCount(src_idx)
        for row in range(n):
            child = self._fs.index(row, 0, src_idx)
            if self._fs.isDir(child):
                _submit_classify(self._fs.filePath(child))

    def _drain_classify_results(self) -> None:
        """Drain result queue; call invalidateFilter if anything changed."""
        changed = False
        while not _result_queue.empty():
            try:
                _result_queue.get_nowait()
                changed = True
            except _queue.Empty:
                break
        if changed:
            self._proxy.invalidateFilter()

    # ── Internal helpers ───────────────────────────────────────────────────

    def _set_root(self, path: str) -> None:
        src_idx = self._fs.index(path)
        self._tree.setRootIndex(self._proxy.mapFromSource(src_idx))

    def _path_from_proxy(self, proxy_idx) -> str:
        return self._fs.filePath(self._proxy.mapToSource(proxy_idx))

    # ── Compatibility (called by MainWindow after load) ────────────────────

    def update_series_type(self, series_path: str, stype: SeriesType) -> None:
        pass   # QFileSystemModel manages its own display

    # ── Directory picker ───────────────────────────────────────────────────

    def _pick_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select root directory", self._data_root
        )
        if path and path != self._data_root:
            self._data_root = path
            self._dir_btn.setToolTip(path)
            self._fs.setRootPath(path)
            self._set_root(path)
            self.root_changed.emit(path)

    # ── Double-click to load ───────────────────────────────────────────────

    def _on_double_clicked(self, proxy_idx) -> None:
        path = self._path_from_proxy(proxy_idx)
        meta = _make_series_meta(path)
        if meta is not None:
            self.series_selected.emit(meta)

    # ── Context menu ───────────────────────────────────────────────────────

    def _show_context_menu(self, pos: QPoint) -> None:
        proxy_idx = self._tree.indexAt(pos)
        if not proxy_idx.isValid():
            return
        path = self._path_from_proxy(proxy_idx)

        menu     = QMenu(self)
        act_load = menu.addAction("Load")
        menu.addSeparator()
        act_copy = menu.addAction("Copy to…")
        act_move = menu.addAction("Move to…")
        menu.addSeparator()
        act_del  = menu.addAction("Delete")

        action = menu.exec_(self._tree.viewport().mapToGlobal(pos))
        if action == act_load:
            meta = _make_series_meta(path)
            if meta:
                self.series_selected.emit(meta)
        elif action == act_del:
            self._op_delete(path)
        elif action == act_move:
            self._op_move(path)
        elif action == act_copy:
            self._op_copy(path)

    def _op_delete(self, path: str) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Permanently delete:\n{path}\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))

    def _op_move(self, path: str) -> None:
        dest = QFileDialog.getExistingDirectory(
            self, "Move to…", os.path.dirname(path)
        )
        if not dest:
            return
        try:
            shutil.move(path, dest)
        except Exception as exc:
            QMessageBox.critical(self, "Move Failed", str(exc))

    def _op_copy(self, path: str) -> None:
        dest = QFileDialog.getExistingDirectory(
            self, "Copy to…", os.path.dirname(path)
        )
        if not dest:
            return
        try:
            name   = os.path.basename(path)
            target = os.path.join(dest, name)
            shutil.copytree(path, target) if os.path.isdir(path) else shutil.copy2(path, target)
        except Exception as exc:
            QMessageBox.critical(self, "Copy Failed", str(exc))
