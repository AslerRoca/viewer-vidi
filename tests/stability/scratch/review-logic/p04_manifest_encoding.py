"""manifest.csv with non-UTF-8 bytes / UTF-16 (Excel re-save) → read_manifest raises; inside _save / _open_dir slot = abort."""
from common import *
import subprocess, textwrap
from viewer_vidi import workspace as W
d = fresh_ws("p04", [os.path.join(FIX, "bpd1_20100101_1.dcm")])
out = os.path.join(d, "vidi_output"); os.makedirs(out)
man = os.path.join(out, "manifest.csv")
# case A: cp1252 (ANSI) bytes in the source column, as Excel writes for 'Röntgen'
with open(man, "wb") as f:
    f.write("stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\n".encode())
    f.write("other,/data/Röntgen/other.dcm,2026-10-26T10:00:00,10,,,,,png,png/other_mask.png\n".encode("cp1252"))
for label in ("read_manifest", "write_manifest_row"):
    try:
        if label == "read_manifest":
            W.read_manifest(man)
        else:
            W.write_manifest_row(man, dict(stem="x", source="y"))
        check(f"A cp1252 manifest: {label} does not raise", True)
    except Exception as e:
        check(f"A cp1252 manifest: {label} does not raise", False, f"{type(e).__name__}: {e}")
# case B: UTF-16 with BOM (Excel 'Unicode Text')
with open(man, "wb") as f:
    f.write("stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\nother,/x.dcm,,0,,,,,png,\n".encode("utf-16"))
try:
    W.read_manifest(man); check("B utf-16 manifest: read_manifest does not raise", True)
except Exception as e:
    check("B utf-16 manifest: read_manifest does not raise", False, f"{type(e).__name__}: {e}")
# case C: GUI — a cp1252 manifest present, open workspace via dock (build_workspace is called in _open_dir slot) then Save → write_manifest_row in slot
with open(man, "wb") as f:
    f.write("stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\n".encode())
    f.write("other,/data/Röntgen/other.dcm,2026-10-26T10:00:00,10,,,,,png,png/other_mask.png\n".encode("cp1252"))
child = textwrap.dedent(f"""
    import sys; sys.path.insert(0, {SCR!r})
    from common import *
    from viewer_vidi import workspace as W
    app, win = H.boot(); dock, quad = win._dock, win._quad
    win._ws_btn.setChecked(True); app.processEvents()
    images, _ = W.probe_workspace({d!r}, "vidi_output")
    # _set_workspace path: build_workspace would already raise in _open_dir; emulate the slot by invoking through a Qt timer
    from PyQt5.QtCore import QTimer
    def go():
        ws = W.Workspace(root={d!r}, mode="image"); ws.items=[W.Item(path=images[0], stem="bpd1_20100101_1")]
        dock._set_workspace(ws); H.wait_loaded(app, quad.active_cell())
        c = quad.active_cell().canvas(); H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3))
        dock._save_btn.click()      # real slot invocation
        print("after save click, status:", dock._status_lbl.text(), flush=True)
        app.quit()
    QTimer.singleShot(0, go); app.exec_()
    print("CHILD_EXIT_OK", flush=True)
""")
r = subprocess.run([H.PYTHON, "-c", child], capture_output=True, text=True, timeout=120, cwd=SCR)
err = "\n".join(l for l in r.stderr.splitlines() if "propagateSizeHints" not in l and "XDG_SESSION_TYPE" not in l)
print("child rc", r.returncode); print("child stdout:", r.stdout[-400:]); print("child stderr:", err[-1500:])
check("C GUI Save with cp1252 manifest on disk: process survives (no abort)", r.returncode == 0 and "CHILD_EXIT_OK" in r.stdout, f"rc={r.returncode}")
sys.exit(summary())
