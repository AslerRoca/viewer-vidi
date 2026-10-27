"""PNG export rounds (+0.5) while the canvas truncates: compare saved 8-bit image to the on-screen RGB buffer."""
from common import *
import numpy as np
from viewer_vidi.annotation_export import window_to_uint8
app, win = H.boot(); dock, quad = win._dock, win._quad
cell = quad.active_cell(); c = cell.canvas()
assert H.load_file(app, cell, os.path.join(FIX, "bpd1_20100101_1.dcm"))
px = c.displayed_pixels(); wc, ww = c.wl()
shown = np.asarray(c._rgb_buf)[..., 0]           # gray LUT is identity → displayed value
saved = window_to_uint8(px, wc, ww, c.invert())
diff = saved.astype(int) - shown.astype(int)
frac = np.mean(diff != 0); mx = np.abs(diff).max()
print(f"wl={wc},{ww} differing px: {frac:.1%}, max |diff| {mx}, diff values {np.unique(diff)}")
check("saved 8-bit equals displayed 8-bit (README: 'what you see')", frac == 0, f"{frac:.1%} px differ by up to {mx}")
cell.set_invert(True); app.processEvents()
shown_i = np.asarray(c._rgb_buf)[..., 0]; saved_i = window_to_uint8(px, wc, ww, c.invert())
d2 = saved_i.astype(int) - shown_i.astype(int)
print(f"invert: differing {np.mean(d2!=0):.1%}, values {np.unique(d2)}")
check("inverted: saved equals displayed", np.mean(d2 != 0) == 0, f"{np.mean(d2!=0):.1%} differ, values {np.unique(d2)}")
# GPU vs CPU render agree?
from viewer_vidi.windowing import render_to_rgb
from viewer_vidi.colormaps import COLORMAPS
cpu = render_to_rgb(np.asarray(px), wc, ww, COLORMAPS[c._cmap_name])[..., 0]
check("CPU render_to_rgb equals what the canvas shows (GPU path)", np.array_equal(cpu, np.asarray(c._rgb_buf)[...,0]) or c.invert(), "")
win.close(); app.processEvents(); sys.exit(summary())
