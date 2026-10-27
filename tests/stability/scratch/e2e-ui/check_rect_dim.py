"""README: Rect — 'the outside is dimmed'. Grab the canvas before/after a rectangle and compare."""
import sys
import repro_common as R
from repro_common import H
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
ws_dir = R.fresh_ws("repro_dim", ["bpd1_20100115_1.dcm"])
app, win = H.boot(); dock = win._dock; canvas = win._quad.active_cell().canvas()
win._ws_btn.setChecked(True); app.processEvents()
R.open_dir(app, win, ws_dir)
def grab():
    img = canvas.grab().toImage().convertToFormat(4)   # Format_RGB32
    ptr = img.constBits(); ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(), :3].astype(np.int16)
before = grab()
QTest.mouseClick(dock._tool_btns["rect"], Qt.LeftButton); app.processEvents()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.7, 0.7)); H.pump(app, 100)
after = grab()
pi, po = H.pt(canvas, 0.5, 0.5), H.pt(canvas, 0.1, 0.1)
ins = (before[pi.y()-5:pi.y()+5, pi.x()-5:pi.x()+5].mean(), after[pi.y()-5:pi.y()+5, pi.x()-5:pi.x()+5].mean())
out = (before[po.y()-5:po.y()+5, po.x()-5:po.x()+5].mean(), after[po.y()-5:po.y()+5, po.x()-5:po.x()+5].mean())
print("inside rect mean before/after:", ins, "| outside mean before/after:", out)
print("outside dimmed:", out[1] < out[0] - 5, "| inside unchanged:", abs(ins[1] - ins[0]) < 2)
win.close(); sys.exit(0)
