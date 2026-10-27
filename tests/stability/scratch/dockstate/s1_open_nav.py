"""dockstate lens, part 1: opening workspaces, list warnings, navigation bounds,
double-click while loading, deleted file mid-job. Dialogs driven through the real
_open_dir/_open_list slots by stubbing the static QFileDialog pickers."""
import os, sys, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFileDialog



app, win = H.boot()
from viewer_vidi import workspace as W
from viewer_vidi import annotation_dock as AD
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()

def stub_dir(path):
    AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
def stub_file(path):
    AD.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, ""))

wsA = fresh_ws("A")           # 4 dicoms
wsB = fresh_ws("B", n=2)      # 2 dicoms

@scenario("open same root twice")
def t1():
    win._ws_btn.setChecked(True); app.processEvents()
    stub_dir(wsA); dock._open_dir(); H.wait_loaded(app, cell)
    check("A: 4 items, index 0, count label", dock._list.count() == 4 and dock._index == 0
          and dock._count_lbl.text() == "1/4 · 0 done", f"{dock._list.count()} {dock._index} '{dock._count_lbl.text()}'")
    check("A: ws label IMAGE mode", "IMAGE mode" in dock._ws_lbl.text() and "4 items, 0 done" in dock._ws_lbl.text(), dock._ws_lbl.text())
    # draw + save item 0 so a manifest exists, then reopen the same root
    stroke(app, canvas); dock._save(advance=False); app.processEvents()
    check("A: item0 done after save", dock._ws.items[0].done and dock._count_lbl.text() == "1/4 · 1 done", dock._count_lbl.text())
    dock._step(+1); H.wait_loaded(app, cell)
    stroke(app, canvas)              # unsaved work on item 1
    n_before = canvas.mask_pixels()
    stub_dir(wsA); dock._open_dir(); H.wait_loaded(app, cell)
    check("reopen same root: 4 items, jumps to first pending (1), 1 done",
          dock._list.count() == 4 and dock._index == 1 and dock._ws.n_done == 1
          and dock._list.item(0).text().startswith("✓"), f"n={dock._list.count()} idx={dock._index} done={dock._ws.n_done}")
    check("reopen: unsaved mask of the reloaded item is discarded (fresh canvas)", canvas.mask_pixels() == 0, f"{n_before} -> {canvas.mask_pixels()}")
    check("reopen: status cleared", dock._status_lbl.text() == "", repr(dock._status_lbl.text()))
    check("reopen: tool mode still paint", canvas.wl_mode() == "paint", canvas.wl_mode())
    check("invariants", not H.invariants(canvas), str(H.invariants(canvas)))
t1()

@scenario("open a different root")
def t2():
    stub_dir(wsB); dock._open_dir(); H.wait_loaded(app, cell)
    check("B: 2 items, index 0, 0 done", dock._list.count() == 2 and dock._index == 0 and dock._ws.n_done == 0
          and dock._count_lbl.text() == "1/2 · 0 done", f"{dock._list.count()} {dock._index} {dock._count_lbl.text()}")
    check("B: label names root B", dock._ws_lbl.text().startswith(wsB), dock._ws_lbl.text().splitlines()[0])
    check("B: loaded file belongs to B", cell.series_data().meta.series_dir.startswith(wsB), cell.series_data().meta.series_dir)
    check("B: prev disabled, next enabled", not dock._prev_btn.isEnabled() and dock._next_btn.isEnabled())
t2()

@scenario("open list: all paths missing")
def t3():
    lf = os.path.join(WSROOT, "all_missing.txt")
    with open(lf, "w") as f: f.write("/nonexistent/a.dcm\n/nonexistent/b.dcm\n")
    before = (dock._ws.root, dock._index, dock._list.count())
    stub_file(lf)
    seen = H.auto_close_dialogs(app, 200)
    dock._open_list(); app.processEvents()
    check("warning box 'Empty list' shown", any(s[1] == "Empty list" for s in seen), str(seen))
    check("workspace unchanged after refused list", (dock._ws.root, dock._index, dock._list.count()) == before, str(before))
t3()

