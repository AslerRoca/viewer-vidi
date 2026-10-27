"""Repro: a manifest read_manifest cannot parse (UTF-8 BOM from Excel 'CSV UTF-8', or header line missing) is
treated as EMPTY, so done flags vanish and the next write_manifest_row REPLACES the file, dropping every old row.
Usage: timeout 300 python repro_bom_dataloss.py
Expected: rows a,b survive (open with utf-8-sig, or refuse to overwrite a manifest that could not be parsed)."""
import os, sys, shutil
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); import harness as H; H.register_package()
from viewer_vidi import workspace as W
HDR = "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files\r\n"
ROWS = "a,/x/a.png,t,5,1,2,3,4,png,png/a_mask.png\r\nb,/x/b.png,t,7,,,,,png,png/b_mask.png\r\n"
d = os.path.join(STAB, "manifest", "work", "repro_bom"); shutil.rmtree(d, ignore_errors=True)
for name, content, enc in (("bom", HDR + ROWS, "utf-8-sig"), ("nohdr", ROWS, "utf-8")):
    m = os.path.join(d, name, "manifest.csv"); os.makedirs(os.path.dirname(m))
    with open(m, "w", newline="", encoding=enc) as f: f.write(content)
    print(f"{name:6s} read_manifest     → {sorted(W.read_manifest(m))}   (expected ['a', 'b'])")
    W.write_manifest_row(m, dict(stem="c", source="/x/c.png", saved_at="t", mask_pixels=1, x0="", y0="", x1="", y1="", formats="png", files="png/c_mask.png"))
    print(f"{name:6s} after saving 'c'  → {sorted(W.read_manifest(m))}   (expected ['a', 'b', 'c'])")
    print(f"{name:6s} file now:\n" + open(m, encoding="utf-8").read())
