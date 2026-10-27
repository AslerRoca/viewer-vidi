"""REPRO: _out_name() only strips leading/trailing slashes. '..' and '../x' write the
manifest and format dirs OUTSIDE the workspace (tooltip: 'Created inside the workspace');
an absolute '/tmp/x' is silently turned into <workspace>/tmp/x."""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
app, win = H.boot()
dock, quad = win._dock, win._quad; cell = quad.active_cell(); canvas = cell.canvas()
root = fresh_ws("R3", n=2); parent = os.path.dirname(root)
for p in ("manifest.csv", "png", "R3_escaped"):
    q = os.path.join(parent, p); shutil.rmtree(q, ignore_errors=True) if os.path.isdir(q) else (os.path.exists(q) and os.remove(q))
bad = 0
for text in ("..", "../R3_escaped", "/tmp/R3_abs"):
    H.open_workspace(app, win, root, out_dir=text); stroke(app, canvas)
    dock._out_edit.setText(text); dock._save(advance=False); app.processEvents()
    out_dir = os.path.abspath(dock._ws.out_dir)
    inside = out_dir.startswith(root + os.sep)
    print(f"Output dir {text!r}: status={dock._status_lbl.text()!r}\n   ws.out_dir={out_dir}  inside workspace={inside}  manifest exists={os.path.isfile(dock._ws.manifest_path)}")
    if text.startswith(".."): bad += inside is False
print("parent dir now holds:", sorted(n for n in os.listdir(parent) if n in ("manifest.csv", "png", "R3_escaped")))
print("EXPECTED: '..'/'../x' refused (or confined to the workspace); absolute paths refused or honoured, not silently relocated")
for p in ("manifest.csv", "png", "R3_escaped"):
    q = os.path.join(parent, p); shutil.rmtree(q, ignore_errors=True) if os.path.isdir(q) else (os.path.exists(q) and os.remove(q))
win.close(); app.processEvents(); sys.exit(1 if bad else 0)
