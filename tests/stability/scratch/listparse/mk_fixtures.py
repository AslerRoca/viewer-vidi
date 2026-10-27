"""Build read-write fixtures for the listparse lens (copies only; repo untouched)."""
import os, shutil, random
S = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/listparse"
FX = "/media/zsk/ressd/research/alldata_backup/dicom/original"
MR = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
PNG = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"

def reset(d):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)

imgs = os.path.join(S, "imgs"); reset(imgs); os.makedirs(os.path.join(imgs, "sub"))
src = sorted(f for f in os.listdir(FX) if f.endswith(".dcm"))[:3]
for name, dst in zip(src, ("a.dcm", "b.dcm", "c.dcm")):
    shutil.copy(os.path.join(FX, name), os.path.join(imgs, dst))
shutil.copy(os.path.join(FX, src[0]), os.path.join(imgs, "sub", "a.dcm"))
shutil.copy(PNG, os.path.join(imgs, "pic.png"))
shutil.copy(PNG, os.path.join(imgs, "café.png"))

mr = os.path.join(S, "mr20"); reset(mr)
for f in sorted(os.listdir(MR))[:20]:
    shutil.copy(os.path.join(MR, f), os.path.join(mr, f))

odd = os.path.join(S, "odd"); reset(odd)
shutil.copy(os.path.join(FX, src[1]), os.path.join(odd, "x.ima"))      # DICOM, unknown ext
shutil.copy(os.path.join(FX, src[1]), os.path.join(odd, "y.dicom"))    # DICOM, unknown ext
shutil.copy(PNG, os.path.join(odd, "noext_png"))                        # PNG without ext
shutil.copy(os.path.join(MR, sorted(os.listdir(MR))[0]), os.path.join(odd, "42228791"))  # extless DICOM

home = os.path.join(S, "fakehome"); reset(home)
shutil.copy(os.path.join(FX, src[2]), os.path.join(home, "h.dcm"))

# second tree outside the 'lists' root for the '..'/outside-root stem cases
far = os.path.join(S, "far", "deep"); shutil.rmtree(os.path.join(S, "far"), ignore_errors=True); os.makedirs(far)
shutil.copy(os.path.join(FX, src[0]), os.path.join(far, "a.dcm"))
shutil.copy(os.path.join(FX, src[0]), os.path.join(S, "far", "a.dcm"))

L = os.path.join(S, "lists"); reset(L)
A = os.path.join(imgs, "a.dcm"); B = os.path.join(imgs, "b.dcm"); C = os.path.join(imgs, "c.dcm")
def w(name, data, mode="w", **kw):
    p = os.path.join(L, name)
    with open(p, mode, **kw) as f: f.write(data)
    return p

w("bom.txt", "﻿" + A + "\n" + B + "\n", encoding="utf-8")
w("bom_hdr0.csv", "﻿path,label\n" + A + ",x\n" + B + ",y\n", encoding="utf-8")
w("bom_hdr1.csv", "﻿id,path,label\n1," + A + ",x\n2," + B + ",y\n", encoding="utf-8")
w("crlf.txt", A + "\r\n" + B + "\r\n", newline="")
w("crlf.csv", "id,path\r\n1," + A + "\r\n2," + B + "\r\n", newline="")
w("cr_only.txt", A + "\r" + B + "\r", newline="")
w("trailing_ws.txt", A + "   \n\t" + B + "\t\t\n  " + C + " \n")
w("trailing_tab.tsv", "path\tlabel\n" + A + "\tx\t\n" + B + "\t\n")
w("quoted_comma.csv", 'path,label\n"' + os.path.join(imgs, "sub", "a.dcm") + '",x\n"' + B + '",y\n')
w("quoted_txt.txt", '"' + A + '"\n\'' + B + "'\n")
w("semicolon.csv", "id;path;label\n1;" + A + ";x\n2;" + B + ";y\n")
w("tabs_as_csv.csv", "path\tlabel\n" + A + "\tx\n")
w("plain.tsv", "Path\tLabel\n" + A + "\tx\n" + B + "\ty\n")
w("tsv_nohdr.tsv", A + "\tx\n" + B + "\ty\n")
w("hdr_Path.csv", "ID,Path\n1," + A + "\n2," + B + "\n")
w("hdr_FILE.csv", "FILE,label\n" + A + ",1\n" + B + ",2\n")
w("hdr_unknown.csv", "img_path,label\n" + A + ",1\n" + B + ",2\n")
w("hdr_unknown_col2.csv", "subject_id,img_path,label\n1," + A + ",1\n2," + B + ",2\n")
w("hdr_dotted.csv", "file.name,label\n" + A + ",1\n")
w("col3_nohdr.csv", "1,x," + A + "\n2,y," + B + "\n")
w("single.txt", A + "\n")
w("single_noeol.txt", A)
w("hdr_only.csv", "path,label\n")
w("hdr_only_unknown.csv", "id,label\n")
w("empty.txt", "")
w("ws_only.txt", "\n  \n\t\n")
random.seed(1); w("binary.txt", bytes(random.getrandbits(8) for _ in range(2_000_000)), mode="wb")
w("tilde.txt", "~/h.dcm\n")
w("dotdot.txt", "../imgs/a.dcm\n../imgs/sub/a.dcm\n../far/a.dcm\n../far/deep/a.dcm\n")
w("dup.txt", A + "\n" + A + "\n./../imgs/a.dcm\n")
w("seriesdir.txt", mr + "\n" + A + "\n")
w("unknown_ext.txt", os.path.join(odd, "x.ima") + "\n" + os.path.join(odd, "y.dicom") + "\n"
  + os.path.join(odd, "noext_png") + "\n" + os.path.join(odd, "42228791") + "\n" + A + "\n")
