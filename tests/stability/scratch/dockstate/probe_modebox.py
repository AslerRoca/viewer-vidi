import os, sys, time
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
app, win = H.boot()
from viewer_vidi import annotation_dock as AD
dock, quad = win._dock, win._quad
cell = quad.active_cell()
win._ws_btn.setChecked(True); app.processEvents()
wsC = fresh_ws("C", n=2)
with open(os.path.join(wsC, "job.txt"), "w") as f: f.write("bpd1_20100101_1.dcm\n")
AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: wsC)

def closer(choose, tag):
    log = []
    def _close():
        tl = [(type(w).__name__, w.isVisible(), w.windowTitle()) for w in app.topLevelWidgets() if isinstance(w, QDialog)]
        log.append(("fired", time.time() - t0, tl))
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                if isinstance(w, QMessageBox):
                    for b in w.buttons():
                        if choose in b.text():
                            log.append(("click", b.text())); b.click(); break
                    else:
                        w.reject()
                else:
                    w.reject()
    QTimer.singleShot(200, _close)
    return log
t0 = time.time()
log = closer("Image mode", "first")
dock._open_dir()
print("first  returned after", round(time.time() - t0, 2), "s; log:", log, "mode:", dock._ws.mode if dock._ws else None, "n:", dock._list.count())
H.wait_loaded(app, cell)
t0 = time.time()
log = closer("List mode", "second")
dock._open_dir()
print("second returned after", round(time.time() - t0, 2), "s; log:", log, "mode:", dock._ws.mode if dock._ws else None, "n:", dock._list.count())
H.wait_loaded(app, cell)
win.close(); app.processEvents()
