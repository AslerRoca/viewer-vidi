"""Export lens: Save of an 8192x8192 raster item through the dock — wall time the GUI thread is blocked, per format."""
import os, sys, time, shutil; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np
from PIL import Image
WS = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/export/ws_big"; shutil.rmtree(WS, ignore_errors=True); os.makedirs(WS)
rng = np.random.default_rng(1)
Image.fromarray((rng.random((8192, 8192)) * 255).astype(np.uint8), "L").save(os.path.join(WS, "big.png"))
app, win = H.boot(); dock, quad = win._dock, win._quad
ws = H.open_workspace(app, win, WS); cell = quad.active_cell(); canvas = cell.canvas()
print("loaded", canvas.displayed_pixels().shape)
dock._tool_btns["paint"].setChecked(True); dock._apply_tool(); dock._brush_spin.setValue(50); dock._apply_brush()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.3), H.pt(canvas, 0.7, 0.35))
dock._tool_btns["rect"].setChecked(True); dock._apply_tool(); H.drag(app, canvas, H.pt(canvas, 0.1, 0.1), H.pt(canvas, 0.9, 0.9)); H.pump(app, 50)
dock._image_chk.setChecked(True)
for fmt in ("png", "jpeg", "nifti"):
    for k, chk in dock._fmt_chk.items(): chk.setChecked(k == fmt)
    seen = H.auto_close_dialogs(app, 300)
    t0 = time.time(); dock._save(advance=False); dt = time.time() - t0; app.processEvents()
    print(f"{fmt}: dock._save returned after {dt:.1f}s (GUI thread blocked); dialogs={seen}; status='{dock._status_lbl.text()}'")
sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(ws.out_dir) for f in fs) / 1e6
print(f"total output {sz:.0f} MB")
win.close(); shutil.rmtree(WS, ignore_errors=True)
