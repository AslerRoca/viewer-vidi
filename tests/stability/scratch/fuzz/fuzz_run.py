"""Seeded random-action fuzzer for the viewer-vidi annotation workspace.

usage: fuzz_run.py --seed N --actions K --out RUNDIR [--replay LOG.jsonl] [--keep IDX,IDX,...] [--nowait P]

Writes RUNDIR/actions.jsonl (one JSON per action, replayable), RUNDIR/violations.json,
RUNDIR/summary.json. Exit code 0 = no violations, 2 = violations, anything else = crash.
"""
import os, sys, json, time, random, shutil, traceback, argparse
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
import numpy as np

SP   = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/fuzz"
WS_SRC = None
EXTRA_FIXTURES = (
    [os.path.join(H.FIXTURES, f) for f in sorted(os.listdir(H.FIXTURES)) if f.endswith(".dcm")]
    + ["/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii",
       "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"]
)

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--actions", type=int, default=300)
ap.add_argument("--out", required=True)
ap.add_argument("--replay", default=None)
ap.add_argument("--keep", default=None, help="comma list of action indices of the replay log to execute")
ap.add_argument("--nowait", type=float, default=0.0, help="probability of NOT waiting after a load")
ap.add_argument("--no-desync", action="store_true", help="drop load_file/roi_btn (known tool desync paths)")
ap.add_argument("--ws", default="ws", help="source workspace dir name under the fuzz scratch dir")
args = ap.parse_args()

RUN = args.out
WS_SRC = os.path.join(SP, args.ws)
os.makedirs(RUN, exist_ok=True)
WS = os.path.join(RUN, "ws")
if os.path.isdir(WS):
    shutil.rmtree(WS)
shutil.copytree(WS_SRC, WS)
OUT_NAME = "vidi_output"
EXPECTED_SHAPES = {"bpd1_20100101_1": (2044, 1514), "bpd1_20100101_2": (2044, 1514),
                   "bpd3_20100419_1": (2570, 2040), "bpd3_20100502_2": (2570, 2040),
                   "synth2d_160x120": (160, 120), "synth_300x200": (200, 300), "C": (288, 384)}

rng = random.Random(args.seed)
log_f = open(os.path.join(RUN, "actions.jsonl"), "w")
violations = []
shapes = {}            # stem -> displayed pixel shape (recorded on load)
save_shapes = {}       # stem -> displayed pixel shape at the last successful save
save_log = []

def viol(kind, idx, msg, **extra):
    v = dict(kind=kind, idx=idx, msg=msg, **extra)
    violations.append(v)
    print(f"VIOLATION #{len(violations)} [{kind}] at action {idx}: {msg}", flush=True)

# ── boot ─────────────────────────────────────────────────────────────────────
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QApplication
from viewer_vidi import workspace as W
from PIL import Image

app, win = H.boot()
dock, quad = win._dock, win._quad
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog, QMessageBox
DIALOGS = []   # (class, title, text) of every dialog auto-closed during the run
def _dialog_sweep():
    for w in app.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible():
            DIALOGS.append((type(w).__name__, w.windowTitle(), w.text() if isinstance(w, QMessageBox) else ""))
            w.reject()
_sweep = QTimer(); _sweep.setInterval(30); _sweep.timeout.connect(_dialog_sweep); _sweep.start()
cells = quad.cells()
ws = H.open_workspace(app, win, WS, "image", out_dir=OUT_NAME)
for chk in dock._fmt_chk.values():
    chk.setChecked(True)
items = ws.items
N_ITEMS = len(items)
print("items:", [it.stem for it in items], flush=True)
stem_by_path = {os.path.abspath(it.path): it.stem for it in items}

def active():
    c = quad.active_cell()
    return c, c.canvas()

