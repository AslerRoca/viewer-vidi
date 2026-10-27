"""WRONG-OUTPUT (silent): in a header-less CSV the first row is dropped as a 'header' when its first cell has no
extension and does not exist -> a missing extensionless DICOM path in row 1 is neither an item nor in ws.missing."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
d = fresh("extless"); dcm(d, "a.dcm")
ok = os.path.join(d, "42228802"); os.rename(dcm(d, "tmp"), ok)             # existing extensionless DICOM
gone = os.path.join(d, "42228791")                                          # listed but deleted
lst = os.path.join(d, "cohort.csv")
open(lst, "w").write(gone + ",x\n" + ok + ",y\n")
paths = W.parse_list_file(lst); ws = W.build_workspace(d, "list", paths, list_file=lst)
print("parsed:", paths); print("items:", len(ws.items), "missing:", ws.missing)
assert len(paths) == 2 and ws.missing == [gone], "row 1 silently swallowed as a header"
