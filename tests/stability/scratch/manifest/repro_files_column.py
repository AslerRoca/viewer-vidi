"""Repro (two 'files'-column issues, pure Python):
 1. Re-saving an item with other formats / without the rectangle leaves the earlier outputs on disk, while the
    manifest 'files' column only lists the latest set → stale <stem>_roi*.png from an OLD rectangle sit next to a
    fresh <stem>_mask.png and nothing records that they are stale.
 2. 'files' is space-joined, so a stem containing a space cannot be split back into paths.
Usage: timeout 300 python repro_files_column.py"""
import os, sys, shutil
import numpy as np
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); import harness as H; H.register_package()
from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
out = os.path.join(STAB, "manifest", "work", "repro_files", "vidi_output"); shutil.rmtree(os.path.dirname(out), ignore_errors=True)
px = np.random.default_rng(0).random((60, 80)).astype(np.float32) * 100; mk = np.zeros((60, 80), np.uint8); mk[10:30, 10:40] = 1
def save(stem, fmts, rect, mask):
    w = export_item(out, ExportInput(stem=stem, pixels=px, wc=50, ww=100, mask=mask, rect=rect), ExportOptions(formats=fmts))
    W.write_manifest_row(os.path.join(out, "manifest.csv"), dict(stem=stem, source="/x", saved_at="t", mask_pixels=int(mask.sum()), x0="", y0="", x1="", y1="", formats=" ".join(fmts), files=" ".join(w)))
def disk(): return sorted(os.path.relpath(os.path.join(dp, f), out) for dp, _, fs in os.walk(out) for f in fs if f != "manifest.csv")
save("a", ("png",), (5, 5, 50, 40), mk);          print("save1 png mask+rect   files:", W.read_manifest(os.path.join(out, "manifest.csv"))["a"]["files"], "\n    disk:", disk())
save("a", ("nifti",), (5, 5, 50, 40), mk);        print("save2 nifti           files:", W.read_manifest(os.path.join(out, "manifest.csv"))["a"]["files"], "\n    disk:", disk())
mk2 = np.zeros_like(mk); mk2[40:50, 50:70] = 1
save("a", ("png",), None, mk2);                   print("save3 png mask only   files:", W.read_manifest(os.path.join(out, "manifest.csv"))["a"]["files"], "\n    disk:", disk(), "  ← a_roi*.png still from save1's rectangle/mask")
save("space stem", ("png",), (5, 5, 50, 40), mk); fc = W.read_manifest(os.path.join(out, "manifest.csv"))["space stem"]["files"]
print("stem 'space stem'     files:", repr(fc), "→ split():", fc.split(" "), " (3 files on disk, 6 tokens)")
