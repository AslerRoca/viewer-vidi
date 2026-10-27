"""Flow 3: dir with images AND a usable list.txt → Open directory… → mode prompt.
Run with argv[1] = 'Image mode' | 'List mode' | 'Cancel'."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H

choice = sys.argv[1]
ROOT = os.path.join(C.FX, "ws_both")
shutil.rmtree(os.path.join(ROOT, "vidi_output"), ignore_errors=True)
app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()

seen = C.open_dir_via_ui(app, win, ROOT, choose=choice)
check("exactly one QMessageBox 'Workspace mode'", len(seen) == 1 and seen[0][0] == "QMessageBox" and seen[0][1] == "Workspace mode", str(seen))
if seen:
    txt, btns = seen[0][2], seen[0][3]
    check("box text names 3 image files and 1 list file", "holds 3 image files and 1 list file(s)" in txt, txt)
    check("buttons: Image mode (3 files), List mode, Cancel", btns == ["Image mode (3 files)", "List mode", "Cancel"], str(btns))
ws = dock.workspace()
if choice == "Image mode":
    check("image mode with 3 items (list.txt not an item)", ws is not None and ws.mode == "image" and [it.stem for it in ws.items] == ["bpd3_20100420_1", "bpd3_20100420_2", "bpd3_20100421_1"], str(ws and [it.stem for it in ws.items]))
    check("label IMAGE mode", "IMAGE mode · image directory · 3 items" in dock._ws_lbl.text(), dock._ws_lbl.text())
    check("first item loads", H.wait_loaded(app, cell))
elif choice == "List mode":
    check("list mode with 1 item from list.txt (comment skipped)", ws is not None and ws.mode == "list" and [it.stem for it in ws.items] == ["bpd3_20100420_1"] and ws.list_file == os.path.join(ROOT, "list.txt"), str(ws and ([it.stem for it in ws.items], ws.list_file)))
    check("label LIST mode · list list.txt", "LIST mode · list list.txt · 1 items" in dock._ws_lbl.text(), dock._ws_lbl.text())
    check("first item loads", H.wait_loaded(app, cell))
    check("Prev & Next both disabled with 1 item", not dock._prev_btn.isEnabled() and not dock._next_btn.isEnabled())
else:
    check("cancel: no workspace", ws is None and dock._ws_lbl.text() == "No workspace open.", dock._ws_lbl.text())
sys.exit(C.finish(win, app))
