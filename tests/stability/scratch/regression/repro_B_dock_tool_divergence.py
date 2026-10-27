"""Finding B: with the dock visible and Brush checked, two pre-existing paths put the
canvas back into "drag" without the dock noticing:
  (i)  the cell's ROI W/L button toggled off
  (ii) a series loaded by double-click in the study tree (MainWindow._on_series_selected → load_meta)
Expected: canvas mode == dock tool after either; a drag paints.
Observed: mode "drag", Brush still checked; a drag changes W/L and paints nothing.
Run: QT_QPA_PLATFORM=offscreen timeout 300 python repro_B_dock_tool_divergence.py"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
DCM0 = os.path.join(H.FIXTURES, "bpd1_20100101_1.dcm")
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
app, win = H.boot(); quad, dock, tree = win._quad, win._dock, win._tree
cell = quad.active_cell(); cv = cell.canvas()
assert H.load_file(app, cell, DCM0)
win._ws_btn.setChecked(True); app.processEvents()
print("dock visible → mode", cv.wl_mode(), "dock tool", dock._current_tool())

def probe(label):
    wl0 = cv.wl(); m0 = cv.mask_pixels()
    H.drag(app, cv, H.pt(cv, .3, .5), H.pt(cv, .6, .3))
    print(f"{label}: mode={cv.wl_mode()} dock_tool={dock._current_tool()} Brush_checked={dock._tool_btns['paint'].isChecked()} | drag: wl {wl0}->{cv.wl()} mask {m0}->{cv.mask_pixels()}")
    return cv.wl_mode() == dock._current_tool()

# (i) cell ROI W/L button on → off
cell._roi_btn.setChecked(True); app.processEvents(); cell._roi_btn.setChecked(False); app.processEvents()
ok1 = probe("(i) after ROI btn off")

# (ii) tree double-click load (real StudyTreeWidget path)
parent = os.path.dirname(H.FIXTURES)
tree._data_root = parent; tree._fs.setRootPath(parent); tree._set_root(parent)
pf = None; t0 = time.time()
while time.time() - t0 < 15 and pf is None:
    app.processEvents(); time.sleep(.02)
    d = tree._fs.index(H.FIXTURES)
    if d.isValid() and tree._proxy.mapFromSource(d).isValid():
        tree._tree.expand(tree._proxy.mapFromSource(d))
        f = tree._fs.index(DCM1)
        if f.isValid() and tree._proxy.mapFromSource(f).isValid(): pf = tree._proxy.mapFromSource(f)
assert pf is not None, "tree row not found"
dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); app.processEvents()
print("before tree load: mode", cv.wl_mode())
tree._on_double_clicked(pf); app.processEvents(); assert H.wait_loaded(app, cell)
print("loaded", cell.series_data().meta.series_dir, "| status:", win._status_series.text())
ok2 = probe("(ii) after tree load")
sys.exit(0 if (ok1 and ok2) else 1)
