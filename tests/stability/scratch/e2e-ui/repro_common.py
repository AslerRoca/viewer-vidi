"""Tiny helpers shared by the minimal repros: boot, show dock, open a dir through the real button."""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
ORIG = "/media/zsk/ressd/research/alldata_backup/dicom/original"
HERE = os.path.dirname(os.path.abspath(__file__))

def fresh_ws(name, files):
    d = os.path.join(HERE, "fx", name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for f in files: shutil.copy(os.path.join(ORIG, f), d)
    return d

def open_dir(app, win, path):
    from PyQt5.QtWidgets import QFileDialog
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: path)
    QTest.mouseClick(win._dock._open_dir_btn, Qt.LeftButton); app.processEvents()
    H.wait_loaded(app, win._quad.active_cell())

def ctrl(app, win, widget, key, mods=None):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
    QApplication.setActiveWindow(win)
    QTest.keyClick(widget, key, mods if mods is not None else Qt.ControlModifier); app.processEvents()
