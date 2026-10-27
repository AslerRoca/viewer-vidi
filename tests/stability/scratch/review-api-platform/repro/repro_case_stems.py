"""REPRO (no Qt, Linux shows the logic): unique_stems() treats 'Case' and 'case' as distinct stems.
On a case-insensitive filesystem (macOS APFS default, Windows NTFS) png/Case_mask.png and png/case_mask.png
are the SAME file, so the second item's export silently overwrites the first while manifest.csv keeps both rows.
Run: timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_case_stems.py"""
import os, sys, shutil, numpy as np
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_case"); shutil.rmtree(D, ignore_errors=True)
os.makedirs(os.path.join(D, "sub1")); os.makedirs(os.path.join(D, "sub2"))
src = os.path.join(H.FIXTURES, sorted(os.listdir(H.FIXTURES))[0])
shutil.copy(src, os.path.join(D, "sub1", "Case.dcm")); shutil.copy(src, os.path.join(D, "sub2", "case.dcm"))
imgs, _ = W.probe_workspace(D); ws = W.build_workspace(D, "image", imgs)
stems = [it.stem for it in ws.items]; print("stems:", stems, "→ lowercased:", [s.lower() for s in stems])
for s in stems: export_item(ws.out_dir, ExportInput(stem=s, pixels=np.zeros((4, 4), np.float32), wc=1, ww=1, mask=np.ones((4, 4), np.uint8)), ExportOptions(formats=("png",)))
print("png/ on Linux:", sorted(os.listdir(os.path.join(ws.out_dir, "png"))), "— on APFS/NTFS these two names resolve to ONE file")
