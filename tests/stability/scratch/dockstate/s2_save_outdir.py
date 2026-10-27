"""dockstate lens, part 2: Save guards and Output-dir handling."""
import os, sys, time, csv
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
app, win = H.boot()
from viewer_vidi import workspace as W
from viewer_vidi import annotation_dock as AD
from viewer_vidi.tree_panel import _make_series_meta
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
def stub_dir(path): AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
def set_fmts(**kw):
    for k, chk in dock._fmt_chk.items(): chk.setChecked(kw.get(k, False))
def reset_export():
    set_fmts(png=True); dock._mask_chk.setChecked(True); dock._crop_chk.setChecked(True); dock._image_chk.setChecked(False)
    dock._out_edit.setText("vidi_output")
def open_ws(root):
    stub_dir(root); dock._open_dir(); return H.wait_loaded(app, cell)

win._ws_btn.setChecked(True); app.processEvents()
wsA = fresh_ws("S_A")

@scenario("save with no formats ticked")
def t1():
    reset_export(); open_ws(wsA); stroke(app, canvas)
    set_fmts()
    dock._save(advance=True); app.processEvents()
    check("status asks for a format; item pending; no advance; no out dir",
          dock._status_lbl.text().startswith("Tick at least one format") and not dock._ws.items[0].done and dock._index == 0
          and not os.path.exists(os.path.join(wsA, "vidi_output")), dock._status_lbl.text())
t1()

@scenario("save with nothing drawn and Original unticked")
def t2():
    reset_export(); open_ws(wsA)
    check("fresh item: mask 0, no rect", canvas.mask_pixels() == 0 and canvas.crop_rect() is None)
    dock._save(advance=True); app.processEvents()
    check("'Nothing to save' message; item pending; no advance", "Nothing to save" in dock._status_lbl.text() and not dock._ws.items[0].done and dock._index == 0, dock._status_lbl.text())
    check("no output dir / manifest created by an empty save", not os.path.exists(os.path.join(wsA, "vidi_output")), str(listdir_rel(wsA)))
    # mask ticked off, a stroke drawn, crop ticked, no rect → also nothing
    stroke(app, canvas); dock._mask_chk.setChecked(False)
    dock._save(advance=False); app.processEvents()
    check("mask drawn but Mask unticked, no rect → nothing to save", "Nothing to save" in dock._status_lbl.text() and not dock._ws.items[0].done, dock._status_lbl.text())
t2()

@scenario("save with Original only")
def t3():
    reset_export(); open_ws(wsA)
    dock._image_chk.setChecked(True); set_fmts(png=True, nifti=True)
    stem = dock._ws.items[0].stem
    dock._save(advance=False); app.processEvents()
    files = listdir_rel(os.path.join(wsA, "vidi_output"))
    check("Original only: exactly image files + manifest", sorted(files) == sorted(["manifest.csv", f"png/{stem}_image.png", f"nifti/{stem}_image.nii.gz"]), str(files))
    man = W.read_manifest(os.path.join(wsA, "vidi_output", "manifest.csv"))
    check("manifest row: mask_pixels 0, empty rect, formats 'png nifti'", man[stem]["mask_pixels"] == "0" and man[stem]["x0"] == "" and man[stem]["formats"] == "png nifti", str(man[stem]))
    check("item done, status 'Saved 2 file(s)'", dock._ws.items[0].done and dock._status_lbl.text().startswith("Saved 2 file(s)"), dock._status_lbl.text())
t3()

