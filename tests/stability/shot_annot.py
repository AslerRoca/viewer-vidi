import os, sys, time, types, importlib.util
os.environ["QT_QPA_PLATFORM"] = "offscreen"
SP = os.path.dirname(os.path.abspath(__file__)); SRC = "/media/zsk/ressd/research/viewer-vidi"
pkg = types.ModuleType("viewer_vidi"); pkg.__path__ = [SRC]; pkg.__package__ = "viewer_vidi"
pkg.__file__ = os.path.join(SRC, "__init__.py"); sys.modules["viewer_vidi"] = pkg
spec = importlib.util.spec_from_file_location("viewer_vidi", pkg.__file__); spec.loader.exec_module(pkg)
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from viewer_vidi import workspace as W
app = QApplication(sys.argv)
from viewer_vidi.main_window import MainWindow
win = MainWindow(); win.resize(1400, 900); win.show(); app.processEvents()
ws_img = os.path.join(SP, "ws_img"); images, _ = W.probe_workspace(ws_img)
win._ws_btn.setChecked(True); app.processEvents()
dock = win._dock; cell = win._quad.active_cell(); canvas = cell.canvas()
dock._set_workspace(W.build_workspace(ws_img, "image", images))
t0 = time.time()
while time.time() - t0 < 15 and canvas.displayed_pixels() is None:
    app.processEvents(); time.sleep(0.02)
# fullscreen the panel so the picture is big
win._quad._toggle_fullscreen(cell); app.processEvents()
r = canvas._dest_rect()
def pt(fx, fy): return QPoint(int(r.x() + r.width() * fx), int(r.y() + r.height() * fy))
def drag(a, b, steps=12):
    QTest.mousePress(canvas, Qt.LeftButton, Qt.NoModifier, a)
    for i in range(1, steps + 1):
        p = QPoint(a.x() + (b.x() - a.x()) * i // steps, a.y() + (b.y() - a.y()) * i // steps)
        QApplication.sendEvent(canvas, QMouseEvent(QEvent.MouseMove, p, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(canvas, Qt.LeftButton, Qt.NoModifier, b); app.processEvents()
dock._brush_spin.setValue(40)
drag(pt(0.30, 0.35), pt(0.45, 0.55))
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (pt(0.55, 0.30), pt(0.75, 0.32), pt(0.72, 0.60), pt(0.52, 0.55)):
    QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, p)
QTest.mouseDClick(canvas, Qt.LeftButton, Qt.NoModifier, pt(0.52, 0.55)); app.processEvents()
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
drag(pt(0.20, 0.20), pt(0.85, 0.75))
# polygon in progress + cursor, for the screenshot
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (pt(0.30, 0.80), pt(0.45, 0.85)):
    QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, p)
QApplication.sendEvent(canvas, QMouseEvent(QEvent.MouseMove, pt(0.40, 0.92), Qt.NoButton, Qt.NoButton, Qt.NoModifier))
app.processEvents()
win.grab().save(os.path.join(SP, "shot_annot.png"))
# timing: repaint with mask overlay, and a long brush segment
canvas.set_wl_mode("paint")
t0 = time.perf_counter()
for _ in range(20): canvas.repaint()
rep_ms = (time.perf_counter() - t0) / 20 * 1000
canvas._brush_r = 40
t0 = time.perf_counter(); canvas._paint_segment((100, 100), (1400, 1900)); seg_ms = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter(); canvas._push_undo(); undo_ms = (time.perf_counter() - t0) * 1000
print(f"repaint {rep_ms:.1f} ms | diagonal brush segment {seg_ms:.1f} ms | undo snapshot {undo_ms:.1f} ms | mask px {canvas.mask_pixels():,}")
win.close()
