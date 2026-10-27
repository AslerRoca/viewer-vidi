"""Shared headless harness for viewer-vidi stability tests.

Usage (in your own script):
    import sys; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
    import harness as H
    app, win = H.boot()
    dock, quad = win._dock, win._quad
    cell = quad.active_cell(); canvas = cell.canvas()
    H.load_file(app, cell, "/path/to/file.dcm")        # loads + waits for pixels
    H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.4))
Everything runs offscreen; never touches the real display. The harness only
reads the repo (/media/zsk/ressd/research/viewer-vidi) — never write there.
"""
import os, sys, time, types, importlib.util
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC      = "/media/zsk/ressd/research/viewer-vidi"
FIXTURES = "/media/zsk/ressd/research/alldata_backup/dicom/original"   # 18 CR DICOMs, 2044x1514
PYTHON   = os.path.expanduser("~/miniconda3/envs/viewer_vidi/bin/python")


def register_package():
    """Expose the dash-named project dir as importable package 'viewer_vidi'."""
    if "viewer_vidi" in sys.modules:
        return sys.modules["viewer_vidi"]
    pkg = types.ModuleType("viewer_vidi")
    pkg.__path__ = [SRC]; pkg.__package__ = "viewer_vidi"
    pkg.__file__ = os.path.join(SRC, "__init__.py")
    sys.modules["viewer_vidi"] = pkg
    spec = importlib.util.spec_from_file_location("viewer_vidi", pkg.__file__)
    spec.loader.exec_module(pkg)
    return pkg


def boot(size=(1400, 900)):
    """(app, win). Handles: win._dock (AnnotationDock), win._quad (QuadView),
    win._tree (StudyTreeWidget), win._ws_btn (Workspace toggle), win._invert_btn."""
    register_package()
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from viewer_vidi.main_window import MainWindow
    win = MainWindow(); win.resize(*size); win.show(); app.processEvents()
    return app, win


def pump(app, ms=50):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents(); time.sleep(0.005)


def wait_loaded(app, cell, timeout=30.0):
    """True once the cell has SeriesData and pixels on its canvas."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cell.series_data() is not None and cell.canvas().displayed_pixels() is not None:
            return True
        time.sleep(0.01)
    return False


def load_file(app, cell, path, timeout=30.0):
    """Load one file/dir into a cell the way the dock does; returns wait_loaded()."""
    from viewer_vidi.tree_panel import _make_series_meta
    meta = _make_series_meta(path)
    if meta is None:
        raise ValueError(f"not a loadable series: {path}")
    cell.load_meta(meta)
    return wait_loaded(app, cell, timeout)


def open_workspace(app, win, root, mode="image", list_file=None, out_dir="vidi_output"):
    """Open a workspace through the dock (shows the dock first). Returns the Workspace."""
    from viewer_vidi import workspace as W
    if not win._dock.isVisible():
        win._ws_btn.setChecked(True); app.processEvents()
    if mode == "image":
        images, _ = W.probe_workspace(root, out_dir)
        ws = W.build_workspace(root, "image", images, out_dir)
    else:
        ws = W.build_workspace(root, "list", W.parse_list_file(list_file), out_dir, list_file=list_file)
    win._dock._out_edit.setText(out_dir)
    win._dock._set_workspace(ws)          # loads the first pending item asynchronously
    if ws.items:
        wait_loaded(app, win._quad.active_cell())
    return ws


# ── pointer helpers (canvas = cell.canvas()) ─────────────────────────────────

def pt(canvas, fx, fy):
    """Widget point at fraction (fx, fy) of the drawn image rect (0..1 inside)."""
    from PyQt5.QtCore import QPoint
    r = canvas._dest_rect()
    return QPoint(int(r.x() + r.width() * fx), int(r.y() + r.height() * fy))


def _mouse(canvas, etype, pos, button, buttons, mods=None):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtWidgets import QApplication
    QApplication.sendEvent(canvas, QMouseEvent(etype, pos, button, buttons, mods or Qt.NoModifier))


def press(canvas, pos, button=None):
    from PyQt5.QtCore import Qt, QEvent
    b = button or Qt.LeftButton
    _mouse(canvas, QEvent.MouseButtonPress, pos, b, b)


def move(canvas, pos, buttons=None):
    from PyQt5.QtCore import Qt, QEvent
    _mouse(canvas, QEvent.MouseMove, pos, Qt.NoButton, buttons if buttons is not None else Qt.NoButton)


def release(canvas, pos, button=None):
    from PyQt5.QtCore import Qt, QEvent
    b = button or Qt.LeftButton
    _mouse(canvas, QEvent.MouseButtonRelease, pos, b, Qt.NoButton)


def click(canvas, pos, button=None):
    press(canvas, pos, button); release(canvas, pos, button)


def dclick(canvas, pos):
    from PyQt5.QtCore import Qt, QEvent
    press(canvas, pos); release(canvas, pos)
    _mouse(canvas, QEvent.MouseButtonDblClick, pos, Qt.LeftButton, Qt.LeftButton)
    release(canvas, pos)


def drag(app, canvas, a, b, steps=10, button=None):
    """Press at a, move to b in steps with the button held, release at b."""
    from PyQt5.QtCore import Qt, QPoint
    btn = button or Qt.LeftButton
    press(canvas, a, btn)
    for i in range(1, steps + 1):
        p = QPoint(a.x() + (b.x() - a.x()) * i // steps, a.y() + (b.y() - a.y()) * i // steps)
        move(canvas, p, btn)
    release(canvas, b, btn)
    app.processEvents()


def key(widget, k, mods=None):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    QTest.keyClick(widget, k, mods or Qt.NoModifier)


def auto_close_dialogs(app, delay_ms=200, choose=None):
    """Arm a timer that closes any visible QMessageBox / QInputDialog.
    choose: substring of the button text to click (QMessageBox), else reject().
    Returns a list that fills with (class name, window title, text) tuples."""
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QMessageBox, QDialog
    seen = []
    def _close():
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                title = w.windowTitle()
                text = w.text() if isinstance(w, QMessageBox) else ""
                seen.append((type(w).__name__, title, text))
                if isinstance(w, QMessageBox) and choose:
                    for b in w.buttons():
                        if choose in b.text():
                            b.click(); break
                    else:
                        w.reject()
                else:
                    w.reject()
    QTimer.singleShot(delay_ms, _close)
    return seen


def invariants(canvas):
    """Assert canvas annotation invariants; returns a list of violations."""
    import numpy as np
    bad = []
    px, m = canvas.displayed_pixels(), canvas.mask()
    if px is None:
        if m is not None: bad.append("mask exists without pixels")
        if canvas.crop_rect() is not None: bad.append("crop rect without pixels")
        return bad
    if m is None:
        bad.append("pixels without mask"); return bad
    if m.shape != px.shape: bad.append(f"mask shape {m.shape} != pixels {px.shape}")
    if m.dtype != np.uint8: bad.append(f"mask dtype {m.dtype}")
    if m.max() > 1: bad.append(f"mask max {m.max()}")
    rgba = canvas._mask_rgba
    if rgba is None or rgba.shape[:2] != m.shape: bad.append("rgba buffer missing/mismatched")
    elif not np.array_equal(rgba[..., 3] > 0, m > 0): bad.append("overlay alpha out of sync with mask")
    r = canvas.crop_rect()
    if r is not None:
        h, w = px.shape
        x0, y0, x1, y1 = r
        if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h): bad.append(f"crop rect {r} out of bounds {w}x{h}")
    return bad
