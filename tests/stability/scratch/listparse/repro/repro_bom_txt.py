"""WRONG-OUTPUT: UTF-8 BOM at the start of a .txt list sticks to the first path -> that entry is 'not found'."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
d = fresh("bom"); a = dcm(d, "a.dcm"); b = dcm(d, "b.dcm")
lst = os.path.join(d, "list.txt")
open(lst, "w", encoding="utf-8-sig").write(a + "\n" + b + "\n")      # Notepad / Excel style BOM
paths = W.parse_list_file(lst)
ws = W.build_workspace(d, "list", paths, list_file=lst)
print("parsed:", [repr(p) for p in paths])
print("items:", [it.stem for it in ws.items], "missing:", ws.missing)
assert len(ws.items) == 2 and not ws.missing, "first entry lost to the BOM"
