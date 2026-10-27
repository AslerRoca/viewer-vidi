"""blockSignals sync between ws_btn and dock; floating; close via dock X; tool modes restored."""
from common import *
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, fresh_ws("p14", [os.path.join(FIX, "bpd1_20100101_1.dcm")]))
c = quad.active_cell().canvas()
check("dock visible + btn checked + paint", dock.isVisible() and win._ws_btn.isChecked() and c.wl_mode() == "paint")
dock.close(); app.processEvents()
check("dock X-close: btn unchecked, drag restored", not dock.isVisible() and not win._ws_btn.isChecked() and c.wl_mode() == "drag", f"{win._ws_btn.isChecked()} {c.wl_mode()}")
win._ws_btn.click(); app.processEvents()
check("btn click reopens dock, tool re-applied", dock.isVisible() and c.wl_mode() == "paint")
dock.setFloating(True); app.processEvents()
check("floating: still visible, btn checked, tool kept", dock.isVisible() and win._ws_btn.isChecked() and c.wl_mode() == "paint", f"{dock.isVisible()} {win._ws_btn.isChecked()} {c.wl_mode()}")
dock.setFloating(False); app.processEvents()
check("re-docked: tool kept", dock.isVisible() and c.wl_mode() == "paint", c.wl_mode())
# window minimize → dock hidden? → modes
win.showMinimized(); app.processEvents(); H.pump(app, 100)
print("minimized: dock.isVisible", dock.isVisible(), "btn", win._ws_btn.isChecked(), "mode", c.wl_mode())
win.showNormal(); app.processEvents(); H.pump(app, 100)
check("after minimize/restore: dock visible, btn checked, tool paint", dock.isVisible() and win._ws_btn.isChecked() and c.wl_mode() == "paint", f"{dock.isVisible()} {win._ws_btn.isChecked()} {c.wl_mode()}")
# panel ROI button while dock open: who wins?
cell = quad.active_cell(); cell._roi_btn.click(); app.processEvents()
print("after panel ROI btn:", c.wl_mode())
quad._on_activated(quad.cells()[1]); quad._on_activated(cell); app.processEvents()
check("re-activating the panel re-applies the dock tool over ROI mode", c.wl_mode() == "paint", c.wl_mode())
win.close(); app.processEvents(); sys.exit(summary())
