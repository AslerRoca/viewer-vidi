"""REPRO: manifest.csv with a user-added column (e.g. 'notes' added in Excel) → Save aborts the app.
write_manifest_row() re-writes the rows read by DictReader; the extra key makes DictWriter raise
ValueError, which is raised inside the Save slot (outside the try/except that guards export_item),
so PyQt5 calls qFatal → SIGABRT. The PNG was already written; the manifest is not updated and
manifest.csv.tmp is left behind.
Run: QT_QPA_PLATFORM=offscreen timeout 300 ~/miniconda3/envs/viewer_vidi/bin/python repro_manifest_extra_column_abort.py ; echo rc=$?
Expect rc=134 and 'ValueError: dict contains fields not in fieldnames: 'notes'' on stderr."""
import os, sys, shutil, csv
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
from viewer_vidi import workspace as W
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_extra_col"); shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
shutil.copy(os.path.join(H.FIXTURES, sorted(os.listdir(H.FIXTURES))[0]), D)
os.makedirs(os.path.join(D, "vidi_output"))
with open(os.path.join(D, "vidi_output", "manifest.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(list(W.MANIFEST_FIELDS) + ["notes"])
    w.writerow(["other_item", "src", "t", "3", "1", "2", "3", "4", "png", "png/x.png", "reviewed"])
app, win = H.boot()
H.open_workspace(app, win, D)
canvas = win._quad.active_cell().canvas()
H.drag(app, canvas, H.pt(canvas, 0.2, 0.2), H.pt(canvas, 0.5, 0.2))
print("mask px", canvas.mask_pixels(), "→ clicking Save", flush=True)
win._dock._save_btn.click(); app.processEvents()
print("SURVIVED (unexpected)")
