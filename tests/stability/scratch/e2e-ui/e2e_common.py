"""Shared helpers for the e2e-ui lens: drive the dock through its PUBLIC UI only."""
import os, sys, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H

SCRATCH = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/e2e-ui"
FX = os.path.join(SCRATCH, "fx")

results = []
_GEN = [0]   # generation counter so stale dialog closers never act
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

def finish(win, app):
    win.close(); app.processEvents()
    n_fail = sum(1 for _, ok in results if not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} checks passed", flush=True)
    return 1 if n_fail else 0


def patch_dialogs(dir_path=None, file_path=None):
    """Monkeypatch the QFileDialog static pickers to return our paths."""
    from PyQt5.QtWidgets import QFileDialog
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: dir_path or "")
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (file_path or "", ""))


def click_button(app, btn):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    QTest.mouseClick(btn, Qt.LeftButton)
    app.processEvents()


def open_dir_via_ui(app, win, path, choose=None, pick_item=None):
    """Click 'Open directory…' with the picker patched to *path*.
    choose: substring of a QMessageBox button to press; pick_item: QInputDialog item text."""
    patch_dialogs(dir_path=path)
    seen = arm_dialog_closer(app, choose=choose, pick_item=pick_item)
    click_button(app, win._dock._open_dir_btn)
    return seen


def open_list_via_ui(app, win, list_path, choose=None):
    patch_dialogs(file_path=list_path)
    seen = arm_dialog_closer(app, choose=choose)
    click_button(app, win._dock._open_list_btn)
    return seen


def arm_dialog_closer(app, delay_ms=150, choose=None, pick_item=None, repeat=True):
    """Like harness.auto_close_dialogs but also handles QInputDialog item pickers
    and keeps re-arming for a short time so chained dialogs are caught."""
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QMessageBox, QDialog, QInputDialog
    seen = []
    _GEN[0] += 1
    gen = _GEN[0]
    state = {"n": 0}
    def _close():
        if gen != _GEN[0]:
            return            # a newer closer was armed: this one is stale
        state["n"] += 1
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                title = w.windowTitle()
                if isinstance(w, QMessageBox):
                    text = w.text()
                    btns = [b.text() for b in w.buttons()]
                    seen.append((type(w).__name__, title, text, btns))
                    if choose:
                        for b in w.buttons():
                            if choose in b.text():
                                b.click(); break
                        else:
                            w.reject()
                    else:
                        w.reject()
                elif isinstance(w, QInputDialog):
                    items = list(w.comboBoxItems())
                    seen.append((type(w).__name__, title, w.labelText(), items))
                    if pick_item is not None:
                        w.setTextValue(pick_item); w.accept()
                    else:
                        w.reject()
                else:
                    seen.append((type(w).__name__, title, "", []))
                    w.reject()
        if repeat and state["n"] < 8:
            QTimer.singleShot(delay_ms, _close)
    QTimer.singleShot(delay_ms, _close)
    return seen


def ctrl_s(app, win, target=None):
    """Press Ctrl+S on the window (QShortcut, WindowShortcut context)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    w = target or win
    from PyQt5.QtWidgets import QApplication
    QApplication.setActiveWindow(w.window())   # a dismissed modal box leaves no active window offscreen
    QTest.keyClick(w, Qt.Key_S, Qt.ControlModifier)
    app.processEvents()


def key_on(app, widget, k, mods=None):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
    QApplication.setActiveWindow(widget.window())
    QTest.keyClick(widget, k, mods or Qt.NoModifier)
    app.processEvents()


def wait_status(app, dock, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if dock._status_lbl.text():
            return dock._status_lbl.text()
        time.sleep(0.01)
    return dock._status_lbl.text()


def list_texts(dock):
    return [dock._list.item(i).text() for i in range(dock._list.count())]


def out_files(out_dir):
    out = []
    for dp, dn, fn in os.walk(out_dir):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), out_dir))
    return sorted(out)


def click_focus(canvas, pos, button=None):
    """A *spontaneous* click (QTest) — like a real click it moves keyboard focus to the canvas."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    QTest.mouseClick(canvas, button or Qt.LeftButton, Qt.NoModifier, pos)


def dclick_list_row(app, dock, row):
    """Real double-click on a QListWidget row: press/release, then dblclick/release."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    lst = dock._list
    r = lst.visualItemRect(lst.item(row))
    QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, r.center())
    QTest.mouseDClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, r.center())
    app.processEvents()


def poly(canvas, pts):
    """Click polygon vertices like a user: the first click is spontaneous (moves focus)."""
    click_focus(canvas, pts[0])
    for p in pts[1:]:
        H.click(canvas, p)
