"""Repro: export_item joins the stem into the path unsanitised, so a stem containing '../' writes outside out_dir;
and workspace.unique_stems treats a basename that starts with '..' (e.g. '..img.dcm') as outside-root."""
import os, sys, shutil, tempfile; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
from viewer_vidi import workspace as W
base = tempfile.mkdtemp(dir="/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export/out")
out = os.path.join(base, "vidi_output"); target = os.path.join(base, "elsewhere"); os.makedirs(target)
px = np.zeros((4, 4), np.float32); m = np.ones((4, 4), np.uint8)
w = export_item(out, ExportInput("../../elsewhere/evil", px, 0, 1, mask=m), ExportOptions(formats=("png",)))
print("returned:", w); print("files outside out_dir:", os.listdir(target))
root = os.path.join(base, "ws"); os.makedirs(os.path.join(root, "a"))
print("unique_stems:", W.unique_stems([os.path.join(root, "..img.dcm"), os.path.join(root, "a", "..img.dcm")], root))
shutil.rmtree(base)
