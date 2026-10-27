"""F5: a dangling symlink named *.dcm is counted by probe_workspace (mode box) but dropped by build_workspace.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_dangling_dcm_count.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
from viewer_vidi import workspace as W, annotation_dock as AD
d = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery/repro_dangling"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
shutil.copy("/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png", os.path.join(d, "real.png"))
os.symlink(os.path.join(d, "nope.dcm"), os.path.join(d, "dangling.dcm"))
open(os.path.join(d, "list.txt"), "w").write("real.png\n")
print("is_image_path(dangling.dcm):", W.is_image_path(os.path.join(d, "dangling.dcm")), "| is_image_path(nonexistent.dcm):", W.is_image_path(os.path.join(d, "zzz.dcm")))
imgs, lists = W.probe_workspace(d); print("probe images:", [os.path.basename(p) for p in imgs])
print("build items  :", [i.stem for i in W.build_workspace(d, "image", imgs).items])
dock = win._dock; win._ws_btn.setChecked(True); app.processEvents()
AD.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: d)
seen = H.auto_close_dialogs(app, 300, choose="Image mode"); dock._open_dir(); H.pump(app, 500)
print("mode box text:", repr(seen[0][2]) if seen else None, "| items:", len(dock.workspace().items))
win.close(); app.processEvents()
