"""GUI manifest / resume scenarios — one scenario per process.

    python t_gui.py <scenario>        run it (may abort the process on purpose)
    python t_gui.py <scenario> post   inspect the disk state afterwards (no Qt)
"""
import os, sys, csv, time, shutil, stat
STAB = "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab"
sys.path.insert(0, STAB)
import harness as H

D    = os.path.join(STAB, "manifest")
WORK = os.path.join(D, "work")
SCN  = sys.argv[1]
POST = len(sys.argv) > 2 and sys.argv[2] == "post"
FIELDS = "stem,source,saved_at,mask_pixels,x0,y0,x1,y1,formats,files"


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + f"[{SCN}] " + name + (f"  [{info}]" if info else ""), flush=True)


def ws_root(name=SCN):
    return os.path.join(WORK, name, "ws")


def fresh_ws(src="ws_plain"):
    shutil.rmtree(os.path.join(WORK, SCN), ignore_errors=True)
    shutil.copytree(os.path.join(D, src), ws_root())
    return ws_root()


def raw_rows(path):
    """Manifest rows via csv directly (independent of read_manifest's blind spots)."""
    if not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def write_manifest(path, rows, header=FIELDS, encoding="utf-8", raw=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if raw is not None:
        with open(path, "wb") as f:
            f.write(raw)
        return
    with open(path, "w", newline="", encoding=encoding) as f:
        f.write(header + "\r\n")
        for r in rows:
            f.write(r + "\r\n")


def listdir_rec(root):
    out = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            out.append(os.path.relpath(os.path.join(dp, n), root))
    return sorted(out)


# ── Qt helpers ───────────────────────────────────────────────────────────────

def boot_open(root, out_name="vidi_output"):
    """Boot, show the dock and open *root* through the REAL _open_dir slot
    (QFileDialog patched to return root)."""
    app, win = H.boot()
    from viewer_vidi import annotation_dock as AD

    class FakeFD:
        @staticmethod
        def getExistingDirectory(*a, **k):
            return root

        @staticmethod
        def getOpenFileName(*a, **k):
            return ("", "")
    AD.QFileDialog = FakeFD
    dock = win._dock
    win._ws_btn.setChecked(True); app.processEvents()
    dock._out_edit.setText(out_name)
    return app, win, dock


def click_open(app, win, dock):
    dock._open_dir_btn.click(); app.processEvents()
    cell = win._quad.active_cell()
    ok = H.wait_loaded(app, cell) if (dock._ws and dock._ws.items) else False
    return cell, cell.canvas(), ok


def paint(app, dock, canvas, fy=0.3):
    dock._tool_btns["paint"].setChecked(True); dock._apply_tool()
    H.drag(app, canvas, H.pt(canvas, 0.3, fy), H.pt(canvas, 0.6, fy))
    return canvas.mask_pixels()


def draw_rect(app, dock, canvas):
    dock._tool_btns["rect"].setChecked(True); dock._apply_tool()
    H.drag(app, canvas, H.pt(canvas, 0.1, 0.1), H.pt(canvas, 0.7, 0.8))
    return canvas.crop_rect()


def save(app, dock, advance=False, choose=None):
    """Click the real Save / Save & Next button (goes through the Qt slot)."""
    seen = H.auto_close_dialogs(app, 300, choose)
    (dock._save_next_btn if advance else dock._save_btn).click()
    H.pump(app, 500)
    return seen


def current_item(dock):
    return dock._ws.items[dock._index] if dock._ws and dock._index >= 0 else None


# ── Scenarios ────────────────────────────────────────────────────────────────

def s_ro_outdir():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    check("workspace opened, first item loaded", ok and len(dock._ws.items) == 3)
    n = paint(app, dock, canvas)
    os.makedirs(out); os.chmod(out, 0o500)
    try:
        seen = save(app, dock)
    finally:
        os.chmod(out, 0o700)
    check("read-only out dir: 'Export failed' dialog shown, process alive",
          any(s[1] == "Export failed" for s in seen), str(seen))
    check("read-only out dir: item NOT marked done, no manifest, no files",
          not dock._ws.items[0].done and not os.path.exists(os.path.join(out, "manifest.csv"))
          and listdir_rec(out) == [], str(listdir_rec(out)))
    check("read-only out dir: mask kept on canvas after the failed save", canvas.mask_pixels() == n)
    # now writable again → save works
    seen = save(app, dock)
    check("after chmod back: save succeeds", dock._ws.items[0].done and not seen, str(seen))
    win.close()


def s_manifest_is_dir():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    os.makedirs(os.path.join(out, "manifest.csv"))          # a DIRECTORY where the manifest goes
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    check("manifest.csv is a directory: workspace still opens (read_manifest → {})", ok and dock._ws.n_done == 0)
    paint(app, dock, canvas)
    print("BEFORE_SAVE", flush=True)
    seen = save(app, dock)
    print("AFTER_SAVE alive", flush=True)
    check("manifest.csv is a directory: process survived the save", True, str(seen))
    win.close()


def s_manifest_is_dir_post():
    out = os.path.join(ws_root(), "vidi_output")
    files = listdir_rec(out)
    check("manifest.csv is a directory (post): export wrote png/a_mask.png before the manifest step blew up",
          "png/a_mask.png" in files, str(files))
    check("manifest.csv is a directory (post): manifest.csv.tmp left behind", "manifest.csv.tmp" in files)


def s_ro_after_subdirs():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    n1 = paint(app, dock, canvas)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    check("first save ok: manifest has a", not seen and rows and rows[0]["stem"] == "a", str(rows))
    os.chmod(out, 0o500)                                     # png/ stays writable, out dir not
    n2 = paint(app, dock, canvas, fy=0.6)
    print(f"BEFORE_SAVE mask={n2}", flush=True)
    seen = save(app, dock)
    print("AFTER_SAVE alive", flush=True)
    os.chmod(out, 0o700)
    check("out dir chmod 500 after png/ exists: process survived second save", True, str(seen))
    win.close()


def s_ro_after_subdirs_post():
    out = os.path.join(ws_root(), "vidi_output")
    os.chmod(out, 0o700)
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    from PIL import Image
    import numpy as np
    m = np.array(Image.open(os.path.join(out, "png", "a_mask.png")))
    n_disk = int((m == 255).sum())
    check("ro-after-subdirs (post): png/a_mask.png on disk was OVERWRITTEN by the 2nd stroke while manifest still has the 1st count",
          rows is not None and int(rows[0]["mask_pixels"]) != n_disk,
          f"manifest mask_pixels={rows and rows[0]['mask_pixels']} disk={n_disk} tmp_left={os.path.exists(os.path.join(out, 'manifest.csv.tmp'))}")


def s_extra_column():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    write_manifest(os.path.join(out, "manifest.csv"),
                   [f"a,{root}/a.png,2026-10-26T00:00:00,5,1,2,3,4,png,png/a_mask.png,reviewed by Dr X"],
                   header=FIELDS + ",note")
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    check("manifest with extra 'note' column: opens, a is done, jumps to b",
          ok and dock._ws.items[0].done and dock._index == 1, f"done={[i.done for i in dock._ws.items]} idx={dock._index}")
    paint(app, dock, canvas)
    print("BEFORE_SAVE", flush=True)
    seen = save(app, dock)
    print("AFTER_SAVE alive", flush=True)
    check("extra column: process survived the save", True, str(seen))
    win.close()


def s_extra_column_post():
    out = os.path.join(ws_root(), "vidi_output")
    files = listdir_rec(out); rows = raw_rows(os.path.join(out, "manifest.csv"))
    check("extra column (post): png/b_mask.png written, manifest unchanged (b missing), .tmp left",
          "png/b_mask.png" in files and [r["stem"] for r in rows] == ["a"] and "manifest.csv.tmp" in files,
          f"files={files} stems={[r['stem'] for r in rows]}")


def s_bom_manifest():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    write_manifest(os.path.join(out, "manifest.csv"),
                   [f"a,{root}/a.png,2026-10-26T00:00:00,5,1,2,3,4,png,png/a_mask.png",
                    f"b,{root}/b.png,2026-10-26T00:00:00,7,,,,,png,png/b_mask.png"],
                   encoding="utf-8-sig")
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    done = [i.done for i in dock._ws.items]
    check("BOM manifest: a and b should resume as done (observed done flags)", done == [True, True, False], f"done={done} idx={dock._index} label={dock._count_lbl.text()!r}")
    # save the current item (whatever it is) → does the manifest keep a and b?
    paint(app, dock, canvas)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    stems = [r["stem"] for r in rows]
    check("BOM manifest: after one save the previous rows a,b must survive", set(stems) >= {"a", "b"}, f"stems now={stems} dialogs={seen}")
    win.close()


def s_nonutf8_open():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    write_manifest(os.path.join(out, "manifest.csv"), [], raw=(FIELDS + "\r\n").encode() + b"\xe4rger,/x/\xe4.png,t,5,1,2,3,4,png,png/\xe4_mask.png\r\n")
    app, win, dock = boot_open(root)
    print("BEFORE_OPEN", flush=True)
    cell, canvas, ok = click_open(app, win, dock)
    print("AFTER_OPEN alive", flush=True)
    check("latin-1 manifest: Open directory survived", True, f"ws={dock._ws}")
    win.close()


def s_nul_open():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    write_manifest(os.path.join(out, "manifest.csv"), [], raw=(FIELDS + "\r\na,/x/a.png,t,5,1,2,3,4,png,png/a_mask.png\r\n").encode() + b"\x00" * 512)
    app, win, dock = boot_open(root)
    print("BEFORE_OPEN", flush=True)
    cell, canvas, ok = click_open(app, win, dock)
    print("AFTER_OPEN alive", flush=True)
    check("NUL-tail manifest: Open directory survived", True, f"ws={dock._ws}")
    win.close()


def s_outdir_change():
    root = fresh_ws()
    app, win, dock = boot_open(root, "vidi_output")
    cell, canvas, ok = click_open(app, win, dock)
    paint(app, dock, canvas)
    seen = save(app, dock, advance=True); H.wait_loaded(app, cell)
    check("save a into vidi_output, advanced to b", not seen and dock._index == 1 and current_item(dock).stem == "b")
    dock._out_edit.setText("out2")
    paint(app, dock, canvas)
    seen = save(app, dock)
    m1 = raw_rows(os.path.join(root, "vidi_output", "manifest.csv")); m2 = raw_rows(os.path.join(root, "out2", "manifest.csv"))
    check("after changing Output dir mid-job: b goes to out2/manifest.csv, a stays in vidi_output/manifest.csv",
          [r["stem"] for r in m1] == ["a"] and [r["stem"] for r in m2] == ["b"], f"m1={m1 and [r['stem'] for r in m1]} m2={m2 and [r['stem'] for r in m2]}")
    check("in-session done flags mix both dirs (a✓ b✓), count label says 2 done",
          [i.done for i in dock._ws.items] == [True, True, False] and "2 done" in dock._count_lbl.text(), dock._count_lbl.text())
    check("ws.out_dir_name followed the edit", dock._ws.out_dir_name == "out2")
    # reopen with out2 → which manifest? and do vidi_output/png/*.png leak into the item list?
    cell, canvas, ok = click_open(app, win, dock)
    stems = [i.stem for i in dock._ws.items]; done = [i.done for i in dock._ws.items]
    check("reopen with Output dir 'out2': items are still exactly a,b,c (old vidi_output/png outputs must not become items)",
          stems == ["a", "b", "c"], f"stems={stems}")
    check("reopen with 'out2': only b is done (out2 manifest), first pending a loaded",
          done[:3] == [False, True, False] and dock._index == 0, f"done={done} idx={dock._index}")
    # reopen with vidi_output → only a done; out2/png/* must not become items
    dock._out_edit.setText("vidi_output")
    cell, canvas, ok = click_open(app, win, dock)
    stems = [i.stem for i in dock._ws.items]; done = [i.done for i in dock._ws.items]
    check("reopen with 'vidi_output': items exactly a,b,c (out2/png outputs must not become items)", stems == ["a", "b", "c"], f"stems={stems}")
    check("reopen with 'vidi_output': only a done, b loaded", done[:3] == [True, False, False] and dock._index == 1, f"done={done} idx={dock._index}")
    win.close()


def s_delete_source():
    root = fresh_ws()
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    paint(app, dock, canvas)
    seen = save(app, dock)
    check("saved a", not seen and dock._ws.items[0].done)
    os.remove(os.path.join(root, "a.png"))
    cell, canvas, ok = click_open(app, win, dock)
    stems = [i.stem for i in dock._ws.items]
    rows = raw_rows(os.path.join(root, "vidi_output", "manifest.csv"))
    check("deleted source: reopen lists b,c only, manifest keeps the a row, b loaded, no crash",
          ok and stems == ["b", "c"] and [r["stem"] for r in rows] == ["a"] and dock._index == 0, f"stems={stems} rows={[r['stem'] for r in rows]} idx={dock._index}")
    check("deleted source: label shows 0 done of 2", "0 done" in dock._count_lbl.text() and "2 items" in dock._ws_lbl.text(), dock._count_lbl.text())
    # current item deleted underneath while displayed → Save still writes (pixels in memory) and records a dead source path
    os.remove(os.path.join(root, "b.png"))
    paint(app, dock, canvas)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(root, "vidi_output", "manifest.csv"))
    check("source deleted while displayed: save succeeds (pixels in memory), manifest row records the vanished path",
          not seen and any(r["stem"] == "b" for r in rows), f"dialogs={seen} stems={[r['stem'] for r in rows]}")
    win.close()


