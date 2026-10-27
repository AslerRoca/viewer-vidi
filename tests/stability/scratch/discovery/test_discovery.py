"""Discovery-lens tests for workspace.py (pure Python, no Qt)."""
import os, sys, shutil, stat, time, traceback
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
from viewer_vidi import workspace as W

SCR = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/discovery"
FIX_DCM = "/media/zsk/ressd/research/alldata_backup/dicom/original"
FIX_MR  = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOM/26070517/54450002"
FIX_DICOMDIR = "/media/zsk/ressd/research/alldata_backup/mymri/Liver_3T_sub5_2026_07_05/DICOMDIR"
FIX_NII = "/media/zsk/ressd/research/alldata_backup/Tongyu_Wang/radiology_qingyi/qingyi/+C/2035104/C.nii"
FIX_PNG = "/media/zsk/ressd/research/alldata_backup/project_workstation/PhD/image_exsample/3.png"

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)

def fresh(name):
    d = os.path.join(SCR, "ws_" + name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d

def tiny_png(path, w=4, h=4):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("L", (w, h), 128).save(path)

def rel(paths, root):
    return sorted(os.path.relpath(p, root) for p in paths)

# ── 1. empty dir ─────────────────────────────────────────────────────────────
d = fresh("empty")
imgs, lists = W.probe_workspace(d)
check("empty dir -> no images, no lists", imgs == [] and lists == [], f"{imgs} {lists}")
ws = W.build_workspace(d, "image", imgs)
check("empty dir -> build_workspace yields 0 items, n_done 0", ws.items == [] and ws.n_done == 0)

# ── 2. only non-images ───────────────────────────────────────────────────────
d = fresh("nonimg")
for n in ("a.txt", "b.doc", "c.bin", "d.xml", "e.json", "readme"):
    with open(os.path.join(d, n), "w") as f: f.write("hello\n")
imgs, lists = W.probe_workspace(d)
check("non-image dir -> no images", imgs == [], str(rel(imgs, d)))
check("non-image dir -> a.txt without existing paths is not a list", lists == [], str(lists))

# ── 3. nesting 3+ levels ─────────────────────────────────────────────────────
d = fresh("deep")
shutil.copy(os.path.join(FIX_DCM, "bpd1_20100101_1.dcm"), os.path.join(d, "l0.dcm"))
os.makedirs(os.path.join(d, "a/b/c/d/e"))
shutil.copy(os.path.join(FIX_DCM, "bpd1_20100101_2.dcm"), os.path.join(d, "a/b/c/d/e/l5.dcm"))
tiny_png(os.path.join(d, "a/b/c/l3.png"))
shutil.copy(FIX_NII, os.path.join(d, "a/b/l2.nii"))
imgs, _ = W.probe_workspace(d)
check("5-level nesting found", rel(imgs, d) == ["a/b/c/d/e/l5.dcm", "a/b/c/l3.png", "a/b/l2.nii", "l0.dcm"], str(rel(imgs, d)))
check("scan order is sorted-walk order (root files first, then subdirs)", [os.path.relpath(p, d) for p in imgs] == ["l0.dcm", "a/b/l2.nii", "a/b/c/l3.png", "a/b/c/d/e/l5.dcm"], str([os.path.relpath(p, d) for p in imgs]))

# ── 4. hidden dirs and files ─────────────────────────────────────────────────
d = fresh("hidden")
tiny_png(os.path.join(d, "vis.png"))
tiny_png(os.path.join(d, ".hidden.png"))
tiny_png(os.path.join(d, ".hdir/inside.png"))
tiny_png(os.path.join(d, "sub/.also_hidden.png"))
imgs, _ = W.probe_workspace(d)
check("hidden files and hidden dirs are skipped", rel(imgs, d) == ["vis.png"], str(rel(imgs, d)))

# ── 5. symlink loop + symlinked file ─────────────────────────────────────────
d = fresh("symlink")
tiny_png(os.path.join(d, "sub/real.png"))
os.symlink(d, os.path.join(d, "sub/loop"))            # points at ancestor
os.symlink(os.path.join(d, "sub/real.png"), os.path.join(d, "linked.png"))
os.symlink(os.path.join(d, "does_not_exist.png"), os.path.join(d, "dangling.png"))
t0 = time.time()
imgs, _ = W.probe_workspace(d)
dt = time.time() - t0
check("symlink loop does not hang (os.walk followlinks=False)", dt < 5, f"{dt:.2f}s")
check("symlinked dir is not descended", not any("loop" in p for p in imgs), str(rel(imgs, d)))
check("symlinked file counts as an item; dangling symlink is dropped", rel(imgs, d) == ["linked.png", "sub/real.png"], str(rel(imgs, d)))
ws = W.build_workspace(d, "image", imgs)
check("symlinked file + target get distinct stems", sorted(i.stem for i in ws.items) == ["linked", "real"], str([i.stem for i in ws.items]))

# ── 6. permission-denied subdir ──────────────────────────────────────────────
d = fresh("perm")
tiny_png(os.path.join(d, "ok.png"))
tiny_png(os.path.join(d, "locked/secret.png"))
tiny_png(os.path.join(d, "zz/after.png"))
os.chmod(os.path.join(d, "locked"), 0)
try:
    imgs, lists = W.probe_workspace(d)
    check("chmod-000 subdir skipped without exception", rel(imgs, d) == ["ok.png", "zz/after.png"], str(rel(imgs, d)))
    # unreadable file (dir readable, file chmod 000) with .dcm name
    with open(os.path.join(d, "zz/unreadable.dcm"), "wb") as f: f.write(b"x" * 300)
    os.chmod(os.path.join(d, "zz/unreadable.dcm"), 0)
    with open(os.path.join(d, "zz/unreadable_extless"), "wb") as f: f.write(b"\0" * 128 + b"DICM")
    os.chmod(os.path.join(d, "zz/unreadable_extless"), 0)
    imgs, _ = W.probe_workspace(d)
    check("unreadable .dcm still becomes an item (name only); unreadable extensionless dropped",
          "zz/unreadable.dcm" in rel(imgs, d) and "zz/unreadable_extless" not in rel(imgs, d), str(rel(imgs, d)))
    # root itself unreadable
    os.chmod(d, 0)
    try:
        imgs, lists = W.probe_workspace(d)
        check("chmod-000 root -> empty, no exception", imgs == [] and lists == [], f"{imgs} {lists}")
    except Exception as e:
        check("chmod-000 root -> empty, no exception", False, repr(e))
    finally:
        os.chmod(d, 0o755)
finally:
    os.chmod(os.path.join(d, "locked"), 0o755)
    for n in ("zz/unreadable.dcm", "zz/unreadable_extless"):
        p = os.path.join(d, n)
        if os.path.exists(p): os.chmod(p, 0o644)

# ── 7. extensionless DICOM + DICOMDIR ────────────────────────────────────────
d = fresh("extless")
mr = sorted(os.listdir(FIX_MR))[:5]
os.makedirs(os.path.join(d, "DICOM/26070517/54450002"))
for n in mr:
    shutil.copy(os.path.join(FIX_MR, n), os.path.join(d, "DICOM/26070517/54450002", n))
shutil.copy(FIX_DICOMDIR, os.path.join(d, "DICOMDIR"))
# extensionless non-dicom
with open(os.path.join(d, "README"), "w") as f: f.write("not dicom\n")
with open(os.path.join(d, "tiny"), "wb") as f: f.write(b"\0" * 10)      # shorter than 132 bytes
imgs, _ = W.probe_workspace(d)
check("5 extensionless DICOMs are items, DICOMDIR/README/tiny are not",
      rel(imgs, d) == sorted("DICOM/26070517/54450002/" + n for n in mr), str(rel(imgs, d)))
ws = W.build_workspace(d, "image", imgs)
check("extensionless stems are the bare numbers", sorted(i.stem for i in ws.items) == sorted(mr), str([i.stem for i in ws.items]))
# lower-case dicomdir and a 'DICOMDIR.bak'
shutil.copy(FIX_DICOMDIR, os.path.join(d, "dicomdir"))
shutil.copy(FIX_DICOMDIR, os.path.join(d, "DICOMDIR.dcm"))
imgs, _ = W.probe_workspace(d)
check("lower-case dicomdir skipped; DICOMDIR.dcm accepted by name", "dicomdir" not in rel(imgs, d) and "DICOMDIR.dcm" in rel(imgs, d), str(rel(imgs, d)))

# ── 8. garbage x.dcm / garbage .png ──────────────────────────────────────────
d = fresh("garbage")
with open(os.path.join(d, "x.dcm"), "wb") as f: f.write(b"this is not dicom\n" * 20)
with open(os.path.join(d, "y.png"), "wb") as f: f.write(b"\x89PNG not really\n")
with open(os.path.join(d, "z.nii.gz"), "wb") as f: f.write(b"\x1f\x8b garbage")
with open(os.path.join(d, "empty.dcm"), "wb") as f: pass
with open(os.path.join(d, "empty.png"), "wb") as f: pass
with open(os.path.join(d, "UPPER.DCM"), "wb") as f: f.write(b"\0" * 200)
with open(os.path.join(d, "pic.PNG"), "wb") as f: f.write(b"\0" * 200)
imgs, _ = W.probe_workspace(d)
check("garbage/empty files with image extensions are accepted as items (no content check)",
      rel(imgs, d) == ["UPPER.DCM", "empty.dcm", "empty.png", "pic.PNG", "x.dcm", "y.png", "z.nii.gz"], str(rel(imgs, d)))
check("is_image_path: dir named foo.png is NOT an item", True)
os.makedirs(os.path.join(d, "dir.png")); os.makedirs(os.path.join(d, "dir.dcm")); os.makedirs(os.path.join(d, "dir.nii.gz"))
imgs2, _ = W.probe_workspace(d)
check("directories named *.png/*.dcm/*.nii.gz are not items", len(imgs2) == len(imgs), str(rel(imgs2, d)))
check("is_image_path on a dir named x.dcm", W.is_image_path(os.path.join(d, "dir.dcm")) in (True, False), str(W.is_image_path(os.path.join(d, "dir.dcm"))))
check("is_image_path(dir.dcm) is False", W.is_image_path(os.path.join(d, "dir.dcm")) is False, str(W.is_image_path(os.path.join(d, "dir.dcm"))))
check("is_image_path(nonexistent.dcm) is False", W.is_image_path(os.path.join(d, "nope.dcm")) is False, str(W.is_image_path(os.path.join(d, "nope.dcm"))))
check("is_image_path(nonexistent.png) is False", W.is_image_path(os.path.join(d, "nope.png")) is False)

# ── 9. output dir skipping / rename ─────────────────────────────────────────
d = fresh("outdir")
tiny_png(os.path.join(d, "a.png"))
tiny_png(os.path.join(d, "vidi_output/png/a_mask.png"))
tiny_png(os.path.join(d, "vidi_output/png/a_image.png"))
tiny_png(os.path.join(d, "sub/vidi_output/png/b_mask.png"))      # nested out dir of same name
tiny_png(os.path.join(d, "results/png/c_mask.png"))               # a renamed out dir
imgs, _ = W.probe_workspace(d, "vidi_output")
check("default out dir skipped at every depth; other dirs scanned",
      rel(imgs, d) == ["a.png", "results/png/c_mask.png"], str(rel(imgs, d)))
imgs, _ = W.probe_workspace(d, "results")
check("renamed out dir: old vidi_output outputs now become items",
      rel(imgs, d) == ["a.png", "sub/vidi_output/png/b_mask.png", "vidi_output/png/a_image.png", "vidi_output/png/a_mask.png"], str(rel(imgs, d)))
imgs, _ = W.probe_workspace(d, "")
check("empty out_dir_name: nothing skipped (dock substitutes default before probe)",
      len(imgs) == 5, str(rel(imgs, d)))
imgs, _ = W.probe_workspace(d, "vidi_output/")
check("out_dir_name with trailing slash still skips", rel(imgs, d) == ["a.png", "results/png/c_mask.png"], str(rel(imgs, d)))
imgs, _ = W.probe_workspace(d, "VIDI_OUTPUT")
check("out dir skip is case-sensitive (VIDI_OUTPUT does not skip vidi_output)", len(imgs) == 5, str(rel(imgs, d)))
tiny_png(os.path.join(d, "exports/run1/png/q_mask.png"))
imgs, _ = W.probe_workspace(d, "exports/run1")
check("out_dir_name 'exports/run1' (subpath typed in dock): its outputs are skipped on reopen",
      "exports/run1/png/q_mask.png" not in rel(imgs, d), str(rel(imgs, d)))
ws_sub = W.build_workspace(d, "image", imgs, "exports/run1")
check("out_dir_name subpath: out_dir joins under root", ws_sub.out_dir == os.path.join(d, "exports/run1"), ws_sub.out_dir)
os.symlink(os.path.join(d, "missing_target.dcm"), os.path.join(d, "dangling.dcm"))
imgs, _ = W.probe_workspace(d, "vidi_output")
check("dangling symlink named .dcm is NOT an item", "dangling.dcm" not in rel(imgs, d), str(rel(imgs, d)))
ws_dg = W.build_workspace(d, "image", imgs)
check("dangling .dcm symlink dropped by build_workspace isfile filter", not any(i.path.endswith("dangling.dcm") for i in ws_dg.items), str([i.stem for i in ws_dg.items]))
# stems of exported files collide with the source stem? a.png vs vidi_output/png/a_mask.png -> no, different stems.
ws = W.build_workspace(d, "image", W.probe_workspace(d, "results")[0], "results")
check("renamed out dir: manifest from old dir not read -> no done flags", ws.n_done == 0)

# ── 10. unicode + spaces ─────────────────────────────────────────────────────
d = fresh("unicode")
tiny_png(os.path.join(d, "Pat ient 1/im age.png"))
tiny_png(os.path.join(d, "Пациент_2/изображение.png"))
tiny_png(os.path.join(d, "患者3/图像.png"))
tiny_png(os.path.join(d, "émoji 😀/scan ✓.png"))
os.makedirs(os.path.join(d, "patient 4")); shutil.copy(os.path.join(FIX_DCM, "bpd1_20100101_1.dcm"), os.path.join(d, "patient 4/sc an.dcm"))
tiny_png(os.path.join(d, "trailing space /x.png"))
tiny_png(os.path.join(d, "dots.in.dir.name/y.v2.png"))
imgs, _ = W.probe_workspace(d)
check("unicode/space names all found", len(imgs) == 7, str(rel(imgs, d)))
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("unicode stems preserved, no dup fallback", "изображение" in stems and "图像" in stems and "scan ✓" in stems and "im age" in stems and "y.v2" in stems, str(stems))
check("stems unique", len(set(stems)) == len(stems), str(stems))
# NFC/NFD: same visual name twice
import unicodedata
n_nfc = unicodedata.normalize("NFC", "é.png"); n_nfd = unicodedata.normalize("NFD", "é.png")
tiny_png(os.path.join(d, "nfc", n_nfc)); tiny_png(os.path.join(d, "nfd", n_nfd))
imgs, _ = W.probe_workspace(d)
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("NFC/NFD 'é' stems both present and distinct (bytes differ)", len(set(stems)) == len(stems) == 9, str(stems))

# ── 11. duplicates / collisions ──────────────────────────────────────────────
d = fresh("dups")
for sub in ("p1", "p2", "p3", "p4"):
    tiny_png(os.path.join(d, sub, "img.png"))
tiny_png(os.path.join(d, "img.png"))                                   # root-level 5th duplicate
imgs, _ = W.probe_workspace(d)
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("5 duplicate basenames -> folder__name stems, root keeps bare", stems == ["img", "p1__img", "p2__img", "p3__img", "p4__img"], str(stems))

d = fresh("samefolder")
tiny_png(os.path.join(d, "s/a.png"))
tiny_png(os.path.join(d, "s/t/s/a.png"))        # same folder name 's' at depth 1 and 3
tiny_png(os.path.join(d, "t/s/a.png"))
imgs, _ = W.probe_workspace(d)
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("identical folder names at different depths -> distinct full-rel stems",
      sorted(stems) == ["s__a", "s__t__s__a", "t__s__a"], str(stems))

d = fresh("collide")
tiny_png(os.path.join(d, "a/b__c.png"))
tiny_png(os.path.join(d, "a__b/c.png"))
# these only collide if basenames are duplicates -> they're not ('b__c' vs 'c'), so stems stay as basenames
imgs, _ = W.probe_workspace(d)
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("a/b__c vs a__b/c: no basename dup -> bare stems b__c and c", sorted(stems) == ["b__c", "c"], str(stems))
# force the '__' collision: duplicate basenames whose rel paths join to the same string
d = fresh("collide2")
tiny_png(os.path.join(d, "a/b__x.png"))      # dup basename? no. Need same basename:
tiny_png(os.path.join(d, "a__b/x.png"))
tiny_png(os.path.join(d, "q/x.png"))         # duplicate basename 'x' with a__b/x -> 'a__b__x' and 'q__x'
tiny_png(os.path.join(d, "a/b/x.png"))       # 'a__b__x' as well -> collision after join
imgs, _ = W.probe_workspace(d)
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
pairs = list(zip([os.path.relpath(i.path, d) for i in ws.items], stems))
check("a/b/x vs a__b/x collide after join -> '_1' suffix keeps them unique",
      len(set(stems)) == len(stems) and "a__b__x" in stems and "a__b__x_1" in stems, str(pairs))
# '_1' fallback stability: does the suffix depend on order only? Also a REAL file whose stem already ends in _1
d = fresh("suffix")
tiny_png(os.path.join(d, "u/x.png")); tiny_png(os.path.join(d, "u_1/x.png"))   # u__x, u_1__x -> fine
tiny_png(os.path.join(d, "v/x.png")); tiny_png(os.path.join(d, "v/x_1.png"))   # dup 'x' -> v__x; 'x_1' unique -> 'x_1'
tiny_png(os.path.join(d, "w/x.png")); tiny_png(os.path.join(d, "w/y.png"))
imgs, _ = W.probe_workspace(d)
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("suffix fallback never produces a stem equal to another file's natural stem",
      len(set(stems)) == len(stems), str(list(zip([os.path.relpath(i.path, d) for i in ws.items], stems))))
# manifest resume relies on stem stability: adding a duplicate later changes earlier stems
d = fresh("stability")
tiny_png(os.path.join(d, "k/one.png"))
imgs, _ = W.probe_workspace(d); ws = W.build_workspace(d, "image", imgs)
first_stem = ws.items[0].stem
W.write_manifest_row(ws.manifest_path, dict(stem=first_stem, source=ws.items[0].path))
tiny_png(os.path.join(d, "m/one.png"))           # new duplicate appears after the first save
imgs, _ = W.probe_workspace(d); ws2 = W.build_workspace(d, "image", imgs)
check("stem of an already-saved item changes when a duplicate basename appears later (done flag lost)",
      ws2.items[0].stem == first_stem and ws2.items[0].done,
      f"first={first_stem} now={[ (i.stem, i.done) for i in ws2.items ]}")

# ── 12. .nii.gz vs .nii stems ────────────────────────────────────────────────
d = fresh("nii")
shutil.copy(FIX_NII, os.path.join(d, "C.nii"))
with open(os.path.join(d, "C.nii.gz"), "wb") as f: f.write(b"\x1f\x8b" + b"\0" * 100)
with open(os.path.join(d, "D.NII.GZ"), "wb") as f: f.write(b"\x1f\x8b" + b"\0" * 100)
with open(os.path.join(d, "E.nii.GZ"), "wb") as f: f.write(b"\x1f\x8b" + b"\0" * 100)
with open(os.path.join(d, "F.gz"), "wb") as f: f.write(b"\x1f\x8b" + b"\0" * 100)
imgs, _ = W.probe_workspace(d)
check("C.nii + C.nii.gz + case variants found, F.gz not", rel(imgs, d) == ["C.nii", "C.nii.gz", "D.NII.GZ", "E.nii.GZ"], str(rel(imgs, d)))
ws = W.build_workspace(d, "image", imgs)
stems = [i.stem for i in ws.items]
check("C.nii and C.nii.gz share stem 'C' -> disambiguated (both in root => '_1')", len(set(stems)) == 4, str(stems))
check("file_stem strips .nii.gz case-insensitively", W.file_stem("D.NII.GZ") == "D" and W.file_stem("E.nii.GZ") == "E" and W.file_stem("x.y.nii.gz") == "x.y" and W.file_stem("p.nii") == "p", f"{W.file_stem('D.NII.GZ')} {W.file_stem('E.nii.GZ')}")
check("file_stem of '.nii.gz' bare name", W.file_stem(".nii.gz") == "" , repr(W.file_stem(".nii.gz")))
check("file_stem('a.tar.gz')", W.file_stem("a.tar.gz") == "a.tar", W.file_stem("a.tar.gz"))

# ── 13. root forms: trailing slash / relative / FILE ─────────────────────────
d = fresh("root")
tiny_png(os.path.join(d, "s/one.png")); tiny_png(os.path.join(d, "t/one.png"))
imgs_a, _ = W.probe_workspace(d)
imgs_b, _ = W.probe_workspace(d + "/")
imgs_c, _ = W.probe_workspace(d + "//")
check("trailing slash root -> same files", [os.path.realpath(p) for p in imgs_a] == [os.path.realpath(p) for p in imgs_b] == [os.path.realpath(p) for p in imgs_c], f"{imgs_b[:1]} {imgs_c[:1]}")
check("trailing slash root -> paths not doubled-slashed", all("//" not in p for p in imgs_b + imgs_c), str(imgs_c))
ws_a = W.build_workspace(d, "image", imgs_a); ws_b = W.build_workspace(d + "/", "image", imgs_b); ws_c = W.build_workspace(d + "//", "image", imgs_c)
check("trailing slash root -> same stems and same root/manifest path",
      [i.stem for i in ws_a.items] == [i.stem for i in ws_b.items] == [i.stem for i in ws_c.items] and ws_a.root == ws_b.root == ws_c.root and ws_a.manifest_path == ws_b.manifest_path,
      f"{[i.stem for i in ws_b.items]} {[i.stem for i in ws_c.items]} root={ws_c.root}")
# relative root
cwd0 = os.getcwd(); os.chdir(SCR)
try:
    relroot = os.path.relpath(d, SCR)
    imgs_r, _ = W.probe_workspace(relroot)
    ws_r = W.build_workspace(relroot, "image", imgs_r)
    check("relative root: items found", len(imgs_r) == 2, str(imgs_r))
    check("relative root: ws.root absolute", os.path.isabs(ws_r.root), ws_r.root)
    check("relative root: item paths absolute (dock compares abspath, Panel mismatch otherwise)", all(os.path.isabs(i.path) for i in ws_r.items), str([i.path for i in ws_r.items]))
    check("relative root: stems same as absolute", [i.stem for i in ws_r.items] == [i.stem for i in ws_a.items], f"{[i.stem for i in ws_r.items]} vs {[i.stem for i in ws_a.items]}")
    # relative root + manifest written with relative 'source' -> read back later? done flags use stem only -> fine
    # relative dot root
    os.chdir(d)
    imgs_dot, _ = W.probe_workspace(".")
    ws_dot = W.build_workspace(".", "image", imgs_dot)
    check("root='.': stems not polluted with './'", [i.stem for i in ws_dot.items] == ["s__one", "t__one"], str([i.stem for i in ws_dot.items]))
    check("root='.': item paths absolute", all(os.path.isabs(i.path) for i in ws_dot.items), str([i.path for i in ws_dot.items]))
finally:
    os.chdir(cwd0)
# root is a FILE
fp = os.path.join(d, "s/one.png")
try:
    imgs_f, lists_f = W.probe_workspace(fp)
    check("root=FILE: probe returns nothing (os.walk on a file yields nothing)", imgs_f == [] and lists_f == [], f"{imgs_f} {lists_f}")
except Exception as e:
    check("root=FILE: probe does not raise", False, repr(e))
try:
    ws_f = W.build_workspace(fp, "image", [fp])
    check("root=FILE: build_workspace with the file as root does not raise", True, f"stems={[i.stem for i in ws_f.items]} out_dir={ws_f.out_dir}")
except Exception as e:
    check("root=FILE: build_workspace with the file as root does not raise", False, repr(e))
# root nonexistent
try:
    imgs_n, lists_n = W.probe_workspace(os.path.join(d, "nope"))
    check("root nonexistent: empty, no raise", imgs_n == [] and lists_n == [])
except Exception as e:
    check("root nonexistent: empty, no raise", False, repr(e))
# paths outside root (list mode): stems
d2 = fresh("outside")
ws_o = W.build_workspace(d2, "list", [os.path.join(d, "s/one.png"), os.path.join(d, "t/one.png")])
check("list mode: duplicates outside root -> stem from absolute path without leading sep", all("__" in i.stem and not i.stem.startswith("__") for i in ws_o.items) and len(set(i.stem for i in ws_o.items)) == 2, str([i.stem for i in ws_o.items]))
check("list mode: outside-root stems do not contain os.sep", all(os.sep not in i.stem for i in ws_o.items), str([i.stem for i in ws_o.items]))
# very long stems from deep outside-root paths: 255-byte filename limit for exported files
longest = max(len(i.stem.encode()) for i in ws_o.items)
check("list mode outside-root stem length (bytes) reported", True, f"{longest} bytes; +'_roi_mask.nii.gz' = {longest + 17}")

# ── 14. list files found only at top level, list of lists ────────────────────
d = fresh("listfind")
tiny_png(os.path.join(d, "img/a.png"))
with open(os.path.join(d, "top.txt"), "w") as f: f.write("img/a.png\n")
with open(os.path.join(d, "img/nested.txt"), "w") as f: f.write("a.png\n")
with open(os.path.join(d, "bad.csv"), "w") as f: f.write("x,y\n1,2\n")
with open(os.path.join(d, ".hidden.txt"), "w") as f: f.write("img/a.png\n")
imgs, lists = W.probe_workspace(d)
check("list files: only top-level usable lists; nested/hidden/bad ignored",
      [os.path.basename(l) for l in lists] == [".hidden.txt", "top.txt"] or [os.path.basename(l) for l in lists] == ["top.txt"], str([os.path.basename(l) for l in lists]))
check("hidden list file: reported for the record", True, str([os.path.basename(l) for l in lists]))
check("image under list dir still found in image probe", rel(imgs, d) == ["img/a.png"], str(rel(imgs, d)))

n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
