"""F3: rename the output dir in the dock after a save, reopen -> old outputs become items, done flag lost.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_outdir_rename.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
from viewer_vidi import annotation_dock as AD
d = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery/repro_rename"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
shutil.copy("/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png", os.path.join(d, "one.png"))
dock, cell = win._dock, win._quad.active_cell()
win._ws_btn.setChecked(True); app.processEvents()
AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: d)
dock._out_edit.setText("vidi_output"); dock._open_dir(); H.wait_loaded(app, cell)
dock._image_chk.setChecked(True); dock._save(advance=False); app.processEvents()
print("saved:", dock._status_lbl.text())
dock._out_edit.setText("round2"); dock._open_dir(); H.wait_loaded(app, cell)
print("items after rename+reopen:", [(os.path.relpath(i.path, d), i.stem, i.done) for i in dock.workspace().items])
win.close(); app.processEvents()
