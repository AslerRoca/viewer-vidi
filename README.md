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
| DICOM | `.dcm`, extensionless | Full header parsing, RescaleSlope/Intercept, multi-frame; extensionless files (DICOMDIR/CD exports) detected via DICM magic |
| NIfTI | `.nii`, `.nii.gz` | 2D / 3D / 4D; voxel spacing from header |
| Raster | `.png` `.jpg` `.jpeg` `.bmp` `.tiff` `.webp` | Grayscale or RGB→grey |

### Workspace
- **4-panel quad layout** — four independent panels split by a resizable cross
- **Drag series from the left tree into any panel** — each panel loads independently
- **Double-click a panel** to fullscreen it; double-click again to restore the grid
- **Colormap selector** in the toolbar (Gray, Bone, Hot, Viridis, …)
- **Directory picker** — change the data root without restarting

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

### Annotation workspace (segment / crop ROI / export)
Toolbar **Workspace** button (Ctrl+Shift+W) opens the right-hand dock. A *workspace* is one
directory: it defines the job (which images to annotate) and receives the outputs.

**Workflow**
1. **Open directory…** — *image mode*: every DICOM / NIfTI / raster file below the directory
   (recursively) becomes one job item. **Open list…** — *list mode*: a `.txt` / `.lst` / `.csv` /
   `.tsv` file with one image path per line (absolute, or relative to the list; CSV/TSV use the
   `path` / `file` / `filename` column, else the first column; `#` lines are comments) is enough
   to start — its directory is the workspace. A directory holding both offers the choice.
2. Items load one at a time into the active panel: **Prev** / **Next**, or double-click in the list.
3. Draw with the tools (below), then **Save** or **Save & Next** (Ctrl+S).
4. **Delete** (Delete key; Backspace on a Mac keyboard) marks the current image as wrong. The
   item stays on screen and the button turns into **Restore** — press it (or the key) again to
   undo the mark.

**Tools** (act on the active panel): **Brush** (radius in image px; **Erase** toggles),
**Polygon** (click vertices; double-click or Enter fills, right-click drops the last vertex, Esc
cancels), **Rect** (drag the crop rectangle; the outside is dimmed), **W/L** (back to
window/level drag). **Undo** (Ctrl+Z) steps back through strokes / polygons / rectangles /
clears; **Clear** wipes mask and rectangle.

**List marks:** `○` pending · `✓` saved · `⊘` deleted (struck through) · `✗` could not be loaded.

**Outputs** go to `<workspace>/<output dir>/` (default `vidi_output`), one subdirectory per
ticked format; content ticks choose **Mask** (the painted segmentation, plus its cut-out inside
a rectangle), **Crop** (the rectangle cut from the image) and **Original** (whole image):

| Format | Files | Values |
|---|---|---|
| `png/` | `<stem>_mask.png`, `<stem>_roi.png`, `<stem>_roi_mask.png`, `<stem>_image.png` | 8-bit; current window/level and invert applied (what you see); masks 0/255 |
| `jpeg/` | same, `.jpg` | 8-bit lossy (quality 95) — prefer PNG for masks |
| `nifti/` | same, `.nii.gz` | raw float32 after DICOM rescale, pixel spacing in the affine; masks uint8 0/1 |

`manifest.csv` in the output dir has one row per item: stem, source path (relative to the
workspace), status (`saved` / `deleted`), save time, displayed slice/view, rectangle, mask pixel
count, formats and the written files (`;`-separated).

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
  products. Saving a deleted item restores it.
- **Nothing is overwritten silently.** A manifest that cannot be parsed is moved aside as
  `manifest.csv.unreadable-<time>` before a new one is written. Directories that hold a
  `manifest.csv` are never scanned for job items, so outputs cannot become inputs.
- **Save refuses rather than guessing.** It refuses when the active panel shows a different file
  than the current item, when the item failed to load, or while a load is still in progress.
  A corrupt or truncated image is reported (✗) instead of being shown or saved as a black image.
- **What you see is what you save.** PNG/JPEG reproduce the on-screen rendering pixel for pixel
  (window/level and invert applied); NIfTI keeps the raw values. Annotations are 2-D on the
  displayed slice: changing slice, time point or plane resets mask and rectangle, and the
  manifest's `view` column records which slice was saved. Each file is one item.
- **Output names are stable and unique.** Duplicate basenames across subfolders get a
  `<folder>__<name>` stem (case-insensitive, so Mac/Windows volumes are safe); very long stems
  are shortened with a hash tail.

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
├── windowing.py          # render_to_rgb, wl_from_percentiles, wl_from_dicom
├── colormaps.py          # precomputed uint8 LUT tables
├── dicom_info.py         # curated DICOM header reads for the info overlay
├── image_canvas.py       # ImageCanvas — QPainter renderer, drag W/L, ROI W/L
├── view_cell.py          # ViewCell — one panel: canvas + controls + drag-drop
├── quad_view.py          # QuadView — 2×2 grid, fullscreen toggle, active tracking
├── tree_panel.py         # StudyTreeWidget — lazy filesystem scan, multi-select drag
├── time_course_window.py # ROI time-course panel with plot and point management
├── workspace.py          # annotation workspace: image/list mode discovery, manifest
├── annotation_export.py  # mask / crop / image writers — PNG, JPEG, NIfTI (no Qt)
├── annotation_dock.py    # Workspace dock — job list, brush/polygon/rect tools, export
└── main_window.py        # MainWindow — toolbar, splitter, status bar
```

## Tests

`tests/stability/` holds the headless checks for the annotation workspace: `test_annot.py`
(35-check baseline; run `make_fixtures.sh` first, then `QT_QPA_PLATFORM=offscreen python
tests/stability/test_annot.py` from the `viewer_vidi` env), `test_fixes.py` (44 regression
checks for the 2026-10-27 stability fixes), `shot_annot.py` (offscreen screenshot), and
`scratch/<lens>/` with the scripts of the 14-lens stability review of 2026-10-27
(`REPORT_2026-10-27.md`; status and open items in `TODO.md`).

## Known Issues

- Multi-select drag requires each series to be loaded (double-clicked) individually first before dragging as a group.
- Annotation workspace: the serious findings of the 2026-10-27 stability review are fixed; the
  remaining open items (NIfTI affine orientation, Ctrl+Z focus, GUI-thread export) are in `TODO.md`.
