"""loaderasync T2: load-error paths (garbage, truncated, 0-byte, unreadable) in the job flow."""
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

# capture load_error emissions ourselves (ViewCell does not connect it)
errors = []
cell._loader.load_error.connect(lambda s: errors.append(s))

def state():
    sd = cell.series_data(); px = canvas.displayed_pixels(); m = canvas.mask()
    return dict(sd=(os.path.basename(sd.meta.series_dir) if sd else None),
                px=(None if px is None else (px.shape, float(px.min()), float(px.max()))),
                mask=(None if m is None else m.shape), idx=dock._index, status=dock._status_lbl.text(),
                label=canvas._label, stack=cell._canvas_stack.currentIndex(), running=cell._loader.isRunning())

root = os.path.join(FX, "errors")
outd = os.path.join(root, "vidi_output")
shutil.rmtree(outd, ignore_errors=True)
from viewer_vidi import workspace as W
images, _ = W.probe_workspace(root)
print("INFO items discovered:", [os.path.basename(p) for p in images])
check("T2.0 chmod-000 file is still listed as an item (is_dicom_file by .dcm name)",
      any(p.endswith("05_noperm.dcm") for p in images), str([os.path.basename(p) for p in images]))
ws = H.open_workspace(app, win, root)
check("T2.1 first (good) item loads", H.wait_loaded(app, cell), str(state()))
stems = [it.stem for it in ws.items]
dock._fmt_chk["png"].setChecked(True); dock._image_chk.setChecked(True)

def try_item(name, expect_loads):
    i = stems.index(name)
    errors.clear()
    dock._load_index(i)
    loaded = H.wait_loaded(app, cell, timeout=8.0)
    # drain
    t0 = time.time()
    while cell._loader.isRunning() and time.time() - t0 < 10: app.processEvents(); time.sleep(0.01)
    H.pump(app, 200)
    st = state()
    # Save attempt
    seen = H.auto_close_dialogs(app, 150)
    dock._save(advance=False); H.pump(app, 300)
    msg = dock._status_lbl.text()
    png = os.path.join(outd, "png", f"{name}_image.png")
    print(f"INFO {name}: loaded={loaded} errors={errors} state={st} save_status={msg!r} dialogs={seen} png_exists={os.path.isfile(png)}")
    return loaded, list(errors), st, msg, seen, os.path.isfile(png)

# ── garbage bytes .dcm ──
loaded, errs, st, msg, seen, png = try_item("01_garbage", False)
check("E1 garbage .dcm: loader emits load_error", bool(errs), str(errs))
check("E1 garbage .dcm: not displayed, nothing saved", not loaded and not png)
check("E1 garbage .dcm: Save gives a load-failure message, not 'still loading'",
      "loading" not in msg.lower(), f"status={msg!r}")
check("E1 garbage .dcm: dock/cell shows an error rather than a stuck loading page",
      st["stack"] != 1 or "error" in (st["label"] + st["status"]).lower(), f"stack={st['stack']} label={st['label']!r} status={st['status']!r}")
# Next still works?
dock._step(+1); ok2 = H.wait_loaded(app, cell, 10)
check("E1 Next after garbage item loads the next item", ok2 and dock._index == stems.index("02_trunc2k"), str(state()))

# ── truncated at 2 KB (inside header) ──
loaded, errs, st, msg, seen, png = try_item("02_trunc2k", False)
check("E2 2KB-truncated .dcm: load_error emitted or image shown", bool(errs) or loaded, f"errs={errs} loaded={loaded}")
if loaded:
    px = canvas.displayed_pixels()
    check("E2 2KB-truncated: displayed pixels are not all-zero garbage", px is not None and px.max() > 0, str(st["px"]))
check("E2 2KB-truncated: Save does not silently write a bogus image", not png or (loaded and canvas.displayed_pixels().max() > 0), f"png={png}")
check("E2 Save message is not 'still loading' for a failed load", loaded or "loading" not in msg.lower(), f"status={msg!r}")

# ── truncated inside pixel data (header intact) ──
loaded, errs, st, msg, seen, png = try_item("03_trunc_half", True)
px = canvas.displayed_pixels()
check("E3 half-pixel-data .dcm: either load_error or real pixels", bool(errs) or (loaded and px is not None and px.max() > 0),
      f"errs={errs} loaded={loaded} px={st['px']}")
check("E3 half-pixel-data .dcm: no silent all-zero export", not (png and px is not None and px.max() == 0),
      f"png={png} px={st['px']} status={msg!r}")

# ── 0-byte png ──
loaded, errs, st, msg, seen, png = try_item("04_empty", False)
check("E4 0-byte png: load_error emitted", bool(errs), str(errs))
check("E4 0-byte png: Save message not 'still loading'", "loading" not in msg.lower(), f"status={msg!r}")
check("E4 0-byte png: nothing saved", not png)

# ── chmod 000 dcm ──
loaded, errs, st, msg, seen, png = try_item("05_noperm", False)
check("E5 unreadable .dcm: load_error emitted", bool(errs), str(errs))
check("E5 unreadable .dcm: Save message not 'still loading'", "loading" not in msg.lower(), f"status={msg!r}")
check("E5 unreadable .dcm: nothing saved", not png)

# ── recovery: Next → good item loads; save works ──
dock._step(+1); ok = H.wait_loaded(app, cell, 10)
check("E6 Next after chain of failures loads good item", ok and dock._index == stems.index("06_good2"), str(state()))
dock._save(advance=False); H.pump(app, 200)
check("E6 Save on good item after failures works", os.path.isfile(os.path.join(outd, "png", "06_good2_image.png")), dock._status_lbl.text())

# ── Prev back into a failing item, then Save & Next (Ctrl+S path) ──
dock._load_index(stems.index("05_noperm")); H.pump(app, 500)
t0 = time.time()
while cell._loader.isRunning() and time.time() - t0 < 10: app.processEvents(); time.sleep(0.01)
dock.save_and_next(); H.pump(app, 200)
check("E7 Save&Next on failed item: stays on the item (no advance), status explains",
      dock._index == stems.index("05_noperm") and not ws.items[stems.index("05_noperm")].done, f"idx={dock._index} status={dock._status_lbl.text()!r}")

# ── item deleted after workspace opened: Next stuck? ──
root2 = os.path.join(FX, "errors_del")
shutil.rmtree(root2, ignore_errors=True); os.makedirs(root2)
for f in ("00_good.dcm", "06_good2.dcm"):
    shutil.copy(os.path.join(root, f), os.path.join(root2, f))
shutil.copy(os.path.join(root, "00_good.dcm"), os.path.join(root2, "03_mid.dcm"))
ws2 = H.open_workspace(app, win, root2)
H.wait_loaded(app, cell)
os.remove(os.path.join(root2, "03_mid.dcm"))
dock._step(+1); H.pump(app, 200)
st1 = (dock._index, dock._status_lbl.text())
dock._step(+1); H.pump(app, 200)
st2 = (dock._index, dock._status_lbl.text())
print("INFO deleted-item Next x2:", st1, st2)
check("E8 Next past a vanished item advances (does not get stuck on index)",
      st2[0] == 2 or st1[0] == 1, f"after 1st Next: {st1}, after 2nd Next: {st2}")

win.close(); app.processEvents()
nf = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - nf}/{len(results)} checks passed")