@scenario("open list: some paths missing")
def t4():
    lf = os.path.join(WSROOT, "some_missing.txt")
    with open(lf, "w") as f:
        f.write(f"{wsA}/bpd1_20100101_1.dcm\n/nonexistent/zzz.dcm\n{wsA}/sub/bpd1_20100102_1.dcm\nrelative_missing.dcm\n")
    stub_file(lf)
    seen = H.auto_close_dialogs(app, 200)
    dock._open_list(); H.wait_loaded(app, cell)
    check("no dialog for partially-missing list", seen == [], str(seen))
    check("2 items loaded, LIST mode label", dock._list.count() == 2 and "LIST mode" in dock._ws_lbl.text(), dock._ws_lbl.text())
    check("status text reports 2 missing", "2 listed path(s) not found" in dock._ws_lbl.text(), dock._ws_lbl.text())
    tip = dock._ws_lbl.toolTip()
    check("tooltip lists both missing paths (relative resolved against list dir)",
          "/nonexistent/zzz.dcm" in tip and os.path.join(WSROOT, "relative_missing.dcm") in tip, tip)
    check("list-mode root is the list's dir", dock._ws.root == WSROOT, dock._ws.root)
t4()

@scenario("open dir holding images AND a list: mode box")
def t5():
    wsC = fresh_ws("C", n=2)
    with open(os.path.join(wsC, "job.txt"), "w") as f: f.write("bpd1_20100101_1.dcm\n")
    stub_dir(wsC)
    seen = H.auto_close_dialogs(app, 200, choose="Image mode")
    dock._open_dir(); H.wait_loaded(app, cell)
    check("mode box shown, Image mode chosen -> 2 items IMAGE", any(s[1] == "Workspace mode" for s in seen)
          and dock._ws.mode == "image" and dock._list.count() == 2, f"{seen} mode={dock._ws.mode} n={dock._list.count()}")
    seen = H.auto_close_dialogs(app, 200, choose="List mode")
    dock._open_dir(); H.wait_loaded(app, cell)
    check("List mode chosen -> 1 item LIST (single list, no chooser)", dock._ws.mode == "list" and dock._list.count() == 1
          and dock._ws.list_file.endswith("job.txt"), f"mode={dock._ws.mode} n={dock._list.count()}")
    # two lists -> QInputDialog chooser; auto_close rejects it -> workspace must stay as is
    with open(os.path.join(wsC, "job2.lst"), "w") as f: f.write("bpd1_20100101_2.dcm\n")
    before = (dock._ws.list_file, dock._index)
    seen = H.auto_close_dialogs(app, 200, choose="List mode")
    seen2 = H.auto_close_dialogs(app, 700)       # second timer: reject the QInputDialog
    dock._open_dir(); app.processEvents()
    check("cancelled list chooser leaves workspace untouched", (dock._ws.list_file, dock._index) == before
          and any(s[0] == "QInputDialog" for s in seen + seen2), f"{seen} {seen2}")
    # cancel on the mode box
    seen = H.auto_close_dialogs(app, 200)   # reject -> Cancel
    dock._open_dir(); app.processEvents()
    check("Cancel on mode box leaves workspace untouched", (dock._ws.list_file, dock._index) == before)
t5()

@scenario("open an empty directory")
def t6():
    empty = os.path.join(WSROOT, "empty"); os.makedirs(empty, exist_ok=True)
    stub_dir(empty)
    before = (dock._ws.root, dock._list.count())
    seen = H.auto_close_dialogs(app, 200)
    dock._open_dir(); app.processEvents()
    check("'Empty workspace' info box; previous workspace kept", any(s[1] == "Empty workspace" for s in seen)
          and (dock._ws.root, dock._list.count()) == before, str(seen))
    # cancelled picker
    stub_dir("")
    dock._open_dir(); app.processEvents()
    check("cancelled dir picker is a no-op", (dock._ws.root, dock._list.count()) == before)
    stub_file("")
    dock._open_list(); app.processEvents()
    check("cancelled list picker is a no-op", (dock._ws.root, dock._list.count()) == before)
t6()

