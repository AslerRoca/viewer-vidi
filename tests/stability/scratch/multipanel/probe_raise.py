import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
app, win = H.boot(); dock = win._dock
win._ws_btn.setChecked(True); app.processEvents()
sys.stderr.write("MARK before setFloating\n"); sys.stderr.flush()
dock.setFloating(True); app.processEvents(); H.pump(app, 100)
sys.stderr.write("MARK after setFloating\n"); sys.stderr.flush()
dock.setFloating(False); app.processEvents()
win.close(); app.processEvents()