def s_rectless_maskless():
    root = fresh_ws()
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    n = paint(app, dock, canvas)                        # a: mask only
    seen = save(app, dock, advance=True); H.wait_loaded(app, cell)
    r = draw_rect(app, dock, canvas)                    # b: rect only
    seen2 = save(app, dock, advance=True); H.wait_loaded(app, cell)
    dock._image_chk.setChecked(True)                    # c: nothing drawn, Original ticked
    seen3 = save(app, dock)
    rows = {x["stem"]: x for x in raw_rows(os.path.join(root, "vidi_output", "manifest.csv"))}
    a, b, c = rows.get("a"), rows.get("b"), rows.get("c")
    check("rect-less save: x0..y1 are empty strings, mask_pixels = painted count, files = png/a_mask.png",
          a and (a["x0"], a["y0"], a["x1"], a["y1"]) == ("", "", "", "") and int(a["mask_pixels"]) == n and a["files"] == "png/a_mask.png", str(a))
    check("mask-less save: mask_pixels 0, rect ints, files = png/b_roi.png",
          b and b["mask_pixels"] == "0" and tuple(int(b[k]) for k in ("x0", "y0", "x1", "y1")) == r and b["files"] == "png/b_roi.png", str(b))
    check("original-only save: mask_pixels 0, empty rect, files = png/c_image.png",
          c and c["mask_pixels"] == "0" and c["x0"] == "" and c["files"] == "png/c_image.png", str(c))
    check("all three done, no dialogs", all(i.done for i in dock._ws.items) and not (seen or seen2 or seen3))
    # resume: read_manifest round trip of these rows
    from viewer_vidi import workspace as W
    rm = W.read_manifest(os.path.join(root, "vidi_output", "manifest.csv"))
    check("read_manifest returns the same 3 rows", set(rm) == {"a", "b", "c"} and rm["a"]["x0"] == "" and rm["b"]["mask_pixels"] == "0")
    win.close()


