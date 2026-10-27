"""CRASH: a .csv/.tsv list containing a NUL byte (e.g. UTF-16 encoded CSV) -> _csv.Error -> abort.
Also hits 'Open directory…' on ANY folder containing such a .csv (find_list_files parses every list)."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
d = fresh("csv_nul"); a = dcm(d)
csvp = os.path.join(d, "export.csv")
open(csvp, "wb").write(("path,label\n" + a + ",x\n").encode("utf-16"))   # Excel/LibreOffice 'Unicode' CSV
mode = sys.argv[1] if len(sys.argv) > 1 else "list"
if mode == "pure":
    from viewer_vidi import workspace as W
    print(W.parse_list_file(csvp))          # _csv.Error: line contains NUL
elif mode == "dir":
    open_dir_in_dock(d)                      # Open directory… -> probe_workspace -> find_list_files -> abort
else:
    open_list_in_dock(csvp)                  # Open list… -> parse_list_file -> abort
print("survived")
