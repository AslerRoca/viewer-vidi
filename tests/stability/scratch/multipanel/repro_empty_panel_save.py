"""Repro: Save / Save & Next with an EMPTY panel active reports 'Image still loading — try again in a moment.'
The panel is not loading anything (never had a series); the message never becomes true.
Expected: a message naming the cause (empty panel / load the item into this panel). Observed: the loading message."""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
app, win = H.boot()
dock, quad = win._dock, win._quad
c0, c1 = quad.cell_at(0), quad.cell_at(1)
ws = H.open_workspace(app, win, STAB + "/multipanel/ws"); H.wait_loaded(app, c0)
c1.activated.emit(); app.processEvents()
print("active cell:", quad.cells().index(quad.active_cell()), "| series_data:", c1.series_data(), "| loader running:", c1._loader.isRunning())
dock._save(advance=False); app.processEvents()
print("status after Save:", repr(dock._status_lbl.text()))
H.pump(app, 500)
dock._save(advance=False); app.processEvents()
print("status after Save, 0.5 s later:", repr(dock._status_lbl.text()))
win.close(); app.processEvents()
