"""Repro: the cell-header ROI button and the dock's tool buttons both drive canvas.set_wl_mode with no sync.
Brush selected in the dock → click the panel's ROI button → canvas 'roi' (dock still shows Brush checked);
un-click ROI → canvas 'drag' (dock still shows Brush) → the next left-drag changes W/L instead of painting.
Clicking Brush in the dock while ROI is checked puts the canvas in 'paint' with the ROI button still lit.
Expected: one visible mode; e.g. the dock reflects the canvas mode or un-ROI returns to the dock's tool.
Observed: see prints."""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
app, win = H.boot()
dock, quad = win._dock, win._quad
c0 = quad.cell_at(0); cv0 = c0.canvas()
ws = H.open_workspace(app, win, STAB + "/multipanel/ws"); H.wait_loaded(app, c0)
def st(tag): print(f"{tag:40s} dock tool={dock._current_tool():5s} ROI btn={c0._roi_btn.isChecked()!s:5s} canvas mode={cv0.wl_mode()}")
st("start (Brush)")
c0._roi_btn.click(); app.processEvents(); st("click ROI header button")
c0._roi_btn.click(); app.processEvents(); st("click ROI again (off)")
wl0 = cv0.wl(); H.drag(app, cv0, H.pt(cv0, .3, .3), H.pt(cv0, .6, .3))
print(f"  left-drag now: W/L {wl0} → {cv0.wl()} | mask px {cv0.mask_pixels()}  (user expected a brush stroke)")
c0._roi_btn.click(); app.processEvents(); st("click ROI (on)")
dock._tool_btns["paint"].click(); app.processEvents(); st("click Brush in dock")
c0._roi_btn.click(); app.processEvents(); st("click lit ROI (off)")
win.close(); app.processEvents()