@scenario("save with an EMPTY active panel (sd None)")
def t4():
    reset_export(); ws4 = fresh_ws("S_A4"); open_ws(ws4)
    other = quad.cell_at(1)
    quad._set_active(other); app.processEvents()   # switch the active panel to an empty one
    check("other panel empty", other.series_data() is None and other.canvas().displayed_pixels() is None)
    check("tool follows active panel (empty cell in paint mode)", other.canvas().wl_mode() == "paint", other.canvas().wl_mode())
    seen = H.auto_close_dialogs(app, 200)
    dock._save(advance=True); app.processEvents()
    check("no dialog; item stays pending; index unchanged", seen == [] and not dock._ws.items[0].done and dock._index == 0, str(seen))
    check("status text (says 'Image still loading' although the panel is simply empty)", dock._status_lbl.text() != "", dock._status_lbl.text())
    # undo/clear/stats on the empty active panel
    dock._undo_btn.click(); dock._clear_btn.click(); app.processEvents()
    check("undo/clear on empty active panel: no crash, stats label 0", dock._stats_lbl.text() == "mask 0 px · no rectangle", dock._stats_lbl.text())
    check("Ctrl+S via shortcut on empty panel: no crash", (H.key(win, Qt.Key_S, Qt.ControlModifier), app.processEvents(), True)[2])
    quad._set_active(cell); app.processEvents()
    check("back on the item panel: stats show its mask", dock._stats_lbl.text().startswith("mask 0 px"), dock._stats_lbl.text())
t4()

@scenario("save after loading a different file into the active cell")
def t5():
    reset_export(); ws5 = fresh_ws("S_A5"); open_ws(ws5)
    wsA = ws5
    other_path = dock._ws.items[2].path
    H.load_file(app, cell, other_path)
    stroke(app, canvas)
    seen = H.auto_close_dialogs(app, 200)
    dock.save_and_next(); app.processEvents()
    check("Panel mismatch box; item 0 pending; index 0; no files", [s[1] for s in seen] == ["Panel mismatch"] and not dock._ws.items[0].done
          and dock._index == 0 and not os.path.exists(os.path.join(wsA, "vidi_output")), f"{[s[1] for s in seen]} done={dock._ws.items[0].done} idx={dock._index}")
    check("mismatch text names both paths", other_path in seen[0][2] and dock._ws.items[0].path in seen[0][2])
    # same file reached through a '..' path → abspath normalises → should save
    weird = os.path.join(wsA, "sub", "..", os.path.basename(dock._ws.items[0].path))
    H.load_file(app, cell, weird); dock._apply_tool(); stroke(app, canvas)
    seen = H.auto_close_dialogs(app, 200)
    dock._save(advance=False); app.processEvents()
    check("same file via '..' path: accepted (abspath normalises)", seen == [] and dock._ws.items[0].done, str(seen))
    # same file through a symlink → abspath does NOT resolve symlinks
    link = os.path.join(WSROOT, "S_A_link")
    if os.path.lexists(link): os.remove(link)
    os.symlink(wsA, link)
    dock._step(+1); H.wait_loaded(app, cell)    # item 1 = bpd1_20100101_2.dcm
    H.load_file(app, cell, os.path.join(link, "bpd1_20100101_2.dcm")); dock._apply_tool(); stroke(app, canvas)
    seen = H.auto_close_dialogs(app, 200)
    dock._save(advance=False); app.processEvents()
    check("same file via symlinked dir: refused as mismatch (abspath != realpath) — minor", [s[1] for s in seen] == ["Panel mismatch"], str(seen))
t5()

@scenario("Save & Next on the last item")
def t6():
    reset_export(); wsB = fresh_ws("S_B", n=2); open_ws(wsB)
    dock._step(+1); H.wait_loaded(app, cell); stroke(app, canvas)
    sd = cell.series_data()
    dock.save_and_next(); app.processEvents(); H.pump(app, 300)
    check("last item saved, index stays 1, no reload (same SeriesData), Next disabled",
          dock._ws.items[1].done and dock._index == 1 and cell.series_data() is sd and not dock._next_btn.isEnabled(), f"idx={dock._index}")
    check("count label 2/2 · 1 done", dock._count_lbl.text() == "2/2 · 1 done", dock._count_lbl.text())
    check("mask still on canvas after last save (no reload)", canvas.mask_pixels() > 0)
    # Ctrl+S again on the done item re-saves (manifest row replaced, no duplicate)
    H.key(win, Qt.Key_S, Qt.ControlModifier); app.processEvents()
    rows = list(csv.DictReader(open(os.path.join(wsB, "vidi_output", "manifest.csv"))))
    check("re-save via Ctrl+S keeps one manifest row", len(rows) == 1 and dock._ws.n_done == 1, str(len(rows)))
t6()