def record_shape(cell):
    sd, px = cell.series_data(), cell.canvas().displayed_pixels()
    if sd is not None and px is not None:
        p = os.path.abspath(sd.meta.series_dir)
        if p in stem_by_path:
            shapes[stem_by_path[p]] = tuple(px.shape)

def wait(cell, force=False):
    if force or rng.random() >= args.nowait:
        ok = H.wait_loaded(app, cell)
        record_shape(cell)
        return ok
    return None

def rpt(canvas, kind):
    """random widget point: 'img' = inside drawn image, 'edge' = possibly outside, 'any' = anywhere in widget."""
    if kind == "img":
        return H.pt(canvas, rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98))
    if kind == "edge":
        return H.pt(canvas, rng.uniform(-0.2, 1.2), rng.uniform(-0.2, 1.2))
    return QPoint(rng.randint(-5, max(1, canvas.width()) + 5), rng.randint(-5, max(1, canvas.height()) + 5))

def current_tool():
    return dock._current_tool()

def wheel(canvas, pos, delta, mods):
    ev = QWheelEvent(QPointF(pos), QPointF(canvas.mapToGlobal(pos)), QPoint(0, 0), QPoint(0, delta),
                     Qt.NoButton, mods, Qt.NoScrollPhase, False)
    QApplication.sendEvent(canvas, ev)

# ── action generators: each returns a dict with 'name' + params (JSON-able) ──
TOOLS = ["drag", "paint", "poly", "rect"]
def gen_action():
    choices = [
        ("tool", 8), ("brush", 4), ("erase", 3), ("drag", 14), ("click", 8), ("dclick", 5),
        ("key", 6), ("undo", 4), ("clear", 2), ("next", 4), ("prev", 3), ("list_dclick", 3),
        ("save", 4), ("save_next", 3), ("dock_toggle", 2), ("invert", 3), ("zoom", 4),
        ("wheel", 2), ("rpan", 3), ("cell", 5), ("load_file", 3), ("fullscreen", 2), ("resize", 2),
        ("shortcut", 2), ("roi_btn", 2), ("win_hide_show", 1), ("view", 3), ("slice", 3),
    ]
    if args.no_desync:
        choices = [(n, w) for n, w in choices if n not in ("load_file", "roi_btn")]
    names = [n for n, w in choices for _ in range(w)]
    name = rng.choice(names)
    a = {"name": name}
    if name == "tool":        a["mode"] = rng.choice(TOOLS)
    elif name == "brush":     a["r"] = rng.randint(1, 200)
    elif name in ("drag", "rpan"):
        k = rng.choice(["img", "img", "edge", "any"])
        a["k"] = k; a["steps"] = rng.randint(1, 12)
        a["n"] = rng.randint(1, 3)   # number of consecutive segments
    elif name in ("click", "dclick"):
        a["k"] = rng.choice(["img", "img", "edge", "any"]); a["n"] = rng.randint(1, 5)
        a["button"] = rng.choice(["L", "L", "L", "R"]) if name == "click" else "L"
    elif name == "key":       a["key"] = rng.choice(["Return", "Enter", "Escape", "I", "Space"])
    elif name == "list_dclick": a["i"] = rng.randint(0, N_ITEMS - 1)
    elif name in ("save", "save_next"): a["image"] = rng.random() < 0.5
    elif name == "invert":    pass
    elif name == "zoom":      a["dir"] = rng.choice([1, -1]); a["n"] = rng.randint(1, 6)
    elif name == "wheel":     a["dir"] = rng.choice([1, -1]); a["mods"] = rng.choice(["none", "shift"])
    elif name == "cell":      a["i"] = rng.randint(0, 3)
    elif name == "load_file": a["path"] = rng.choice(EXTRA_FIXTURES + [it.path for it in items])
    elif name == "fullscreen": a["i"] = rng.randint(0, 3)
    elif name == "resize":    a["w"] = rng.randint(320, 1700); a["h"] = rng.randint(240, 1000)
    elif name == "shortcut":  a["which"] = rng.choice(["Ctrl+Z", "Ctrl+S", "Ctrl+Shift+W", "Ctrl+I"])
    elif name == "view":      a["mode"] = rng.choice(["AXIAL", "SAGITTAL", "CORONAL"])
    elif name == "slice":     a["f"] = rng.random()
    return a

