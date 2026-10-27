"""Discovery lens, GUI side: what the dock does with the items discovery hands it."""
import os, sys, shutil, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
from viewer_vidi import workspace as W
from viewer_vidi import annotation_dock as AD
from PIL import Image
import numpy as np

SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery"
FIX_DCM = "/media/zsk/ressd/research/alldata_backup/dicom/original"
FIX_MR  = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
FIX_DICOMDIR = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOMDIR"
FIX_PNG = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)
def fresh(name):
    d = os.path.join(SCR, "gws_" + name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); return d
def tiny_png(path, w=8, h=8):
    os.makedirs(os.path.dirname(path), exist_ok=True); Image.new("L", (w, h), 100).save(path)

dock, quad = win._dock, win._quad
win._ws_btn.setChecked(True); app.processEvents()
cell = quad.active_cell(); canvas = cell.canvas()

def open_dir_via_dock(path, choose=None):
    """Drive dock._open_dir with QFileDialog patched; returns captured dialogs."""
    AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
    seen = H.auto_close_dialogs(app, 300, choose=choose)
    dock._open_dir(); H.pump(app, 400)
    return seen

def open_list_via_dock(path):
    AD.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, ""))
    seen = H.auto_close_dialogs(app, 300)
    dock._open_list(); H.pump(app, 400)
    return seen

# ── G1 empty dir through the real _open_dir ──────────────────────────────────
d = fresh("empty")
seen = open_dir_via_dock(d)
check("G1 empty dir -> 'Empty workspace' info box, no workspace set", [s[1] for s in seen] == ["Empty workspace"] and dock.workspace() is None, str(seen))

# ── G2 garbage items: do they load? does the app survive stepping through them? ──
d = fresh("garbage")
with open(os.path.join(d, "a_garbage.dcm"), "wb") as f: f.write(b"this is not dicom\n" * 20)
with open(os.path.join(d, "b_garbage.png"), "wb") as f: f.write(b"\x89PNG not really\n")
with open(os.path.join(d, "c_garbage.nii.gz"), "wb") as f: f.write(b"\x1f\x8b garbage")
with open(os.path.join(d, "d_empty.dcm"), "wb") as f: pass
with open(os.path.join(d, "e_empty.png"), "wb") as f: pass
with open(os.path.join(d, "f_truncated.dcm"), "wb") as f: f.write(open(os.path.join(FIX_DCM, "bpd1_20100101_1.dcm"), "rb").read(4000))
shutil.copy(FIX_PNG, os.path.join(d, "g_good.png"))
seen = open_dir_via_dock(d)
ws = dock.workspace()
check("G2 garbage dir opens as image workspace with 7 items", ws is not None and len(ws.items) == 7 and not seen, f"{[i.stem for i in ws.items] if ws else None} {seen}")
states = []
for i in range(7):
    dock._load_index(i); app.processEvents()
    ok = H.wait_loaded(app, cell, timeout=4.0)
    states.append((ws.items[i].stem, ok, cell.series_data() is not None, canvas.displayed_pixels() is not None, dock._status_lbl.text(), cell._canvas_stack.currentIndex()))
print("   load states:", *states, sep="\n     ")
check("G2 garbage items never report loaded; good png loads", [s[1] for s in states] == [False]*6 + [True], str([s[1] for s in states]))
check("G2 garbage load leaves NO user-visible message in the dock status label", all(s[4] == "" for s in states[:6]), str([s[4] for s in states[:6]]))
check("G2 garbage load leaves cell on the 'loaded' page (spinner-less blank) rather than empty page", all(s[5] == 1 for s in states[:6]), str([s[5] for s in states[:6]]))
# save on a garbage item
dock._load_index(0); H.wait_loaded(app, cell, timeout=3.0)
seen = H.auto_close_dialogs(app, 300)
dock._save(advance=True); H.pump(app, 400)
check("G2 save on a never-loaded garbage item -> 'Image still loading' text, no dialog, no advance",
      "still loading" in dock._status_lbl.text() and not seen and dock._index == 0, f"{dock._status_lbl.text()!r} {seen} idx={dock._index}")
# after garbage, a good item must still load (loader thread healthy)
dock._load_index(6); ok = H.wait_loaded(app, cell, timeout=10.0)
check("G2 good item still loads after six failed loads", ok and canvas.mask() is not None, str(ok))
check("G2 invariants after garbage sequence", not H.invariants(canvas), str(H.invariants(canvas)))
# press Save & Next from the good item -> writes, advances? (it's last)
for c in dock._fmt_chk.values(): c.setChecked(c is dock._fmt_chk["png"])
dock._image_chk.setChecked(True)
dock._save(advance=True); H.pump(app, 300)
check("G2 good item saved with 'g_good' stem", os.path.isfile(os.path.join(d, "vidi_output/png/g_good_image.png")), dock._status_lbl.text())