@scenario("change Output dir mid-job")
def t7():
    reset_export(); wsC = fresh_ws("S_C", n=4); open_ws(wsC)
    stroke(app, canvas); dock.save_and_next(); H.wait_loaded(app, cell)      # item0 → vidi_output
    stroke(app, canvas); dock.save_and_next(); H.wait_loaded(app, cell)      # item1 → vidi_output
    check("2 done in vidi_output", dock._ws.n_done == 2 and dock._index == 2)
    dock._out_edit.setText("second_out")
    stroke(app, canvas); dock._save(advance=False); app.processEvents()      # item2 → second_out
    check("new dir created with item2 only; status names it", os.path.isfile(os.path.join(wsC, "second_out", "manifest.csv"))
          and "second_out/" in dock._status_lbl.text(), dock._status_lbl.text())
    man_new = W.read_manifest(os.path.join(wsC, "second_out", "manifest.csv"))
    man_old = W.read_manifest(os.path.join(wsC, "vidi_output", "manifest.csv"))
    check("new manifest has 1 row, old manifest still 2 rows", len(man_new) == 1 and len(man_old) == 2, f"{len(man_new)} {len(man_old)}")
    check("in-memory done count now 3 (mix of two manifests)", dock._ws.n_done == 3 and dock._count_lbl.text() == "3/4 · 3 done", dock._count_lbl.text())
    check("ws.out_dir_name switched", dock._ws.out_dir_name == "second_out")
    # reopen with the new name → only item2 done; reopen with old → items 0,1 done
    open_ws(wsC)
    done = [it.done for it in dock._ws.items]
    check("reopen with Output dir 'second_out': done flags come from second_out only; jumps to 0", done[:4] == [False, False, True, False] and dock._index == 0, str(done))
    check("reopen with 'second_out': the OLD vidi_output/png masks are NOT listed as job items", dock._list.count() == 4, f"n={dock._list.count()} stems={[it.stem for it in dock._ws.items]}")
    dock._out_edit.setText("vidi_output"); open_ws(wsC)
    done = [it.done for it in dock._ws.items]
    check("reopen with 'vidi_output': items 0,1 done, jumps to 2", done[:4] == [True, True, False, False] and dock._index == 2, str(done))
    check("reopen with 'vidi_output': second_out/png masks are NOT listed as job items", dock._list.count() == 4, f"n={dock._list.count()} stems={[it.stem for it in dock._ws.items]}")
t7()

@scenario("Output dir text variants")
def t8():
    cases = {
        "  spaced  ": "spaced",
        "/": "vidi_output",
        "///": "vidi_output",
        "trail/": "trail",
        "/lead": "lead",
        "nested/out": "nested/out",
        "..": "..",
        "../outside_S_D": "../outside_S_D",
        "/tmp/abs_vidi": "tmp/abs_vidi",
        ".": ".",
        "sub": "sub",
    }
    for text, exp in cases.items():
        dock._out_edit.setText(text)
        got = dock._out_name()
        check(f"_out_name({text!r}) == {exp!r}", got == exp, repr(got))
t8()

def save_into(root, out_text, n=2):
    """fresh workspace, out dir text, save item0 with a stroke; return written paths."""
    reset_export(); dock._out_edit.setText(out_text); open_ws(root); stroke(app, canvas)
    seen = H.auto_close_dialogs(app, 200)
    dock._save(advance=False); app.processEvents()
    return seen

