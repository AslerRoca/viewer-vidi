"""F6/F7: garbage *.dcm / *.png become items; loading fails silently (no message), Save says 'still loading';
a truncated .dcm loads as an all-zero image and saves a black _image.png.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_garbage_items.py"""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
from viewer_vidi import workspace as W
d = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery/repro_garbage"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
open(os.path.join(d, "a_text.dcm"), "wb").write(b"not dicom\n" * 20)
open(os.path.join(d, "b_text.png"), "wb").write(b"not png\n")
src = open("/media/zsk/ressd/research/alldata_backup/dicom/original/bpd1_20100101_1.dcm", "rb").read()
open(os.path.join(d, "c_truncated.dcm"), "wb").write(src[:4000])
dock, cell = win._dock, win._quad.active_cell(); canvas = cell.canvas()
win._ws_btn.setChecked(True); app.processEvents()
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
print("items:", [i.stem for i in ws.items])
dock._out_edit.setText("vidi_output"); dock._image_chk.setChecked(True); dock._set_workspace(ws)
for i in range(3):
    dock._load_index(i); ok = H.wait_loaded(app, cell, timeout=4.0)
    px = canvas.displayed_pixels()
    print(f"{ws.items[i].stem}: loaded={ok} pixels={'none' if px is None else f'{px.shape} min={px.min()} max={px.max()}'} dock status={dock._status_lbl.text()!r} canvas page={cell._canvas_stack.currentIndex()}")
    dock._save(advance=False); H.pump(app, 200); print("   Save ->", repr(dock._status_lbl.text()))
win.close(); app.processEvents()
