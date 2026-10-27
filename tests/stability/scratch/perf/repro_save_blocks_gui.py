"""Minimal repro: Save (dock._save) runs export_item synchronously on the GUI thread.
At 8192x8192 the event loop is frozen for ~12 s (PNG+JPEG+NIfTI, Original ticked, no rect);
a 20 ms QTimer fires 0 times during the call. Run with QT_QPA_PLATFORM=offscreen."""
import os, sys, time, shutil
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
from PyQt5.QtCore import QTimer
BIG = os.path.join(STAB, "perf", "fix", "big", "png8192_8.png")   # from perf/make_fixtures.py
WS = os.path.join(STAB, "perf", "ws", "repro_save"); shutil.rmtree(WS, ignore_errors=True); os.makedirs(WS)
lst = os.path.join(WS, "items.txt"); open(lst, "w").write(BIG + "\n")
app, win = H.boot(); dock = win._dock
H.open_workspace(app, win, WS, mode="list", list_file=lst, out_dir="out")
ticks = [0]; tm = QTimer(); tm.setInterval(20); tm.timeout.connect(lambda: ticks.__setitem__(0, ticks[0] + 1)); tm.start()
dock._image_chk.setChecked(True)
for fmts in (("png",), ("jpeg",), ("nifti",), ("png", "jpeg", "nifti")):
    for f, chk in dock._fmt_chk.items(): chk.setChecked(f in fmts)
    app.processEvents(); ticks[0] = 0
    t0 = time.perf_counter(); dock._save(advance=False); dt = time.perf_counter() - t0
    print(f"{'+'.join(fmts):<16} GUI thread blocked {dt:6.2f} s, timer ticks during call: {ticks[0]}  ({dock._status_lbl.text()})")
win.close(); app.processEvents()
