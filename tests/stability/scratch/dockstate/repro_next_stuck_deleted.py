"""REPRO: when an item's file disappears after the workspace was opened, _load_index()
leaves _index unchanged, so Next/Save&Next can never move past it (only a double-click
on a later item recovers); the 'Saved ...' status is overwritten by 'Cannot open ...'."""
import os, sys
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/dockstate")
from common import *
app, win = H.boot()
dock, quad = win._dock, win._quad; cell = quad.active_cell(); canvas = cell.canvas()
root = fresh_ws("R4", n=4)
ws = H.open_workspace(app, win, root)
os.remove(ws.items[1].path)
stroke(app, canvas); dock.save_and_next(); app.processEvents()
print(f"Save&Next with item1 deleted: item0 done={ws.items[0].done} index={dock._index} status={dock._status_lbl.text()!r}")
dock._next_btn.click(); app.processEvents(); i1 = dock._index
dock._next_btn.click(); app.processEvents(); i2 = dock._index
print(f"Next, Next: index {i1}, {i2}  next_btn enabled={dock._next_btn.isEnabled()}")
print("EXPECTED: unreadable item is skipped (index advances to 2) or marked, and the 'Saved' message is kept")
win.close(); app.processEvents(); sys.exit(1 if i2 == 0 else 0)
