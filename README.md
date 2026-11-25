# viewer-vidi

A lightweight, multi-format scientific image viewer built for research workflows.
Supports DICOM, NIfTI, and common raster formats (PNG, JPEG, BMP, TIFF) in a single
four-panel workspace.

## Run

```bash
bash viewer-vidi/start_viewer.sh
```

Run from the research root on either platform — the script auto-detects macOS (uses the `.venv` inside `viewer-vidi/`) or Linux (uses the `viewer_vidi` conda env) and launches via `launch_viewer.py`.

> **Why not `python -m viewer-vidi`?** The dash in the directory name is not a valid Python identifier, and the exFAT drive does not support symlinks, so the standard `-m` approach cannot be used. `run.py` (inside the project) loads the package via `importlib` as a workaround.

## Features

### Formats
| Format | Extensions | Notes |
|---|---|---|
| DICOM | `.dcm`, extensionless | Full header parsing, RescaleSlope/Intercept, MONOCHROME1 shown like MONOCHROME2 (see *Polarity*), multi-frame; extensionless files (DICOMDIR/CD exports) detected via DICM magic |
| NIfTI | `.nii`, `.nii.gz` | 2D / 3D / 4D; voxel spacing from header |
| Raster | `.png` `.jpg` `.jpeg` `.bmp` `.tiff` `.webp` | Grayscale or RGB→grey |

### Workspace
- **4-panel quad layout** — four independent panels split by a resizable cross
- **Drag series from the left tree into any panel** — each panel loads independently
- **Enlarge a panel** — press the **⤢** button in the top right corner of the panel, or
  double-click the image; the panel fills the whole image area. Press the button (now
  highlighted) or double-click again to bring the other panels back. The button works with
  every tool; the double-click does not while a drawing tool of the annotation workspace is
  selected (see *Enlarging the panel* there)
- **Colormap selector** in the toolbar (Gray, Bone, Hot, Viridis, …)
- **Directory picker** — change the data root without restarting

**Drag and drop from the study list (left sidebar)** — one gesture, three targets:

