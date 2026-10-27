"""Is the coronal polygon disagreement vs. the reference confined to the polygon boundary?"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from scipy.ndimage import binary_dilation
from matplotlib.path import Path as MplPath
from PyQt5.QtCore import QPoint
NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
H.load_file(app, cell, NII); cell._set_view("CORONAL"); app.processEvents(); H.pump(app, 100)
tool(dock, "poly")
def ipt(ix, iy):
    r = canvas._dest_rect(); h, w = canvas.displayed_pixels().shape
    return QPoint(int(r.x() + (ix + 0.5) * r.width() / w), int(r.y() + (iy + 0.5) * r.height() / h))
Pp = [ipt(50, 5), ipt(300, 10), ipt(250, 50), ipt(80, 45)]
verts = [canvas._image_coords(p.x(), p.y()) for p in Pp]
for p in Pp: H.click(canvas, p)
H.dclick(canvas, Pp[-1]); app.processEvents()
h, w = canvas.mask().shape; yy, xx = np.mgrid[0:h, 0:w]
ref = MplPath([(x + .5, y + .5) for x, y in verts]).contains_points(np.c_[xx.ravel() + .5, yy.ravel() + .5]).reshape(h, w)
got = canvas.mask() > 0
diff = got != ref
boundary = binary_dilation(ref, iterations=1) & ~binary_dilation(~ref, iterations=0) | (binary_dilation(ref, iterations=1) ^ ref) | (ref ^ binary_dilation(~ref, iterations=1) == False)
edge = binary_dilation(ref, iterations=1) & ~(ref & ~binary_dilation(~ref, iterations=1))   # 1-px band around the edge
print("verts", verts, "mismatch", int(diff.sum()), "of", h * w, "; mismatches off the 1-px edge band:", int((diff & ~edge).sum()))
ys, xs = np.nonzero(got); rys, rxs = np.nonzero(ref)
print("centroid got", (xs.mean(), ys.mean()), "ref", (rxs.mean(), rys.mean()))
win.close()
