"""Minimal repro (no Qt): a list-file entry that names an existing DICOM series DIRECTORY is
reported as a 'listed path not found' and dropped (build_workspace keeps only os.path.isfile).

Run: timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_list_dir_entry.py
"""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
from viewer_vidi.tree_panel import _make_series_meta

D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/listdir"
series_dir = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx/extless/54450002"
lf = os.path.join(D, "items.txt")
paths = W.parse_list_file(lf)
ws = W.build_workspace(D, "list", paths, list_file=lf)
print("series dir exists:", os.path.isdir(series_dir), "| _make_series_meta accepts it:", _make_series_meta(series_dir) is not None)
print("items:", [it.stem for it in ws.items])
print("missing ('not found' in the dock label):", ws.missing)