def s_stale_files():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    n1 = paint(app, dock, canvas); r1 = draw_rect(app, dock, canvas)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    check("save #1 png: 3 files recorded", rows[0]["files"] == "png/a_mask.png png/a_roi.png png/a_roi_mask.png", rows[0]["files"])
    # save #2: switch format to nifti only
    dock._fmt_chk["png"].setChecked(False); dock._fmt_chk["nifti"].setChecked(True)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(out, "manifest.csv")); files = listdir_rec(out)
    check("save #2 nifti: manifest row replaced (one row, formats=nifti), count still 1 done",
          len(rows) == 1 and rows[0]["formats"] == "nifti" and rows[0]["files"].startswith("nifti/") and "1 done" in dock._count_lbl.text(), f"{rows[0]['formats']} | {dock._count_lbl.text()}")
    stale = [f for f in files if f.startswith("png/")]
    check("save #2: the png files from save #1 are STILL on disk but no longer in 'files' (stale outputs)",
          stale == ["png/a_mask.png", "png/a_roi.png", "png/a_roi_mask.png"] and "png/" not in rows[0]["files"], f"disk={files} files={rows[0]['files']!r}")
    # save #3: back to png, mask only (rect dropped) → the old a_roi*.png with the OLD rectangle survive on disk
    dock._fmt_chk["png"].setChecked(True); dock._fmt_chk["nifti"].setChecked(False)
    canvas.clear_annotations(); n3 = paint(app, dock, canvas, fy=0.7)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(out, "manifest.csv")); files = listdir_rec(out)
    check("save #3 png mask-only: files = png/a_mask.png, rect empty", rows[0]["files"] == "png/a_mask.png" and rows[0]["x0"] == "", f"{rows[0]}")
    check("save #3: png/a_roi.png + png/a_roi_mask.png from save #1 (old rectangle) still on disk next to the fresh a_mask.png",
          "png/a_roi.png" in files and "png/a_roi_mask.png" in files, str(files))
    # the roi_mask on disk is from stroke #1 — compare with current mask
    from PIL import Image
    import numpy as np
    m = np.array(Image.open(os.path.join(out, "png", "a_mask.png"))); rm = np.array(Image.open(os.path.join(out, "png", "a_roi_mask.png")))
    check("save #3: on-disk a_roi_mask.png (old) is inconsistent with on-disk a_mask.png (new)",
          int((m == 255).sum()) == n3 and int((rm == 255).sum()) != int((m[r1[1]:r1[3], r1[0]:r1[2]] == 255).sum()),
          f"mask={int((m == 255).sum())} roi_mask_disk={int((rm == 255).sum())} expected_roi_from_new_mask={int((m[r1[1]:r1[3], r1[0]:r1[2]] == 255).sum())}")
    win.close()


