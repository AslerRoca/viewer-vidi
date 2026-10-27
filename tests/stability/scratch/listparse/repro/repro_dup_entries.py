"""UX: the same path listed twice becomes two jobs with path-mangled stems; Save&Next on #1 presents the same image again as pending #2."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
d = fresh("dup"); a = dcm(d); lst = os.path.join(d, "list.txt"); open(lst, "w").write(a + "\n" + a + "\n")
ws = W.build_workspace(d, "list", W.parse_list_file(lst), list_file=lst)
print("items:", [(it.stem, os.path.basename(it.path)) for it in ws.items])
