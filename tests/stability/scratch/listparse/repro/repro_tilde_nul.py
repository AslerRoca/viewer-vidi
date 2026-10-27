"""CRASH: a .txt list line starting with '~' that contains a NUL byte -> os.path.expanduser -> pwd.getpwnam
-> ValueError 'embedded null byte' -> abort. Triggered by any binary garbage named *.txt (Open list… or
Open directory… on a folder holding it)."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
d = fresh("tilde_nul"); a = dcm(d)
lst = os.path.join(d, "list.txt")
open(lst, "w").write(a + "\n~user\x00name/a.dcm\n")
if len(sys.argv) > 1 and sys.argv[1] == "pure":
    from viewer_vidi import workspace as W; print(W.parse_list_file(lst))
else:
    open_list_in_dock(lst)
print("survived")
