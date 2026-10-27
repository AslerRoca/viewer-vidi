"""UX: list mode accepts ANY existing file as an item (no image check); an item the viewer cannot open
(e.g. x.ima, a PNG without extension, the list file itself) leaves _index unchanged -> Next/Prev cannot
step past it, Save&Next stalls on it, first item unloadable => Prev/Next both disabled."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
d = fresh("unloadable"); a = dcm(d, "a.dcm"); x = dcm(d, "x.ima"); b = dcm(d, "b.dcm")
lst = os.path.join(d, "list.txt"); open(lst, "w").write(a + "\n" + x + "\n" + b + "\n")
app, win = open_list_in_dock(lst); dock = win._dock; cell = win._quad.active_cell()
H.wait_loaded(app, cell)
print("items:", [it.stem for it in dock.workspace().items], "index:", dock._index)
dock._next_btn.click(); app.processEvents(); i1, s1 = dock._index, dock._status_lbl.text()
dock._next_btn.click(); app.processEvents(); i2, s2 = dock._index, dock._status_lbl.text()
print(f"Next#1 -> index {i1} status {s1!r}\nNext#2 -> index {i2} status {s2!r}")
assert i2 == 2, "Next cannot get past the unloadable item"
