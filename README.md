# viewer-vidi

A lightweight, multi-format scientific image viewer built for research workflows.
Supports DICOM, NIfTI, and common raster formats (PNG, JPEG, BMP, TIFF) in a single
four-panel workspace.

## Run

```bash
cd /media/zsk/ressd/research
python -m viewer_vidi
```

## Features

### Formats
| Format | Extensions | Notes |
|---|---|---|
| DICOM | `.dcm` | Full header parsing, RescaleSlope/Intercept, multi-frame |
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
- **Slice slider** (right edge) — scrub through slices
- **Time bar** (bottom, hidden for static data) — play/pause, frame scrubbing, FPS control

### Window / Level
| Mode | How to activate | Interaction |
|---|---|---|
| **Drag W/L** | default | Left-drag on image: horizontal → width, vertical → center |
| **ROI W/L** | click **ROI** button in panel header | Drag a rectangle; W/L is set from the p2–p98 range of pixels inside it |

### Multi-series time series (3D-T / 2D-T)
1. Expand a study in the left panel and **double-click each series** to load it first
2. Shift-click or Ctrl-click to select multiple series in the tree
3. Drag the selection into any panel — they load as a time series (2D-T or 3D-T)

> **Note:** Series must be loaded (double-clicked) before multi-select drag is available.
> This is a known limitation of the QFileSystemModel lazy-loading approach.

## Dependencies

```
pydicom >= 3.0
PyQt5 >= 5.15
numpy
Pillow          # for PNG/JPEG/BMP/TIFF
nibabel         # for NIfTI (.nii / .nii.gz)
```

Install missing dependencies:

```bash
pip install nibabel Pillow
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
├── image_canvas.py       # ImageCanvas — QPainter renderer, drag W/L, ROI W/L
├── view_cell.py          # ViewCell — one panel: canvas + controls + drag-drop
├── quad_view.py          # QuadView — 2×2 grid, fullscreen toggle, active tracking
├── tree_panel.py         # StudyTreeWidget — lazy filesystem scan, multi-select drag
├── time_course_window.py # ROI time-course panel with plot and point management
└── main_window.py        # MainWindow — toolbar, splitter, status bar
```

## Known Issues

- Multi-select drag requires each series to be loaded (double-clicked) individually first before dragging as a group.
- ROI time-course "Clear points" button is not yet functional (fix pending).
