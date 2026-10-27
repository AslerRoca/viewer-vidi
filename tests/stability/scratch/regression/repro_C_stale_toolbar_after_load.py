"""Finding C (pre-existing): after a series is loaded through the study tree
(StudyTreeWidget.series_selected → MainWindow._on_series_selected), the toolbar
W/L spin boxes keep their previous values and the type badge stays empty until
the user drags W/L or switches panels. canvas.set_wl() never emits wl_changed and
_on_series_selected does not sync — identical on wip/invert.
Run: QT_QPA_PLATFORM=offscreen timeout 300 python repro_C_stale_toolbar_after_load.py"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
DCM1 = os.path.join(H.FIXTURES, "bpd1_20100101_2.dcm")
app, win = H.boot(); quad, tree = win._quad, win._tree
cell = quad.active_cell(); cv = cell.canvas()
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
assert pf is not None
print("before load: spins", win._wc_spin.value(), win._ww_spin.value(), "badge", repr(win._type_badge.text()))
tree._on_double_clicked(pf); app.processEvents(); assert H.wait_loaded(app, cell); H.pump(app, 300)
print("after tree load: canvas wl", cv.wl(), "| spins", win._wc_spin.value(), win._ww_spin.value(), "| badge", repr(win._type_badge.text()), "| status", win._status_series.text())
stale = abs(win._wc_spin.value() - cv.wl()[0]) > 0.6 or win._type_badge.text() == ""
sys.exit(1 if stale else 0)
