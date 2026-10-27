"""Repro: with duplicate basenames the stem of a file depends on which OTHER files exist, so adding/removing a file
re-keys the manifest match: a never-annotated file is marked done (and would overwrite the other file's outputs),
while the annotated one goes back to pending.  Usage: timeout 300 python repro_stem_shift.py"""
import os, sys, shutil
import numpy as np; from PIL import Image
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); import harness as H; H.register_package()
from viewer_vidi import workspace as W
root = os.path.join(STAB, "manifest", "work", "repro_stem"); shutil.rmtree(root, ignore_errors=True); os.makedirs(os.path.join(root, "sub"))
def png(rel): Image.fromarray(np.full((8, 8), 100, np.uint8), "L").save(os.path.join(root, rel))
def show(tag):
    ws = W.build_workspace(root, "image", W.probe_workspace(root)[0])
    print(f"{tag:45s} " + "  ".join(f"{os.path.relpath(it.path, root)}→stem {it.stem!r} done={it.done}" for it in ws.items)); return ws
png("a.png"); png("sub/a.png")
ws = show("a.png + sub/a.png:")
W.write_manifest_row(ws.manifest_path, dict(stem="a", source=os.path.join(root, "a.png"), saved_at="t", mask_pixels=5, x0="", y0="", x1="", y1="", formats="png", files="png/a_mask.png"))
show("annotated ONLY a.png (manifest row 'a'):")
os.remove(os.path.join(root, "a.png"))
show("deleted a.png → sub/a.png inherits 'a':")
png("a.png")
show("re-added a.png (never annotated):")