def s_big_manifest():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    rows = [f"case_{i:05d},/data/case_{i:05d}.dcm,2026-10-26T00:00:00,5,1,2,3,4,png,png/case_{i:05d}_mask.png png/case_{i:05d}_roi.png" for i in range(5000)]
    write_manifest(os.path.join(out, "manifest.csv"), rows)
    app, win, dock = boot_open(root)
    t0 = time.perf_counter(); cell, canvas, ok = click_open(app, win, dock); t_open = time.perf_counter() - t0
    paint(app, dock, canvas)
    t0 = time.perf_counter(); seen = save(app, dock); t_save = time.perf_counter() - t0 - 0.5   # minus pump
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    check(f"5000-row manifest in GUI: open {t_open*1000:.0f} ms, save click {max(t_save,0)*1000:.0f} ms, rows now {len(rows)}",
          len(rows) == 5001 and not seen and t_save < 1.0)
    win.close()


def s_unicode_stems():
    root = fresh_ws("ws_odd"); out = os.path.join(root, "vidi_output")
    shutil.rmtree(out, ignore_errors=True)
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    stems = [i.stem for i in dock._ws.items]
    check("odd-name workspace: 5 items", len(stems) == 5, str(stems))
    saved = []
    for k in range(5):
        H.wait_loaded(app, cell)
        paint(app, dock, canvas); draw_rect(app, dock, canvas)
        seen = save(app, dock, advance=True)
        saved.append((current_item(dock).stem if k == 4 else dock._ws.items[k].stem, seen))
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    check("odd stems: all 5 saved without dialogs, 5 manifest rows", all(not s[1] for s in saved) and len(rows) == 5, f"{saved} rows={[r['stem'] for r in rows]}")
    files = listdir_rec(out)
    missing = [f for r in rows for f in r["files"].split(" ") if f not in files]
    check("odd stems: every token of 'files' (split on space) exists on disk", not missing, f"missing={missing}")
    # reopen → all done
    cell, canvas, ok = click_open(app, win, dock)
    check("odd stems: reopen resumes 5/5 done", all(i.done for i in dock._ws.items), str([(i.stem, i.done) for i in dock._ws.items]))
    win.close()


