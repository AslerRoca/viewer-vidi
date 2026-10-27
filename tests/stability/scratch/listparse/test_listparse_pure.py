"""listparse lens — pure-Python scenarios for workspace.py (no Qt event loop)."""
import os, sys, time, traceback
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H
H.register_package()
from viewer_vidi import workspace as W

S = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab/listparse"
L = os.path.join(S, "lists"); IM = os.path.join(S, "imgs")
A, B, C = (os.path.join(IM, n) for n in ("a.dcm", "b.dcm", "c.dcm"))
results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""))
def parse(name):
    return W.parse_list_file(os.path.join(L, name))
def build(name, paths=None):
    lf = os.path.join(L, name)
    return W.build_workspace(L, "list", W.parse_list_file(lf) if paths is None else paths, list_file=lf)
def scenario(name, fn):
    try:
        fn()
    except Exception as e:
        results.append((name, False))
        print(f"FAIL {name}  [EXCEPTION {type(e).__name__}: {e}]")
        traceback.print_exc(limit=3)

# 1 UTF-8 BOM
def s_bom():
    p = parse("bom.txt")
    check("bom.txt: BOM stripped, both entries resolve to real files", p == [A, B], repr([os.path.relpath(x, S) for x in p]))
    ws = build("bom.txt")
    check("bom.txt: no entry reported missing", not ws.missing, f"missing={ws.missing!r}")
    p0 = parse("bom_hdr0.csv")
    check("bom_hdr0.csv (BOM + 'path,label'): both paths", p0 == [A, B], repr(p0))
    p1 = parse("bom_hdr1.csv")
    check("bom_hdr1.csv (BOM + 'id,path,label'): path column used", p1 == [A, B], repr(p1))
scenario("bom", s_bom)

# 2 line endings
def s_eol():
    check("crlf.txt", parse("crlf.txt") == [A, B], repr(parse("crlf.txt")))
    check("crlf.csv (id,path)", parse("crlf.csv") == [A, B], repr(parse("crlf.csv")))
    check("cr_only.txt (classic Mac)", parse("cr_only.txt") == [A, B], repr(parse("cr_only.txt")))
scenario("eol", s_eol)

# 3 whitespace
def s_ws():
    check("trailing_ws.txt: spaces/tabs stripped", parse("trailing_ws.txt") == [A, B, C], repr(parse("trailing_ws.txt")))
    check("trailing_tab.tsv: extra empty column ignored", parse("trailing_tab.tsv") == [A, B], repr(parse("trailing_tab.tsv")))
scenario("ws", s_ws)

# 4 quoting / delimiters
def s_quote():
    sa = os.path.join(IM, "sub", "a.dcm")
    check("quoted_comma.csv", parse("quoted_comma.csv") == [sa, B], repr(parse("quoted_comma.csv")))
    check("quoted_txt.txt (\" and ')", parse("quoted_txt.txt") == [A, B], repr(parse("quoted_txt.txt")))
    p = parse("semicolon.csv")
    ws = build("semicolon.csv")
    check("semicolon.csv: not supported -> all missing (visible?)", len(ws.items) == 0, f"parsed={p!r} items={len(ws.items)} missing={len(ws.missing)}")
    p = parse("tabs_as_csv.csv")
    ws = build("tabs_as_csv.csv")
    check("tabs_as_csv.csv: tab-delimited .csv -> ?", True, f"parsed={p!r} items={len(ws.items)} missing={len(ws.missing)}")
    check("plain.tsv header 'Path'", parse("plain.tsv") == [A, B], repr(parse("plain.tsv")))
    check("tsv_nohdr.tsv first column", parse("tsv_nohdr.tsv") == [A, B], repr(parse("tsv_nohdr.tsv")))
scenario("quote", s_quote)

# 5 headers
def s_hdr():
    check("hdr_Path.csv (ID,Path)", parse("hdr_Path.csv") == [A, B], repr(parse("hdr_Path.csv")))
    check("hdr_FILE.csv", parse("hdr_FILE.csv") == [A, B], repr(parse("hdr_FILE.csv")))
    check("hdr_unknown.csv (img_path,label): header dropped, col0", parse("hdr_unknown.csv") == [A, B], repr(parse("hdr_unknown.csv")))
    p = parse("hdr_unknown_col2.csv"); ws = build("hdr_unknown_col2.csv")
    check("hdr_unknown_col2.csv (subject_id,img_path,label): documented=first col -> ids", True, f"parsed={[os.path.relpath(x,S) for x in p]} items={len(ws.items)} missing={len(ws.missing)}")
    p = parse("hdr_dotted.csv"); ws = build("hdr_dotted.csv")
    check("hdr_dotted.csv ('file.name,label'): header not counted as a missing path", ws.missing == [], f"parsed={[os.path.relpath(x,S) for x in p]} missing={ws.missing}")
    check("comments_then_hdr.csv", parse("comments_then_hdr.csv") == [A], repr(parse("comments_then_hdr.csv")))
    check("short_rows.csv: short rows skipped", parse("short_rows.csv") == [A, B], repr(parse("short_rows.csv")))
