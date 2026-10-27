"""REPRO (minor): (a) Save with an EMPTY active panel says 'Image still loading';
(b) the panel's own ROI-W/L button stays checked after the dock re-applies its tool;
(c) same file through a symlinked directory is refused as 'Panel mismatch' (abspath, not realpath)."""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
app, win = H.boot()
dock, quad = win._dock, win._quad; cell = quad.active_cell(); canvas = cell.canvas()
root = fresh_ws("R5", n=2); ws = H.open_workspace(app, win, root)
# (a)
quad._set_active(quad.cell_at(1)); app.processEvents()
dock._save(advance=False); app.processEvents()
print("(a) empty active panel -> status:", repr(dock._status_lbl.text()), "| expected: a message saying the active panel is empty / load the item")
quad._set_active(cell); app.processEvents()
# (b)
cell._roi_btn.setChecked(True); app.processEvents(); m1 = canvas.wl_mode()
dock.on_active_cell_changed(cell); app.processEvents()
print(f"(b) panel ROI button: mode {m1} -> {canvas.wl_mode()} after dock re-apply; ROI button still checked={cell._roi_btn.isChecked()} | expected: button and mode agree")
cell._roi_btn.setChecked(False); app.processEvents(); dock._apply_tool()
# (c)
link = os.path.join(WSROOT, "R5_link")
if os.path.lexists(link): os.remove(link)
os.symlink(root, link)
H.load_file(app, cell, os.path.join(link, os.path.basename(ws.items[0].path))); dock._apply_tool(); stroke(app, canvas)
seen = H.auto_close_dialogs(app, 200); dock._save(advance=False); app.processEvents()
print(f"(c) same file via symlink: dialogs={[s[1] for s in seen]} done={ws.items[0].done} | expected: accepted (os.path.realpath / samefile)")
win.close(); app.processEvents()
