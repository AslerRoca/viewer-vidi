"""Flow 4: dir with two list files → Open directory… → QInputDialog item picker."""
import os, sys, shutil
import e2e_common as C
from e2e_common import check, H

ROOT = os.path.join(C.FX, "ws_twolists")
shutil.rmtree(os.path.join(ROOT, "vidi_output"), ignore_errors=True)
app, win = H.boot()
dock, quad = win._dock, win._quad
C.click_button(app, win._ws_btn)
cell = quad.active_cell(); canvas = cell.canvas()

seen = C.open_dir_via_ui(app, win, ROOT, pick_item="beta.csv")
check("one QInputDialog 'Choose list' with both names", len(seen) == 1 and seen[0][0] == "QInputDialog" and seen[0][1] == "Choose list" and seen[0][3] == ["alpha.txt", "beta.csv"], str(seen))
ws = dock.workspace()
check("beta.csv chosen → 2 items", ws is not None and ws.mode == "list" and os.path.basename(ws.list_file) == "beta.csv" and len(ws.items) == 2, str(ws and (ws.list_file, [it.stem for it in ws.items])))
check("root is the picked dir (not the images' dir)", ws is not None and ws.root == ROOT, str(ws and ws.root))
check("first item loads", H.wait_loaded(app, cell))

# save one item → output lands under ws_twolists (the list's dir), not next to the images
H.drag(app, canvas, H.pt(canvas, 0.4, 0.4), H.pt(canvas, 0.5, 0.5))
C.click_button(app, dock._save_btn)
st = C.wait_status(app, dock)
check("saved", st.startswith("Saved 1 file(s)"), st)
check("manifest in ws_twolists/vidi_output", os.path.isfile(os.path.join(ROOT, "vidi_output", "manifest.csv")))

# cancel in the picker → workspace unchanged
seen = C.open_dir_via_ui(app, win, ROOT, pick_item=None)
check("cancel picker: workspace unchanged", len(seen) == 1 and dock.workspace() is ws)

# pick alpha.txt → 1 item
seen = C.open_dir_via_ui(app, win, ROOT, pick_item="alpha.txt")
ws2 = dock.workspace()
check("alpha.txt chosen → 1 item", ws2 is not None and os.path.basename(ws2.list_file) == "alpha.txt" and len(ws2.items) == 1, str(ws2 and [it.stem for it in ws2.items]))
check("list widget replaced (1 row)", dock._list.count() == 1, str(C.list_texts(dock)))
check("first item loads", H.wait_loaded(app, cell))

# empty dir → 'Empty workspace' info box
empty = os.path.join(C.SCRATCH, "empty_dir"); os.makedirs(empty, exist_ok=True)
seen = C.open_dir_via_ui(app, win, empty)
check("empty dir → 'Empty workspace' info", len(seen) == 1 and seen[0][1] == "Empty workspace", str(seen))
check("workspace unchanged after empty", dock.workspace() is ws2)

# cancel the directory dialog
seen = C.open_dir_via_ui(app, win, "")
check("cancel dir dialog: nothing", seen == [] and dock.workspace() is ws2)
sys.exit(C.finish(win, app))