scenario("hdr", s_hdr)

# 6 no-header csv with path in col 3
def s_col3():
    p = parse("col3_nohdr.csv"); ws = build("col3_nohdr.csv")
    check("col3_nohdr.csv (id,x,path): README says first col; first DATA row must not vanish", len(p) == 2, f"parsed={[os.path.relpath(x,S) for x in p]} items={len(ws.items)} missing={[os.path.relpath(x,S) for x in ws.missing]}")
    p = parse("extless_first_missing.csv"); ws = build("extless_first_missing.csv")
    check("extless_first_missing.csv: missing extless path in row 1 is reported, not swallowed", len(p) == 2 and len(ws.missing) == 1, f"parsed={[os.path.relpath(x,S) for x in p]} items={len(ws.items)} missing={len(ws.missing)}")
scenario("col3", s_col3)

# 7 degenerate files
def s_degen():
    check("single.txt", parse("single.txt") == [A])
    check("single_noeol.txt", parse("single_noeol.txt") == [A])
    check("hdr_only.csv -> []", parse("hdr_only.csv") == [], repr(parse("hdr_only.csv")))
    p = parse("hdr_only_unknown.csv")
    check("hdr_only_unknown.csv ('id,label' only) -> [] (not a bogus 'id' path)", p == [], repr(p))
    check("empty.txt -> []", parse("empty.txt") == [])
    check("ws_only.txt -> []", parse("ws_only.txt") == [])
    t0 = time.time(); p = parse("binary.txt"); dt = time.time() - t0
    ws = build("binary.txt")
    check("binary.txt (2MB random): no exception, no items", len(ws.items) == 0, f"{len(p)} entries, {len(ws.missing)} missing, {dt:.2f}s")
    check("unreadable.txt (mode 000) -> [] (silently)", parse("unreadable.txt") == [] and not os.access(os.path.join(L, "unreadable.txt"), os.R_OK))
    check("self.txt lists itself -> item that is not an image", True, f"items={[it.stem for it in build('self.txt').items]}")
    p = parse("longline.txt"); check("longline.txt 5000-char path", len(p) == 2 and p[1] == A)
scenario("degen", s_degen)

# 8 csv module error paths (Python 3.10: NUL / field limit)
for name in ("utf16.csv", "nul.tsv", "binary.csv", "longfield.csv", "longfield.tsv", "quote_eol.csv"):
    def s_csverr(name=name):
        p = parse(name)
        check(f"{name}: parse_list_file returns without exception", True, f"{len(p)} entries: {[os.path.relpath(x,S)[:60] for x in p[:3]]}")
    scenario(name, s_csverr)
def s_find_utf16():
    lists = W.find_list_files(os.path.join(S, "root_utf16csv"))
    check("find_list_files on root with UTF-16 export.csv: no exception", True, repr(lists))
    imgs, lists = W.probe_workspace(os.path.join(S, "root_utf16csv"))
    check("probe_workspace on that root: no exception", True, f"{len(imgs)} imgs, lists={lists}")
scenario("find_utf16", s_find_utf16)

# 9 encodings
def s_enc():
    cafe = os.path.join(IM, "café.png")
    check("utf8_accent.txt", parse("utf8_accent.txt") == [cafe], repr(parse("utf8_accent.txt")))
    p = parse("latin1.txt"); ws = build("latin1.txt")
    check("latin1.txt: not found but reported (visible)", len(ws.missing) == 1, f"parsed={p!r}")
    p = parse("utf16.txt"); ws = build("utf16.txt")
    check("utf16.txt: nothing found, no exception", len(ws.items) == 0, f"{len(p)} entries, {len(ws.missing)} missing")
scenario("enc", s_enc)

# 10 ~ and ..
def s_paths():
    os.environ["HOME"] = os.path.join(S, "fakehome")
    p = parse("tilde.txt")
    check("tilde.txt: ~ expanded", p == [os.path.join(S, "fakehome", "h.dcm")] and os.path.isfile(p[0]), repr(p))
    p = parse("dotdot.txt"); ws = build("dotdot.txt")
    stems = [it.stem for it in ws.items]
    check("dotdot.txt: 4 entries outside root all found", len(ws.items) == 4 and not ws.missing, repr([os.path.relpath(x, S) for x in p]))
    check("dotdot.txt: stems unique", len(set(stems)) == 4, repr(stems))
    check("dotdot.txt: stems are filename-safe (no os.sep)", all(os.sep not in s for s in stems), repr(stems))
    check("dotdot.txt: stems < 100 chars", all(len(s) < 100 for s in stems), f"max len {max(len(s) for s in stems)}: {max(stems, key=len)!r}")
    ws = build("deep_dup.txt"); stems = [it.stem for it in ws.items]
    too_long = [s for s in stems if len(s + "_roi_mask.nii.gz") > 255]
    check("deep_dup.txt: duplicate basenames outside root -> stems usable as file names (<=255 incl. suffix)", not too_long, f"lens={[len(s) for s in stems]}")
    if too_long:
        import numpy as np
        from viewer_vidi.annotation_export import ExportInput, ExportOptions, export_item
        px = np.zeros((8, 8), np.float32); m = np.ones((8, 8), np.uint8)
        out = os.path.join(S, "deep_out")
        try:
            export_item(out, ExportInput(stem=stems[0], pixels=px, wc=1, ww=1, mask=m, rect=None), ExportOptions(formats=("png",)))
            check("deep_dup export", True)
        except Exception as e:
            check("deep_dup.txt: export with that stem", False, f"{type(e).__name__}: {str(e)[:120]}")
