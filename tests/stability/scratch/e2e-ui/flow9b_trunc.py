"""Probe: what the panel shows for a truncated .dcm item, and what Ctrl+S then writes."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H
import numpy as np
from PIL import Image

ERR = os.path.join(C.FX, "ws_err"); OUT = os.path.join(ERR, "vidi_output"); shutil.rmtree(OUT, ignore_errors=True)
app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()
seen = C.arm_dialog_closer(app)
C.open_dir_via_ui(app, win, ERR); ws = dock.workspace()
check("item 1 (a_good) loads", H.wait_loaded(app, cell))
good_px = canvas.displayed_pixels().copy()
good_dir = cell.series_data().meta.series_dir
# go straight to c_trunc via the list
C.dclick_list_row(app, dock, 2)
print("   right after dclick: index", dock._index, "sd", cell.series_data() is not None, "px", canvas.displayed_pixels() is not None)
loaded = H.wait_loaded(app, cell, timeout=8.0)
sd = cell.series_data()
px = canvas.displayed_pixels()
print("   after wait: loaded", loaded, "| sd.series_dir", sd and os.path.basename(sd.meta.series_dir), "| px", None if px is None else px.shape,
      "| px is the PREVIOUS image?", px is not None and px.shape == good_px.shape and np.array_equal(px, good_px),
      "| series_lbl", repr(cell._series_lbl.text()), "| status", repr(dock._status_lbl.text()), "| dialogs", seen)
check("truncated item: panel must not present a loaded image", not loaded, f"sd={sd is not None} px={px is not None}")
if px is not None:
    check("…and if it does, the pixels must not be the previous item's", not np.array_equal(px, good_px))
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
C.click_button(app, dock._image_chk)
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock); H.pump(app, 300)
print("   Ctrl+S on c_trunc → status", repr(st), "| dialogs", seen, "| files", C.out_files(OUT))
f = os.path.join(OUT, "png", "c_trunc_image.png")
if os.path.isfile(f):
    saved = np.array(Image.open(f))
    from viewer_vidi.annotation_export import window_to_uint8
    wc, ww = canvas.wl()
    check("c_trunc_image.png written: is it actually a_good's pixels?", False, f"equal to window_to_uint8(a_good)={np.array_equal(saved, window_to_uint8(good_px, wc, ww, canvas.invert()))} shape={saved.shape}")
    print("   manifest:", open(os.path.join(OUT, "manifest.csv")).read())
else:
    check("nothing written for the truncated item", not ws.items[2].done, str(ws.items[2].done))
# junk item for comparison
C.dclick_list_row(app, dock, 1); loaded = H.wait_loaded(app, cell, timeout=6.0)
print("   junk: loaded", loaded, "| sd", cell.series_data() is not None, "| px", canvas.displayed_pixels() is not None, "| series_lbl", repr(cell._series_lbl.text()))
sys.exit(C.finish(win, app))
