"""listparse lens — dock flows (Open list… / Open directory…) with dialogs monkeypatched.
usage: test_listparse_gui.py main | list <listfile> | dir <root>   (list/dir: one flow, for crash probing)"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
S = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/listparse"
L = os.path.join(S, "lists")
app, win = H.boot()
from PyQt5.QtWidgets import QFileDialog
dock, quad = win._dock, win._quad
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

def open_list(path, choose=None):
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, "Lists"))
    if not dock.isVisible():
        win._ws_btn.setChecked(True); app.processEvents()
    seen = H.auto_close_dialogs(app, 300, choose)
    t0 = time.time()
    dock._open_list_btn.click(); app.processEvents()
    dt = time.time() - t0
    H.pump(app, 400)
    return seen, dt

def open_dir(path, choose=None):
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
    if not dock.isVisible():
        win._ws_btn.setChecked(True); app.processEvents()
    seen = H.auto_close_dialogs(app, 300, choose)
    dock._open_dir_btn.click(); app.processEvents()
    H.pump(app, 400)
    return seen

mode = sys.argv[1] if len(sys.argv) > 1 else "main"
if mode == "list":
    seen, dt = open_list(sys.argv[2])
    print("survived; dialogs:", seen, "ws:", dock.workspace() and len(dock.workspace().items))
    win.close(); sys.exit(0)
if mode == "dir":
    seen = open_dir(sys.argv[2])
    print("survived; dialogs:", seen, "ws:", dock.workspace() and len(dock.workspace().items))
    win.close(); sys.exit(0)

cell = quad.active_cell(); canvas = cell.canvas()

# G1 all paths missing
seen, _ = open_list(os.path.join(L, "ten_k_missing.txt"))
check("G1 all-missing list: 'Empty list' warning, no workspace", seen and seen[0][1] == "Empty list" and dock.workspace() is None, repr(seen))

# G7 unreadable list file (EACCES)
seen, _ = open_list(os.path.join(L, "unreadable.txt"))
check("G7 unreadable list: warning text explains permission problem", seen and "ermission" in seen[0][2], repr(seen))

# G8 semicolon csv / G9 unknown header col2
seen, _ = open_list(os.path.join(L, "semicolon.csv"))
check("G8 semicolon.csv: warning", seen and seen[0][1] == "Empty list", repr(seen))
seen, _ = open_list(os.path.join(L, "hdr_unknown_col2.csv"))
check("G9 hdr_unknown_col2.csv: warning", seen and seen[0][1] == "Empty list", repr(seen))

# G2 series directory entry
seen, _ = open_list(os.path.join(L, "seriesdir.txt"))
ws = dock.workspace()
lbl, tip = dock._ws_lbl.text(), dock._ws_lbl.toolTip()
check("G2 seriesdir.txt: 1 item, label says 1 not found, tooltip names the dir", ws and len(ws.items) == 1 and "1 listed path(s) not found" in lbl and tip == os.path.join(S, "mr20"), f"label={lbl!r} tip={tip!r} dialogs={seen}")
check("G2 wording: an existing directory is reported as 'not found'", False, f"label={lbl.splitlines()[-1]!r}; os.path.isdir(tip)={os.path.isdir(tip)}")

# G5 BOM txt
seen, _ = open_list(os.path.join(L, "bom.txt"))
ws = dock.workspace(); lbl, tip = dock._ws_lbl.text(), dock._ws_lbl.toolTip()
check("G5 bom.txt: both entries become items", ws and len(ws.items) == 2 and not ws.missing, f"items={[it.stem for it in ws.items]} label_tail={lbl.splitlines()[-1]!r} tip={tip!r} tip_has_BOM={chr(0xfeff) in tip}")

# G6 duplicate entries
seen, _ = open_list(os.path.join(L, "dup.txt"))
ws = dock.workspace()
check("G6 dup.txt: same file listed 3x -> items", True, f"n_items={len(ws.items)} stems={[it.stem[-12:] for it in ws.items]} list_rows={dock._list.count()}")
H.wait_loaded(app, cell)
dock._fmt_chk["png"].setChecked(True)
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3))
dock._save(advance=True); app.processEvents(); H.wait_loaded(app, cell)
check("G6 after Save&Next on dup item 1: item 2 is the SAME file, pending again", ws.items[0].done and not ws.items[1].done and ws.items[1].path == ws.items[0].path and dock._index == 1, f"done={[it.done for it in ws.items]} index={dock._index}")
import shutil; shutil.rmtree(os.path.join(L, "vidi_output"), ignore_errors=True)

# G3 unknown extensions: items that cannot be opened
seen, _ = open_list(os.path.join(L, "unknown_ext.txt"))
ws = dock.workspace()
st = dock._status_lbl.text()
check("G3 unknown_ext.txt: 5 items, first (x.ima) -> 'Cannot open' status", len(ws.items) == 5 and st.startswith("Cannot open"), f"status={st!r} index={dock._index}")
check("G3 after failed first load: Next enabled?", dock._next_btn.isEnabled(), f"next={dock._next_btn.isEnabled()} prev={dock._prev_btn.isEnabled()} count={dock._count_lbl.text()!r} index={dock._index}")
dock._next_btn.click(); app.processEvents()
check("G3 Next from index -1 retries item 0 (stuck?)", dock._index != -1, f"index={dock._index} status={dock._status_lbl.text()!r}")
# double-click item 3 (42228791, loadable), then Prev twice -> noext_png fails
dock._load_index(3); H.wait_loaded(app, cell); app.processEvents()
check("G3 double-click on loadable item 3 works", dock._index == 3 and cell.series_data() is not None and cell.series_data().meta.series_dir == ws.items[3].path)
dock._prev_btn.click(); app.processEvents()
i1 = dock._index; s1 = dock._status_lbl.text()
dock._prev_btn.click(); app.processEvents()
i2 = dock._index; s2 = dock._status_lbl.text()
check("G3 Prev over an unloadable item skips it", i2 != 3, f"after Prev#1 index={i1} status={s1!r}; after Prev#2 index={i2} status={s2!r}")
# save while the failed item is 'current'? index stayed 3 so the loaded file matches; ok. Now what does save do after a failed load of item 2 — index still 3 and panel shows item 3 -> normal.

# G4 10k-entry list timing
seen, dt = open_list(os.path.join(L, "ten_k.txt"))
ws = dock.workspace()
ok = H.wait_loaded(app, cell)
check("G4 ten_k.txt: 6667 items, open+populate time", ws and len(ws.items) == 6667 and dt < 3.0, f"open={dt:.2f}s loaded={ok} list_rows={dock._list.count()} label_tail={dock._ws_lbl.text().splitlines()[-1]!r}")

# G10 Open directory… on a root with a huge README.txt (timing on GUI thread)
t0 = time.time(); seen = open_dir(os.path.join(S, "root_readme")); dt = time.time() - t0
check("G10 Open directory… root_readme (22MB README.txt): image mode, time", dock.workspace() and dock.workspace().mode == "image", f"{dt:.2f}s dialogs={seen}")

# G11 README with a bare 'LICENSE.txt' line -> mode prompt on an image folder
seen = open_dir(os.path.join(S, "root_readme_bare"), choose="List mode")
ws = dock.workspace()
check("G11 root_readme_bare: no mode prompt for an image folder whose README names a file", not seen, f"dialogs={seen} ws.mode={ws.mode} items={[it.stem for it in ws.items]} missing={[os.path.basename(m) for m in ws.missing]} status={dock._status_lbl.text()!r}")

# G12 root with only a list naming missing files
seen = open_dir(os.path.join(S, "root_missing_only"))
check("G12 root_missing_only: 'Empty workspace' info", seen and seen[0][1] == "Empty workspace", repr(seen))

win.close(); app.processEvents()
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
