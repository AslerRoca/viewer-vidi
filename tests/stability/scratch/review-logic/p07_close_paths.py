"""hideEvent / visibilityChanged at app close with dock visible + workspace open: several exit paths, each in a subprocess."""
from common import *
import subprocess, textwrap
d = fresh_ws("p07", [os.path.join(FIX, "bpd1_20100101_1.dcm")])
variants = {
 "close_then_exit": "win.close(); app.processEvents()",
 "no_close_gc_exit": "pass",
 "exec_quit_from_timer": "from PyQt5.QtCore import QTimer; QTimer.singleShot(100, win.close); QTimer.singleShot(300, app.quit); app.exec_()",
 "closeAllWindows": "app.closeAllWindows(); app.processEvents()",
 "del_win": "win.close(); app.processEvents(); del win; import gc; gc.collect(); app.processEvents()",
 "dock_close_then_win_close": "dock.close(); app.processEvents(); win.close(); app.processEvents()",
}
for name, tail in variants.items():
    child = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {SCR!r})
        from common import *
        app, win = H.boot(); dock, quad = win._dock, win._quad
        ws = H.open_workspace(app, win, {d!r})
        c = quad.active_cell().canvas(); H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3))
        {tail}
        print("CHILD_EXIT_OK", flush=True)
    """)
    r = subprocess.run([H.PYTHON, "-c", child], capture_output=True, text=True, timeout=120, cwd=SCR)
    err = "\n".join(l for l in r.stderr.splitlines() if "propagateSizeHints" not in l and "XDG_SESSION_TYPE" not in l)
    check(f"exit path '{name}': rc=0, clean stderr", r.returncode == 0 and "CHILD_EXIT_OK" in r.stdout and not err.strip(), f"rc={r.returncode} stderr={err[-600:]!r}")
sys.exit(summary())
