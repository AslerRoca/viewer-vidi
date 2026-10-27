import os, sys, shutil
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
FUZZ = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/fuzz"
def fresh_ws(name):
    d = os.path.join(FUZZ, "repro", "ws_" + name)
    if os.path.isdir(d): shutil.rmtree(d)
    shutil.copytree(os.path.join(FUZZ, "ws"), d)
    return d
