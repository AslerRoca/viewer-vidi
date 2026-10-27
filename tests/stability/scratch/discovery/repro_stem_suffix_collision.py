"""F1: unique_stems '_N' fallback collides with a natural stem -> two items share one stem.
Run: timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_stem_suffix_collision.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
d = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery/repro_suffix"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
for n in ("scan.nii", "scan.nii.gz", "scan_1.nii"):
    open(os.path.join(d, n), "wb").write(b"\0" * 64)
print("pure API :", W.unique_stems(["/r/k.png", "/r/k.nii", "/r/k_1.png"], "/r"), "<- expected 3 distinct")
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
print("workspace:", [(os.path.basename(i.path), i.stem) for i in ws.items])
W.write_manifest_row(ws.manifest_path, dict(stem=ws.items[1].stem, source=ws.items[1].path))
ws2 = W.build_workspace(d, "image", imgs)
print("after saving scan.nii.gz only:", [(os.path.basename(i.path), i.stem, i.done) for i in ws2.items], "<- scan_1.nii wrongly done")
