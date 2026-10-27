"""Shared prelude for review-logic probes."""
import os, sys, time, shutil
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
SCR = os.path.dirname(os.path.abspath(__file__))
FIX = H.FIXTURES
MR  = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
PNG = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)
def summary():
    n = sum(1 for _, ok in results if not ok)
    print(f"\n{len(results)-n}/{len(results)} passed", flush=True)
    return n
def fresh_ws(name, files, sub=None):
    """Copy fixture files into a fresh workspace dir under SCR; returns the dir."""
    d = os.path.join(SCR, "ws", name)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for f in files:
        shutil.copy(f, d)
    return d
