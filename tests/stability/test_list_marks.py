"""List marks of the annotation workspace: running number, and ⚠ for an item that was saved
with neither a rectangle nor a mask (offscreen Qt)."""
import os, sys, csv, time, shutil, tempfile, types, importlib.util
os.environ["QT_QPA_PLATFORM"] = "offscreen"
SP = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(os.path.dirname(SP))

pkg = types.ModuleType("viewer_vidi"); pkg.__path__ = [SRC]; pkg.__package__ = "viewer_vidi"
pkg.__file__ = os.path.join(SRC, "__init__.py"); sys.modules["viewer_vidi"] = pkg
spec = importlib.util.spec_from_file_location("viewer_vidi", pkg.__file__); spec.loader.exec_module(pkg)

from PyQt5.QtWidgets import QApplication
from viewer_vidi import workspace as W

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))

# ── 1. workspace.py: the flag follows the manifest row ───────────────────────
check("a row with a rectangle is not empty", not W.row_is_empty(dict(status="saved", x0="1", y0="2", x1="9", y1="8", mask_pixels="0")))
check("a row with a mask only is not empty", not W.row_is_empty(dict(status="saved", x0="", y0="", x1="", y1="", mask_pixels="12")))
check("a saved row with neither is empty", W.row_is_empty(dict(status="saved", x0="", y0="", x1="", y1="", mask_pixels="0")))
check("a deleted row and no row are not empty", not W.row_is_empty(dict(status="deleted")) and not W.row_is_empty(None) and not W.row_is_empty({}))

tmp = tempfile.mkdtemp(prefix="vidi_marks_")
src = sorted(p for p in (os.path.join(SP, "ws_img", f) for f in os.listdir(os.path.join(SP, "ws_img"))) if p.endswith(".dcm"))
films = []
for k in range(4):                                   # four items from the two fixture films
    films.append(os.path.join(tmp, f"film{k + 1}.dcm")); shutil.copy(src[k % len(src)], films[-1])
out = os.path.join(tmp, "vidi_output"); os.makedirs(out)
with open(os.path.join(out, "manifest.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=W.MANIFEST_FIELDS); w.writeheader()
    w.writerow(dict(stem="film1", source="film1.dcm", status="saved", mask_pixels=0, x0=5, y0=6, x1=50, y1=60, formats="png", files="png/film1_roi.png"))
    w.writerow(dict(stem="film2", source="film2.dcm", status="saved", mask_pixels=0, formats="png", files="png/film2_image.png"))
    w.writerow(dict(stem="film3", source="film3.dcm", status="deleted"))
ws = W.build_workspace(tmp, "image", films)
flags = [(it.stem, it.done, it.empty, it.deleted) for it in ws.items]
check("reopening: with box = done, without = done + empty, deleted, pending",
      flags == [("film1", True, False, False), ("film2", True, True, False), ("film3", False, False, True), ("film4", False, False, False)]
      and ws.n_done == 2 and ws.n_empty == 1 and ws.n_deleted == 1, str(flags))

# ── 2. the dock: marks, numbers, counter; a save changes the mark ────────────
app = QApplication(sys.argv)
from viewer_vidi.main_window import MainWindow
win = MainWindow(); win.resize(1400, 900); win.show(); app.processEvents()
dock, cell = win._dock, win._quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
dock._set_workspace(ws)
def wait_loaded(path, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        sd = cell.series_data()
        if sd is not None and canvas.displayed_pixels() is not None and os.path.realpath(sd.meta.series_dir) == os.path.realpath(path):
            return True
        time.sleep(0.02)
    return False
rows = [dock._list.item(i).text() for i in range(4)]
check("rows read: mark, number, stem", rows == ["✓ 1  film1", "⚠ 2  film2", "⊘ 3  film3", "○ 4  film4"], str(rows))
check("the counter names the save without box or mask", "2 done" in dock._count_lbl.text() and "1 without box/mask" in dock._count_lbl.text(), dock._count_lbl.text())
check("only the ⚠ row explains itself in a tooltip", "no crop" in dock._list.item(1).toolTip() and dock._list.item(0).toolTip() == "")
check("the first pending item (4) is opened", dock._index == 3 and wait_loaded(films[3]))

for f, chk in dock._fmt_chk.items(): chk.setChecked(f == "png")
dock._image_chk.setChecked(True)                      # whole image only: no rectangle, no mask
dock._save(advance=False); app.processEvents()
check("saving the whole image only marks the item ⚠", ws.items[3].done and ws.items[3].empty and dock._list.item(3).text() == "⚠ 4  film4"
      and "2 without box/mask" in dock._count_lbl.text(), f"{dock._list.item(3).text()} · {dock._count_lbl.text()} · {dock._status_lbl.text()}")
canvas.set_annotations(None, (10, 12, 120, 140)); app.processEvents()
dock._save(advance=False); app.processEvents()
row4 = W.read_manifest(os.path.join(out, "manifest.csv")).get("film4", {})
check("saving again with a rectangle turns it into ✓", not ws.items[3].empty and dock._list.item(3).text() == "✓ 4  film4"
      and row4.get("x0") == "10" and os.path.isfile(os.path.join(out, "png", "film4_roi.png")) and "1 without box/mask" in dock._count_lbl.text(),
      f"{dock._list.item(3).text()} · {row4.get('x0')} · {dock._count_lbl.text()}")
dock.toggle_delete(); app.processEvents()
check("deleting clears the flag", ws.items[3].deleted and not ws.items[3].empty and dock._list.item(3).text().startswith("⊘ 4"))
ws2 = W.build_workspace(tmp, "image", films)
check("a reopened workspace shows the same marks", [(i.done, i.empty, i.deleted) for i in ws2.items] == [(i.done, i.empty, i.deleted) for i in ws.items])

win.close(); app.processEvents(); shutil.rmtree(tmp, ignore_errors=True)
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
sys.exit(1 if n_fail else 0)
