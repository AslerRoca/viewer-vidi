"""REPRO: Ctrl+S while the Workspace dock is hidden still saves + advances, and the newly loaded
item is put into the dock's current annotation tool (here 'poly') although the dock is hidden —
README: hiding the dock restores drag on all panels; dock.undo() guards on isVisible(), save_and_next() does not.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_ctrl_s_dock_hidden.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_ctrl_s"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
for f in sorted(os.listdir(H.FIXTURES))[:2]: shutil.copy(os.path.join(H.FIXTURES, f), D)
app, win = H.boot()
ws = H.open_workspace(app, win, D)
dock, cell = win._dock, win._quad.active_cell(); canvas = cell.canvas()
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3), H.pt(canvas, 0.6, 0.6)): H.click(canvas, p)
H.dclick(canvas, H.pt(canvas, 0.3, 0.6)); app.processEvents()
win._ws_btn.setChecked(False); app.processEvents()
print("dock visible:", dock.isVisible(), "mode after hide:", canvas.wl_mode(), "index:", dock._index)
QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); app.processEvents(); H.wait_loaded(app, cell)
print("after Ctrl+S: dock visible:", dock.isVisible(), "index:", dock._index, "mode:", canvas.wl_mode(),
      "written:", sorted(os.listdir(os.path.join(D, "vidi_output", "png"))))
print("EXPECTED: no save while hidden (or at least mode 'drag'); OBSERVED: saved + advanced + mode", canvas.wl_mode())
win.close()
