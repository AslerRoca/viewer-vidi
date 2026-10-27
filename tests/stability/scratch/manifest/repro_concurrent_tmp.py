"""Repro: write_manifest_row from several processes at once — all use the same <manifest>.csv.tmp name, so one
process's os.replace() removes another's tmp (FileNotFoundError → in the GUI that is an abort) and the
read-modify-write cycle drops rows.  Usage: timeout 300 python repro_concurrent_tmp.py   Expected: 150 rows, no errors."""
import os, sys, shutil, subprocess
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB); import harness as H; H.register_package()
from viewer_vidi import workspace as W
d = os.path.join(STAB, "manifest", "work", "repro_conc"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); m = os.path.join(d, "manifest.csv")
code = f"""
import sys; sys.path.insert(0, {STAB!r}); import harness as H; H.register_package()
from viewer_vidi import workspace as W
for i in range(50):
    W.write_manifest_row({m!r}, dict(stem=f"{{sys.argv[1]}}_{{i}}", source="s", saved_at="t", mask_pixels=1, x0="", y0="", x1="", y1="", formats="png", files="f"))
"""
procs = [subprocess.Popen([H.PYTHON, "-c", code, tag], cwd="/tmp", stderr=subprocess.PIPE, text=True) for tag in "ABC"]
errs = [p.communicate()[1].strip().splitlines()[-1:] for p in procs]
print("exit codes:", [p.returncode for p in procs], "last stderr lines:", errs)
print("rows kept:", len(W.read_manifest(m)), "/ 150")