# points are generated at execution time from the rng too, but we store them so replay is exact
def pts_for(a, canvas):
    if "pts" in a:
        return [QPoint(x, y) for x, y in a["pts"]]
    n = a.get("n", 1)
    if a["name"] in ("drag", "rpan"):
        pts = [rpt(canvas, a["k"]) for _ in range(n + 1)]
    else:
        pts = [rpt(canvas, a["k"]) for _ in range(n)]
    a["pts"] = [[p.x(), p.y()] for p in pts]
    return pts

KEYS = {"Return": Qt.Key_Return, "Enter": Qt.Key_Enter, "Escape": Qt.Key_Escape, "I": Qt.Key_I, "Space": Qt.Key_Space}

def do_save(idx, a, advance):
    cell, canvas = active()
    item = items[dock._index] if dock._index >= 0 else None
    sd = cell.series_data()
    px = canvas.displayed_pixels()
    dock._image_chk.setChecked(a["image"])
    pre = dict(mask_px=canvas.mask_pixels(), rect=canvas.crop_rect(), index=dock._index,
               shape=None if px is None else tuple(px.shape),
               shown=None if sd is None else os.path.abspath(sd.meta.series_dir),
               item=None if item is None else os.path.abspath(item.path),
               dock_visible=dock.isVisible(), invert=canvas.invert(), wl=canvas.wl())
    n0 = len(DIALOGS)
    dock._status_lbl.setText("")          # the refusal path leaves the label untouched
    if advance:
        dock.save_and_next()
    else:
        dock._save(advance=False)
    app.processEvents()
    seen = DIALOGS[n0:]
    status = dock._status_lbl.text()
    rec = dict(idx=idx, advance=advance, pre=pre, dialogs=list(seen), status=status)
    save_log.append(rec)
    a["result"] = {"status": status, "dialogs": [d[1] for d in seen]}
    # ── consistency checks ──
    expect_mismatch = (pre["shown"] is not None and pre["item"] is not None and pre["shown"] != pre["item"])
    got_mismatch = any(d[1] == "Panel mismatch" for d in seen)
    if any(d[1] == "Export failed" for d in seen):
        viol("export_failed", idx, f"Export failed dialog: {seen}")
    if pre["shown"] is None or pre["shape"] is None:
        if not status.startswith("Image still loading") and not status.startswith("Open a workspace"):
            viol("save_without_image", idx, f"no image/pixels shown but status={status!r} dialogs={seen}")
        return
    if expect_mismatch and not got_mismatch:
        viol("mismatch_not_refused", idx, f"panel shows {pre['shown']} item {pre['item']} but no refusal; status={status!r}")
    if got_mismatch and not expect_mismatch:
        viol("spurious_mismatch", idx, f"refused although panel shows item: {pre}")
    if got_mismatch:
        return
    if status.startswith("Saved"):
        save_shapes[item.stem] = pre["shape"]
        # the item must be done, its row in the manifest, files on disk, mask png consistent
        if not item.done:
            viol("done_flag", idx, "status Saved but item.done False")
        man = W.read_manifest(ws.manifest_path)
        row = man.get(item.stem)
        if row is None:
            viol("manifest_row_missing", idx, f"status Saved but no manifest row for {item.stem}")
            return
        files = row["files"].split()
        missing = [f for f in files if not os.path.isfile(os.path.join(ws.out_dir, f))]
        if missing:
            viol("files_missing", idx, f"manifest files missing on disk: {missing}")
        if int(row["mask_pixels"]) != pre["mask_px"]:
            viol("manifest_mask_px", idx, f"manifest mask_pixels {row['mask_pixels']} != canvas {pre['mask_px']}")
        mp = os.path.join(ws.out_dir, "png", f"{item.stem}_mask.png")
        if pre["mask_px"] > 0:
            if not os.path.isfile(mp):
                viol("mask_png_missing", idx, f"mask had {pre['mask_px']} px but {mp} missing")
            else:
                m = np.array(Image.open(mp))
                if m.shape != pre["shape"]:
                    viol("mask_png_shape", idx, f"mask png {m.shape} != pixels {pre['shape']}")
                if not set(np.unique(m)).issubset({0, 255}):
                    viol("mask_png_values", idx, f"mask png values {np.unique(m)[:10]}")
                if int((m == 255).sum()) != pre["mask_px"]:
                    viol("mask_png_count", idx, f"mask png 255-count {(m == 255).sum()} != canvas {pre['mask_px']}")
                if "png/" + os.path.basename(mp) not in files:
                    viol("manifest_files_list", idx, f"mask png written but not in manifest files: {files}")
        else:
            if any(f.endswith("_mask.png") for f in files):
                viol("empty_mask_written", idx, f"mask empty but manifest lists {files}")
        rect = pre["rect"]
        rp = os.path.join(ws.out_dir, "png", f"{item.stem}_roi.png")
        if rect is not None:
            if not os.path.isfile(rp):
                viol("roi_png_missing", idx, f"rect {rect} but {rp} missing")
            else:
                r = np.array(Image.open(rp))
                exp = (rect[3] - rect[1], rect[2] - rect[0])
                if r.shape != exp:
                    viol("roi_png_shape", idx, f"roi png {r.shape} != rect {exp}")
            if (row["x0"], row["y0"], row["x1"], row["y1"]) != tuple(str(v) for v in rect):
                viol("manifest_rect", idx, f"manifest rect {row['x0'], row['y0'], row['x1'], row['y1']} != {rect}")
        else:
            if any(f.endswith("_roi.png") for f in files):
                viol("roi_without_rect", idx, f"no rect but manifest lists {files}")
        if a["image"]:
            ip = os.path.join(ws.out_dir, "png", f"{item.stem}_image.png")
            if not os.path.isfile(ip):
                viol("image_png_missing", idx, f"Original ticked but {ip} missing")
            else:
                im = np.array(Image.open(ip))
                if im.shape != pre["shape"]:
                    viol("image_png_shape", idx, f"image png {im.shape} != pixels {pre['shape']}")
        if advance and pre["index"] < len(items) - 1 and dock._index != pre["index"] + 1:
            viol("advance", idx, f"Save&Next did not advance: {pre['index']} -> {dock._index}")
        if advance and pre["index"] < len(items) - 1:
            wait(quad.active_cell(), force=True)
    elif status.startswith("Nothing to save"):
        if pre["mask_px"] > 0 or pre["rect"] is not None or a["image"]:
            viol("nothing_to_save", idx, f"'Nothing to save' but mask_px={pre['mask_px']} rect={pre['rect']} image={a['image']}")
    else:
        viol("save_status", idx, f"unexpected save status {status!r} dialogs={seen}")

