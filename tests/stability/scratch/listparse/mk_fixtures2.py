"""Extra fixtures for the listparse lens (NUL / csv-limit / README / long-stem cases)."""
import os, shutil, random
S = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/listparse"
L = os.path.join(S, "lists"); imgs = os.path.join(S, "imgs")
A = os.path.join(imgs, "a.dcm"); B = os.path.join(imgs, "b.dcm")
def w(name, data, mode="w", **kw):
    p = os.path.join(L, name)
    with open(p, mode, **kw) as f: f.write(data)
    return p
def reset(d):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)

w("utf16.csv", ("path,label\n" + A + ",x\n" + B + ",y\n").encode("utf-16"), mode="wb")   # Excel 'Unicode' style
w("nul.tsv", (A + "\tx\n" + B + "\t\x00\n"), newline="")
w("binary.csv", bytes(random.Random(3).getrandbits(8) for _ in range(200_000)), mode="wb")
w("longfield.csv", "path,blob\n" + A + "," + "z" * 140_000 + "\n" + B + ",short\n")
w("longfield.tsv", A + "\t" + "z" * 140_000 + "\n")
w("quote_eol.csv", "path\n\"" + A + "\n" + B + "\n")       # unterminated quote on a row

# root that holds images + a UTF-16 csv (any 'Open directory…' probes it)
r = os.path.join(S, "root_utf16csv"); reset(r)
shutil.copy(A, os.path.join(r, "a.dcm"))
with open(os.path.join(r, "export.csv"), "wb") as f:
    f.write(("id,path\n1," + A + "\n").encode("utf-16"))

# root with images + README.txt whose one line is a bare file name of a sibling
r = os.path.join(S, "root_readme_bare"); reset(r)
shutil.copy(A, os.path.join(r, "a.dcm"))
with open(os.path.join(r, "README.txt"), "w") as f:
    f.write("Image folder\n\nLICENSE.txt\n")
with open(os.path.join(r, "LICENSE.txt"), "w") as f: f.write("MIT\n")

# two a.dcm under long directory chains, listed from a root they are outside of
deep = os.path.join(S, "deep"); reset(deep)
chain1 = os.path.join(deep, *["d" * 40] * 5)
chain2 = os.path.join(deep, *["e" * 40] * 5)
os.makedirs(chain1); os.makedirs(chain2)
shutil.copy(A, os.path.join(chain1, "a.dcm")); shutil.copy(A, os.path.join(chain2, "a.dcm"))
w("deep_dup.txt", os.path.join(chain1, "a.dcm") + "\n" + os.path.join(chain2, "a.dcm") + "\n")
print("fixtures2 ok")