@scenario("Prev at 0 / Next at end, direct _step calls")
def t7():
    stub_dir(wsB); dock._open_dir(); H.wait_loaded(app, cell)
    check("at 0: prev disabled", not dock._prev_btn.isEnabled())
    dock._step(-1); app.processEvents()
    check("_step(-1) at 0 is a no-op", dock._index == 0 and dock._count_lbl.text() == "1/2 · 0 done", dock._count_lbl.text())
    dock._step(+1); H.wait_loaded(app, cell)
    check("at end: next disabled, prev enabled", not dock._next_btn.isEnabled() and dock._prev_btn.isEnabled())
    sd_before = cell.series_data()
    dock._step(+1); app.processEvents()
    check("_step(+1) at end is a no-op (no reload)", dock._index == 1 and cell.series_data() is sd_before)
    dock._step(+5); dock._step(-5); app.processEvents()
    check("big steps are no-ops", dock._index == 1 and cell.series_data() is sd_before)
    check("list row follows index", dock._list.currentRow() == 1)
t7()

@scenario("Prev/Next with no workspace")
def t8():
    dock._ws = None; dock._index = -1; dock._list.clear(); dock._update_nav()
    dock._prev_btn.click(); dock._next_btn.click(); dock._step(1); dock._step(-1); app.processEvents()
    check("nav with no workspace: no exception, both disabled, empty count", not dock._prev_btn.isEnabled()
          and not dock._next_btn.isEnabled() and dock._count_lbl.text() == "")
    dock._load_index(0); dock._load_index(-1)
    check("_load_index with no workspace is a no-op", dock._index == -1)
t8()

@scenario("double-click a list item while another is loading")
def t9():
    stub_dir(wsA); dock._open_dir()          # item 0 loading asynchronously
    # immediately double-click item 3 (not wait_loaded)
    it = dock._list.item(3)
    dock._list.itemDoubleClicked.emit(it); app.processEvents()
    check("index switched to 3 immediately", dock._index == 3, str(dock._index))
    ok = H.wait_loaded(app, cell)
    H.pump(app, 400)   # let any late signal from the cancelled load arrive
    sd = cell.series_data()
    check("loaded file is item 3", ok and sd is not None and os.path.abspath(sd.meta.series_dir) == os.path.abspath(dock._ws.items[3].path),
          sd.meta.series_dir if sd else None)
    px = canvas.displayed_pixels()
    check("mask matches displayed pixels, invariants ok", canvas.mask() is not None and canvas.mask().shape == px.shape and not H.invariants(canvas),
          str(H.invariants(canvas)))
    check("tool mode paint after racing loads", canvas.wl_mode() == "paint", canvas.wl_mode())
    # rapid-fire: open, step, step, dclick without waiting
    stub_dir(wsA); dock._open_dir(); dock._step(+1); dock._step(+1); dock._list.itemDoubleClicked.emit(dock._list.item(0)); app.processEvents()
    ok = H.wait_loaded(app, cell); H.pump(app, 400)
    sd = cell.series_data()
    check("rapid open/step/step/dclick ends on item 0", ok and dock._index == 0 and os.path.abspath(sd.meta.series_dir) == os.path.abspath(dock._ws.items[0].path),
          f"idx={dock._index} {sd.meta.series_dir if sd else None}")
    check("invariants after rapid-fire", not H.invariants(canvas), str(H.invariants(canvas)))
t9()

@scenario("item file deleted after opening: Next gets stuck?")
def t10():
    wsD = fresh_ws("D", n=4)
    stub_dir(wsD); dock._open_dir(); H.wait_loaded(app, cell)
    os.remove(os.path.join(wsD, "bpd1_20100101_2.dcm"))     # item 1 vanishes
    dock._step(+1); app.processEvents()
    check("Next onto a deleted item: status 'Cannot open', index stays 0", dock._index == 0 and dock._status_lbl.text().startswith("Cannot open"), dock._status_lbl.text())
    dock._step(+1); app.processEvents()
    check("second Next still stuck at 0 (cannot skip past deleted item with Next)", dock._index == 0, str(dock._index))
    dock._list.itemDoubleClicked.emit(dock._list.item(2)); ok = H.wait_loaded(app, cell)
    check("double-click item 2 recovers", ok and dock._index == 2)
    # Save & Next with the next item deleted
    stroke(app, canvas)
    os.remove(os.path.join(wsD, "sub", "bpd1_20100102_1.dcm"))  # item 3 vanishes
    dock.save_and_next(); app.processEvents()
    check("Save&Next: item 2 saved, stays at 2, status overwritten by 'Cannot open'", dock._ws.items[2].done and dock._index == 2,
          f"idx={dock._index} status={dock._status_lbl.text()!r}")
    check("invariants", not H.invariants(canvas))
t10()

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