scenario("paths", s_paths)

# 11 duplicates
def s_dup():
    p = parse("dup.txt"); ws = build("dup.txt")
    check("dup.txt: same file 3x -> ?", True, f"parsed={[os.path.relpath(x,S) for x in p]} items={[(os.path.relpath(it.path,S), it.stem) for it in ws.items]}")
    check("dup.txt: all parsed entries are one identical path", len(set(p)) == 1)
scenario("dup", s_dup)

# 12 directory entry / unknown extensions
def s_dir():
    ws = build("seriesdir.txt")
    check("seriesdir.txt: DICOM series dir -> counted as missing (is it?)", True, f"items={[it.stem for it in ws.items]} missing={[os.path.relpath(x,S) for x in ws.missing]}")
    from viewer_vidi.tree_panel import _make_series_meta
    check("seriesdir.txt: the dir IS loadable by the viewer", _make_series_meta(os.path.join(S, "mr20")) is not None)
    ws = build("unknown_ext.txt")
    loadable = {it.stem: _make_series_meta(it.path) is not None for it in ws.items}
    check("unknown_ext.txt: every existing file becomes an item (x.ima, y.dicom, noext_png, 42228791, a)", len(ws.items) == 5, f"stems={[it.stem for it in ws.items]} missing={ws.missing}")
    check("unknown_ext.txt: all items loadable (else dock says 'Cannot open')", all(loadable.values()), repr(loadable))
    check("nii.txt", len(build("nii.txt").items) == 1)
    check("plain.lst (.lst + comment)", parse("plain.lst") == [A, B], repr(parse("plain.lst")))
scenario("dir", s_dir)

# 13 timing
def s_timing():
    t0 = time.time(); p = parse("ten_k.txt"); t1 = time.time(); ws = build("ten_k.txt", p); t2 = time.time()
    check("ten_k.txt: parse+build", len(p) == 10_000 and len(ws.items) == 6667 and len(ws.missing) == 3333, f"parse {t1-t0:.2f}s build {t2-t1:.2f}s stems_unique={len({it.stem for it in ws.items})==len(ws.items)} sample={[it.stem for it in ws.items[:4]]}")
    t0 = time.time(); r = W.find_list_files(os.path.join(S, "root_missing_only")); dt = time.time() - t0
    check("find_list_files root_missing_only -> []", r == [], f"{dt:.3f}s")
    t0 = time.time(); r = W.find_list_files(L); dt = time.time() - t0
    check("find_list_files(lists/) over all fixtures: no exception", True, f"{len(r)} usable of {len(os.listdir(L))} in {dt:.2f}s")
    t0 = time.time(); r = W.find_list_files(os.path.join(S, "root_readme")); dt = time.time() - t0
    sz = os.path.getsize(os.path.join(S, "root_readme", "README.txt")) / 1e6
    check("find_list_files root with %.0fMB README.txt (400k lines): under 2s" % sz, dt < 2.0 and r == [], f"{dt:.2f}s -> {r}")
    t0 = time.time(); imgs, lists = W.probe_workspace(os.path.join(S, "root_readme")); dt = time.time() - t0
    check("probe_workspace same root (what Open directory… runs on the GUI thread)", True, f"{dt:.2f}s imgs={len(imgs)} lists={lists}")
    r = W.find_list_files(os.path.join(S, "root_readme_names_file"))
    check("README 'See LICENSE.txt for terms.' is not a list", r == [], repr(r))
    r = W.find_list_files(os.path.join(S, "root_readme_bare"))
    check("README with a bare 'LICENSE.txt' line is not a list", r == [], repr(r))
    r = W.find_list_files(os.path.join(S, "root_two_lists"))
    check("root_two_lists -> both", len(r) == 2, repr(r))
    t0 = time.time(); r = W.find_list_files(os.path.join(S, "root_ten_k_missing")) if os.path.isdir(os.path.join(S, "root_ten_k_missing")) else None
scenario("timing", s_timing)

n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
