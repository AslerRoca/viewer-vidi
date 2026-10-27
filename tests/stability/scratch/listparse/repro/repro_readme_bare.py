"""MINOR: an image folder whose README.txt contains a bare file name of a sibling counts as 'images + list' -> 'Workspace mode' prompt; list mode yields a non-image item."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
d = fresh("readme"); dcm(d)
open(os.path.join(d, "README.txt"), "w").write("Image folder\n\nLICENSE.txt\n"); open(os.path.join(d, "LICENSE.txt"), "w").write("MIT\n")
print("probe:", W.probe_workspace(d))
app, win = open_dir_in_dock(d)   # auto-closed dialog => prompt shown; see printed title
