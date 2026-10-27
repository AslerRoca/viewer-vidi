import os, sys, shutil
import e2e_common as C
from e2e_common import check, H
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
import numpy as np

ROOT = os.path.join(C.FX, "ws_claims")
app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()
C.open_dir_via_ui(app, win, ROOT); ws = dock.workspace(); H.wait_loaded(app, cell)
H.pump(app, 200)
lst = dock._list
print("dock size", dock.size(), "list size", lst.size(), "viewport", lst.viewport().size(), "visible", lst.isVisible(), lst.viewport().isVisible())
for i in range(lst.count()):
    print(i, lst.visualItemRect(lst.item(i)), "indexAt→", lst.indexAt(lst.visualItemRect(lst.item(i)).center()).row())
got = []
lst.itemDoubleClicked.connect(lambda it: got.append(lst.row(it)))
r = lst.visualItemRect(lst.item(2))
QTest.mouseDClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, r.center()); app.processEvents()
print("after QTest.mouseDClick: signal rows", got, "index", dock._index)
# alternative: explicit press/release/dblclick sequence
QTest.mouseClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, r.center()); app.processEvents()
QTest.mouseDClick(lst.viewport(), Qt.LeftButton, Qt.NoModifier, r.center()); app.processEvents()
print("after click+dclick: rows", got, "index", dock._index, "loaded", H.wait_loaded(app, cell), os.path.basename(cell.series_data().meta.series_dir))

# hidden dock + Ctrl+S
HID = os.path.join(C.FX, "ws_hidden"); shutil.rmtree(os.path.join(HID, "vidi_output"), ignore_errors=True)
C.open_dir_via_ui(app, win, HID); wsh = dock.workspace(); H.wait_loaded(app, cell)
print("active is cell0?", quad.active_cell() is cell, "mode", canvas.wl_mode())
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.5, 0.3)); nh = canvas.mask_pixels(); print("painted", nh)
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier)
print("dock visible", dock.isVisible(), "btn", win._ws_btn.isChecked(), "mode", canvas.wl_mode(), "mask", canvas.mask_pixels())
C.ctrl_s(app, win, target=canvas); H.pump(app, 300)
print("after hidden Ctrl+S: status", repr(dock._status_lbl.text()), "done", wsh.items[0].done, "index", dock._index, "files", C.out_files(os.path.join(HID, "vidi_output")))
H.wait_loaded(app, cell); print("panel now shows", os.path.basename(cell.series_data().meta.series_dir), "mode", canvas.wl_mode())
C.key_on(app, win, Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier); print("dock visible again", dock.isVisible(), "mode", canvas.wl_mode())

# MR
MR = os.path.join(C.FX, "ws_mr"); shutil.rmtree(os.path.join(MR, "vidi_output"), ignore_errors=True)
C.open_dir_via_ui(app, win, MR); wsm = dock.workspace(); print("mr items", len(wsm.items), "loaded", H.wait_loaded(app, cell))
sd = cell.series_data(); print("series_dir", sd.meta.series_dir, "n_files", sd.meta.n_files, "pixels", canvas.displayed_pixels().shape, "spacing", sd.pixel_spacing)
print("fmt state", {k: v.isChecked() for k, v in dock._fmt_chk.items()}, "image", dock._image_chk.isChecked(), "out", dock._out_edit.text())
C.click_button(app, dock._fmt_chk["nifti"])
H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.6, 0.6))
seen = C.arm_dialog_closer(app)
C.ctrl_s(app, win, target=canvas); st = C.wait_status(app, dock); H.pump(app, 300)
print("MR save status:", repr(st), "seen", seen, "files", C.out_files(os.path.join(MR, "vidi_output")))
win.close()
