"""Pure-Python data model. No Qt imports."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import numpy as np


class SeriesType(Enum):
    S2D   = "2D"
    S2DT  = "2D-T"
    S3D   = "3D"
    S3DT  = "3D-T"
    MULTI = "MULTI"


@dataclass
class SeriesMeta:
    study_dir:   str   # absolute path to study folder
    series_dir:  str   # absolute path to series folder
    series_name: str   # folder basename (e.g. "0004_t2_haste_tra_bh_ecg_5mm")
    study_name:  str   # folder basename (e.g. "0000554122_20071214")
    n_files:     int
    series_type:  Optional[SeriesType] = None   # filled after loading
    file_format:  str = "dicom"                 # "dicom" | "nifti" | "image"


@dataclass
class FileEntry:
    path:         str
    instance_num: int
    position:     float   # dot(N, IPP) — slice ordering key
    timepoint:    int     # 0 for S2D/S3D; temporal index for S2DT/S3DT
    orient_group: int     # orientation cluster index (0 for single-orient series)


@dataclass
class SeriesData:
    meta:            SeriesMeta
    series_type:     SeriesType
    file_index:      list[FileEntry]
    window_center:   float
    window_width:    float
    pixel_spacing:   tuple[float, float]   # (row_mm, col_mm)
    slice_spacing:   float                 # mm between slices (0 for 2D)
    n_timepoints:    int                   # 1 for 2D/3D
    n_slices:        int                   # 1 for 2D
    rows:            int
    cols:            int
    wl_from_header:  bool = True           # False → derived from percentiles
    # Orientation info (set by loader from IOP)
    acq_plane:      str  = "AXIAL"        # "AXIAL" | "CORONAL" | "SAGITTAL" | "OBLIQUE"
    flip_acq_rows:  bool = False          # flip acquisition-plane slices vertically
    flip_acq_cols:  bool = False          # flip acquisition-plane slices horizontally
    flip_reformat:  bool = False          # flip Z axis of reformatted (MPR) planes
    panel_labels:   tuple = ("ACQ", "MPR1", "MPR2")  # 3D display panel labels


@dataclass
class GroupedSeriesMeta:
    """Multiple series directories that form one 4D acquisition."""
    study_dir:    str
    study_name:   str
    group_name:   str        # base series name (temporal suffix stripped)
    series_dirs:  list       # sorted list of (series_name, series_path, n_files)
    n_timepoints: int


@dataclass
class VolumeData:
    series_data:  SeriesData
    array:        Optional[np.ndarray] = None   # filled by LoaderWorker
    loaded_mask:  np.ndarray           = field(default_factory=lambda: np.zeros(0, bool))


# ─── Detection helpers ────────────────────────────────────────────────────────

def acq_plane_info(iop: list[float]) -> dict:
    """Derive display orientation metadata from ImageOrientationPatient (6 floats).

    Returns a dict with:
      acq_plane      — "AXIAL" | "CORONAL" | "SAGITTAL" | "OBLIQUE"
      flip_acq_rows  — flip the acquisition plane image vertically
      flip_acq_cols  — flip the acquisition plane image horizontally
      flip_reformat  — flip the Z (slice) axis of MPR reformatted planes
      panel_labels   — tuple(acq_label, mpr1_label, mpr2_label)
    """
    if len(iop) < 6:
        return dict(acq_plane="AXIAL", flip_acq_rows=False, flip_acq_cols=False,
                    flip_reformat=False, panel_labels=("AXIAL", "CORONAL", "SAGITTAL"))

    row_dir = np.array(iop[:3], dtype=np.float64)
    col_dir = np.array(iop[3:], dtype=np.float64)
    normal  = np.cross(row_dir, col_dir)
    nn = np.linalg.norm(normal)
    if nn > 1e-9:
        normal /= nn

    abs_n    = np.abs(normal)
    acq_axis = int(np.argmax(abs_n))  # 0=LR→Sagittal, 1=AP→Coronal, 2=SI→Axial

    if abs_n[acq_axis] < 0.5:
        acq_plane = "OBLIQUE"
        panel_labels = ("ACQ", "MPR1", "MPR2")
    elif acq_axis == 2:
        acq_plane = "AXIAL"
        panel_labels = ("AXIAL", "CORONAL", "SAGITTAL")
    elif acq_axis == 1:
        acq_plane = "CORONAL"
        panel_labels = ("CORONAL", "AXIAL", "SAGITTAL")
    else:
        acq_plane = "SAGITTAL"
        panel_labels = ("SAGITTAL", "AXIAL", "CORONAL")

    # Acquisition plane flip:
    # col_dir tells us the "down" direction in the image.
    # If it points away from the expected anatomical "down", flip rows.
    # AXIAL expected down: posterior (+Y). Flip if col points anterior (col_dir[1] < 0).
    # CORONAL expected down: inferior (−Z). Flip if col points superior (col_dir[2] > 0).
    # SAGITTAL expected down: inferior (−Z). Flip if col points superior (col_dir[2] > 0).
    if acq_plane == "AXIAL":
        flip_acq_rows = bool(col_dir[1] < 0)
    elif acq_plane in ("CORONAL", "SAGITTAL"):
        flip_acq_rows = bool(col_dir[2] > 0)
    else:
        flip_acq_rows = False

    flip_acq_cols = False  # L/R flip is a display convention choice; not applied by default

    # Reformatted-plane flip: slices are sorted by ascending dot(normal, IPP).
    # If normal[acq_axis] > 0, then Z=0 is the "bottom" anatomically
    # (inferior for axial, posterior for coronal) → flip the Z axis of MPR planes.
    flip_reformat = bool(normal[acq_axis] > 0)

    return dict(
        acq_plane=acq_plane,
        flip_acq_rows=flip_acq_rows,
        flip_acq_cols=flip_acq_cols,
        flip_reformat=flip_reformat,
        panel_labels=panel_labels,
    )


def _normal(iop: list[float]) -> np.ndarray:
    row = np.array(iop[:3], dtype=np.float64)
    col = np.array(iop[3:], dtype=np.float64)
    n = np.cross(row, col)
    norm = np.linalg.norm(n)
    return n / norm if norm > 1e-9 else n


def _same_orientation(n1: np.ndarray, n2: np.ndarray, tol: float = 0.05) -> bool:
    return abs(float(np.dot(n1, n2))) > (1.0 - tol)


def detect_series_type(
    headers: list[tuple[str, object]]  # list of (filepath, pydicom_dataset)
) -> tuple[SeriesType, list[FileEntry]]:
    """Classify a series and return (SeriesType, sorted FileEntry list).

    headers: list of (path, ds) where ds was read with stop_before_pixels=True.
    """
    records = []
    for path, ds in headers:
        iop_raw = ds.get("ImageOrientationPatient")
        ipp_raw = ds.get("ImagePositionPatient")
        iop = [float(v) for v in iop_raw] if iop_raw else [1, 0, 0, 0, 1, 0]
        ipp = np.array([float(v) for v in ipp_raw], dtype=np.float64) if ipp_raw else np.zeros(3)
        n   = _normal(iop)
        pos = float(np.dot(n, ipp))
        inst = int(ds.get("InstanceNumber", 0) or 0)
        records.append((path, iop, n, pos, inst))

    # cluster by orientation
    groups: list[list[tuple]] = []
    group_normals: list[np.ndarray] = []
    for rec in records:
        n = rec[2]
        placed = False
        for gi, gn in enumerate(group_normals):
            if _same_orientation(n, gn):
                groups[gi].append(rec)
                placed = True
                break
        if not placed:
            groups.append([rec])
            group_normals.append(n)

    if len(groups) > 1:
        # multi-orientation scout / localizer
        file_entries = []
        for gi, grp in enumerate(groups):
            grp_sorted = sorted(grp, key=lambda r: (r[4], r[3]))
            for rank, rec in enumerate(grp_sorted):
                file_entries.append(FileEntry(
                    path=rec[0], instance_num=rec[4], position=rec[3],
                    timepoint=0, orient_group=gi,
                ))
        return SeriesType.MULTI, file_entries

    # single orientation
    grp = groups[0]
    positions = sorted(set(round(r[3], 2) for r in grp))
    n_locs  = len(positions)
    n_total = len(grp)

    if n_locs == 1 and n_total == 1:
        series_type = SeriesType.S2D
    elif n_locs == 1 and n_total > 1:
        series_type = SeriesType.S2DT
    elif n_locs > 1 and n_total <= n_locs:
        series_type = SeriesType.S3D
    else:
        series_type = SeriesType.S3DT

    # build sorted FileEntry list
    pos_to_idx = {p: i for i, p in enumerate(positions)}
    sorted_by_inst = sorted(grp, key=lambda r: r[4])

    if series_type in (SeriesType.S2D, SeriesType.S3D):
        file_entries = []
        for rec in sorted(grp, key=lambda r: r[3]):
            file_entries.append(FileEntry(
                path=rec[0], instance_num=rec[4], position=rec[3],
                timepoint=0, orient_group=0,
            ))
    elif series_type == SeriesType.S2DT:
        file_entries = []
        for t, rec in enumerate(sorted_by_inst):
            file_entries.append(FileEntry(
                path=rec[0], instance_num=rec[4], position=rec[3],
                timepoint=t, orient_group=0,
            ))
    else:  # S3DT
        n_t = n_total // n_locs
        file_entries = []
        for rank, rec in enumerate(sorted_by_inst):
            t_idx = rank // n_locs
            s_idx = rank %  n_locs
            if t_idx >= n_t:
                continue  # discard incomplete final timepoint
            file_entries.append(FileEntry(
                path=rec[0], instance_num=rec[4], position=rec[3],
                timepoint=t_idx, orient_group=0,
            ))

    return series_type, file_entries


def build_series_data(
    meta: SeriesMeta,
    series_type: SeriesType,
    file_entries: list[FileEntry],
    ds0,             # first pydicom dataset (for spacing / W/L)
    wl: tuple[float, float],
    wl_from_header: bool,
    rows: int,
    cols: int,
) -> SeriesData:
    px_spacing = [1.0, 1.0]
    if hasattr(ds0, "PixelSpacing") and ds0.PixelSpacing:
        px_spacing = [float(ds0.PixelSpacing[0]), float(ds0.PixelSpacing[1])]
    elif hasattr(ds0, "ImagerPixelSpacing") and ds0.ImagerPixelSpacing:
        px_spacing = [float(ds0.ImagerPixelSpacing[0]), float(ds0.ImagerPixelSpacing[1])]

    slice_spacing = 0.0
    positions = sorted(set(e.position for e in file_entries))
    if len(positions) > 1:
        diffs = [abs(positions[i+1] - positions[i]) for i in range(len(positions)-1)]
        slice_spacing = float(np.median(diffs))

    n_slices = len(positions) if series_type in (SeriesType.S3D, SeriesType.S3DT) else 1
    timepoints = sorted(set(e.timepoint for e in file_entries))
    n_timepoints = len(timepoints)

    iop_raw = ds0.get("ImageOrientationPatient")
    iop = [float(v) for v in iop_raw] if iop_raw else [1,0,0,0,1,0]
    plane_info = acq_plane_info(iop)

    return SeriesData(
        meta=meta,
        series_type=series_type,
        file_index=file_entries,
        window_center=wl[0],
        window_width=wl[1],
        pixel_spacing=(px_spacing[0], px_spacing[1]),
        slice_spacing=slice_spacing,
        n_timepoints=n_timepoints,
        n_slices=n_slices,
        rows=rows,
        cols=cols,
        wl_from_header=wl_from_header,
        acq_plane=plane_info["acq_plane"],
        flip_acq_rows=plane_info["flip_acq_rows"],
        flip_acq_cols=plane_info["flip_acq_cols"],
        flip_reformat=plane_info["flip_reformat"],
        panel_labels=plane_info["panel_labels"],
    )
