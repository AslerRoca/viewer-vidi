"""loaderasync T1: rapid Next/Prev, Save while loading, stale loader signals."""
import os, sys, time, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np

FX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx"
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

def state():
    sd = cell.series_data(); px = canvas.displayed_pixels(); m = canvas.mask()
    return dict(sd=(os.path.basename(sd.meta.series_dir) if sd else None),
                px=(None if px is None else px.shape), mask=(None if m is None else m.shape),
                row=dock._list.currentRow(), idx=dock._index, loader_running=cell._loader.isRunning())

def consistent():
    sd = cell.series_data(); px = canvas.displayed_pixels(); m = canvas.mask()
    it = dock._ws.items[dock._index]
    ok = (sd is not None and os.path.abspath(sd.meta.series_dir) == os.path.abspath(it.path)
          and px is not None and m is not None and m.shape == px.shape
          and dock._list.currentRow() == dock._index and not cell._loader.isRunning())
    return ok

# ── workspace: 6 CR DICOMs ──────────────────────────────────────────────────
root = os.path.join(FX, "rapid")
shutil.rmtree(os.path.join(root, "vidi_output"), ignore_errors=True)
ws = H.open_workspace(app, win, root)
check("T1.0 workspace opened, first item loaded", H.wait_loaded(app, cell) and dock._index == 0, str(state()))
n = len(ws.items)

# ── S1: 20 direct _step calls with NO event processing between (worst case) ──
t0 = time.time()
for i in range(20):
    dock._step(+1 if (i // n) % 2 == 0 else -1)
H.wait_loaded(app, cell); H.pump(app, 300)
# wait until the loader is idle
t1 = time.time()
while cell._loader.isRunning() and time.time() - t1 < 30: app.processEvents(); time.sleep(0.01)
H.pump(app, 200)
check("S1 20 rapid _step (no pump) → final state consistent", consistent(), str(state()))
check("S1 invariants", not H.invariants(canvas), str(H.invariants(canvas)))

# ── S2: 20 real button clicks ~40 ms apart (events processed between) ──
dock._load_index(0); H.wait_loaded(app, cell)
t0 = time.time()
for i in range(20):
    btn = dock._next_btn if dock._next_btn.isEnabled() else dock._prev_btn
    QTest.mouseClick(btn, Qt.LeftButton)
    H.pump(app, 40)
el = time.time() - t0
t1 = time.time()
while cell._loader.isRunning() and time.time() - t1 < 30: app.processEvents(); time.sleep(0.01)
H.wait_loaded(app, cell); H.pump(app, 300)
check(f"S2 20 button clicks in {el:.2f}s → final state consistent", consistent(), str(state()))
check("S2 invariants", not H.invariants(canvas), str(H.invariants(canvas)))
check("S2 tool mode is still paint after rapid loads", canvas.wl_mode() == "paint", canvas.wl_mode())

# ── S3: Save immediately after load_meta (sd None, pixels None) ──
outd = os.path.join(root, "vidi_output")
shutil.rmtree(outd, ignore_errors=True)
dock._load_index(1)                     # async; nothing loaded yet
seen = H.auto_close_dialogs(app, 150)
dock._save(advance=False); app.processEvents()
msg3 = dock._status_lbl.text()
H.pump(app, 300)
check("S3 Save right after load_meta → guard text, nothing written, not done",
      "loading" in msg3.lower() and not os.path.isdir(outd) and not dock._ws.items[1].done and not seen,
      f"status={msg3!r} dialogs={seen}")
H.wait_loaded(app, cell)

# ── S4: Save in the window headers_ready → pixels_ready (sd set, pixels None) ──
dock._load_index(2)
got_window = False; msg4 = None; written4 = None
t0 = time.time()
while time.time() - t0 < 20:
    app.processEvents()
    if cell.series_data() is not None and canvas.displayed_pixels() is None:
        got_window = True
        dock._save(advance=False)
        msg4 = dock._status_lbl.text()
        written4 = os.path.isdir(outd)
        break
    if canvas.displayed_pixels() is not None:
        break
    time.sleep(0.0005)
H.wait_loaded(app, cell); H.pump(app, 200)
if got_window:
    check("S4 Save in headers→pixels window → guard text, nothing written",
          "loading" in (msg4 or "").lower() and not written4 and not dock._ws.items[2].done,
          f"status={msg4!r} written={written4}")
else:
    print("INFO S4: headers→pixels window not observed (too fast); state", state())
check("S4 after wait: consistent", consistent(), str(state()))

# ── S5: stale signals — let item A's loader finish while the main thread is blocked,
#        then load_meta(B) before the queued headers_ready(A)/pixels_ready(A) are delivered ──
dock._load_index(0); H.wait_loaded(app, cell)
A, B = ws.items[2].path, ws.items[0].path            # different shapes: 2570x2040 vs 2044x1514
dock._load_index(2)                                  # starts A
cell._loader.wait()                                  # thread done → both signals queued, unprocessed
dock._load_index(0)                                  # B: cancel (no-op), sd=None, set_image(None), start B
# Deliver the queue once; observe the state immediately after
app.processEvents()
st_after_one = state()
stale_sd_seen = (st_after_one["sd"] == os.path.basename(A))
# Poll: does a state with sd == B but pixels of A's shape ever appear?
mismatch_seen = None; save_in_mismatch = None
shpA = (2570, 2040)
t0 = time.time()
while time.time() - t0 < 15:
    app.processEvents()
    sd = cell.series_data(); px = canvas.displayed_pixels()
    if sd is not None and os.path.basename(sd.meta.series_dir) == os.path.basename(B) and px is not None and px.shape == shpA:
        mismatch_seen = state()
        # Save now: the dock's current item is B (index 0) — what gets written?
        dock._fmt_chk["png"].setChecked(True); dock._image_chk.setChecked(True)
        dock._save(advance=False)
        save_in_mismatch = (dock._status_lbl.text(), sorted(os.listdir(os.path.join(outd, "png"))) if os.path.isdir(os.path.join(outd, "png")) else [])
        break
    if px is not None and px.shape != shpA and sd is not None and os.path.basename(sd.meta.series_dir) == os.path.basename(B):
        break
    time.sleep(0.0005)
H.wait_loaded(app, cell); H.pump(app, 300)
print("INFO S5 state after one processEvents:", st_after_one)
print("INFO S5 stale sd(A) seen after load_meta(B):", stale_sd_seen)
print("INFO S5 sd=B/pixels=A window seen:", mismatch_seen, "save result:", save_in_mismatch)
check("S5 final state consistent after stale-signal race", consistent(), str(state()))
check("S5 no stale A headers delivered after load_meta(B)", not stale_sd_seen, str(st_after_one))
if mismatch_seen is not None:
    saved_img = os.path.join(outd, "png", f"{ws.items[0].stem}_image.png")
    shape_saved = None
    if os.path.isfile(saved_img):
        from PIL import Image
        shape_saved = np.array(Image.open(saved_img)).shape
    check("S5 Save in sd=B/pixels=A window must not write A's pixels under B's stem",
          shape_saved != shpA, f"saved shape={shape_saved} status={save_in_mismatch}")

win.close(); app.processEvents()
nf = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - nf}/{len(results)} checks passed")
