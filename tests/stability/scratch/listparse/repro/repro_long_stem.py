"""WRONG-OUTPUT: duplicate basenames OUTSIDE the workspace root get the whole absolute path as stem; a deep
path makes the stem > 255 chars so every save of that item fails with 'File name too long'."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
import numpy as np
from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
d = fresh("longstem")
p1 = os.path.join(d, *["d" * 40] * 5); p2 = os.path.join(d, *["e" * 40] * 5)
os.makedirs(p1); os.makedirs(p2); a1 = dcm(p1); a2 = dcm(p2)
wsdir = os.path.join(d, "lists"); os.makedirs(wsdir); lst = os.path.join(wsdir, "list.txt")
open(lst, "w").write(a1 + "\n" + a2 + "\n")
ws = W.build_workspace(wsdir, "list", W.parse_list_file(lst), list_file=lst)
print("stem lengths:", [len(it.stem) for it in ws.items]); print("stem[0]:", ws.items[0].stem[:80], "…")
px = np.zeros((8, 8), np.float32); m = np.ones((8, 8), np.uint8)
export_item(ws.out_dir, ExportInput(stem=ws.items[0].stem, pixels=px, wc=1, ww=1, mask=m, rect=None), ExportOptions(formats=("png",)))
print("survived")
