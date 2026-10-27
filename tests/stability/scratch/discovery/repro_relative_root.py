"""F8: a relative root keeps item paths relative (ws.root is made absolute, item.path is not).
Run: cd <scratch> && timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_relative_root.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery"
d = os.path.join(SCR, "repro_relroot"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
open(os.path.join(d, "a.png"), "wb").write(b"\0" * 64)
os.chdir(SCR)
imgs, _ = W.probe_workspace("repro_relroot"); ws = W.build_workspace("repro_relroot", "image", imgs)
print("root:", ws.root); print("item paths:", [i.path for i in ws.items], "<- relative; manifest 'source' and loader get relative paths")
