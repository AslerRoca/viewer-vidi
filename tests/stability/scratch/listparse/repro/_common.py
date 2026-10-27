"""Shared bits for the listparse repros: package registration + a tiny writable fixture."""
import os, sys, shutil
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
FX = "/media/zsk/ressd/research/alldata_backup/dicom/original"
DATA = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/listparse/repro_data"

def fresh(name):
    d = os.path.join(DATA, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); return d

def dcm(dst_dir, name="a.dcm"):
    src = sorted(f for f in os.listdir(FX) if f.endswith(".dcm"))[0]
    p = os.path.join(dst_dir, name); shutil.copy(os.path.join(FX, src), p); return p

def open_list_in_dock(path):
    """Click the dock's Open list… with the file dialog answering *path*."""
    app, win = H.boot()
    from PyQt5.QtWidgets import QFileDialog
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (path, ""))
    win._ws_btn.setChecked(True); app.processEvents()
    seen = H.auto_close_dialogs(app, 300)
    win._dock._open_list_btn.click(); app.processEvents(); H.pump(app, 300)
    print('dialogs:', seen)
    return app, win

def open_dir_in_dock(path):
    app, win = H.boot()
    from PyQt5.QtWidgets import QFileDialog
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
    win._ws_btn.setChecked(True); app.processEvents()
    seen = H.auto_close_dialogs(app, 300)
    win._dock._open_dir_btn.click(); app.processEvents(); H.pump(app, 300)
    print('dialogs:', seen)
    return app, win