def s_tmp_leftover_gui():
    root = fresh_ws(); out = os.path.join(root, "vidi_output")
    write_manifest(os.path.join(out, "manifest.csv"), [f"a,{root}/a.png,2026-10-26T00:00:00,5,1,2,3,4,png,png/a_mask.png"])
    with open(os.path.join(out, "manifest.csv.tmp"), "w") as f:
        f.write("stem,source\r\nzzz,partial")                  # crash leftover
    app, win, dock = boot_open(root)
    cell, canvas, ok = click_open(app, win, dock)
    check("leftover .tmp: open ignores it, a done, b loaded", dock._ws.items[0].done and dock._index == 1)
    paint(app, dock, canvas)
    seen = save(app, dock)
    rows = raw_rows(os.path.join(out, "manifest.csv"))
    check("leftover .tmp: save ok, tmp replaced, rows a,b", not seen and not os.path.exists(os.path.join(out, "manifest.csv.tmp")) and [r["stem"] for r in rows] == ["a", "b"], str([r["stem"] for r in rows]))
    win.close()


SCENARIOS = {k[2:]: v for k, v in globals().items() if k.startswith("s_") and callable(v)}
fn = SCENARIOS[SCN + ("_post" if POST else "")]
fn()
print("END_OK", flush=True)
