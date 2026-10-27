"""MINOR: Open directory… stats every line of every .txt in the root; a 22MB README.txt (400k lines) freezes the GUI thread ~2.5s."""
import os, sys, time, random; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from viewer_vidi import workspace as W
d = fresh("bigreadme"); dcm(d); rnd = random.Random(2); words = "lorem ipsum dolor sit amet consectetur".split()
with open(os.path.join(d, "README.txt"), "w") as f:
    for _ in range(400_000): f.write(" ".join(rnd.choice(words) for _ in range(rnd.randint(3, 14))) + "\n")
t0 = time.time(); print(W.probe_workspace(d), f"{time.time()-t0:.2f}s", os.path.getsize(os.path.join(d, 'README.txt'))//1_000_000, "MB")
