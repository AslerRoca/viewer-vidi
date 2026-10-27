"""UX: a list entry that is a DICOM series DIRECTORY (loadable in the tree) is reported as 'listed path(s) not found'."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
from viewer_vidi.tree_panel import _make_series_meta
d = fresh("direntry"); series = os.path.join(d, "series"); os.makedirs(series)
for i in range(3): dcm(series, f"{i}.dcm")
a = dcm(d); lst = os.path.join(d, "list.txt"); open(lst, "w").write(series + "\n" + a + "\n")
ws = W.build_workspace(d, "list", W.parse_list_file(lst), list_file=lst)
print("items:", [it.stem for it in ws.items], "missing:", ws.missing, "isdir:", os.path.isdir(ws.missing[0]), "viewer can load it:", _make_series_meta(series) is not None)