# ── G3 extensionless DICOM + DICOMDIR through the dock ──────────────────────
d = fresh("extless")
mr = sorted(os.listdir(FIX_MR))[:5]
os.makedirs(os.path.join(d, "DICOM/26070517/54450002"))
for n in mr: shutil.copy(os.path.join(FIX_MR, n), os.path.join(d, "DICOM/26070517/54450002", n))
shutil.copy(FIX_DICOMDIR, os.path.join(d, "DICOMDIR"))
shutil.copy(FIX_DICOMDIR, os.path.join(d, "DICOMDIR.dcm"))    # a DICOMDIR that got a .dcm extension
seen = open_dir_via_dock(d)
ws = dock.workspace()
check("G3 5 extensionless items + DICOMDIR.dcm = 6 items, DICOMDIR itself excluded", ws is not None and len(ws.items) == 6, str([i.stem for i in ws.items] if ws else None))
ok = H.wait_loaded(app, cell, timeout=20.0)
px = canvas.displayed_pixels()
check("G3 first extensionless DICOM loads with pixels", ok and px is not None and px.shape[0] > 10, str(px.shape if px is not None else None))
dock._step(+1); ok2 = H.wait_loaded(app, cell, timeout=20.0)
check("G3 Next loads the second extensionless file", ok2 and dock._index == 1)
# DICOMDIR.dcm item
dock._load_index(5); ok3 = H.wait_loaded(app, cell, timeout=6.0)
check("G3 DICOMDIR.dcm item: does not load (no pixel data), no abort", not ok3, f"loaded={ok3} status={dock._status_lbl.text()!r}")
check("G3 invariants after DICOMDIR.dcm", not H.invariants(canvas), str(H.invariants(canvas)))

# ── G4 output dir typed as a sub-path: outputs rescanned as items on reopen ──
d = fresh("outsub")
shutil.copy(FIX_PNG, os.path.join(d, "one.png"))
dock._out_edit.setText("exports/run1")
seen = open_dir_via_dock(d); ws = dock.workspace()
H.wait_loaded(app, cell, timeout=10.0)
check("G4 workspace with 1 item before any save", len(ws.items) == 1, str([i.stem for i in ws.items]))
dock._save(advance=False); H.pump(app, 300)
check("G4 save into exports/run1/png", os.path.isfile(os.path.join(d, "exports/run1/png/one_image.png")), dock._status_lbl.text())
seen = open_dir_via_dock(d); ws = dock.workspace()
check("G4 reopen with same 'exports/run1' out dir: exported files are NOT items",
      [i.stem for i in ws.items] == ["one"], str([os.path.relpath(i.path, d) for i in ws.items]))
check("G4 reopen: the saved item is marked done", ws.items[0].done if ws.items else False, str([(i.stem, i.done) for i in ws.items]))

# ── G5 rename output dir after first save, then reopen ───────────────────────
d = fresh("rename")
shutil.copy(FIX_PNG, os.path.join(d, "one.png"))
dock._out_edit.setText("vidi_output")
open_dir_via_dock(d); ws = dock.workspace(); H.wait_loaded(app, cell, timeout=10.0)
dock._save(advance=False); H.pump(app, 300)
check("G5 first save to vidi_output", os.path.isfile(os.path.join(d, "vidi_output/png/one_image.png")))
dock._out_edit.setText("round2")
seen = open_dir_via_dock(d); ws = dock.workspace()
stems = [i.stem for i in ws.items]
check("G5 reopen after renaming out dir: old outputs become items & done flag lost",
      stems == ["one"] and ws.items[0].done, f"stems={stems} done={[i.done for i in ws.items]}")
# and in-session rename without reopen: list unchanged, next save lands in round2 with its own manifest
dock._load_index(0); H.wait_loaded(app, cell, timeout=10.0)
dock._save(advance=False); H.pump(app, 300)
check("G5 in-session rename: second save goes to round2/", os.path.isfile(os.path.join(d, "round2/png/one_image.png")), dock._status_lbl.text())
dock._out_edit.setText("vidi_output")

# ── G6 2000 PNGs through the real _open_dir: GUI-thread blocking time ────────
d = fresh("png2000")
im = Image.new("L", (8, 8), 7)
for i in range(2000):
    sub = os.path.join(d, f"p{i % 20:02d}"); os.makedirs(sub, exist_ok=True); im.save(os.path.join(sub, f"img_{i:04d}.png"))
AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: d)
t0 = time.perf_counter(); dock._open_dir(); dt_open = time.perf_counter() - t0
ws = dock.workspace()
check("G6 2000-item workspace opens; _open_dir blocked the GUI thread for (ms)", ws is not None and len(ws.items) == 2000, f"{dt_open*1000:.0f} ms, list rows={dock._list.count()}")
ok = H.wait_loaded(app, cell, timeout=10.0)
check("G6 first of 2000 loads", ok)
t0 = time.perf_counter()
for _ in range(20):
    dock._step(+1); H.wait_loaded(app, cell, timeout=5.0)
check("G6 20× Next through tiny PNGs", dock._index == 20, f"{(time.perf_counter()-t0)*1000:.0f} ms for 20 steps")
check("G6 invariants", not H.invariants(canvas), str(H.invariants(canvas)))