@scenario("Output dir '..' and '../outside' escape the workspace")
def t9():
    wsD = fresh_ws("S_D", n=2)
    parent = os.path.dirname(wsD)
    for p in ("manifest.csv", "png"):
        q = os.path.join(parent, p)
        if os.path.isdir(q): shutil.rmtree(q)
        elif os.path.exists(q): os.remove(q)
    shutil.rmtree(os.path.join(parent, "outside_S_D"), ignore_errors=True)
    seen = save_into(wsD, "..")
    check("'..': save succeeded with no dialog", seen == [] and dock._ws.items[0].done, f"{seen} {dock._status_lbl.text()}")
    check("'..': manifest + png/ written in the PARENT of the workspace", os.path.isfile(os.path.join(parent, "manifest.csv")) and os.path.isdir(os.path.join(parent, "png")),
          str(sorted(os.listdir(parent))))
    check("'..': nothing written inside the workspace", not any(d in os.listdir(wsD) for d in ("png", "manifest.csv")), str(os.listdir(wsD)))
    check("'..': ws.out_dir resolves outside root", not os.path.abspath(dock._ws.out_dir).startswith(wsD + os.sep), dock._ws.out_dir)
    seen = save_into(wsD, "../outside_S_D")
    check("'../outside_S_D': written as sibling dir of the workspace", os.path.isfile(os.path.join(parent, "outside_S_D", "manifest.csv")), str(sorted(os.listdir(parent))))
    check("status shows the relative name verbatim", "../outside_S_D/" in dock._status_lbl.text(), dock._status_lbl.text())
    # clean the parent so later scans are not polluted
    for p in ("manifest.csv", "png", "outside_S_D"):
        q = os.path.join(parent, p)
        shutil.rmtree(q, ignore_errors=True) if os.path.isdir(q) else (os.remove(q) if os.path.exists(q) else None)
t9()

@scenario("Output dir absolute '/tmp/x' becomes workspace-relative")
def t10():
    wsE = fresh_ws("S_E", n=2)
    seen = save_into(wsE, "/tmp/abs_vidi_x")
    check("absolute path is silently relocated under the workspace", os.path.isdir(os.path.join(wsE, "tmp", "abs_vidi_x", "png")) and not os.path.exists("/tmp/abs_vidi_x"),
          str(listdir_rel(wsE)))
    check("status reports the relocated name", "tmp/abs_vidi_x/" in dock._status_lbl.text(), dock._status_lbl.text())
t10()

@scenario("Output dir nested 'a/b' or '.' pollutes the image scan on reopen")
def t11():
    wsF = fresh_ws("S_F", n=2)
    seen = save_into(wsF, "nested/out")
    check("nested: files written", os.path.isdir(os.path.join(wsF, "nested", "out", "png")))
    open_ws(wsF)
    stems = [it.stem for it in dock._ws.items]
    check("reopen with nested out dir 'nested/out': saved mask PNG is NOT listed as a job item", dock._list.count() == 2, str(stems))
    wsG = fresh_ws("S_G", n=2)
    seen = save_into(wsG, ".")
    check("'.': output lands directly in the workspace root (png/ + manifest.csv beside the images)", os.path.isdir(os.path.join(wsG, "png")) and os.path.isfile(os.path.join(wsG, "manifest.csv")), str(os.listdir(wsG)))
    open_ws(wsG)
    stems = [it.stem for it in dock._ws.items]
    check("reopen with '.': png outputs are NOT listed as job items", dock._list.count() == 2, str(stems))
t11()

@scenario("Output dir named like an existing image subdir ('sub')")
def t12():
    wsH = fresh_ws("S_H", n=4)         # 2 files in root + 2 in sub/
    reset_export(); dock._out_edit.setText("sub"); open_ws(wsH)
    check("opening with out dir 'sub': the 2 source images in sub/ are still job items", dock._list.count() == 4, f"n={dock._list.count()} stems={[it.stem for it in dock._ws.items]}")
    stroke(app, canvas); dock._save(advance=False); app.processEvents()
    check("saving into 'sub' writes next to source images", os.path.isdir(os.path.join(wsH, "sub", "png")), str(listdir_rel(wsH)))
t12()

@scenario("manifest written while the output dir is read-only → Export failed box")
def t13():
    wsI = fresh_ws("S_I", n=2)
    reset_export(); open_ws(wsI)
    ro = os.path.join(wsI, "vidi_output"); os.makedirs(ro); os.chmod(ro, 0o500)
    stroke(app, canvas)
    seen = H.auto_close_dialogs(app, 200)
    dock.save_and_next(); app.processEvents()
    os.chmod(ro, 0o700)
    check("'Export failed' critical box; item pending; no advance", [s[1] for s in seen] == ["Export failed"] and not dock._ws.items[0].done and dock._index == 0, str(seen))
t13()

win.close(); app.processEvents()
sys.exit(1 if summary() else 0)
