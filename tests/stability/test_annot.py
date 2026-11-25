"""Headless checks for the annotation workspace feature (offscreen Qt)."""
import os, sys, time, types, importlib.util
os.environ["QT_QPA_PLATFORM"] = "offscreen"
SP = os.path.dirname(os.path.abspath(__file__))
SRC = "/media/zsk/ressd/research/viewer-vidi"

pkg = types.ModuleType("viewer_vidi"); pkg.__path__ = [SRC]; pkg.__package__ = "viewer_vidi"
pkg.__file__ = os.path.join(SRC, "__init__.py"); sys.modules["viewer_vidi"] = pkg
spec = importlib.util.spec_from_file_location("viewer_vidi", pkg.__file__); spec.loader.exec_module(pkg)

import numpy as np
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item, window_to_uint8

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))

# ── 1. workspace.py ──────────────────────────────────────────────────────────
ws_img, ws_list = os.path.join(SP, "ws_img"), os.path.join(SP, "ws_list")
images, lists = W.probe_workspace(ws_img)
check("image mode finds 4 dicoms recursively", len(images) == 4, str([os.path.relpath(p, ws_img) for p in images]))
check("notes.txt is not a list file", lists == [])
ws = W.build_workspace(ws_img, "image", images)
stems = [it.stem for it in ws.items]
check("duplicate basenames get unique stems", len(set(stems)) == 4 and "sub__bpd1_20100101_1" in stems, str(stems))

images2, lists2 = W.probe_workspace(ws_list)
check("list dir: no images, 2 list files", images2 == [] and len(lists2) == 2, str([os.path.basename(l) for l in lists2]))
txt = W.parse_list_file(os.path.join(ws_list, "list.txt"))
check("txt list: comment skipped, relative resolved, missing kept", len(txt) == 3 and txt[1].endswith("ws_img/sub/bpd1_20100102_1.dcm"), str(txt))
csvp = W.parse_list_file(os.path.join(ws_list, "cohort.csv"))
check("csv list: header 'path' column used, quotes stripped", len(csvp) == 2 and all(p.endswith(".dcm") for p in csvp), str(csvp))
wsl = W.build_workspace(ws_list, "list", txt, list_file=os.path.join(ws_list, "list.txt"))
check("list workspace: 2 items + 1 missing", len(wsl.items) == 2 and len(wsl.missing) == 1)

# ── 2. export module on synthetic data ──────────────────────────────────────
px = np.linspace(0, 4095, 50 * 40, dtype=np.float32).reshape(50, 40)
mask = np.zeros((50, 40), np.uint8); mask[10:20, 5:15] = 1
out = os.path.join(SP, "export_synth"); os.makedirs(out, exist_ok=True)
inp = ExportInput(stem="s", pixels=px, wc=2048, ww=4096, invert=False, mask=mask, rect=(2, 3, 22, 33), spacing=(0.5, 0.25))
written = export_item(out, inp, ExportOptions(formats=("png", "jpeg", "nifti"), save_image=True))
check("export writes 5 products × 3 formats", len(written) == 15, str(written))
from PIL import Image
im = np.array(Image.open(os.path.join(out, "png", "s_mask.png")))
check("png mask is 0/255 with 100 px", im.shape == (50, 40) and im.max() == 255 and (im == 255).sum() == 100)
roi = np.array(Image.open(os.path.join(out, "png", "s_roi.png")))
check("png roi crop has rect shape (30×20)", roi.shape == (30, 20), str(roi.shape))
import nibabel as nib
ni = nib.load(os.path.join(out, "nifti", "s_image.nii.gz"))
check("nifti image is (W,H,1) float32 with spacing", ni.shape == (40, 50, 1) and tuple(np.round(ni.header.get_zooms()[:2], 3)) == (0.25, 0.5), f"{ni.shape} {ni.header.get_zooms()}")
check("nifti raw values round-trip", np.allclose(np.asarray(ni.dataobj)[:, :, 0].T, px))
nroi = nib.load(os.path.join(out, "nifti", "s_roi.nii.gz"))
check("nifti roi carries origin offset", nroi.shape == (20, 30, 1) and np.allclose(nroi.affine[:2, 3], [2 * 0.25, 3 * 0.5]), str(nroi.affine[:2, 3]))
box = np.array(Image.open(os.path.join(out, "png", "s_rect_mask.png")))
nbox = nib.load(os.path.join(out, "nifti", "s_rect_mask.nii.gz"))
only_rect = export_item(out, ExportInput(stem="r", pixels=px, wc=2048, ww=4096, mask=np.zeros_like(mask), rect=(2, 3, 22, 33)),
                        ExportOptions(formats=("png",)))