STATE = {"last": None, "clear_pre": None, "desync": False}

def execute(idx, a):
    name = a["name"]
    cell, canvas = active()
    if name == "tool":
        dock._tool_btns[a["mode"]].click(); app.processEvents()
        if dock.isVisible() and canvas.wl_mode() != a["mode"]:
            viol("tool_apply", idx, f"clicked {a['mode']} but active canvas mode {canvas.wl_mode()}")
    elif name == "brush":
        dock._brush_spin.setValue(a["r"])
    elif name == "erase":
        dock._erase_chk.toggle()
    elif name == "drag":
        pts = pts_for(a, canvas)
        for p0, p1 in zip(pts, pts[1:]):
            H.drag(app, canvas, p0, p1, steps=a["steps"])
    elif name == "rpan":
        pts = pts_for(a, canvas)
        for p0, p1 in zip(pts, pts[1:]):
            H.drag(app, canvas, p0, p1, steps=a["steps"], button=Qt.RightButton)
    elif name == "click":
        b = Qt.RightButton if a["button"] == "R" else Qt.LeftButton
        for p in pts_for(a, canvas):
            H.click(canvas, p, b)
    elif name == "dclick":
        fs_before = quad.is_fullscreen(); mode = canvas.wl_mode()
        for p in pts_for(a, canvas):
            H.dclick(canvas, p)
        app.processEvents()
        if mode == "poly" and quad.is_fullscreen() != fs_before:
            viol("dclick_fullscreen", idx, "double-click in poly mode toggled fullscreen")
    elif name == "key":
        H.key(canvas, KEYS[a["key"]])
    elif name == "undo":
        pre_px, pre_rect = canvas.mask_pixels(), canvas.crop_rect()
        dock._undo_btn.click(); app.processEvents()
        if STATE.get("last") == "clear" and STATE.get("clear_pre") is not None:
            cpx, crect = STATE["clear_pre"]
            if canvas.mask_pixels() == cpx and crect is not None and canvas.crop_rect() is None and not STATE.get("undo_rect_reported"):
                STATE["undo_rect_reported"] = True
                viol("undo_rect_after_clear", idx, f"Undo after Clear restored the mask ({cpx} px) but not the rectangle {crect}")
    elif name == "clear":
        STATE["clear_pre"] = (canvas.mask_pixels(), canvas.crop_rect())
        dock._clear_btn.click(); app.processEvents()
        if canvas.mask_pixels() != 0 or canvas.crop_rect() is not None:
            viol("clear", idx, f"after Clear mask_px={canvas.mask_pixels()} rect={canvas.crop_rect()}")
    elif name in ("next", "prev"):
        before = dock._index
        (dock._next_btn if name == "next" else dock._prev_btn).click(); app.processEvents()
        d = 1 if name == "next" else -1
        exp = before + d if 0 <= before + d < len(items) else before
        if dock._index != exp:
            viol("nav_index", idx, f"{name}: index {before} -> {dock._index}, expected {exp}")
        if dock._index != before:
            c2 = quad.active_cell()
            ok = wait(c2)
            if ok is not None:
                sd = c2.series_data()
                if not ok or sd is None or os.path.abspath(sd.meta.series_dir) != os.path.abspath(items[dock._index].path):
                    viol("nav_load", idx, f"{name}: active panel shows {None if sd is None else sd.meta.series_dir}, item {items[dock._index].path}")
                if dock.isVisible() and c2.canvas().wl_mode() != current_tool():
                    viol("tool_after_nav", idx, f"after {name} canvas mode {c2.canvas().wl_mode()} != tool {current_tool()}")
                if ok and (c2.canvas().mask_pixels() != 0 or c2.canvas().crop_rect() is not None):
                    viol("stale_annotation", idx, f"after {name} new item has mask_px={c2.canvas().mask_pixels()} rect={c2.canvas().crop_rect()}")
    elif name == "list_dclick":
        before = dock._index
        dock._list.itemDoubleClicked.emit(dock._list.item(a["i"])); app.processEvents()
        if dock._index != a["i"]:
            viol("list_index", idx, f"list dclick {a['i']}: index {before} -> {dock._index}")
        c2 = quad.active_cell(); ok = wait(c2)
        if ok is not None:
            sd = c2.series_data()
            if not ok or sd is None or os.path.abspath(sd.meta.series_dir) != os.path.abspath(items[a['i']].path):
                viol("list_load", idx, f"after list dclick {a['i']} active panel shows {None if sd is None else sd.meta.series_dir}")
    elif name == "save":
        do_save(idx, a, advance=False)
    elif name == "save_next":
        do_save(idx, a, advance=True)
    elif name == "dock_toggle":
        was = dock.isVisible()
        win._ws_btn.toggle(); app.processEvents()
        if dock.isVisible() == was:
            viol("dock_toggle", idx, f"dock visibility unchanged ({was})")
        if not dock.isVisible():
            bad = [i for i, c in enumerate(cells) if c.canvas().wl_mode() in ("paint", "poly", "rect")]
            if bad:
                viol("dock_hide_modes", idx, f"dock hidden but cells {bad} still in annotation mode")
        else:
            if quad.active_cell().canvas().wl_mode() != current_tool():
                viol("dock_show_mode", idx, f"dock shown, active mode {quad.active_cell().canvas().wl_mode()} != {current_tool()}")
    elif name == "invert":
        was = cell.invert()
        win._invert_btn.toggle(); app.processEvents()
        if cell.invert() == was:
            viol("invert", idx, f"invert unchanged {was}")
    elif name == "zoom":
        p = H.pt(canvas, 0.5, 0.5)
        for _ in range(a["n"]):
            wheel(canvas, p, 120 * a["dir"], Qt.ControlModifier)
    elif name == "wheel":
        p = H.pt(canvas, 0.5, 0.5)
        wheel(canvas, p, 120 * a["dir"], Qt.ShiftModifier if a["mods"] == "shift" else Qt.NoModifier)
    elif name == "cell":
        c2 = cells[a["i"]]
        if c2.isVisible():
            pts = pts_for({"name": "click", "k": "img", "n": 1, **({"pts": a["pts"]} if "pts" in a else {})}, c2.canvas())
            a["pts"] = [[p.x(), p.y()] for p in pts]
            H.click(c2.canvas(), pts[0]); app.processEvents()
            if quad.active_cell() is not c2:
                viol("cell_activate", idx, f"click on cell {a['i']} did not activate it")
            if dock.isVisible() and c2.canvas().wl_mode() != current_tool():
                viol("tool_after_cell", idx, f"active cell {a['i']} mode {c2.canvas().wl_mode()} != tool {current_tool()}")
        else:
            a["skipped"] = "hidden"
    elif name == "load_file":
        ok = H.load_file(app, quad.active_cell(), a["path"], timeout=0.0)   # non-blocking request
        ok = wait(quad.active_cell())
        if ok is False:
            viol("load_timeout", idx, f"load_file {a['path']} did not finish")
    elif name == "fullscreen":
        quad._toggle_fullscreen(cells[a["i"]]); app.processEvents()
    elif name == "resize":
        win.resize(a["w"], a["h"]); app.processEvents()
    elif name == "shortcut":
        from PyQt5.QtGui import QKeySequence
        from PyQt5.QtTest import QTest
        k = {"Ctrl+Z": (Qt.Key_Z, Qt.ControlModifier), "Ctrl+S": (Qt.Key_S, Qt.ControlModifier),
             "Ctrl+Shift+W": (Qt.Key_W, Qt.ControlModifier | Qt.ShiftModifier), "Ctrl+I": (Qt.Key_I, Qt.ControlModifier)}[a["which"]]
        if a["which"] == "Ctrl+S":
            # the shortcut would call dock.save_and_next; drive it through the same slot with dialog guard
            a["image"] = dock._image_chk.isChecked()
            do_save(idx, a, advance=True)
        else:
            QTest.keyClick(win, k[0], k[1]); app.processEvents()
    elif name == "view":
        sd = cell.series_data()
        if sd is not None and sd.series_type.value in ("3D", "3D-T") and cell.canvas().displayed_pixels() is not None:
            before = cell.canvas().displayed_pixels().shape
            cell._set_view(a["mode"]); app.processEvents()
            px = cell.canvas().displayed_pixels()
            a["shape"] = [list(before), None if px is None else list(px.shape)]
            if px is not None and dock.isVisible() and cell is quad.active_cell() and cell.canvas().wl_mode() != current_tool():
                viol("tool_after_view", idx, f"view switch reset mode to {cell.canvas().wl_mode()}")
        else:
            a["skipped"] = "not 3D"
    elif name == "slice":
        sl = getattr(cell, "_slice_slider", None)
        if sl is not None and sl.isVisible() and sl.maximum() > 0:
            v = int(round(a["f"] * sl.maximum())); sl.setValue(v); app.processEvents()
            a["value"] = v
        else:
            a["skipped"] = "no slice slider"
    elif name == "roi_btn":
        cell._roi_btn.toggle(); app.processEvents()
        a["roi_checked"] = cell._roi_btn.isChecked()
    elif name == "win_hide_show":
        dv = dock.isVisible()
        win.hide(); app.processEvents(); win.show(); app.processEvents()
        if dock.isVisible() != dv:
            viol("win_hide_show", idx, f"dock visibility changed {dv} -> {dock.isVisible()} across window hide/show")
    else:
        raise RuntimeError("unknown action " + name)

