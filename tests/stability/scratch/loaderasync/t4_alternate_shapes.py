"""loaderasync T4: alternating items of different shapes at high speed; active-panel switch
mid-load; Save & Next across a slow (3-D NIfTI) item; invariants sampled during loads."""
import os, sys, time, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
import numpy as np
from PIL import Image

FX = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/loaderasync/fx"
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

app, win = H.boot()
dock, quad = win._dock, win._quad
cell = quad.active_cell(); canvas = cell.canvas()

def state():
    sd = cell.series_data(); px = canvas.displayed_pixels(); m = canvas.mask()
    return dict(sd=(os.path.basename(sd.meta.series_dir) if sd else None),
                px=(None if px is None else px.shape), mask=(None if m is None else m.shape),
                row=dock._list.currentRow(), idx=dock._index, running=cell._loader.isRunning())

def consistent():
    sd = cell.series_data(); px = canvas.displayed_pixels(); m = canvas.mask()
    it = dock._ws.items[dock._index]
    return (sd is not None and os.path.abspath(sd.meta.series_dir) == os.path.abspath(it.path)
            and px is not None and m is not None and m.shape == px.shape
            and dock._list.currentRow() == dock._index and not cell._loader.isRunning())

def drain(timeout=30):
    t0 = time.time()
    while cell._loader.isRunning() and time.time() - t0 < timeout: app.processEvents(); time.sleep(0.005)
    H.wait_loaded(app, cell); H.pump(app, 200)

root = os.path.join(FX, "shapes")      # a_small.png (200x300), b_big.dcm (2044x1514), c_small_t.png (300x200), d_big2.dcm (2570x2040)
shutil.rmtree(os.path.join(root, "vidi_output"), ignore_errors=True)
ws = H.open_workspace(app, win, root)
stems = [it.stem for it in ws.items]
print("INFO items", stems)
check("A.0 first item (200x300 png) loaded", H.wait_loaded(app, cell) and canvas.displayed_pixels().shape == (200, 300), str(state()))

# ── A1: alternate small png / big dicom 30 times with 5 ms gaps; sample invariants each time ──
viol = []
for k in range(30):
    dock._load_index(1 if k % 2 == 0 else 0)
    H.pump(app, 5)
    v = H.invariants(canvas)
    if v: viol.append((k, v, state()))
drain()
check("A1 alternate 300x200 png / 2044x1514 dcm ×30 → final consistent", consistent(), str(state()))
check("A1 invariants never violated during alternation", not viol, str(viol[:3]))

# ── A2: alternate with ZERO gap (same event-loop turn) incl. the 2570x2040 one ──
viol = []
for k in range(30):
    dock._load_index([0, 3, 2, 1][k % 4])
    v = H.invariants(canvas)
    if v: viol.append((k, v, state()))
drain()
check("A2 4-way alternation with no event processing → final consistent", consistent(), str(state()))
check("A2 invariants never violated", not viol, str(viol[:3]))

# ── A3: paint on the big one, then jump to small → mask reset to small shape, no leak ──
dock._load_index(1); drain()
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3))
n_big = canvas.mask_pixels()
dock._load_index(0); drain()
check("A3 switching big→small after painting: fresh zero mask with the small shape",
      n_big > 0 and canvas.mask_pixels() == 0 and canvas.mask().shape == (200, 300), f"n_big={n_big} now={canvas.mask_pixels()} {canvas.mask().shape}")
# and small→small-same-shape (a_small 200x300 → b_big → a_small again) must not resurrect an old mask
H.drag(app, canvas, H.pt(canvas, 0.3, 0.3), H.pt(canvas, 0.6, 0.3))
n_small = canvas.mask_pixels()
dock._load_index(1); drain(); dock._load_index(0); drain()
check("A3b returning to the same item gives a fresh mask (no resurrection)", n_small > 0 and canvas.mask_pixels() == 0, f"n_small={n_small} now={canvas.mask_pixels()}")

# ── A4: active panel switched to an empty cell while item loads → Save guard text ──
dock._load_index(3)                    # big2 loading into cell 0
other = quad.cells()[1]
quad._set_active(other) if hasattr(quad, "_set_active") else other.activated.emit()
app.processEvents()
dock._save(advance=False); app.processEvents()
msg = dock._status_lbl.text()
print("INFO A4 active cell is", quad.active_cell()._idx, "save status:", repr(msg))
check("A4 Save with an EMPTY other panel active gives a message that names the real cause (not 'still loading')",
      "loading" not in msg.lower(), f"status={msg!r}")
# tools: is the empty panel in paint mode now (tools follow active panel)?
check("A4 tool follows active panel", other.canvas().wl_mode() == "paint", other.canvas().wl_mode())
# switch back, wait, consistent
cell.activated.emit(); app.processEvents(); drain()
check("A4 back on the loading panel: consistent", quad.active_cell() is cell and consistent(), str(state()))

# ── A5: Save & Next chain across all 4 items with the png/jpeg/nifti all on; verify every saved image shape ──
for c in dock._fmt_chk.values(): c.setChecked(True)
dock._image_chk.setChecked(True)
dock._load_index(0); drain()
outd = os.path.join(root, "vidi_output")
shutil.rmtree(outd, ignore_errors=True)
shapes = {}
for k in range(4):
    H.wait_loaded(app, cell)
    sd = cell.series_data(); st = ws.items[dock._index].stem
    shapes[st] = canvas.displayed_pixels().shape
    dock.save_and_next(); app.processEvents()
    drain()
bad = []
for st, shp in shapes.items():
    p = os.path.join(outd, "png", f"{st}_image.png")
    a = np.array(Image.open(p)) if os.path.isfile(p) else None
    if a is None or a.shape != shp: bad.append((st, shp, None if a is None else a.shape))
check("A5 Save&Next ×4: every saved image has its own item's shape", not bad and all(it.done for it in ws.items), f"bad={bad} done={[it.done for it in ws.items]}")
check("A5 after last Save&Next stays on last item", dock._index == 3 and not dock._next_btn.isEnabled())

# ── A6: Next/Prev spam while the 3-D NIfTI (12 MB) loads, then Save & Next ──
root_f = os.path.join(FX, "formats")
shutil.rmtree(os.path.join(root_f, "vidi_output"), ignore_errors=True)
ws_f = H.open_workspace(app, win, root_f)      # first = c3d (slow)
stems_f = [it.stem for it in ws_f.items]
i3 = stems_f.index("c3d")
for k in range(10):
    dock._load_index(i3); H.pump(app, 3); dock._step(+1); H.pump(app, 3); dock._step(-1)
drain()
check("A6 spam around the 3-D NIfTI → consistent", consistent(), str(state()))
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
H.drag(app, canvas, H.pt(canvas, 0.4, 0.5), H.pt(canvas, 0.6, 0.5))
dock._fmt_chk["nifti"].setChecked(True)
dock.save_and_next(); app.processEvents(); drain()
check("A6 Save&Next from the 3-D item advances and writes its mask", ws_f.items[i3].done and dock._index == i3 + 1 and os.path.isfile(os.path.join(root_f, "vidi_output", "png", "c3d_mask.png")), str(state()))

win.close(); app.processEvents()
nf = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - nf}/{len(results)} checks passed")
