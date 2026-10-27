"""REPRO (no Qt): a manifest.csv saved by Excel as 'CSV UTF-8' carries a BOM; read_manifest() opens with
encoding='utf-8' (not 'utf-8-sig') so the header becomes '﻿stem', every row lacks 'stem' and the
manifest reads as empty → done flags lost, and the NEXT save rewrites the manifest with only the new row.
Run: timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_manifest_bom.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_bom"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
mp = os.path.join(D, "manifest.csv")
W.write_manifest_row(mp, dict(stem="s1", source="a.dcm")); W.write_manifest_row(mp, dict(stem="s2", source="b.dcm"))
body = open(mp, "rb").read(); open(mp, "wb").write(b"\xef\xbb\xbf" + body)      # Excel 'CSV UTF-8' round-trip
print("rows read with BOM:", sorted(W.read_manifest(mp)), "(expected ['s1','s2'])")
W.write_manifest_row(mp, dict(stem="s3", source="c.dcm"))
print("rows after next save:", sorted(W.read_manifest(mp)), "(expected ['s1','s2','s3'])")
