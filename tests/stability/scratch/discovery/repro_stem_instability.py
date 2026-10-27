"""F4: stems depend on the whole item set -> a new duplicate basename renames an already-saved item and loses its done flag.
Run: timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_stem_instability.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
d = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery/repro_instab"
shutil.rmtree(d, ignore_errors=True); os.makedirs(os.path.join(d, "p1"))
open(os.path.join(d, "p1/image.png"), "wb").write(b"\0" * 64)
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
print("session 1 stems:", [i.stem for i in ws.items])
W.write_manifest_row(ws.manifest_path, dict(stem=ws.items[0].stem, source=ws.items[0].path))
os.makedirs(os.path.join(d, "p2")); open(os.path.join(d, "p2/image.png"), "wb").write(b"\0" * 64)   # new patient folder
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
print("session 2 stems/done:", [(i.stem, i.done) for i in ws.items], "<- p1/image.png was saved as 'image' but is now 'p1__image', not done")