no_mask = export_item(out, ExportInput(stem="n", pixels=px, wc=2048, ww=4096, mask=mask, rect=(2, 3, 22, 33)),
                      ExportOptions(formats=("png",), save_mask=False))
check("the rectangle is written as a mask on the whole image, painted mask or not, only with Mask ticked",
      box.shape == (50, 40) and (box == 255).sum() == 600 and (box[3:33, 2:22] == 255).all()
      and nbox.shape == (40, 50, 1) and np.array_equal(nbox.affine, ni.affine) and int(np.asarray(nbox.dataobj).sum()) == 600
      and only_rect == ["png/r_roi.png", "png/r_rect_mask.png"] and no_mask == ["png/n_roi.png"], f"{only_rect} {no_mask}")
check("nothing-to-write returns []", export_item(out, ExportInput(stem="e", pixels=px, wc=1, ww=1, mask=np.zeros_like(mask), rect=None), ExportOptions(formats=("png",))) == [])
u8 = window_to_uint8(px, 2048, 4096, invert=True)
check("invert flips 8-bit output", u8[0, 0] == 255 and u8[-1, -1] <= 1)   # truncation like the canvas

# ── 3. GUI: load item, draw, save, resume ───────────────────────────────────
app = QApplication(sys.argv)
from viewer_vidi.main_window import MainWindow
win = MainWindow(); win.resize(1400, 900); win.show(); app.processEvents()

dock = win._dock
quad = win._quad
cell = quad.active_cell()
canvas = cell.canvas()
check("W/L drag is default while dock hidden", canvas.wl_mode() == "drag")
win._ws_btn.setChecked(True); app.processEvents()
check("Workspace button shows dock and applies brush tool", dock.isVisible() and canvas.wl_mode() == "paint")

