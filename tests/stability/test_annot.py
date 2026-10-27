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
check("export writes 4 products × 3 formats", len(written) == 12, str(written))
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

# save with all formats → files + manifest + done flag + advance
for chk in dock._fmt_chk.values(): chk.setChecked(True)
dock._image_chk.setChecked(True)
stem0 = ws.items[0].stem
dock._save(advance=True); app.processEvents()
outd = os.path.join(ws_img, "vidi_output")
expect_files = [os.path.join(outd, f, f"{stem0}_{s}{e}") for f, e in (("png", ".png"), ("jpeg", ".jpg"), ("nifti", ".nii.gz")) for s in ("image", "mask", "roi", "roi_mask")]
missing = [p for p in expect_files if not os.path.isfile(p)]
check("save writes 12 files in 3 format dirs", not missing, f"missing {missing}" if missing else "")
man = W.read_manifest(os.path.join(outd, "manifest.csv"))
check("manifest records the item with rect + mask pixels", stem0 in man and int(man[stem0]["mask_pixels"]) == n_poly and man[stem0]["x0"] == str(rect[0]), str(man.get(stem0)))
check("item marked done and job advanced", dock._ws.items[0].done and dock._index == 1 and dock._list.item(0).text().startswith("✓"))
check("next item loads with a fresh mask", wait_loaded() and canvas.mask_pixels() == 0 and canvas.crop_rect() is None)
pm = np.array(Image.open(os.path.join(outd, "png", f"{stem0}_mask.png")))
check("saved mask matches canvas shape and count", pm.shape == (H, Wd) and (pm == 255).sum() == n_poly)
img8 = np.array(Image.open(os.path.join(outd, "png", f"{stem0}_image.png")))
check("saved image is 8-bit with the image shape", img8.dtype == np.uint8 and img8.shape == (H, Wd) and img8.max() > img8.min())

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
dock._save(advance=False); app.processEvents()
man = W.read_manifest(os.path.join(outd, "manifest.csv"))
check("saving a deleted item restores it (status saved)",
      not it1b.deleted and it1b.done and man[it1b.stem]["status"] == "saved")
dock.toggle_delete(); app.processEvents()
check("deleting a saved item removes its products",
      it1b.deleted and not any(f.startswith(it1b.stem) for f in os.listdir(os.path.join(outd, "png"))))
dock.toggle_delete(); app.processEvents()   # leave it pending for the remaining checks

# hiding the dock restores W/L drag on all panels
win._ws_btn.setChecked(False); app.processEvents()
check("hiding dock restores drag mode", not dock.isVisible() and all(c.canvas().wl_mode() == "drag" for c in quad.cells()))

win.close(); app.processEvents()
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
sys.exit(1 if n_fail else 0)
