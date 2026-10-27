"""Empty workspace / missing files / deleted item file: no slot exceptions."""
from common import *
import subprocess, textwrap
d = fresh_ws("p15", [os.path.join(FIX, "bpd1_20100101_1.dcm"), os.path.join(FIX, "bpd1_20100101_2.dcm")])
child = textwrap.dedent(f"""
    import sys, os; sys.path.insert(0, {SCR!r})
    from common import *
    from viewer_vidi import workspace as W
    from PyQt5.QtCore import QTimer
    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import Qt
    app, win = H.boot(); dock, quad = win._dock, win._quad
    win._ws_btn.setChecked(True); app.processEvents()
    def go():
        # 1. empty workspace
        dock._set_workspace(W.build_workspace({d!r}, "list", [os.path.join({d!r}, "nope.dcm")], list_file="x.txt"))
        for b in (dock._prev_btn, dock._next_btn, dock._save_btn, dock._save_next_btn, dock._undo_btn, dock._clear_btn):
            b.click(); app.processEvents()
        QTest.keyClick(win, Qt.Key_S, Qt.ControlModifier); QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier); app.processEvents()
        print("empty ws ok; nav label:", dock._count_lbl.text(), "status:", dock._status_lbl.text(), flush=True)
        # 2. real workspace, delete item 2's file, then Next
        ws = H.open_workspace(app, win, {d!r})
        os.remove(ws.items[1].path)
        dock._next_btn.click(); app.processEvents()
        print("after Next onto deleted file: index", dock._index, "status", dock._status_lbl.text(), "row", dock._list.currentRow(), flush=True)
        # 3. delete the CURRENT item's file after it was loaded, then save
        os.remove(ws.items[0].path)
        c = quad.active_cell().canvas(); H.drag(app, c, H.pt(c,0.3,0.3), H.pt(c,0.5,0.3))
        dock._save_btn.click(); app.processEvents()
        print("save after source deleted:", dock._status_lbl.text(), flush=True)
        # 4. all tool buttons unchecked → _current_tool
        for b in dock._tool_btns.values(): b.setChecked(False)
        print("checked tools:", [m for m,b in dock._tool_btns.items() if b.isChecked()], flush=True)
        dock._apply_tool(); print("apply_tool with group state ok", flush=True)
        app.quit()
    QTimer.singleShot(0, go); app.exec_(); print("CHILD_EXIT_OK", flush=True)
""")
r = subprocess.run([H.PYTHON, "-c", child], capture_output=True, text=True, timeout=180, cwd=SCR)
err = "\n".join(l for l in r.stderr.splitlines() if "propagateSizeHints" not in l and "XDG_SESSION_TYPE" not in l)
print("rc", r.returncode); print(r.stdout[-1500:]); print("stderr:", err[-1500:])
check("empty / missing / deleted-item paths: no abort", r.returncode == 0 and "CHILD_EXIT_OK" in r.stdout, f"rc={r.returncode}")
check("Next onto a deleted file reports 'Cannot open' and keeps index 0", "Cannot open" in r.stdout and "index 0" in r.stdout)
sys.exit(summary())
