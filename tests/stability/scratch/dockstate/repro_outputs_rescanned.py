"""REPRO: scan_images() only skips directories named exactly like the CURRENT output dir
(single path component). Saved mask/image PNGs are listed as new job items on reopen when
the output dir is nested ('a/b'), '.', or was changed mid-job (old dir no longer skipped).
Also: an output dir named like an existing image subdir ('sub') drops those images."""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
app, win = H.boot()
dock, quad = win._dock, win._quad; cell = quad.active_cell(); canvas = cell.canvas()
bad = 0
def run(name, out_names):
    global bad
    root = fresh_ws(name, n=2)
    for o in out_names:
        ws = H.open_workspace(app, win, root, out_dir=o)
        stroke(app, canvas); dock._save(advance=False); app.processEvents()
    ws = H.open_workspace(app, win, root, out_dir=out_names[-1])
    stems = [it.stem for it in ws.items]
    ok = len(stems) == 2
    bad += not ok
    print(f"{name}: saved into {out_names} -> reopen lists {len(stems)} items {stems}  {'OK' if ok else 'DEFECT: outputs became job items'}  count label {dock._count_lbl.text()!r}")
run("R2_nested", ["nested/out"])
run("R2_dot", ["."])
run("R2_changed", ["vidi_output", "second_out"])     # saved item0 into vidi_output, then into second_out
# existing subdir name
root = fresh_ws("R2_sub", n=4)                        # 2 in root + 2 in sub/
ws = H.open_workspace(app, win, root, out_dir="sub")
print(f"R2_sub: out dir 'sub' -> {len(ws.items)} items {[it.stem for it in ws.items]} (4 source images exist)  {'OK' if len(ws.items)==4 else 'DEFECT: images in sub/ silently dropped'}")
bad += len(ws.items) != 4
print("EXPECTED: reopening lists only the 2 source images; outputs never become items")
win.close(); app.processEvents(); sys.exit(1 if bad else 0)