def check_invariants(idx, a):
    for i, c in enumerate(cells):
        bad = H.invariants(c.canvas())
        if bad:
            viol("invariant", idx, f"cell {i}: {bad}", action=a)
    # dock-level: if visible and workspace open, list row == index
    if dock._ws is not None and dock._index >= 0 and dock._list.currentRow() != dock._index:
        viol("list_row", idx, f"list row {dock._list.currentRow()} != index {dock._index}", action=a)
    # active tool sync while visible
    if dock.isVisible():
        m = quad.active_cell().canvas().wl_mode()
        desync = m != current_tool()
        if desync and not STATE["desync"]:
            viol("tool_sync", idx, f"after {a['name']}: dock visible, tool {current_tool()} but active canvas mode {m}", action=a)
        STATE["desync"] = desync
    else:
        STATE["desync"] = False

# ── main loop ────────────────────────────────────────────────────────────────
replay = None
if args.replay:
    with open(args.replay) as f:
        replay = [json.loads(l) for l in f if l.strip()]
    if args.keep:
        keep = set(int(x) for x in args.keep.split(","))
        replay = [a for a in replay if a["idx"] in keep]

record_shape(quad.active_cell())
n = len(replay) if replay is not None else args.actions
t_start = time.time()
for idx in range(n):
    if replay is not None:
        a = dict(replay[idx]); orig_idx = a.pop("idx", idx); a.pop("result", None); a.pop("error", None); a.pop("skipped", None)
    else:
        a = gen_action(); orig_idx = idx
    a["idx"] = orig_idx
    try:
        execute(idx, a)
        app.processEvents()
    except Exception:
        tb = traceback.format_exc()
        a["error"] = tb
        viol("exception", idx, f"{a['name']}: {tb.strip().splitlines()[-1]}", traceback=tb, action=a)
    try:
        check_invariants(idx, a)
    except Exception:
        tb = traceback.format_exc()
        viol("invariant_check_exception", idx, tb.strip().splitlines()[-1], traceback=tb, action=a)
    STATE["last"] = a["name"]
    log_f.write(json.dumps(a) + "\n"); log_f.flush()