| Drag | Onto | Result |
|---|---|---|
| an image series or image folder (several selected series: a time series) | an image panel | loads into that panel |
| one folder or file with reports (`.txt` / `.rtf` / `.csv` / `.tsv`) | the [Reports](#reports-read-text-reports-next-to-the-images) panel | opens as the report source |
| one list file (`.txt` / `.lst` / `.csv` / `.tsv`) | the **Open list…** button of the [Workspace](#annotation-workspace-segment--crop-roi--export) dock | opens as a list-mode workspace |

A target that cannot use what is dragged refuses it (the cursor shows that) and nothing is
opened halfway. Drags from other applications, such as the desktop file manager, are not accepted.

### Viewing modes (per panel)
- **AX / COR / SAG** buttons — switch between axial, coronal, and sagittal planes (3D data)
- **Scroll wheel** — step through slices; Shift+scroll steps through time
- **Wheel tilt left/right** (e.g. Logitech G502) — scrub time backward/forward, wrapping at the ends like a cine loop.
  On Linux/X11 the tilt is read directly from the kernel input device, because Qt 5 drops isolated
  horizontal detents; this needs read access to `/dev/input/event*`:
  `sudo usermod -aG input $USER` (log out/in once). Without it the viewer falls back to Qt wheel
  events, where single tilt clicks may be swallowed (hold/fast tilts still work).
- **Slice slider** (right edge) — scrub through slices
- **Time bar** (bottom, hidden for static data) — play/pause, frame scrubbing, FPS control
- **DICOM info overlay** — **i** button in the panel header (or press **I** on the canvas):
  shows curated header info in the image corners — patient/study (top-left), modality and
  series/instance (top-right), geometry + current W/L (bottom-left), acquisition parameters
  (bottom-right). Below those, collapsible groups (**Equipment / Plate / Staff / Image / IDs**) —
  click a group title to expand its details; expansion state persists while scrubbing.
  Follows the displayed file while scrubbing slices/time; for NIfTI and plain images it shows
  the available geometry instead. Tag selection lives in `dicom_info.py`.

### Window / Level
| Mode | How to activate | Interaction |
|---|---|---|
| **Drag W/L** | default | Left-drag on image: horizontal → width, vertical → center |
| **ROI W/L** | click **ROI** button in panel header | Drag a rectangle; W/L is set from the p2–p98 range of pixels inside it |

**Default window.** A film opens with the window its header gives, in this order:

1. `WindowCenter` / `WindowWidth`, if the header has them.
2. Otherwise, for films that describe their display by a lookup table (`VOILUTSequence`; some
   CR systems store no window at all): a straight window over the range of values that table
   maps. That is the anatomy the maker meant to show. The table's curve itself is not applied,
   so the picture is somewhat darker and flatter than on the maker's own workstation.
3. With neither: the median ± half the 2nd–98th percentile range of the whole image. This is a
   guess from the whole plate and can miss an anatomy that fills only a small part of it.

**Reset W/L** returns to that window.

**Polarity (MONOCHROME1 films).** Some X-ray systems store their films as `MONOCHROME1`: a high
value means black. Such a film is flipped when it is read, so it is shown like every other film
(high value = white) without pressing **Invert**:

- The flip is `S − v`, with `S` taken from the header alone (`BitsStored`,
  `PixelRepresentation`, rescale) — `4095 − v` for an unsigned 12-bit film. The same film
  always gets the same flip, whatever its content.
- Everything works on the flipped values: the value under the cursor, window/level, ROI
  statistics, time curves and all exports. A window stored in the header is mirrored with them.
- The DICOM info overlay names the stored polarity: `MONOCHROME1 (shown flipped: high = white)`.
- **Invert** (Ctrl+I) stays what it is: a display switch on top, also applied to PNG / JPEG
  exports. It is not needed for these films any more.

### Annotation workspace (segment / crop ROI / export)
Toolbar **Workspace** button (Ctrl+Shift+W) opens the right-hand dock. A *workspace* is one
directory: it defines the job (which images to annotate) and receives the outputs.

**Workflow**
1. **Open directory…** — *image mode*: every DICOM / NIfTI / raster file below the directory
   (recursively) becomes one job item. **Open list…** — *list mode*: a `.txt` / `.lst` / `.csv` /
   `.tsv` file with one image path per line (absolute, or relative to the list; CSV/TSV use the
   `path` / `file` / `filename` column, else the first column; `#` lines are comments) is enough
   to start — its directory is the workspace. A directory holding both offers the choice.
   A list can also be dragged from the study list (left sidebar) onto the **Open list…**
   button; the button takes one list file at a time and refuses folders and images.
2. Items load one at a time into the active panel: **Prev** / **Next**, or double-click in the list.
3. Draw with the tools (below), then **Save** or **Save & Next** (Ctrl+S). After a save the
   panel's **Invert** is switched off again, so it does not carry over to the next item; the
   files just written keep the inversion they were saved with.
4. **Delete** (Delete key; Backspace on a Mac keyboard) marks the current image as wrong. The
   item stays on screen and the button turns into **Restore** — press it (or the key) again to
   undo the mark. While the mark is set the item is not saved: **Save** says so and writes
   nothing, **Save & Next** (Ctrl+S) only moves on to the next item.

**Tools** (act on the active panel): **Brush** (radius in image px; **Erase** toggles),
**Polygon** (click vertices; double-click or Enter fills, right-click drops the last vertex, Esc
cancels), **Rect** (drag the crop rectangle; the outside is dimmed; its edges and corners can
be adjusted afterwards, see below), **W/L** (back to window/level drag). **Undo** (Ctrl+Z) steps back through strokes / polygons / rectangles /
clears; **Clear** wipes mask and rectangle.

**Choosing a tool at the cursor:** a right-click on the image opens the tool row as a menu —
**W/L**, **Brush**, **Polygon**, **Rect** (the current one ticked) and **Erase** — so the mouse
does not have to travel to the dock. It applies to the panel that was clicked. A right-button
*drag* still pans the image, and while a polygon is being drawn the right-click still removes
its last vertex. The menu exists only while the Workspace dock is open.

**Enlarging the panel:** use the **⤢** button in the top right corner of the panel — it works
with every tool and keeps the tool, the mask and the rectangle as they are. The panel stays
enlarged while you draw and step through the items with **Prev** / **Next**; press the button
again to get the four panels back. A double-click on the image does *not* enlarge while
**Brush**, **Polygon** or **Rect** is selected, because it belongs to the tool there (Polygon
closes its outline with it; Brush and Rect ignore it so that quick clicks cannot flip the
layout).

**Adjusting the rectangle** (Rect tool): once drawn, the rectangle does not have to be redrawn
to correct it. It shows handles on its four corners and four edge midpoints.

| Drag | Effect |
|---|---|
| an edge (anywhere along it, within about 6 screen pixels of the line) | moves that side; the other three stay |
| a corner | moves the two sides that meet there |
| anywhere else, inside or outside | draws a new rectangle, as before |

- The cursor turns into a resize arrow (↔ ↕ ⤡ ⤢) wherever a drag would adjust, and stays a
  cross where it would draw a new rectangle.
- An edge stops at the opposite edge (the rectangle keeps at least one pixel) and at the image
  border.
- The Tools line of the dock shows position and size (`rect (x0, y0) → (x1, y1), w×h px`) live
  while you drag.
- Each adjustment is one **Undo** step (Ctrl+Z).
- An edge moves by whole screen pixels — about 2 image pixels per step on a full chest image
  at normal size. For pixel-exact edges zoom in first (Ctrl+scroll).
- The handles are shown only while the Rect tool is active; with another tool the rectangle
  stays visible but cannot be moved.

**Reopening a saved item:** when an item that was saved is opened again (**Prev** / **Next**,
double-click in the list, or a reopened workspace), the mask and the rectangle of its last save
are put back on the image. Correct them and save again, or tick other content and save again —
nothing has to be redrawn, and a second save cannot lose what the first one wrote.

- The painted mask is kept with every save in `<output dir>/work/<stem>_mask.png`, **whatever
  content is ticked** — also when **Mask** is not. The rectangle is kept in `manifest.csv`.
- Ticking **Mask** later and saving the reopened item writes the mask products.
- Items saved before the viewer kept masks get their rectangle from the manifest, and their
  mask from a saved mask product (PNG, else NIfTI) if there is one. A mask that was painted but
  never written is gone.
- The annotation comes back only on the view it was saved on. For a volume or a time series
  that is the slice / time point named in the manifest's `view` column, and only if it is the
  one shown right after loading.
- Marking an item as deleted removes its kept mask together with its products.

**List marks:** `○` pending · `✓` saved · `⚠` saved without a rectangle or mask (no crop was
written) · `⊘` deleted (struck through) · `✗` could not be loaded. After the mark comes the
item's running number — its place in the list — then the stem. The counter under the list names
how many items are saved without a rectangle or mask.

**Outputs** go to `<workspace>/<output dir>/` (default `vidi_output`), one subdirectory per
ticked format; content ticks choose **Mask** (the painted segmentation, plus its cut-out inside
a rectangle; with a rectangle also the rectangle itself as a mask), **Crop** (the rectangle cut
from the image) and **Original** (whole image):

| Format | Files | Values |
|---|---|---|
| `png/` | `<stem>_mask.png`, `<stem>_roi.png`, `<stem>_roi_mask.png`, `<stem>_rect_mask.png`, `<stem>_image.png` | 8-bit; current window/level and invert applied (what you see); masks 0/255 |
| `jpeg/` | same, `.jpg` | 8-bit lossy (quality 95) — prefer PNG for masks |
| `nifti/` | same, `.nii.gz` | float32 values as the viewer reads them: DICOM rescale applied, MONOCHROME1 flipped (high = white, see *Polarity*); pixel spacing in the affine; masks uint8 0/1 |

`<stem>_rect_mask` is the crop rectangle as a mask on the whole image: same size and geometry
as `<stem>_image`, 1 inside the rectangle (255 in PNG / JPEG), 0 outside. It is written whenever
**Mask** is ticked and a rectangle exists, whether or not anything was painted — a rectangle
alone therefore does give a mask file. `<stem>_mask` and `<stem>_roi_mask` exist only when
something was painted.

Next to the format folders, `work/<stem>_mask.png` is the viewer's own copy of each painted
mask (see *Reopening a saved item*). It is not a product; deleting it only means that the item
comes back without its mask.

`manifest.csv` in the output dir has one row per item: stem, source path (relative to the
workspace), status (`saved` / `deleted`), save time, displayed slice/view, rectangle, mask pixel
count, formats, the written files (`;`-separated), `photometric` (the source's
PhotometricInterpretation), `invert` (1 if Invert was on at the save, so the 8-bit products
are negatives on purpose), and the window of the save: `wc`, `ww` and `wl_default` (1 if that
was the film's default window, 0 if it was set by hand).

**Exports made before 2026-11-25** were written while the viewer still worked on the stored
values. For films stored as MONOCHROME1 this means: their NIfTI image and crop are negatives,
and their PNG / JPEG are right only if Invert was on when they were saved. Rows of that time
have an empty `photometric` column. `tools/repair_mono1.py` brings such an output directory to
the present convention:

```bash
python tools/repair_mono1.py <output dir>            # dry run: counts only, writes nothing
python tools/repair_mono1.py <output dir> --apply    # rewrite
python tools/repair_mono1.py <output dir> --list     # also name the products concerned
```

It reads only the header of each row's source film. For MONOCHROME1 films it rewrites the NIfTI
image and crop with the same flip the viewer now applies at load (masks are not touched) and
fills the row's `photometric`; other films only get the column filled. PNG / JPEG are never
changed: each one is compared with its film and reported as right, negative (saved without
Invert) or unclear. A second run changes nothing — rewritten files carry a note in their NIfTI
header and are never flipped twice.

`tools/update_exports.py` does the other two things an older output directory lacks, again from
`manifest.csv` and the source films, without reopening any item:

```bash
python tools/update_exports.py <output dir> --default-window --rect-masks            # dry run
python tools/update_exports.py <output dir> --default-window --rect-masks --apply
```

- `--default-window`: films without a header window used to open with the whole-plate guess
  (rule 3 above), so their PNG / JPEG were saved with windows set by hand, film by film. Their
  PNG / JPEG image and crop are rendered again with today's default window (rule 2), Invert
  off — one rule for all of them. The replaced files are first moved to
  `<output dir>/replaced-<time>/`; the rows get `wc`, `ww`, `wl_default = 1`, `invert = 0`.
  Films with their own header window are left as they are, and so is every NIfTI file.
- `--rect-masks`: every saved row with a rectangle gets its `<stem>_rect_mask` in each of the
  row's formats. Nothing existing is changed.

A second run finds nothing left to do. Rows of volume slices are left alone.

**Policies — what the viewer will and will not do with your data**
- **Source images are never modified, moved or deleted.** The viewer only reads them. *Delete*
  is a mark in `manifest.csv` (`status = deleted`), nothing else. The whole job can be deleted
  by removing the output directory.
- **Everything the viewer writes lives under `<workspace>/<output dir>/`.** The output dir must
  be a plain folder name (no paths, no `.`/`..`); anything else falls back to `vidi_output`.
- **`manifest.csv` is the record of the job.** Reopening the workspace matches rows to files by
  source path (so a moved or copied workspace, e.g. on the other device, resumes correctly),
  marks items ✓ / ⊘, and jumps to the first pending one. An output stem recorded there is kept
  even if the folder's contents change. Files on disk for an item always match its row:
  re-saving removes products that were not rewritten, and marking an item deleted removes its
  products. An item marked as deleted is not saved until it is restored.
- **Nothing is overwritten silently.** A manifest that cannot be parsed is moved aside as
  `manifest.csv.unreadable-<time>` before a new one is written. Directories that hold a
  `manifest.csv` are never scanned for job items, so outputs cannot become inputs.
- **Save refuses rather than guessing.** It refuses when the active panel shows a different file
  than the current item, when the item failed to load, or while a load is still in progress.
  A corrupt or truncated image is reported (✗) instead of being shown or saved as a black image.
- **What you see is what you save.** PNG/JPEG reproduce the on-screen rendering pixel for pixel
  (window/level and invert applied); NIfTI keeps the values behind the picture (MONOCHROME1
  flipped, see *Polarity*), whatever Invert says. Annotations are 2-D on the
  displayed slice: changing slice, time point or plane resets mask and rectangle, and the
  manifest's `view` column records which slice was saved. Each file is one item.
- **Output names are stable and unique.** Duplicate basenames across subfolders get a
  `<folder>__<name>` stem (case-insensitive, so Mac/Windows volumes are safe); very long stems
  are shortened with a hash tail.

### Reports (read text reports next to the images)
Toolbar **Reports** button (Ctrl+Shift+R) opens the report panel for reading radiology reports.
It is a reader: nothing is written anywhere, and it is not linked to the loaded images yet.

The panel takes the place of the right two image panels (and a strip of the left two, which
stay for images). Drag the divider between images and reports to change the split; the width
is kept until the viewer is closed. Closing Reports brings the right two panels back with
whatever was loaded in them.

- **Open folder…** — every `.txt` / `.rtf` file of the folder is one report, and every row of
  its `.csv` / `.tsv` files is one report. Subfolders are not searched; hidden files are skipped.
  **Open file…** — one report file, or one table.
- **Drag and drop** — drag one folder or file from the study list (left sidebar) onto the
  report panel to open it, the same as picking it with the buttons. Image panels do not take
  report folders.
- **Tables** — the report text is the column with the longest values (among the columns named
  like *text* / *report* / *Bericht*, if there are any); the other columns are shown as the
  report's header. RTF text is converted to plain text. Rows identical in every column are
  listed once. An export is indexed in the background (372 MB in about 2 s) and its rows are
  read from disk on demand, so it is never held in memory.
- **List** — one line per report: patient ID and examination time when they can be read from
  the file name (`<id>_<YYYYMMDD>-<HHMMSS>.txt`) or from the table (the `pacs_id` /
  `patient_id` … column, else the first one, plus the first date column), sorted so that one
  patient's examinations are adjacent. **Filter** keeps the reports whose list line or header
  values contain every word typed — it does not search the report text. **Prev** / **Next** or
  the arrow keys step through the filtered list.
- **Formatting** follows the layout of the text, not a fixed template: a line in capitals is a
  section, a short first line of a paragraph is a sub-heading, `•` / `·` / `-` lines are
  bullets, `Key: value` and `Label:` lines are highlighted, and `===== … =====` separates
  several reports of one examination. Bold / italic of an RTF source is not carried over.

With the Workspace dock open as well, the reports stand between the images and the dock.

### Multi-series time series (3D-T / 2D-T)
1. Expand a study in the left panel and **double-click each series** to load it first
2. Shift-click or Ctrl-click to select multiple series in the tree
3. Drag the selection into any panel — they load as a time series (2D-T or 3D-T)

> **Note:** Series must be loaded (double-clicked) before multi-select drag is available.
> This is a known limitation of the QFileSystemModel lazy-loading approach.

## Dependencies

```
PyQt5 >= 5.15
numpy >= 1.24
pydicom >= 3.0
nibabel             # for NIfTI (.nii / .nii.gz)
Pillow              # for PNG/JPEG/BMP/TIFF
matplotlib >= 3.6   # for the time-course plot panel
```

Install into the venv:

```bash
pip install -r requirements.txt
```

## Package layout

```
viewer_vidi/
├── __main__.py           # entry point
├── constants.py          # DATA_ROOT, style paths, colour tokens
├── style.qss             # dark Catppuccin-inspired stylesheet
├── data_model.py         # SeriesType, SeriesMeta, SeriesData, GroupedSeriesMeta
├── loader.py             # LoaderWorker (QThread) — DICOM / NIfTI / image loading
├── windowing.py          # render_to_rgb, default window (header, VOI LUT range, percentiles), rescale + MONOCHROME1 flip
├── colormaps.py          # precomputed uint8 LUT tables
├── dicom_info.py         # curated DICOM header reads for the info overlay
├── image_canvas.py       # ImageCanvas — QPainter renderer, drag W/L, ROI W/L, mask + adjustable crop rectangle
├── drag_state.py         # what a drag from the study list carries: series payload, dragged paths
├── view_cell.py          # ViewCell — one panel: canvas + controls + drag-drop
├── quad_view.py          # QuadView — 2×2 grid, fullscreen toggle, active tracking
├── tree_panel.py         # StudyTreeWidget — lazy filesystem scan, multi-select drag
├── time_course_window.py # ROI time-course panel with plot and point management
├── workspace.py          # annotation workspace: image/list mode discovery, manifest
├── annotation_export.py  # mask / crop / image writers — PNG, JPEG, NIfTI; kept masks (no Qt)
├── annotation_dock.py    # Workspace dock — job list, brush/polygon/rect tools, export
├── rtf_text.py           # RTF → plain text (no Qt)
├── reports.py            # report sources: folder / table index, on-demand read, layout rules (no Qt)
├── report_panel.py       # Reports panel — source, filterable list, formatted report view
├── main_window.py        # MainWindow — toolbar, splitter, status bar
└── tools/                # for output directories written by an older version
    ├── repair_mono1.py   #   NIfTI values of MONOCHROME1 films: flip to high = white
    └── update_exports.py #   PNG / JPEG with the default window; rectangle masks
```

## Tests

`tests/stability/` holds the headless checks for the annotation workspace: `test_annot.py`
(72 checks, among them adjusting the crop rectangle by its edges and corners, dropping a
list on **Open list…**, the panels' enlarge button, the right-click tool menu, kept and
restored annotations, the rectangle mask, the default window of a film without a header
window, and saving with Invert, a hand-set window or a deleted mark; run `make_fixtures.sh` first, then `QT_QPA_PLATFORM=offscreen python
tests/stability/test_annot.py` from the `viewer_vidi` env), `test_fixes.py` (44 regression
checks for the 2026-10-27 stability fixes), `test_mono1.py` (22 checks: the MONOCHROME1 flip
at load on a fixture film and a MONOCHROME2 twin of it, the default window from a VOI LUT, and
`tools/repair_mono1.py` and `tools/update_exports.py` on an output directory written the old
way — dry run, apply, second run), `test_list_marks.py` (13 checks: the running numbers of
the list rows and the `⚠` mark and counter for items saved without a rectangle or mask), `shot_annot.py` (offscreen screenshot), and
`scratch/<lens>/` with the scripts of the 14-lens stability review of 2026-10-27
(`REPORT_2026-10-27.md`; status and open items in `TODO.md`).

`tests/reports/test_reports.py` holds the headless checks for the Reports panel (71 checks: RTF
conversion, folder / table discovery, on-demand reads, layout rules, panel behaviour, its place
in the window, drag and drop from the study list). It builds
its own synthetic fixtures in a temp dir — no report data is stored in the repo:
`QT_QPA_PLATFORM=offscreen python tests/reports/test_reports.py`.

## Known Issues

- Multi-select drag requires each series to be loaded (double-clicked) individually first before dragging as a group.
- Annotation workspace: the serious findings of the 2026-10-27 stability review are fixed; the
  remaining open items (NIfTI affine orientation, Ctrl+Z focus, GUI-thread export) are in `TODO.md`.
