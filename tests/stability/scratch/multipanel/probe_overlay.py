"""Step-by-step: info-overlay header clicks in paint mode — does any step paint / push undo?"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H
from PyQt5.QtCore import Qt
app, win = H.boot()
dock, quad = win._dock, win._quad
c0 = quad.cell_at(0); cv0 = c0.canvas()
ws = H.open_workspace(app, win, STAB + "/multipanel/ws"); H.wait_loaded(app, c0)
def st(tag):
    print(f"{tag:55s} undo={len(cv0._undo)} mask={cv0.mask_pixels()} expanded={sorted(cv0._ov_expanded)} rects={[(t, r.y()) for r, t in cv0._ov_header_rects]}")
dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
st("start")
dock._clear_btn.click(); app.processEvents(); st("after Clear (undoable)")
c0._info_btn.setChecked(True); app.processEvents(); st("after i on + processEvents")
r, title = cv0._ov_header_rects[0]; centre = r.center()
H.click(cv0, centre); app.processEvents(); st(f"click header '{title}' at {centre.x()},{centre.y()}")
r2 = next(rr for rr, t in cv0._ov_header_rects if t == title)
H.drag(app, cv0, r2.center(), H.pt(cv0, .5, .5)); st(f"drag from header {r2.center().x()},{r2.center().y()} away")
# now rects should be the collapsed layout again; click the original centre
print("centre in current rects:", [t for rr, t in cv0._ov_header_rects if rr.contains(centre)])
H.click(cv0, centre); app.processEvents(); st("click original centre again")
# the WITHOUT-processEvents case: toggle then immediately click the same spot
H.click(cv0, centre); st("click same spot, no processEvents in between")
app.processEvents(); st("after processEvents")
# click on a detail line of an expanded group (not a header) → expected to paint (only headers consumed)
cv0._ov_expanded.add(title); cv0.update(); app.processEvents(); st("expanded programmatically")
hdr = next(rr for rr, t in cv0._ov_header_rects if t == title)
from PyQt5.QtCore import QPoint
detail = QPoint(hdr.center().x(), hdr.bottom() + 10)
H.click(cv0, detail); app.processEvents(); st(f"click detail line at {detail.x()},{detail.y()} (expected: paints)")
win.close(); app.processEvents()
