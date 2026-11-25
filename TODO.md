# TODO — viewer-vidi

## Workspace round of 2026-11-25 (requested 2026-11-18 and 2026-11-24)

Done — code, tests (`test_annot.py` 72, `test_mono1.py` 22, `test_list_marks.py` 13) and README:

- [x] **MONOCHROME1 films flipped at load (#75)** — `windowing.mono1_flip_sum`, used by
      `apply_rescale` and `wl_from_dicom`; display, statistics and every export are high = white.
      Manifest columns `photometric` and `invert`. Info overlay names the stored polarity.
- [x] **List rows carry a running number and a mark for a save without a crop** (asked
      2026-11-25, made in another session): `✓ 41  <stem>`; `⚠` = saved with neither a
      rectangle nor a mask (`workspace.row_is_empty`, `Item.empty`); the counter names how many.
      Test: `tests/stability/test_list_marks.py` (13).
- [x] **Invert goes back to off after a save** (`AnnotationDock.item_saved` → toolbar button).
- [x] **Right-click on the image opens the tool menu** (W/L, Brush, Polygon, Rect, Erase). A
      right-button drag still pans; a polygon in progress keeps its right-click.
- [x] **An item marked as deleted is not saved**: Save says so, Save & Next only moves on.
      Plain Save is refused the same way (not asked for explicitly — to confirm with the user).
- [x] **The mask is kept with every save** (`<output dir>/work/<stem>_mask.png`) and put back,
      with the rectangle, when the item is reopened; pre-existing items fall back to the manifest
      rectangle and a saved mask product.

Still to do:

- [x] **`tools/repair_mono1.py --apply` run on the output directory of the finished crop job**
      (2026-11-25, on the user's word, the files copied aside first): the NIfTI image and crop of
      the MONOCHROME1 films are now high = white like all others; every row carries `photometric`.
- [ ] **Export ticks are not remembered** (seen 2026-11-25). A new viewer session starts with
      the default ticks (PNG only; Mask + Crop, no Original). Re-saving an item of an existing
      job then writes only those products, and — as designed, "files on disk match the row" —
      removes the item's JPEG / NIfTI / whole-image products of the earlier save without a word.
      Options: take the ticks from the manifest when a workspace with saved rows is opened;
      and / or ask before a save removes products of formats that are not ticked.
      Until then: set the ticks by hand before re-saving anything in a fresh session. The 13
      items of the first crop job that lost products this way were completed from the manifest
      on 2026-11-25 (one-off script, not in the repo).
- [x] **Default window of films that carry a VOI LUT instead of a window** (found and fixed
      2026-11-25; seen on AGFA ADC CR films). User chose option A: `wl_from_dicom` takes the
      LUT's input range as the default window when the header has no window. The manifest
      records `wc`, `ww`, `wl_default`. `tools/update_exports.py --default-window` renders the
      8-bit products of such films again in an older output directory.
- [x] **Rectangle as a mask** (asked 2026-11-25): with **Mask** ticked and a rectangle, the
      export writes `<stem>_rect_mask`; `tools/update_exports.py --rect-masks` adds it to an
      older output directory.
- [ ] Option B of the window question — applying the VOI LUT curve itself for display and
      8-bit export (the maker's exact picture) — was not chosen; only if option A's flatter
      picture turns out not to be enough.
- [ ] Films with a header window whose 8-bit products were saved with a hand-set window are
      left as they are by `update_exports.py`; decide whether they should follow the default too
      (10 films of the first crop job).
- [ ] **Backup copies in the output directory of the first crop job** — three
      `replaced-<time>/` folders and two `manifest.csv.before-*` copies (about 1.4 GB) from the
      tool runs of 2026-11-25. Delete them once the re-rendered and flipped products have been
      looked at; only on the user's word.
- [ ] **Check on a real display** — everything of this round was tested headless only:
      right-click tool menu, annotation put back on reopen, list marks, the default window of
      VOI-LUT films, the Reports panel, list drop, rectangle adjustment, enlarge button. Takes
      over the check pending since 2026-10-26 (brush feel, dock layout).
- [ ] **Decide whether to merge `wip/report-viewer` → `master`.** The branch carries
      `wip/roi-export` (annotation workspace, with the unverified `wip/invert` work), the Reports
      panel and this round.
- [ ] Possible additions nobody asked for yet: Undo / Clear in the right-click menu; putting the
      annotation back on a volume slice other than the one shown right after loading.

## Annotation workspace stability (branch `wip/roi-export`, review of 2026-10-27)

Source: 14 independent headless testers, ~1,100 checks, 98 raw findings → 88 unique.
**None of them is independently verified yet** — the verification phase hit the usage limit.
Details: `tests/stability/REPORT_2026-10-27.md` (every finding with repro command);
scripts: `tests/stability/scratch/<lens>/`; baseline suite that passes: `tests/stability/test_annot.py`.

### Status 2026-10-27 (second session): fixes applied by hand, no verification agents

The 31 crash / data-loss / wrong-output findings were reproduced by hand with the testers'
scripts, fixed, and re-checked. Regression suite: `tests/stability/test_fixes.py` (44 checks)
plus the baseline `tests/stability/test_annot.py` (35 checks) — both pass. The two
verification routes from the first draft of this file are no longer needed for these groups.

- [x] **G1** manifest write guarded (`QMessageBox`, item stays pending); unique temp file; user
      columns preserved on rewrite.
- [x] **G2** `parse_list_file` never raises: UTF-16 by BOM, UTF-8 BOM stripped, NULs dropped,
      `csv.Error` falls back to a plain split, `expanduser` errors ignored, lists > 20 MB ignored.
- [x] **G3** `read_manifest` never raises (lenient decode, `csv.Error` caught).
- [x] **G4** stems: case-folded duplicate detection, collision-aware `_N` suffix, 96-char cap with
      hash tail; manifest rows carry `source` relative to the workspace and done flags + stems are
      matched by source, so they follow the file across renames/devices.
- [x] **G5** `ViewCell` drops `headers_ready` from a superseded request; Save also checks the
      displayed shape against the series header.
- [x] **G6** single-image reads are strict: decode failures and multi-frame files raise →
      `load_error` → panel label "Load failed", item marked ✗, Save refused, Next still works.
- [x] **G7** BOM manifests read; an unreadable manifest is moved to `manifest.csv.unreadable-<ts>`
      instead of being overwritten (status line says so).
- [x] **G8** Output dir must be a plain folder name (else default); only the top-level output dir
      is skipped by name, and any directory holding a `manifest.csv` is skipped.
- [x] **G9** loader: NIfTI rows=Y, cols=X for 2-D as well, spacing (row, col) = (zooms[1],
      zooms[0]); export uses `ViewCell.display_spacing()` (slice spacing on reformat rows).
- [x] **G10** BOM in `.txt` lists; header heuristic keeps missing paths visible; long stems capped.
- [x] **G11** re-save removes products of the previous save that were not rewritten; `files`
      column is `;`-separated.
- [x] **G12** annotations are reset when the displayed slice/time/view changes; manifest has a
      `view` column (e.g. `AXIAL z=9 t=0`).
- [x] Also fixed from the ux/minor list: Ctrl+S ignored while the dock is hidden; tree loads keep
      the dock tool; dock tool unchecks the panel's ROI/TC buttons; ROI-TC panel restored on
      panel switch; undo covers rectangles; tiny rect drags ignored; double-click in brush/rect
      no longer paints or toggles fullscreen; winding polygon fill (no holes); brush cursor on
      anisotropic reformats; PNG/JPEG export truncates like the canvas (pixel-exact); NaN/inf
      pixels without warnings; wait cursor during export; empty-panel message; symlinked paths
      compared by realpath; dangling `.dcm` symlinks not counted; list entries naming a DICOM
      series directory are items; duplicate list entries collapse.

### Still open (not fixed in this round)
- [ ] NIfTI exports use a diagonal affine: source orientation / translation / slice z are not
      carried over (#73) — needs the source affine plumbed through `SeriesData`.
- [ ] Ctrl+Z is swallowed while a spin box has focus (#53).
- [ ] Export runs on the GUI thread (wait cursor only; 8192² takes ~15 s) (#40, #59).
- [x] MONOCHROME1 polarity on display/export (#75) — fixed 2026-11-25, see the top of this file.
- [ ] Output dir `.` is still accepted at the `workspace.py` API level (the dock rejects it).
- [ ] In-progress polygon vertices are dropped when switching panels (#54).
- [ ] Toolbar W/L spins not synced after a tree load (#63, pre-existing).
- [ ] Visual check on a real display and the merge decision — now listed at the top of this
      file (round of 2026-11-25), since `wip/report-viewer` carries this branch.
