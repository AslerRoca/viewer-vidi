"""Output dir not writable but png/ subdir is: export succeeds, write_manifest_row raises PermissionError inside the Save slot."""
from common import *
import subprocess, textwrap, stat
d = fresh_ws("p05", [os.path.join(FIX, "bpd1_20100101_1.dcm")])
out = os.path.join(d, "vidi_output"); os.makedirs(os.path.join(out, "png"))
os.chmod(out, 0o555)
child = textwrap.dedent(f"""
    import sys; sys.path.insert(0, {SCR!r})
    from common import *
    from viewer_vidi import workspace as W
    app, win = H.boot(); dock, quad = win._dock, win._quad
    ws = H.open_workspace(app, win, {d!r})
    c = quad.active_cell().canvas(); H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3))
    from PyQt5.QtCore import QTimer
    def go():
        dock._save_btn.click()
        print("after save click, status:", dock._status_lbl.text(), "done:", ws.items[0].done, flush=True)
        app.quit()
    QTimer.singleShot(0, go); app.exec_()
    print("CHILD_EXIT_OK", flush=True)
""")
try:
    r = subprocess.run([H.PYTHON, "-c", child], capture_output=True, text=True, timeout=120, cwd=SCR)
finally:
    os.chmod(out, 0o755)
err = "\n".join(l for l in r.stderr.splitlines() if "propagateSizeHints" not in l and "XDG_SESSION_TYPE" not in l)
print("child rc", r.returncode); print("child stdout:", r.stdout[-400:]); print("child stderr:", err[-1500:])
print("files written:", os.listdir(os.path.join(out, "png")))
check("Save into read-only out dir (writable png/) survives; error shown instead of abort", r.returncode == 0 and "CHILD_EXIT_OK" in r.stdout, f"rc={r.returncode}")
sys.exit(summary())
