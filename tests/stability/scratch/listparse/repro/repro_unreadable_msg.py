"""UX: a list file without read permission -> parse_list_file returns [] silently -> 'No existing image paths found in …'."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
d = fresh("unreadable"); a = dcm(d); lst = os.path.join(d, "list.txt"); open(lst, "w").write(a + "\n"); os.chmod(lst, 0)
app, win = open_list_in_dock(lst)
