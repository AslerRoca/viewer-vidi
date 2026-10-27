"""Perf lens (Qt offscreen): probe_workspace / scan blocking on the GUI thread; dock list with 20k items."""
import os, sys, time, json, shutil
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); sys.path.insert(0, STAB + "/perf")
import harness as H
from perfutil import rss_mb, ms
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QListWidget
FIX = os.path.join(STAB, "perf", "fix")
MR = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
app, win = H.boot()
from viewer_vidi import workspace as W
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
ticks = [0]
tm = QTimer(); tm.setInterval(10); tm.timeout.connect(lambda: ticks.__setitem__(0, ticks[0] + 1)); tm.start()
R = {}
def gui(name, fn):
    app.processEvents(); ticks[0] = 0
    t, out = ms(fn); R[name] = dict(ms=round(t, 1), timer_ticks_during=ticks[0]); app.processEvents(); return out
imgs = gui("probe_workspace tiny3000 on GUI thread", lambda: W.probe_workspace(os.path.join(FIX, "tiny3000")))[0]
gui("scan_images MR 500 extensionless DICOM on GUI thread", lambda: W.scan_images(MR))
gui("probe_workspace FIX root (3004 imgs + 2x20k lists) on GUI thread", lambda: W.probe_workspace(FIX))

# 20k-item workspace (list mode over tiny PNGs)
WS = os.path.join(STAB, "perf", "ws", "list20k"); shutil.rmtree(WS, ignore_errors=True); os.makedirs(WS)
lst = os.path.join(WS, "list20k.txt"); shutil.copy(os.path.join(FIX, "list20k.txt"), lst)
paths = gui("parse_list_file 20k", lambda: W.parse_list_file(lst))
ws = gui("build_workspace 20k", lambda: W.build_workspace(WS, "list", paths, "out", list_file=lst))
R["n_items"] = len(ws.items)
if not dock.isVisible(): win._ws_btn.setChecked(True); app.processEvents()
dock._out_edit.setText("out")
r0 = rss_mb()
gui("dock._set_workspace 20k (addItem loop + first load)", lambda: dock._set_workspace(ws))
ok = H.wait_loaded(app, cell); R["first_item_loaded"] = ok
R["rss_delta_after_20k_list_MB"] = round(rss_mb() - r0)
R["list_count"] = dock._list.count()
lw = QListWidget()
texts = [dock._item_text(it) for it in ws.items]
gui("fresh QListWidget addItem x20000", lambda: [lw.addItem(t) for t in texts])
lw2 = QListWidget(); gui("fresh QListWidget addItems(list of 20000)", lambda: lw2.addItems(texts))
gui("dock._load_index(19999) (setCurrentRow on 20k list)", lambda: dock._load_index(19999)); H.wait_loaded(app, cell)
gui("dock._update_nav (n_done over 20k items)", dock._update_nav)
# 30 quick steps backwards through tiny PNGs: per-step time incl. loader thread round trip
steps = []
for _ in range(30):
    t0 = time.perf_counter(); dock._step(-1); H.wait_loaded(app, cell); steps.append((time.perf_counter() - t0) * 1000)
R["step_tiny_png_ms"] = dict(mean=round(sum(steps) / len(steps), 1), max=round(max(steps), 1))
# save once at 20k items (manifest small) and reopen (read_manifest + 20k addItem)
from PyQt5.QtCore import QPoint
a = H.pt(canvas, 0.3, 0.5); H.drag(app, canvas, a, QPoint(a.x() + 20, a.y()), steps=2)
gui("dock._save at 20k items", lambda: dock._save(advance=False)); R["save_status"] = dock._status_lbl.text()
ws2 = W.build_workspace(WS, "list", paths, "out", list_file=lst)
gui("dock._set_workspace reopen 20k (1 done)", lambda: dock._set_workspace(ws2)); H.wait_loaded(app, cell)
R["reopen_index"] = dock._index; R["reopen_done"] = ws2.n_done
gui("dock._list.clear() 20k", dock._list.clear)
win.close(); app.processEvents()
print(json.dumps(R, indent=1))
