"""CRASH: a .csv/.tsv list with a field > 131072 chars -> _csv.Error 'field larger than field limit' -> abort."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
d = fresh("csv_long"); a = dcm(d)
csvp = os.path.join(d, "cohort.csv")
open(csvp, "w").write("path,notes\n" + a + "," + "z" * 140_000 + "\n")
if len(sys.argv) > 1 and sys.argv[1] == "pure":
    from viewer_vidi import workspace as W; print(W.parse_list_file(csvp))
else:
    open_list_in_dock(csvp)
print("survived")
