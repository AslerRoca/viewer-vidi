"""List/CSV files with NUL bytes (UTF-16 export) in the workspace root: find_list_files → parse_list_file → csv.Error in the Open-directory slot."""
from common import *
import subprocess, textwrap
from viewer_vidi import workspace as W
d = fresh_ws("p13", [os.path.join(FIX, "bpd1_20100101_1.dcm")])
with open(os.path.join(d, "cohort.csv"), "wb") as f:
    f.write("path\nbpd1_20100101_1.dcm\n".encode("utf-16"))
for fn in ("parse_list_file", "find_list_files", "probe_workspace"):
    try:
        res = getattr(W, fn)(os.path.join(d, "cohort.csv") if fn == "parse_list_file" else d)
        check(f"{fn} on UTF-16 csv does not raise", True, str(res)[:120])
    except Exception as e:
        check(f"{fn} on UTF-16 csv does not raise", False, f"{type(e).__name__}: {e}")
# .txt with NUL
with open(os.path.join(d, "list.txt"), "wb") as f:
    f.write("bpd1_20100101_1.dcm\n".encode("utf-16"))
try:
    res = W.parse_list_file(os.path.join(d, "list.txt")); check("parse_list_file on UTF-16 txt does not raise", True, str(res)[:120])
except Exception as e:
    check("parse_list_file on UTF-16 txt does not raise", False, f"{type(e).__name__}: {e}")
# GUI: emulate 'Open directory…' slot with the dialog patched to return d
child = textwrap.dedent(f"""
    import sys; sys.path.insert(0, {SCR!r})
    from common import *
    from PyQt5.QtWidgets import QFileDialog
    from PyQt5.QtCore import QTimer
    app, win = H.boot(); dock = win._dock
    win._ws_btn.setChecked(True); app.processEvents()
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: {d!r})
    def go():
        seen = H.auto_close_dialogs(app, 300)
        dock._open_dir_btn.click(); app.processEvents()
        print("dialogs:", seen, "ws:", dock.workspace() and dock.workspace().mode, flush=True); app.quit()
    QTimer.singleShot(0, go); app.exec_(); print("CHILD_EXIT_OK", flush=True)
""")
r = subprocess.run([H.PYTHON, "-c", child], capture_output=True, text=True, timeout=120, cwd=SCR)
err = "\n".join(l for l in r.stderr.splitlines() if "propagateSizeHints" not in l and "XDG_SESSION_TYPE" not in l)
print("rc", r.returncode, "stdout", r.stdout[-300:], "stderr", err[-1200:])
check("GUI 'Open directory…' on a dir holding a UTF-16 csv survives", r.returncode == 0 and "CHILD_EXIT_OK" in r.stdout, f"rc={r.returncode}")
sys.exit(summary())
