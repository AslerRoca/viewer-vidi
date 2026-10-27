"""unique_stems: the '_N' fallback can collide with another file's natural stem."""
import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
from viewer_vidi import workspace as W
SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery"
def fresh(name):
    d = os.path.join(SCR, "ws_" + name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); return d
def touch(p, data=b"\x1f\x8b" + b"\0"*64):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data)

# Case A: same dir, scan.nii + scan.nii.gz + scan_1.nii
d = fresh("sufA")
for n in ("scan.nii", "scan.nii.gz", "scan_1.nii"): touch(os.path.join(d, n))
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
pairs = [(os.path.relpath(i.path, d), i.stem) for i in ws.items]
print("A", pairs, "UNIQUE" if len({s for _, s in pairs}) == len(pairs) else "DUPLICATE STEMS")

# Case B: pure API
print("B", W.unique_stems(["/r/k.png", "/r/k.nii", "/r/k_1.png"], "/r"))

# Case C: '__' join collision + natural suffix name
d = fresh("sufC")
for n in ("a/b/x.png", "a__b/x.png", "a__b/x_1.png", "q/x_1.png"): touch(os.path.join(d, n))
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
pairs = [(os.path.relpath(i.path, d), i.stem) for i in ws.items]
print("C", pairs, "UNIQUE" if len({s for _, s in pairs}) == len(pairs) else "DUPLICATE STEMS")

# Consequence: write a manifest row for the first 'k_1' and see the second one marked done too
d = fresh("sufD")
for n in ("scan.nii", "scan.nii.gz", "scan_1.nii"): touch(os.path.join(d, n))
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
W.write_manifest_row(ws.manifest_path, dict(stem=ws.items[1].stem, source=ws.items[1].path))
ws2 = W.build_workspace(d, "image", imgs)
print("D after saving item[1]:", [(os.path.basename(i.path), i.stem, i.done) for i in ws2.items])