log_f.close()

# make sure no loader is mid-flight before the audit / close
for c in cells:
    if c.series_data() is None and c.canvas().displayed_pixels() is None:
        pass
for c in cells:
    H.wait_loaded(app, c, timeout=5.0)
    record_shape(c)

# ── post-seed audit ──────────────────────────────────────────────────────────
man = W.read_manifest(ws.manifest_path)
audit = []
for stem, row in man.items():
    files = row["files"].split()
    missing = [f for f in files if not os.path.isfile(os.path.join(ws.out_dir, f))]
    if missing:
        viol("audit_files_missing", -1, f"{stem}: manifest files missing {missing}")
    mp = os.path.join(ws.out_dir, "png", f"{stem}_mask.png")
    if os.path.isfile(mp):
        m = np.array(Image.open(mp))
        vals = set(np.unique(m).tolist())
        if not vals.issubset({0, 255}):
            viol("audit_mask_values", -1, f"{stem}_mask.png values {sorted(vals)[:10]}")
        exp = save_shapes.get(stem, shapes.get(stem, EXPECTED_SHAPES.get(stem)))
        if exp is None:
            viol("audit_no_shape", -1, f"{stem}: no recorded pixel shape")
        elif m.shape != exp:
            viol("audit_mask_shape", -1, f"{stem}_mask.png shape {m.shape} != item pixel shape {exp}")
        if int(row["mask_pixels"]) != int((m == 255).sum()) and ("png/" + os.path.basename(mp)) in files:
            viol("audit_mask_count", -1, f"{stem}: manifest mask_pixels {row['mask_pixels']} != png 255-count {(m == 255).sum()}")
        # stale check: file on disk but not in manifest files
        if ("png/" + os.path.basename(mp)) not in files:
            audit.append(f"stale {stem}_mask.png on disk not listed in manifest row")
    np_ = os.path.join(ws.out_dir, "nifti", f"{stem}_mask.nii.gz")
    if os.path.isfile(np_):
        import nibabel as nib
        ni = nib.load(np_); arr = np.asarray(ni.dataobj)
        exp = save_shapes.get(stem, shapes.get(stem, EXPECTED_SHAPES.get(stem)))
        if arr.dtype != np.uint8 or not set(np.unique(arr).tolist()).issubset({0, 1}):
            viol("audit_nifti_mask_values", -1, f"{stem}_mask.nii.gz dtype {arr.dtype} values {np.unique(arr)[:10]}")
        if exp is not None and arr.shape != (exp[1], exp[0], 1):
            viol("audit_nifti_mask_shape", -1, f"{stem}_mask.nii.gz shape {arr.shape} != {(exp[1], exp[0], 1)}")
    rmp = os.path.join(ws.out_dir, "png", f"{stem}_roi_mask.png")
    if os.path.isfile(rmp) and f"png/{stem}_roi_mask.png" in files and row["x0"] != "":
        rm = np.array(Image.open(rmp)); exp_r = (int(row["y1"]) - int(row["y0"]), int(row["x1"]) - int(row["x0"]))
        if rm.shape != exp_r:
            viol("audit_roi_mask_shape", -1, f"{stem}_roi_mask.png {rm.shape} != rect {exp_r}")
        if not set(np.unique(rm).tolist()).issubset({0, 255}):
            viol("audit_roi_mask_values", -1, f"{stem}_roi_mask.png values {np.unique(rm)[:10]}")
    for suf in ("roi", "roi_mask", "image"):
        p = os.path.join(ws.out_dir, "png", f"{stem}_{suf}.png")
        if os.path.isfile(p) and f"png/{stem}_{suf}.png" not in files:
            audit.append(f"stale {stem}_{suf}.png on disk not listed in manifest row")

summary = dict(seed=args.seed, actions=n, elapsed=round(time.time() - t_start, 1), violations=len(violations),
               manifest_rows=len(man), saves=len(save_log), shapes=shapes, stale=audit,
               kinds=sorted(set(v["kind"] for v in violations)))
with open(os.path.join(RUN, "violations.json"), "w") as f:
    json.dump(violations, f, indent=1, default=str)
with open(os.path.join(RUN, "summary.json"), "w") as f:
    json.dump(summary, f, indent=1, default=str)
with open(os.path.join(RUN, "saves.json"), "w") as f:
    json.dump(save_log, f, indent=1, default=str)
print("SUMMARY", json.dumps(summary, default=str), flush=True)
win.close(); app.processEvents()
sys.exit(2 if violations else 0)
