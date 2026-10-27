"""Repro: scan_images skips only the CURRENT Output dir name. Exported PNGs under any other output dir — an earlier
Output dir name, or Output dir '.' — are rescanned as job items on reopen.
Usage: timeout 300 python repro_outdir_leak.py      Expected: items == ['a.png'] in both cases."""
import os, sys, shutil
import numpy as np; from PIL import Image
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); import harness as H; H.register_package()
from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
px = np.full((8, 8), 100, np.float32); mk = np.zeros((8, 8), np.uint8); mk[2:4, 2:4] = 1
for out_name_saved, out_name_reopen in (("vidi_output", "out2"), (".", ".")):
    root = os.path.join(STAB, "manifest", "work", "repro_leak_" + out_name_reopen.strip(".") or "dot"); shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
    Image.fromarray(np.full((8, 8), 100, np.uint8), "L").save(os.path.join(root, "a.png"))
    ws = W.build_workspace(root, "image", W.probe_workspace(root, out_name_saved)[0], out_name_saved)
    written = export_item(ws.out_dir, ExportInput(stem="a", pixels=px, wc=100, ww=200, mask=mk), ExportOptions(formats=("png",)))
    W.write_manifest_row(ws.manifest_path, dict(stem="a", source=ws.items[0].path, saved_at="t", mask_pixels=4, x0="", y0="", x1="", y1="", formats="png", files=" ".join(written)))
    items = [os.path.relpath(p, root) for p in W.probe_workspace(root, out_name_reopen)[0]]
    print(f"saved with Output dir {out_name_saved!r}, reopened with {out_name_reopen!r}: items = {items}   (expected ['a.png'])")
