import sys, time, os
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
app, win = H.boot()
quad = win._quad; cell = quad.active_cell()
ws = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/fuzz/ws"
paths = [os.path.join(ws, f) for f in sorted(os.listdir(ws))]
paths += ["/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii",
          "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"]
for p in paths:
    t0 = time.time(); ok = H.load_file(app, cell, p); dt = time.time() - t0
    px = cell.canvas().displayed_pixels()
    sd = cell.series_data()
    print(f"{os.path.basename(p):28s} ok={ok} {dt:.2f}s shape={None if px is None else px.shape} dtype={None if px is None else px.dtype} type={sd.series_type.value} spacing={sd.pixel_spacing} wl={cell.canvas().wl()}")
win.close(); app.processEvents()