# remove any stale output from an earlier run
import shutil; shutil.rmtree(os.path.join(ws_img, "vidi_output"), ignore_errors=True)
dock._set_workspace(W.build_workspace(ws_img, "image", images))
def wait_loaded(timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cell.series_data() is not None and canvas.displayed_pixels() is not None:
            return True
        time.sleep(0.02)
    return False
check("first item loads into the active panel", wait_loaded(), str(cell.series_data().meta.series_dir if cell.series_data() else None))
check("tool mode survives load_meta reset", canvas.wl_mode() == "paint")
H, Wd = canvas.displayed_pixels().shape
check("mask allocated with image shape", canvas.mask() is not None and canvas.mask().shape == (H, Wd), f"{H}x{Wd}")
# the fixtures carry no window in the header, only a lookup table: its range is the default window
import pydicom
lut_n, lut_first = (int(v) for v in pydicom.dcmread(images[0], stop_before_pixels=True).VOILUTSequence[0].LUTDescriptor[:2])
check("a film without a header window opens with the range of its lookup table as window",
      canvas.wl() == (4095 - (lut_first + (lut_n - 1) / 2), float(lut_n)) and cell.series_data().wl_from_header,
      f"{canvas.wl()} · LUT {lut_n} entries from {lut_first}")

r = canvas._dest_rect()
def pt(fx, fy): return QPoint(int(r.x() + r.width() * fx), int(r.y() + r.height() * fy))
def drag(a, b, steps=8):
    QTest.mousePress(canvas, Qt.LeftButton, Qt.NoModifier, a)
    for i in range(1, steps + 1):
        p = QPoint(a.x() + (b.x() - a.x()) * i // steps, a.y() + (b.y() - a.y()) * i // steps)
        QApplication.sendEvent(canvas, QMouseEvent(QEvent.MouseMove, p, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(canvas, Qt.LeftButton, Qt.NoModifier, b)
    app.processEvents()

# brush stroke
drag(pt(0.3, 0.3), pt(0.6, 0.3))
n_brush = canvas.mask_pixels()
check("brush stroke paints mask pixels", n_brush > 0, f"{n_brush} px")
# erase part of it
dock._erase_chk.setChecked(True); drag(pt(0.3, 0.3), pt(0.4, 0.3)); dock._erase_chk.setChecked(False)
n_after_erase = canvas.mask_pixels()
check("erase removes pixels", 0 < n_after_erase < n_brush, f"{n_brush} → {n_after_erase}")
# undo the erase
check("undo restores the stroke", canvas.undo_annotation() and canvas.mask_pixels() == n_brush)

# polygon: 4 clicks, close by double-click; must not toggle fullscreen
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (pt(0.2, 0.6), pt(0.5, 0.6), pt(0.5, 0.9), pt(0.2, 0.9)):
    QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, p)
QTest.mouseDClick(canvas, Qt.LeftButton, Qt.NoModifier, pt(0.2, 0.9)); app.processEvents()
n_poly = canvas.mask_pixels()
expected = (0.3 * Wd) * (0.3 * H)
check("polygon fills roughly its area", n_poly - n_brush > 0.8 * expected, f"+{n_poly - n_brush} px, expected ≈{expected:.0f}")
check("double-click in polygon mode does not fullscreen", not quad.is_fullscreen())

# rectangle crop
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
drag(pt(0.1, 0.1), pt(0.7, 0.8))
rect = canvas.crop_rect()
check("rectangle stored in image coords", rect is not None and rect[2] - rect[0] > 0.5 * Wd and rect[3] - rect[1] > 0.6 * H, str(rect))

# adjust the rectangle by its edges and corners; a drag elsewhere still draws a new one
x0, y0, x1, y1 = rect
xm, ym = (x0 + x1) // 2, (y0 + y1) // 2
def sp(x, y): return QPoint(*canvas._screen_coords(x, y))
def hover(p):
    QApplication.sendEvent(canvas, QMouseEvent(QEvent.MouseMove, p, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    return canvas.cursor().shape()
def yellow(p):      # the colour of the rectangle and its handles
    c = canvas.grab().toImage().pixelColor(p)
    return (c.red(), c.green(), c.blue()) == (245, 200, 66)
check("cursor shows what a drag would move: an edge, a corner, or nothing",
      hover(sp(x1, ym)) == Qt.SizeHorCursor and hover(sp(xm, y0)) == Qt.SizeVerCursor
      and hover(sp(x0, y0)) == Qt.SizeFDiagCursor and hover(sp(x1, y0)) == Qt.SizeBDiagCursor
      and hover(sp(xm, ym)) == Qt.CrossCursor)
corner = sp(x0, y0) + QPoint(-3, -3)
dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); no_handle = not yellow(corner)
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
check("handles are drawn on the rectangle while the Rect tool is active", no_handle and yellow(corner))
dx = round(-30 * Wd / r.width())
a = sp(x1, ym); drag(a, a + QPoint(-30, 12))
right_moved = (x0, y0, x1 + dx, y1)
check("dragging the right edge moves only that edge", dx < 0 and canvas.crop_rect() == right_moved, f"{rect} → {canvas.crop_rect()}")
check("the dock's rectangle line follows the adjustment", f"{x1 + dx - x0}×{y1 - y0} px" in dock._stats_lbl.text(), dock._stats_lbl.text())
a = sp(x0, y0); drag(a, a + QPoint(20, 16))
check("dragging a corner moves its two edges",
      canvas.crop_rect() == (x0 + round(20 * Wd / r.width()), y0 + round(16 * H / r.height()), x1 + dx, y1), str(canvas.crop_rect()))
check("each adjustment is one undo step", canvas.undo_annotation() and canvas.crop_rect() == right_moved
      and canvas.undo_annotation() and canvas.crop_rect() == rect)
a = sp(x0, ym); drag(a, a + QPoint(r.width(), 0)); narrow = canvas.crop_rect(); canvas.undo_annotation()
a = sp(xm, y1); drag(a, a + QPoint(0, r.height())); tall = canvas.crop_rect(); canvas.undo_annotation()
check("an edge stops at the opposite edge and at the image border",
      narrow == (x1 - 1, y0, x1, y1) and tall == (x0, y0, x1, H) and canvas.crop_rect() == rect, f"{narrow} {tall}")
depth = len(canvas._undo)
QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, sp(x1, ym)); app.processEvents()
check("a click on an edge changes nothing", canvas.crop_rect() == rect and len(canvas._undo) == depth)
drag(sp(xm, ym), sp(xm, ym) + QPoint(60, 40)); inner = canvas.crop_rect()
check("a drag started away from the edges draws a new rectangle",
      x0 < inner[0] and inner[2] < x1 and y0 < inner[1] and inner[3] < y1
      and canvas.undo_annotation() and canvas.crop_rect() == rect, str(inner))

# save with all formats → files + manifest + done flag + advance
for chk in dock._fmt_chk.values(): chk.setChecked(True)
dock._image_chk.setChecked(True)
stem0 = ws.items[0].stem
dock._save(advance=True); app.processEvents()
outd = os.path.join(ws_img, "vidi_output")
expect_files = [os.path.join(outd, f, f"{stem0}_{s}{e}") for f, e in (("png", ".png"), ("jpeg", ".jpg"), ("nifti", ".nii.gz")) for s in ("image", "mask", "roi", "roi_mask", "rect_mask")]
missing = [p for p in expect_files if not os.path.isfile(p)]
check("save writes 15 files in 3 format dirs", not missing, f"missing {missing}" if missing else "")
man = W.read_manifest(os.path.join(outd, "manifest.csv"))
check("manifest records the item with rect + mask pixels", stem0 in man and int(man[stem0]["mask_pixels"]) == n_poly and man[stem0]["x0"] == str(rect[0]), str(man.get(stem0)))
check("item marked done and job advanced", dock._ws.items[0].done and dock._index == 1 and dock._list.item(0).text().startswith("✓"))
check("next item loads with a fresh mask", wait_loaded() and canvas.mask_pixels() == 0 and canvas.crop_rect() is None)
pm = np.array(Image.open(os.path.join(outd, "png", f"{stem0}_mask.png")))
check("saved mask matches canvas shape and count", pm.shape == (H, Wd) and (pm == 255).sum() == n_poly)
img8 = np.array(Image.open(os.path.join(outd, "png", f"{stem0}_image.png")))
check("saved image is 8-bit with the image shape", img8.dtype == np.uint8 and img8.shape == (H, Wd) and img8.max() > img8.min())
# the fixtures are MONOCHROME1 films (12 bit): loaded and exported flipped, high = white
stored0 = pydicom.dcmread(images[0]).pixel_array.astype(np.float32)
nimg = np.asarray(nib.load(os.path.join(outd, "nifti", f"{stem0}_image.nii.gz")).dataobj)[:, :, 0].T
check("a MONOCHROME1 film is exported flipped (high = white) and the manifest names its polarity",
      np.array_equal(nimg, 4095 - stored0) and man[stem0]["photometric"] == "MONOCHROME1" and man[stem0]["invert"] == "0",
      f"{man[stem0].get('photometric')!r} invert {man[stem0].get('invert')!r}")
check("the manifest records the window of the save and that it was the default",
      (float(man[stem0]["wc"]), float(man[stem0]["ww"])) == (4095 - (lut_first + (lut_n - 1) / 2), float(lut_n))
      and man[stem0]["wl_default"] == "1", f"{man[stem0].get('wc')} {man[stem0].get('ww')} {man[stem0].get('wl_default')!r}")

# panel-mismatch guard: load a different file into the active cell, then try to save
from viewer_vidi.tree_panel import _make_series_meta
cell.load_meta(_make_series_meta(images[0])); wait_loaded()
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox
shown = []
def _close_box():
    for w in app.topLevelWidgets():
        if isinstance(w, QMessageBox) and w.isVisible():
            shown.append(w.windowTitle()); w.reject()
QTimer.singleShot(200, _close_box)
dock._save(advance=False); app.processEvents()
check("saving refuses when the panel shows a different file", shown == ["Panel mismatch"] and not dock._ws.items[1].done, str(shown))

# resume: reopen → done flags restored, first pending item selected
dock._set_workspace(W.build_workspace(ws_img, "image", images))
check("reopen restores done flags and skips to first pending", dock._ws.items[0].done and dock._index == 1)

# delete / restore mark: button, Delete key, manifest status, reopen, restore, save restores
dock._set_workspace(W.build_workspace(ws_img, "image", images)); wait_loaded()
i1 = dock._index; it1 = dock._ws.items[i1]
stem_before = it1.stem
dock.toggle_delete(); app.processEvents()
man = W.read_manifest(os.path.join(outd, "manifest.csv"))
check("delete marks the item, keeps it on screen, button says Restore",
      it1.deleted and not it1.done and dock._index == i1 and dock._del_btn.text() == "Restore"
      and dock._list.item(i1).text().startswith("⊘") and dock._list.item(i1).font().strikeOut()
      and man.get(it1.stem, {}).get("status") == "deleted", str(man.get(it1.stem)))
check("count label shows deleted", "1 deleted" in dock._count_lbl.text(), dock._count_lbl.text())
QApplication.setActiveWindow(win); win.activateWindow(); app.processEvents()   # shortcuts need an active window (offscreen has none by default)
QTest.keyClick(win, Qt.Key_Delete); app.processEvents()
man = W.read_manifest(os.path.join(outd, "manifest.csv"))
check("Delete key restores: row removed, button says Delete",
      not it1.deleted and it1.stem not in man and dock._del_btn.text() == "Delete"
      and not dock._list.item(i1).font().strikeOut())
QTest.keyClick(win, Qt.Key_Backspace); app.processEvents()
check("Backspace marks again", it1.deleted)
dock._set_workspace(W.build_workspace(ws_img, "image", images)); wait_loaded()
it1b = dock._ws.items[i1]
check("reopen restores the deleted mark and skips it as first pending",
      it1b.deleted and it1b.stem == stem_before and dock._index != i1, f"index {dock._index}")
dock._load_index(i1); wait_loaded()
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
drag(pt(0.2, 0.2), pt(0.6, 0.6))
stem1 = it1b.stem
def of_item():
    return sorted(f for f in os.listdir(os.path.join(outd, "png")) if f.startswith(stem1 + "_"))
def row1():
    return W.read_manifest(os.path.join(outd, "manifest.csv")).get(stem1, {})
dock._save(advance=False); app.processEvents()
check("Save leaves an item marked as deleted alone",
      it1b.deleted and not it1b.done and row1().get("status") == "deleted" and of_item() == []
      and "Restore" in dock._status_lbl.text(), dock._status_lbl.text())
dock._save(advance=True); app.processEvents()
check("Save & Next on it only moves on to the next item",
      dock._index == i1 + 1 and wait_loaded() and it1b.deleted and row1().get("status") == "deleted" and of_item() == [],
      f"index {dock._index} · {dock._status_lbl.text()}")

# the annotation of a save is kept, whatever is ticked, and comes back when the item is reopened
def wait_restored(timeout=15.0):
    """Loaded, and the dock has dealt with the saved annotation of the item."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if dock._restore_cell is None and canvas.displayed_pixels() is not None:
            return True
        time.sleep(0.02)
    return False
dock._load_index(i1); wait_restored()
dock.toggle_delete(); app.processEvents()          # Restore: pending again
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
drag(pt(0.3, 0.4), pt(0.6, 0.5))
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
drag(pt(0.2, 0.2), pt(0.8, 0.8))
n_kept, rect_kept = canvas.mask_pixels(), canvas.crop_rect()
work = os.path.join(outd, "work", f"{stem1}_mask.png")
dock._mask_chk.setChecked(False)
dock._save(advance=True); app.processEvents()
check("a save keeps the mask although Mask is not ticked",
      wait_loaded() and n_kept > 0 and of_item() == [f"{stem1}_image.png", f"{stem1}_roi.png"]
      and os.path.isfile(work) and int((np.array(Image.open(work)) == 255).sum()) == n_kept, str(of_item()))
dock._step(-1)
check("reopening the item puts its mask and rectangle back",
      wait_restored() and dock._index == i1 and canvas.mask_pixels() == n_kept and canvas.crop_rect() == rect_kept
      and not canvas._undo, f"{canvas.mask_pixels()} px of {n_kept}, {canvas.crop_rect()}")
dock._mask_chk.setChecked(True)
dock._save(advance=False); app.processEvents()
check("saved again with Mask ticked: the mask is written, crop and rectangle stay",
      of_item() == [f"{stem1}_{s}.png" for s in ("image", "mask", "rect_mask", "roi", "roi_mask")]
      and tuple(int(row1()[k]) for k in ("x0", "y0", "x1", "y1")) == rect_kept, f"{of_item()} {row1()}")
os.remove(work); dock._load_index(i1)
check("an item saved before masks were kept gets its mask back from the mask product",
      wait_restored() and canvas.mask_pixels() == n_kept and canvas.crop_rect() == rect_kept, f"{canvas.mask_pixels()} px")

# Invert is saved with the item, recorded in the manifest and off again afterwards
win._invert_btn.setChecked(True); app.processEvents()
canvas.set_wl(canvas.wl()[0] + 60, canvas.wl()[1] * 0.8)            # a window set by hand
was_on, (wc1, ww1) = canvas.invert(), canvas.wl()
dock._save(advance=False); app.processEvents()
png1 = np.array(Image.open(os.path.join(outd, "png", f"{stem1}_image.png")))
check("Invert is saved with the item and recorded, and it is off again after the save",
      was_on and not canvas.invert() and not win._invert_btn.isChecked() and row1().get("invert") == "1"
      and np.array_equal(png1, window_to_uint8(canvas.displayed_pixels(), wc1, ww1, invert=True)),
      f"manifest invert {row1().get('invert')!r}")
check("a window set by hand is recorded as such",
      row1().get("wl_default") == "0" and abs(float(row1()["wc"]) - wc1) < 0.01 and abs(float(row1()["ww"]) - ww1) < 0.01,
      f"{row1().get('wc')} {row1().get('ww')} {row1().get('wl_default')!r}")

dock.toggle_delete(); app.processEvents()
check("deleting a saved item removes its products and its kept mask",
      it1b.deleted and of_item() == [] and not os.path.isfile(work))
dock.toggle_delete(); app.processEvents()   # leave it pending for the remaining checks

# right-click on the image: the tool row as a menu at the cursor
from PyQt5.QtWidgets import QMenu
asked, seen = [], {}
canvas.context_requested.connect(lambda p: asked.append(p))
def pick(label):
    """Choose *label* in the menu that is open, as a click on the entry would."""
    def _go():
        menu = QApplication.activePopupWidget()
        if isinstance(menu, QMenu):
            seen["entries"] = [(a.text(), a.isChecked()) for a in menu.actions() if not a.isSeparator()]
            next(a for a in menu.actions() if a.text() == label).trigger()
            menu.close()
    return _go
def right_click(p):
    QTest.mouseClick(canvas, Qt.RightButton, Qt.NoModifier, p); app.processEvents()
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
QTimer.singleShot(300, pick("Brush")); right_click(pt(0.5, 0.5))
check("a right-click opens the tool menu; choosing an entry switches the tool",
      seen.get("entries") == [("W/L", False), ("Brush", False), ("Polygon", False), ("Rect", True), ("Erase", False)]
      and canvas.wl_mode() == "paint" and dock._tool_btns["paint"].isChecked(), str(seen))
QTimer.singleShot(300, pick("Erase")); right_click(pt(0.5, 0.5))
check("Erase can be ticked in the menu", dock._erase_chk.isChecked() and canvas._erase)
dock._erase_chk.setChecked(False)
n_asked, pan0, a = len(asked), (canvas._pan_x, canvas._pan_y), pt(0.5, 0.5)
QTest.mousePress(canvas, Qt.RightButton, Qt.NoModifier, a)
QApplication.sendEvent(canvas, QMouseEvent(QEvent.MouseMove, a + QPoint(30, 20), Qt.NoButton, Qt.RightButton, Qt.NoModifier))
QTest.mouseRelease(canvas, Qt.RightButton, Qt.NoModifier, a + QPoint(30, 20)); app.processEvents()
panned = (canvas._pan_x, canvas._pan_y) == (pan0[0] + 30, pan0[1] + 20)
canvas._pan_x, canvas._pan_y = pan0; canvas.update()
dock._tool_btns["poly"].setChecked(True); dock._apply_tool()
for p in (pt(0.3, 0.3), pt(0.4, 0.3)):
    QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, p)
right_click(pt(0.4, 0.3))
dropped = len(canvas._poly_pts) == 1
QTest.keyClick(canvas, Qt.Key_Escape); app.processEvents()
check("a right-button drag still pans and a polygon in progress keeps its right-click: no menu",
      panned and dropped and len(asked) == n_asked, f"panned {panned}, vertex dropped {dropped}, menus {len(asked) - n_asked}")
dock._tool_btns["rect"].setChecked(True); dock._apply_tool()

# a list dragged from the study list onto "Open list…"
from PyQt5.QtCore import QMimeData, QPointF
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from viewer_vidi import drag_state
tree, btn = win._tree, dock._open_list_btn
def dragged(*paths):
    """What the study list hands to Qt when these entries are dragged (indexes made on the
    spot: the proxy drops its indexes whenever a folder has been classified)."""
    drag_state.clear_payload()
    return tree._proxy.mimeData([tree._proxy.mapFromSource(tree._fs.index(p)) for p in paths])
def enters(mime):
    event = QDragEnterEvent(btn.rect().center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(btn, event)
    return event.isAccepted()
def drop(mime):
    if not enters(mime):
        return False
    QApplication.sendEvent(btn, QDropEvent(QPointF(btn.rect().center()), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    app.processEvents()     # the list is opened after the drop has been delivered
    return True
def shows(path, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        sd = cell.series_data()
        if sd is not None and os.path.realpath(sd.meta.series_dir) == os.path.realpath(path):
            return True
        time.sleep(0.02)
    return False
list_txt = os.path.join(ws_list, "list.txt")
foreign = QMimeData(); foreign.setText(list_txt)
image = QMimeData(); image.setData(drag_state.PATHS_MIME_TYPE, drag_state.encode_paths([images[0]]))
check("Open list… takes one dragged list file: no folder, image, several items or foreign drag",
      enters(dragged(list_txt)) and not enters(dragged(ws_list)) and not enters(image)
      and not enters(dragged(list_txt, os.path.join(ws_list, "cohort.csv"))) and not enters(foreign))
check("dropping the list opens it in list mode and loads its first item",
      drop(dragged(list_txt)) and dock._ws.mode == "list" and dock._ws.list_file == list_txt
      and len(dock._ws.items) == 2 and len(dock._ws.missing) == 1 and shows(dock._ws.items[0].path), dock._ws_lbl.text())
kept = dock._ws
shown.clear(); QTimer.singleShot(300, _close_box)
check("a dropped list without images is answered with a warning and the workspace stays",
      drop(dragged(os.path.join(ws_img, "notes.txt"))) and shown == ["Empty list"] and dock._ws is kept, str(shown))
drag_state.clear_payload()

# the enlarge button of a panel works with every tool; a double-click does not while drawing
on_screen = lambda: [c.isVisible() for c in quad.cells()]
big, small_w = cell._max_btn, canvas.width()
QTest.mouseDClick(canvas, Qt.LeftButton, Qt.NoModifier, canvas.rect().center()); app.processEvents()
ignored = canvas.wl_mode() == "rect" and not quad.is_fullscreen()
QTest.mouseClick(big, Qt.LeftButton); app.processEvents()
check("the enlarge button enlarges the panel while a drawing tool owns the double-click",
      ignored and quad.is_fullscreen() and big.isChecked() and canvas.wl_mode() == "rect"
      and on_screen() == [True, False, False, False] and canvas.width() > 1.5 * small_w, f"{small_w} → {canvas.width()}")
QTest.mouseClick(big, Qt.LeftButton); app.processEvents()
check("pressed again it brings the other panels back",
      not quad.is_fullscreen() and not big.isChecked() and on_screen() == [True] * 4
      and abs(canvas.width() - small_w) <= 2, f"{small_w} → {canvas.width()}")
other = quad.cells()[1]
QTest.mouseDClick(other.canvas(), Qt.LeftButton); app.processEvents()      # no tool on this panel yet
followed = quad.is_fullscreen() and other._max_btn.isChecked() and not big.isChecked()
QTest.mouseClick(other._max_btn, Qt.LeftButton); app.processEvents()
check("the button follows a double-click and takes it back",
      followed and not quad.is_fullscreen() and not other._max_btn.isChecked() and on_screen() == [True] * 4)
quad._set_active(cell); dock._apply_tool()

# hiding the dock restores W/L drag on all panels
win._ws_btn.setChecked(False); app.processEvents()
check("hiding dock restores drag mode", not dock.isVisible() and all(c.canvas().wl_mode() == "drag" for c in quad.cells()))
seen.clear(); n_asked = len(asked)
QTimer.singleShot(300, pick("Brush")); right_click(pt(0.5, 0.5)); QTest.qWait(400)
check("no tool menu while the Workspace is closed",
      len(asked) == n_asked + 1 and not seen and canvas.wl_mode() == "drag", str(seen))

win.close(); app.processEvents()
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
sys.exit(1 if n_fail else 0)