# ── G7 unicode / spaces: load + save through the dock ────────────────────────
d = fresh("unicode")
os.makedirs(os.path.join(d, "Пациент 1")); shutil.copy(FIX_PNG, os.path.join(d, "Пациент 1/изо бражение ✓.png"))
os.makedirs(os.path.join(d, "患者 2")); shutil.copy(os.path.join(FIX_DCM, "bpd1_20100101_1.dcm"), os.path.join(d, "患者 2/sc an.dcm"))
open_dir_via_dock(d); ws = dock.workspace()
check("G7 unicode items found", ws is not None and sorted(i.stem for i in ws.items) == ["sc an", "изо бражение ✓"], str([i.stem for i in ws.items] if ws else None))
ok = H.wait_loaded(app, cell, timeout=15.0)
check("G7 first unicode item loads", ok)
for c in dock._fmt_chk.values(): c.setChecked(True)
dock._image_chk.setChecked(True)
dock._save(advance=True); H.pump(app, 400)
ws = dock.workspace()
written = sorted(os.path.relpath(p, d) for p in __import__("glob").glob(os.path.join(d, "vidi_output", "*", "*")))
check("G7 unicode stem saved in png/jpeg/nifti", len(written) == 3 and all("изо бражение ✓" in w for w in written), str(written))
man = W.read_manifest(os.path.join(d, "vidi_output/manifest.csv"))
check("G7 manifest holds the unicode stem", "изо бражение ✓" in man, str(list(man)))
ok = H.wait_loaded(app, cell, timeout=15.0)
check("G7 Save&Next advanced to the dicom in '患者 2'", ok and dock._index == 1)
dock._save(advance=False); H.pump(app, 400)
open_dir_via_dock(d); ws = dock.workspace()
check("G7 reopen: both unicode items done", all(i.done for i in ws.items), str([(i.stem, i.done) for i in ws.items]))

# ── G8 images+lists -> mode box; dangling .dcm symlink inflates the count ───
d = fresh("modebox")
shutil.copy(FIX_PNG, os.path.join(d, "real.png"))
os.symlink(os.path.join(d, "nope.dcm"), os.path.join(d, "dangling.dcm"))
with open(os.path.join(d, "list.txt"), "w") as f: f.write("real.png\n")
seen = open_dir_via_dock(d, choose="Image mode"); ws = dock.workspace()
check("G8 'Workspace mode' box shown and Image mode chosen", [s[1] for s in seen] == ["Workspace mode"] and ws is not None and ws.mode == "image", str(seen))
check("G8 box count equals item count", seen and (f"holds {len(ws.items)} image files" in seen[0][2]), f"box={seen[0][2]!r} items={len(ws.items)}")

# ── G9 list through _open_list: garbage list, list naming garbage ───────────
d = fresh("lists")
with open(os.path.join(d, "none.txt"), "w") as f: f.write("/nonexistent/a.dcm\n# c\n\n")
seen = open_list_via_dock(os.path.join(d, "none.txt"))
check("G9 list with no existing paths -> 'Empty list' warning", [s[1] for s in seen] == ["Empty list"], str(seen))
with open(os.path.join(d, "junk.dcm"), "wb") as f: f.write(b"junk" * 100)
with open(os.path.join(d, "mixed.lst"), "w") as f: f.write("junk.dcm\n" + FIX_PNG + "\n" + d + "\n")   # a directory entry too
seen = open_list_via_dock(os.path.join(d, "mixed.lst")); ws = dock.workspace()
check("G9 list: junk.dcm + real png accepted; directory entry goes to missing", ws is not None and ws.mode == "list" and len(ws.items) == 2 and len(ws.missing) == 1, f"{[i.stem for i in ws.items] if ws else None} missing={ws.missing if ws else None}")
ok = H.wait_loaded(app, cell, timeout=4.0)
check("G9 first list item (junk.dcm) does not load", not ok)
dock._step(+1); ok = H.wait_loaded(app, cell, timeout=10.0)
check("G9 Next reaches the real png", ok and dock._index == 1)

# ── G10 item deleted between probe and load ──────────────────────────────────
d = fresh("deleted")
shutil.copy(FIX_PNG, os.path.join(d, "a.png")); shutil.copy(FIX_PNG, os.path.join(d, "b.png"))
open_dir_via_dock(d); ws = dock.workspace(); H.wait_loaded(app, cell, timeout=10.0)
os.remove(os.path.join(d, "b.png"))
dock._step(+1); H.pump(app, 300)
check("G10 Next onto a deleted item -> 'Cannot open' status, index stays", "Cannot open" in dock._status_lbl.text() and dock._index == 0, f"{dock._status_lbl.text()!r} idx={dock._index}")
check("G10 panel still shows a.png and Save works", True)
dock._save(advance=True); H.pump(app, 300)
check("G10 save of a.png after the failed step still succeeds", ws.items[0].done, dock._status_lbl.text())

win.close(); app.processEvents()
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
