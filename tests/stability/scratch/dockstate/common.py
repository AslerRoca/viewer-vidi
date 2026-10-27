"""Shared bits for the dockstate lens scripts."""
import os, sys, shutil, traceback
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
MY   = os.path.join(STAB, "dockstate")
WSROOT = os.path.join(MY, "ws")
FIX_IMG = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/ws_img"
sys.path.insert(0, STAB)
import harness as H

RESULTS = []
def check(name, cond, info=""):
    ok = bool(cond)
    RESULTS.append((name, ok, info))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)
    return ok

def scenario(name):
    """Decorator: run fn, record exceptions as FAIL instead of aborting the script."""
    def deco(fn):
        def run(*a, **k):
            print(f"--- {name}", flush=True)
            try:
                return fn(*a, **k)
            except Exception as e:
                traceback.print_exc()
                check(f"{name}: no python exception", False, repr(e))
            finally:
                # flush pending auto_close_dialogs timers so they cannot leak into the next scenario
                from PyQt5.QtWidgets import QApplication
                H.pump(QApplication.instance(), 350)
        return run
    return deco

def fresh_ws(name, n=4):
    """Writable copy of the 4-DICOM fixture workspace (no vidi_output)."""
    dst = os.path.join(WSROOT, name)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.join(dst, "sub"))
    files = ["bpd1_20100101_1.dcm", "bpd1_20100101_2.dcm", "sub/bpd1_20100101_1.dcm", "sub/bpd1_20100102_1.dcm"][:n]
    for f in files:
        shutil.copy(os.path.join(FIX_IMG, f), os.path.join(dst, f))
    return dst

def summary():
    nf = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - nf}/{len(RESULTS)} checks passed", flush=True)
    return nf

def stroke(app, canvas, a=(0.3, 0.3), b=(0.6, 0.3)):
    H.drag(app, canvas, H.pt(canvas, *a), H.pt(canvas, *b))

def listdir_rel(root):
    out = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            out.append(os.path.relpath(os.path.join(dp, f), root))
    return sorted(out)