w("plain.lst", "# c\n" + A + "\n" + B + "\n")
w("comments_then_hdr.csv", "# exported\n# by tool\nid,path\n1," + A + "\n")
w("extless_first_missing.csv", os.path.join(odd, "MISSING_42228791") + ",x\n" + os.path.join(odd, "42228791") + ",y\n")
w("latin1.txt", (os.path.join(imgs, "café.png") + "\n").encode("latin-1"), mode="wb")
w("utf16.txt", (A + "\n" + B + "\n").encode("utf-16"), mode="wb")
w("utf8_accent.txt", os.path.join(imgs, "café.png") + "\n", encoding="utf-8")
w("nii.txt", "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii\n")
w("self.txt", "self.txt\n")
w("longline.txt", "/" + "x" * 5000 + "/a.dcm\n" + A + "\n")
w("unreadable.txt", A + "\n"); os.chmod(os.path.join(L, "unreadable.txt"), 0)
w("short_rows.csv", "id,label,path\n1,x," + A + "\n2,y\n3\n4,z," + B + "\n")
w("ten_k.txt", "".join((A if i % 3 == 0 else (B if i % 3 == 1 else "/nonexistent/%d.dcm" % i)) + "\n" for i in range(10_000)))
w("ten_k_missing.txt", "".join("/nonexistent/%d.dcm\n" % i for i in range(10_000)))

# roots for find_list_files
r1 = os.path.join(S, "root_missing_only"); reset(r1)
with open(os.path.join(r1, "list.txt"), "w") as f: f.write("/nonexistent/a.dcm\n/nonexistent/b.dcm\n")
r2 = os.path.join(S, "root_readme"); reset(r2)
shutil.copy(A, os.path.join(r2, "a.dcm"))
words = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor".split()
random.seed(2)
with open(os.path.join(r2, "README.txt"), "w") as f:
    for i in range(400_000):
        f.write(" ".join(random.choice(words) for _ in range(random.randint(3, 14))) + "\n")
r3 = os.path.join(S, "root_readme_names_file"); reset(r3)
shutil.copy(A, os.path.join(r3, "a.dcm"))
with open(os.path.join(r3, "README.txt"), "w") as f:
    f.write("Image folder.\nSee LICENSE.txt for terms.\nContact: me\n")
with open(os.path.join(r3, "LICENSE.txt"), "w") as f: f.write("MIT\n")
r4 = os.path.join(S, "root_two_lists"); reset(r4)
with open(os.path.join(r4, "l1.txt"), "w") as f: f.write(A + "\n")
with open(os.path.join(r4, "l2.csv"), "w") as f: f.write("path\n" + B + "\n")
print("fixtures ok", os.path.getsize(os.path.join(r2, "README.txt")) // 1_000_000, "MB readme")
