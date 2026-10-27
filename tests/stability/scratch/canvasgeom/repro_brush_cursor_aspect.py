"""Repro: on an anisotropic reformat (CORONAL of C.nii, aspect 3.53) the brush cursor is drawn as a
circle of radius r*sx but the painted footprint is r image px in both axes → on screen 3.5x taller."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
H.load_file(app, cell, NII); cell._set_view("CORONAL"); app.processEvents(); H.pump(app, 100)
tool(dock, "paint"); dock._brush_spin.setValue(5); app.processEvents()
r = canvas._dest_rect(); h, w = canvas.displayed_pixels().shape
sx, sy = r.width() / w, r.height() / h
H.click(canvas, H.pt(canvas, 0.5, 0.5)); app.processEvents()
bb = bbox(canvas.mask())
foot_w, foot_h = (bb[2] - bb[0] + 1) * sx, (bb[3] - bb[1] + 1) * sy
cursor_r = canvas._brush_r * r.width() / canvas._qimage.width()   # as drawn in _draw_annotations
print(f"aspect={canvas._aspect:.2f} slice={h}x{w} sx={sx:.2f} sy={sy:.2f}")
print(f"cursor circle diameter on screen: {2*cursor_r:.1f} px; painted footprint on screen: {foot_w:.1f} x {foot_h:.1f} px")
win.close()
sys.exit(0 if abs(foot_h - 2 * cursor_r) < 2 else 1)
