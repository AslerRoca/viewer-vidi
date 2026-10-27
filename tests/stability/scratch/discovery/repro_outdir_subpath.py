"""F2: output dir typed as a sub-path ('exports/run1') is not skipped by scan_images -> exports become items on reopen.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_outdir_subpath.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
from viewer_vidi import annotation_dock as AD
d = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery/repro_outsub"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
shutil.copy("/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png", os.path.join(d, "one.png"))
dock, cell = win._dock, win._quad.active_cell()
win._ws_btn.setChecked(True); app.processEvents()
AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: d)
dock._out_edit.setText("exports/run1")
dock._open_dir(); H.wait_loaded(app, cell)
print("items before save:", [os.path.relpath(i.path, d) for i in dock.workspace().items])
dock._image_chk.setChecked(True); dock._save(advance=False); app.processEvents()
print("status:", dock._status_lbl.text())
dock._open_dir(); H.wait_loaded(app, cell)
print("items after reopen:", [(os.path.relpath(i.path, d), i.stem, i.done) for i in dock.workspace().items], "<- expected only one.png")
win.close(); app.processEvents()
