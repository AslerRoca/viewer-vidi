"""Build small synthetic PNG workspaces for manifest tests (fast to load)."""
import os, shutil, sys
import numpy as np
from PIL import Image
D = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/manifest"

def png(path, seed=0, w=80, h=60):
    rng = np.random.default_rng(seed)
    a = (rng.random((h, w)) * 255).astype(np.uint8)
    a[h//4:h//2, w//4:w//2] = 255
    Image.fromarray(a, "L").save(path)

def fresh(name, files):
    root = os.path.join(D, name)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    for i, fn in enumerate(files):
        p = os.path.join(root, fn)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        png(p, seed=i)
    return root

if __name__ == "__main__":
    fresh("ws_plain", ["a.png", "b.png", "c.png"])
    fresh("ws_odd", ["ärger_über.png", "comma,stem.png", 'quote"stem.png', "space stem.png", "日本語.png"])
    print("ok")
