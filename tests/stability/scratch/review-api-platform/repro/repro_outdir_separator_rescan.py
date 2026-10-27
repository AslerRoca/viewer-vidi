"""REPRO (no Qt): output dir name with a separator ('out/png') is accepted by _out_name() but
scan_images(root, {out_dir_name}) only skips a *single* directory name, so on reopen the exported
masks under out/png/png/ are discovered as new job items (stem 'a_mask').
Run: timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_outdir_separator_rescan.py"""
import os, sys, shutil, numpy as np
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_sep"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
shutil.copy(os.path.join(H.FIXTURES, sorted(os.listdir(H.FIXTURES))[0]), os.path.join(D, "a.dcm"))
name = "out/png".strip().strip("/\\")                      # what AnnotationDock._out_name() returns
imgs, _ = W.probe_workspace(D, name); ws = W.build_workspace(D, "image", imgs, name)
print("first open items:", [it.stem for it in ws.items])
written = export_item(ws.out_dir, ExportInput(stem="a", pixels=np.zeros((8, 8), np.float32), wc=1, ww=1, mask=np.ones((8, 8), np.uint8)), ExportOptions(formats=("png",)))
W.write_manifest_row(ws.manifest_path, dict(stem="a", source=ws.items[0].path, files=" ".join(written)))
imgs2, _ = W.probe_workspace(D, name); ws2 = W.build_workspace(D, "image", imgs2, name)
print("reopen items:", [(it.stem, it.done, os.path.relpath(it.path, D)) for it in ws2.items])
print("EXPECTED: only 'a'; OBSERVED: the exported mask became a pending item" if len(ws2.items) > 1 else "ok")
