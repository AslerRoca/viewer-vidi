"""Background loader: DICOM, NIfTI, and raster image series."""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pydicom

from PyQt5.QtCore import QThread, pyqtSignal

from .data_model import (
    SeriesMeta, SeriesData, SeriesType, VolumeData,
    GroupedSeriesMeta, detect_series_type, build_series_data,
)
from .windowing import wl_from_dicom, wl_from_percentiles, apply_rescale

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"})
_NIFTI_EXTS = (".nii.gz", ".nii")


def set_unique_z(entries):
    """Return one FileEntry per unique position (deduplicate timepoints)."""
    seen = {}
    for e in entries:
        key = round(e.position, 2)
        if key not in seen:
            seen[key] = e
    return list(seen.values())


def _make_plain_sd(meta: SeriesMeta, stype: SeriesType,
                   rows: int, cols: int, n_z: int, n_t: int,
                   wc: float, ww: float,
                   pixel_spacing=(1.0, 1.0), slice_spacing=1.0) -> SeriesData:
    """Build a minimal SeriesData for non-DICOM series."""
    return SeriesData(
        meta=meta,
        series_type=stype,
        file_index=[],
        window_center=wc,
        window_width=ww,
        pixel_spacing=pixel_spacing,
        slice_spacing=slice_spacing,
        n_timepoints=n_t,
        n_slices=n_z,
        rows=rows,
        cols=cols,
        wl_from_header=False,
        acq_plane="AXIAL",
        flip_acq_rows=False,
        flip_acq_cols=False,
        flip_reformat=False,
        panel_labels=("AXIAL", "CORONAL", "SAGITTAL"),
    )


class LoaderWorker(QThread):
    """Two-phase loader: headers first, then pixels timepoint by timepoint."""

    headers_ready  = pyqtSignal(object)        # SeriesData
    pixels_ready   = pyqtSignal(int, object)   # (timepoint_idx, np.ndarray)
    load_complete  = pyqtSignal()
    load_error     = pyqtSignal(str)
    progress       = pyqtSignal(int, int)      # (loaded, total)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel  = threading.Event()
        self._meta    = None
        self._grouped = False

    def request_load(self, meta) -> None:
        self._cancel.set()
        self.wait()
        self._cancel.clear()
        self._meta    = meta
        self._grouped = isinstance(meta, GroupedSeriesMeta)
        self.start()

    def cancel(self) -> None:
        self._cancel.set()
        self.wait()

    # ── dispatcher ────────────────────────────────────────────────────────────

    def run(self) -> None:
        meta = self._meta
        if meta is None:
            return
        try:
            if self._grouped:
                self._run_grouped_load(meta)
            else:
                fmt = getattr(meta, "file_format", "dicom")
                if fmt == "nifti":
                    self._run_nifti_load(meta)
                elif fmt == "image":
                    self._run_image_load(meta)
                else:
                    self._run_dicom_load(meta)
        except Exception as exc:
            if not self._cancel.is_set():
                self.load_error.emit(str(exc))

    # ── DICOM single-series ───────────────────────────────────────────────────

    def _dcm_files(self, directory: str) -> list[str]:
        if os.path.isfile(directory):
            return [directory]
        return sorted(
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.lower().endswith(".dcm")
        )

    def _parallel_read_headers(self, paths: list[str]) -> list[tuple[str, object]]:
        """Read DICOM headers in parallel using defer_size so pixel data stays lazy."""
        if not paths:
            return []
        n = len(paths)
        n_workers = min(8, n)
        results: dict[str, object] = {}
        done = 0

        def _read_one(path: str):
            try:
                # defer_size=256: all small metadata tags parsed eagerly;
                # PixelData (always >> 256 bytes) stays on-disk until accessed.
                return path, pydicom.dcmread(path, defer_size=256)
            except Exception:
                return path, None

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = {pool.submit(_read_one, p): p for p in paths}
            for fut in as_completed(futures):
                if self._cancel.is_set():
                    break
                path, ds = fut.result()
                if ds is not None:
                    results[path] = ds
                done += 1
                self.progress.emit(done, n)

        if self._cancel.is_set():
            return []
        return [(p, results[p]) for p in paths if p in results]

    def _parallel_read_slices(self, entries, rows: int, cols: int,
                               ds_cache: dict | None = None) -> dict[int, np.ndarray]:
        """Read a batch of slices concurrently. Returns {list_index: array}."""
        n = len(entries)
        if n == 0:
            return {}
        n_workers = min(8, n)
        results: dict[int, np.ndarray] = {}

        def _read(args):
            zi, fe = args
            if self._cancel.is_set():
                return zi, None
            path = fe.path
            if ds_cache and path in ds_cache:
                return zi, self._read_slice_from_ds(ds_cache[path], rows, cols)
            return zi, self._read_slice(path, rows, cols)

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            for zi, sl in pool.map(_read, enumerate(entries)):
                if self._cancel.is_set():
                    return {}
                if sl is not None:
                    results[zi] = sl

        return results

    def _read_slice_from_ds(self, ds, rows: int, cols: int) -> np.ndarray:
        """Extract pixel array from an already-parsed (possibly deferred) ds.

        When ds was read with defer_size, accessing pixel_array triggers a
        targeted disk seek to the PixelData offset — no header re-parsing.
        """
        try:
            raw = ds.pixel_array
            arr = apply_rescale(raw, ds)
            if arr.shape != (rows, cols):
                out = np.zeros((rows, cols), dtype=np.float32)
                h = min(rows, arr.shape[0])
                w = min(cols, arr.shape[1])
                out[:h, :w] = arr[:h, :w]
                return out
            return arr
        except Exception:
            return np.zeros((rows, cols), dtype=np.float32)

    def _run_dicom_load(self, meta: SeriesMeta) -> None:
        files = self._dcm_files(meta.series_dir)
        if not files:
            self.load_error.emit(f"No .dcm files in {meta.series_dir}")
            return

        # Parallel header read; pixel data stays deferred on disk
        headers = self._parallel_read_headers(files)
        if self._cancel.is_set():
            return
        if not headers:
            self.load_error.emit("Could not read any DICOM headers.")
            return

        # Keep the parsed ds objects so phase 2 can reuse them (no re-parse)
        ds_cache = {path: ds for path, ds in headers}

        series_type, file_entries = detect_series_type(headers)
        meta.series_type = series_type

        ds0 = headers[0][1]
        wc, ww = wl_from_dicom(ds0)
        wl_from_hdr = wc is not None
        rows = int(ds0.get("Rows", 0) or 0)
        cols = int(ds0.get("Columns", 0) or 0)
        if not wl_from_hdr:
            wc, ww = 2048.0, 4096.0

        series_data = build_series_data(
            meta=meta,
            series_type=series_type,
            file_entries=file_entries,
            ds0=ds0,
            wl=(wc, ww),
            wl_from_header=wl_from_hdr,
            rows=rows,
            cols=cols,
        )

        if self._cancel.is_set():
            return
        self.headers_ready.emit(series_data)
        self._load_pixels(series_data, ds_cache)

    def _load_pixels(self, sd: SeriesData,
                     ds_cache: dict | None = None) -> None:
        from collections import defaultdict
        stype = sd.series_type
        rows, cols = sd.rows, sd.cols
        n_t = sd.n_timepoints
        n_z = sd.n_slices

        by_t: dict[int, list] = defaultdict(list)
        for fe in sd.file_index:
            by_t[fe.timepoint].append(fe)
        for t in by_t:
            by_t[t].sort(key=lambda e: e.position)

        def read_sl(path: str) -> np.ndarray:
            if ds_cache and path in ds_cache:
                # Reuse cached ds: pixel data loaded via a targeted seek, no
                # header re-parsing (defer_size kept the ds alive in memory).
                return self._read_slice_from_ds(ds_cache[path], rows, cols)
            return self._read_slice(path, rows, cols)

        if stype == SeriesType.S2D:
            arr = read_sl(by_t[0][0].path)
            if not sd.wl_from_header:
                sd.window_center, sd.window_width = wl_from_percentiles(arr)
            self.pixels_ready.emit(0, arr)

        elif stype == SeriesType.S2DT:
            n_frames = len(sd.file_index)
            arr = np.zeros((n_frames, rows, cols), dtype=np.float32)
            sorted_fes = sorted(sd.file_index, key=lambda fe: fe.timepoint)
            slices = self._parallel_read_slices(sorted_fes, rows, cols, ds_cache)
            if self._cancel.is_set():
                return
            for i, sl in slices.items():
                arr[sorted_fes[i].timepoint] = sl
            if not sd.wl_from_header:
                sd.window_center, sd.window_width = wl_from_percentiles(arr[0])
            self.pixels_ready.emit(0, arr)

        elif stype == SeriesType.S3D:
            arr = np.zeros((n_z, rows, cols), dtype=np.float32)
            slices = self._parallel_read_slices(by_t[0], rows, cols, ds_cache)
            if self._cancel.is_set():
                return
            for zi, sl in slices.items():
                arr[zi] = sl
            if not sd.wl_from_header:
                sd.window_center, sd.window_width = wl_from_percentiles(arr[n_z // 2])
            self.pixels_ready.emit(0, arr)

        elif stype == SeriesType.S3DT:
            full_arr = np.zeros((n_t, n_z, rows, cols), dtype=np.float32)
            for t in range(n_t):
                if self._cancel.is_set():
                    return
                slices = self._parallel_read_slices(
                    by_t.get(t, [])[:n_z], rows, cols, ds_cache)
                if self._cancel.is_set():
                    return
                for zi, sl in slices.items():
                    full_arr[t, zi] = sl
                if t == 0 and not sd.wl_from_header:
                    mid = n_z // 2
                    sd.window_center, sd.window_width = wl_from_percentiles(full_arr[0, mid])
                self.pixels_ready.emit(t, full_arr)

        elif stype == SeriesType.MULTI:
            from collections import defaultdict as _dd
            by_group: dict[int, list] = _dd(list)
            for fe in sd.file_index:
                by_group[fe.orient_group].append(fe)
            frames = [read_sl(by_group[gi][0].path) for gi in sorted(by_group)]
            arr = np.stack(frames, axis=0)
            if not sd.wl_from_header:
                sd.window_center, sd.window_width = wl_from_percentiles(arr[0])
            self.pixels_ready.emit(0, arr)

        if not self._cancel.is_set():
            self.load_complete.emit()

    def _read_slice(self, path: str, rows: int, cols: int) -> np.ndarray:
        try:
            ds = pydicom.dcmread(path)
            raw = ds.pixel_array
            arr = apply_rescale(raw, ds)
            if arr.shape != (rows, cols):
                out = np.zeros((rows, cols), dtype=np.float32)
                h = min(rows, arr.shape[0])
                w = min(cols, arr.shape[1])
                out[:h, :w] = arr[:h, :w]
                return out
            return arr
        except Exception:
            return np.zeros((rows, cols), dtype=np.float32)

    # ── NIfTI single-file ─────────────────────────────────────────────────────

    def _run_nifti_load(self, meta: SeriesMeta) -> None:
        try:
            import nibabel as nib
        except ImportError:
            self.load_error.emit("nibabel not installed — run: pip install nibabel")
            return

        try:
            img = nib.load(meta.series_dir)
        except Exception as e:
            self.load_error.emit(f"Failed to load NIfTI: {e}")
            return

        data = np.asarray(img.dataobj, dtype=np.float32)
        ndim = data.ndim

        if ndim == 2:
            stype = SeriesType.S2D
            arr   = data                                   # (H, W)
            H, W  = arr.shape
            n_z, n_t = 1, 1
        elif ndim == 3:
            stype = SeriesType.S3D
            arr   = np.transpose(data, (2, 1, 0))          # (Z, Y, X)
            n_z, H, W = arr.shape
            n_t = 1
        elif ndim == 4:
            stype = SeriesType.S3DT
            arr   = np.transpose(data, (3, 2, 1, 0))       # (T, Z, Y, X)
            n_t, n_z, H, W = arr.shape
        else:
            self.load_error.emit(f"Unsupported NIfTI shape: {data.shape}")
            return

        # Spacing from header
        try:
            zooms = img.header.get_zooms()
            px_row = float(zooms[0]) if len(zooms) > 0 else 1.0
            px_col = float(zooms[1]) if len(zooms) > 1 else 1.0
            sl_sp  = float(zooms[2]) if len(zooms) > 2 else 1.0
        except Exception:
            px_row = px_col = sl_sp = 1.0

        sample = arr.ravel()[::max(1, arr.size // 10000)]
        wc, ww = wl_from_percentiles(sample)
        meta.series_type = stype

        sd = _make_plain_sd(meta, stype, rows=H, cols=W, n_z=n_z, n_t=n_t,
                            wc=wc, ww=ww,
                            pixel_spacing=(px_row, px_col), slice_spacing=sl_sp)

        if self._cancel.is_set():
            return
        self.headers_ready.emit(sd)

        if stype == SeriesType.S3DT:
            for t in range(n_t):
                if self._cancel.is_set():
                    return
                self.pixels_ready.emit(t, arr)
                self.progress.emit(t + 1, n_t)
        else:
            self.pixels_ready.emit(0, arr)

        if not self._cancel.is_set():
            self.load_complete.emit()

    # ── Image (PNG/JPEG/…) directory ──────────────────────────────────────────

    def _run_image_load(self, meta: SeriesMeta) -> None:
        try:
            from PIL import Image as PILImage
        except ImportError:
            self.load_error.emit("Pillow not installed — run: pip install Pillow")
            return

        path = meta.series_dir
        if os.path.isfile(path):
            files = [path]
        elif os.path.isdir(path):
            files = sorted(
                os.path.join(path, f) for f in os.listdir(path)
                if os.path.splitext(f.lower())[1] in _IMAGE_EXTS
            )
        else:
            self.load_error.emit(f"Path not found: {path}")
            return

        if not files:
            self.load_error.emit("No image files found.")
            return

        try:
            arr0 = _pil_to_float(PILImage.open(files[0]))
        except Exception as e:
            self.load_error.emit(f"Failed to open image: {e}")
            return

        H, W  = arr0.shape
        n_t   = len(files)
        stype = SeriesType.S2DT if n_t > 1 else SeriesType.S2D

        sample = arr0.ravel()[::max(1, arr0.size // 5000)]
        wc, ww = wl_from_percentiles(sample)
        meta.series_type = stype

        sd = _make_plain_sd(meta, stype, rows=H, cols=W, n_z=1, n_t=n_t,
                            wc=wc, ww=ww, pixel_spacing=(1.0, 1.0), slice_spacing=0.0)

        if self._cancel.is_set():
            return
        self.headers_ready.emit(sd)

        if stype == SeriesType.S2D:
            self.pixels_ready.emit(0, arr0)
        else:
            full = np.zeros((n_t, H, W), dtype=np.float32)
            full[0] = arr0
            for i in range(1, n_t):
                if self._cancel.is_set():
                    return
                try:
                    arr = _pil_to_float(PILImage.open(files[i]))
                    fh, fw = min(H, arr.shape[0]), min(W, arr.shape[1])
                    full[i, :fh, :fw] = arr[:fh, :fw]
                except Exception:
                    pass
                self.progress.emit(i + 1, n_t)
            self.pixels_ready.emit(0, full)

        if not self._cancel.is_set():
            self.load_complete.emit()

    # ── Grouped (multi-select drag → 4D or 2D-T) ─────────────────────────────

    def _run_grouped_load(self, gmeta: GroupedSeriesMeta) -> None:
        members = gmeta.series_dirs   # list[SeriesMeta]
        n_t = len(members)
        fmt = getattr(members[0], "file_format", "dicom")

        if fmt == "dicom":
            self._run_grouped_dicom(gmeta, members)
        else:
            self._run_grouped_generic(gmeta, members)

    def _run_flat_2dt(self, gmeta, members) -> None:
        """Load N individual flat DICOM files as a 2D-T series."""
        n_t = len(members)
        headers0 = self._parallel_read_headers([members[0].series_dir])
        if not headers0:
            self.load_error.emit("Could not read first DICOM file.")
            return
        ds0      = headers0[0][1]
        rows     = int(ds0.get("Rows", 0) or 0)
        cols     = int(ds0.get("Columns", 0) or 0)
        wc, ww   = wl_from_dicom(ds0)
        wl_hdr   = wc is not None
        if not wl_hdr:
            wc, ww = 2048.0, 4096.0

        dummy = SeriesMeta(
            study_dir=gmeta.study_dir, series_dir=members[0].series_dir,
            series_name=gmeta.group_name, study_name=gmeta.study_name,
            n_files=n_t, series_type=SeriesType.S2DT,
        )
        sd = _make_plain_sd(dummy, SeriesType.S2DT, rows=rows, cols=cols,
                            n_z=1, n_t=n_t, wc=wc, ww=ww)
        sd.wl_from_header = wl_hdr

        if self._cancel.is_set():
            return
        self.headers_ready.emit(sd)

        full = np.zeros((n_t, rows, cols), dtype=np.float32)
        full[0] = self._read_slice_from_ds(headers0[0][1], rows, cols)
        for t in range(1, n_t):
            if self._cancel.is_set():
                return
            full[t] = self._read_slice(members[t].series_dir, rows, cols)
            self.progress.emit(t + 1, n_t)

        if not wl_hdr:
            sd.window_center, sd.window_width = wl_from_percentiles(full[0])
        self.pixels_ready.emit(0, full)

    def _run_grouped_dicom(self, gmeta, members) -> None:
        """Grouped DICOM load: each member is one 3D timepoint directory."""
        # Flat individual files → 2D-T
        if all(os.path.isfile(m.series_dir) for m in members):
            self._run_flat_2dt(gmeta, members)
            return
        from .data_model import acq_plane_info
        n_t = len(members)

        # ── First member: parallel header read ────────────────────────────────
        first_dir   = members[0].series_dir
        first_files = self._dcm_files(first_dir)
        if not first_files:
            self.load_error.emit(f"No DICOM files in {first_dir}")
            return

        first_headers = self._parallel_read_headers(first_files)
        if self._cancel.is_set() or not first_headers:
            self.load_error.emit("Could not read headers from first series.")
            return

        ds_cache_0 = {p: ds for p, ds in first_headers}
        _, file_entries_t0 = detect_series_type(first_headers)
        ds0 = first_headers[0][1]
        rows = int(ds0.get("Rows", 0) or 0)
        cols = int(ds0.get("Columns", 0) or 0)
        wc, ww = wl_from_dicom(ds0)
        wl_from_hdr = wc is not None
        if not wl_from_hdr:
            wc, ww = 2048.0, 4096.0

        positions = sorted(set(round(fe.position, 2) for fe in file_entries_t0))
        n_z = len(positions)

        dummy_meta = SeriesMeta(
            study_dir=gmeta.study_dir,
            series_dir=first_dir,
            series_name=gmeta.group_name,
            study_name=gmeta.study_name,
            n_files=sum(getattr(m, "n_files", 0) for m in members),
            series_type=SeriesType.S3DT,
        )

        iop_raw = ds0.get("ImageOrientationPatient")
        iop = [float(v) for v in iop_raw] if iop_raw else [1, 0, 0, 0, 1, 0]
        plane_info = acq_plane_info(iop)

        px_spacing = [1.0, 1.0]
        if hasattr(ds0, "PixelSpacing") and ds0.PixelSpacing:
            px_spacing = [float(ds0.PixelSpacing[0]), float(ds0.PixelSpacing[1])]

        pos_vals = sorted(set(fe.position for fe in file_entries_t0))
        slice_spacing = 0.0
        if len(pos_vals) > 1:
            diffs = [abs(pos_vals[i+1] - pos_vals[i]) for i in range(len(pos_vals)-1)]
            slice_spacing = float(np.median(diffs))

        sd = SeriesData(
            meta=dummy_meta,
            series_type=SeriesType.S3DT,
            file_index=file_entries_t0,
            window_center=wc,
            window_width=ww,
            pixel_spacing=(px_spacing[0], px_spacing[1]),
            slice_spacing=slice_spacing,
            n_timepoints=n_t,
            n_slices=n_z,
            rows=rows,
            cols=cols,
            wl_from_header=wl_from_hdr,
            acq_plane=plane_info["acq_plane"],
            flip_acq_rows=plane_info["flip_acq_rows"],
            flip_acq_cols=plane_info["flip_acq_cols"],
            flip_reformat=plane_info["flip_reformat"],
            panel_labels=plane_info["panel_labels"],
        )
        dummy_meta.series_type = SeriesType.S3DT

        if self._cancel.is_set():
            return
        self.headers_ready.emit(sd)

        # ── Pixel loading: reuse cached ds for t=0, parallel read for t>0 ────
        full_arr = np.zeros((n_t, n_z, rows, cols), dtype=np.float32)
        for t, smeta in enumerate(members):
            if self._cancel.is_set():
                return

            if t == 0:
                entries_sorted = sorted(set_unique_z(file_entries_t0), key=lambda e: e.position)
                for zi, fe in enumerate(entries_sorted[:n_z]):
                    if self._cancel.is_set():
                        return
                    full_arr[0, zi] = self._read_slice_from_ds(
                        ds_cache_0[fe.path], rows, cols) if fe.path in ds_cache_0 \
                        else self._read_slice(fe.path, rows, cols)
                if not wl_from_hdr:
                    wc2, ww2 = wl_from_percentiles(full_arr[0, n_z // 2])
                    sd.window_center, sd.window_width = wc2, ww2
            else:
                files_t = self._dcm_files(smeta.series_dir)
                recs_t = self._parallel_read_headers(files_t)
                if self._cancel.is_set():
                    return
                _, entries_t = detect_series_type(recs_t)
                entries_sorted = sorted(set_unique_z(entries_t), key=lambda e: e.position)
                ds_cache_t = {p: ds for p, ds in recs_t}
                for zi, fe in enumerate(entries_sorted[:n_z]):
                    if self._cancel.is_set():
                        return
                    full_arr[t, zi] = self._read_slice_from_ds(
                        ds_cache_t[fe.path], rows, cols) if fe.path in ds_cache_t \
                        else self._read_slice(fe.path, rows, cols)

            self.progress.emit(t + 1, n_t)
            self.pixels_ready.emit(t, full_arr)

        if not self._cancel.is_set():
            self.load_complete.emit()

    def _run_grouped_generic(self, gmeta, members) -> None:
        """Grouped load for NIfTI or image members."""
        n_t = len(members)

        # Load first frame to determine shape and type
        first_vol = self._load_one_volume(members[0])
        if first_vol is None:
            self.load_error.emit("Could not load first member of group.")
            return

        is_3d = first_vol.ndim == 3
        if is_3d:
            n_z, H, W = first_vol.shape
            stype = SeriesType.S3DT
        else:
            H, W = first_vol.shape
            n_z = 1
            stype = SeriesType.S2DT

        sample = first_vol.ravel()[::max(1, first_vol.size // 5000)]
        wc, ww = wl_from_percentiles(sample)

        dummy_meta = SeriesMeta(
            study_dir=gmeta.study_dir,
            series_dir=members[0].series_dir,
            series_name=gmeta.group_name,
            study_name=gmeta.study_name,
            n_files=sum(getattr(m, "n_files", 1) for m in members),
            series_type=stype,
        )

        sd = _make_plain_sd(dummy_meta, stype, rows=H, cols=W,
                            n_z=n_z, n_t=n_t, wc=wc, ww=ww)
        dummy_meta.series_type = stype

        if self._cancel.is_set():
            return
        self.headers_ready.emit(sd)

        if is_3d:
            full_arr = np.zeros((n_t, n_z, H, W), dtype=np.float32)
            full_arr[0] = _fit(first_vol, (n_z, H, W))
            self.pixels_ready.emit(0, full_arr)
            for t in range(1, n_t):
                if self._cancel.is_set():
                    return
                vol = self._load_one_volume(members[t])
                if vol is not None and vol.ndim == 3:
                    full_arr[t] = _fit(vol, (n_z, H, W))
                self.progress.emit(t + 1, n_t)
                self.pixels_ready.emit(t, full_arr)
        else:
            full_arr = np.zeros((n_t, H, W), dtype=np.float32)
            full_arr[0] = _fit(first_vol, (H, W))
            for t in range(1, n_t):
                if self._cancel.is_set():
                    return
                vol = self._load_one_volume(members[t])
                if vol is not None and vol.ndim == 2:
                    full_arr[t] = _fit(vol, (H, W))
                self.progress.emit(t + 1, n_t)
            self.pixels_ready.emit(0, full_arr)

        if not self._cancel.is_set():
            self.load_complete.emit()

    def _load_one_volume(self, smeta: SeriesMeta) -> np.ndarray | None:
        """Load one member as a 2D (H,W) or 3D (Z,H,W) float32 array."""
        fmt = getattr(smeta, "file_format", "dicom")
        path = smeta.series_dir

        if fmt == "nifti":
            try:
                import nibabel as nib
                img  = nib.load(path)
                data = np.asarray(img.dataobj, dtype=np.float32)
                if data.ndim == 2:
                    return data
                if data.ndim == 3:
                    return np.transpose(data, (2, 1, 0))    # (Z, Y, X)
                if data.ndim >= 4:
                    return np.transpose(data[..., 0], (2, 1, 0))
            except Exception:
                return None

        elif fmt == "image":
            try:
                from PIL import Image as PILImage
                if os.path.isfile(path):
                    fp = path
                else:
                    candidates = sorted(
                        f for f in os.listdir(path)
                        if os.path.splitext(f.lower())[1] in _IMAGE_EXTS
                    )
                    if not candidates:
                        return None
                    fp = os.path.join(path, candidates[0])
                return _pil_to_float(PILImage.open(fp))
            except Exception:
                return None

        else:  # dicom
            files = self._dcm_files(path)
            if not files:
                return None
            headers = []
            for p in files:
                if self._cancel.is_set():
                    return None
                try:
                    ds = pydicom.dcmread(p, stop_before_pixels=True)
                    headers.append((p, ds))
                except Exception:
                    pass
            if not headers:
                return None
            _, entries = detect_series_type(headers)
            entries = sorted(set_unique_z(entries), key=lambda e: e.position)
            ds0 = headers[0][1]
            rows = int(ds0.get("Rows", 0) or 0)
            cols = int(ds0.get("Columns", 0) or 0)
            arr = np.zeros((len(entries), rows, cols), dtype=np.float32)
            for zi, fe in enumerate(entries):
                if self._cancel.is_set():
                    return None
                arr[zi] = self._read_slice(fe.path, rows, cols)
            return arr


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pil_to_float(img) -> np.ndarray:
    """Convert a PIL Image to a float32 (H, W) grayscale array."""
    if img.mode in ("RGB", "RGBA", "P"):
        img = img.convert("L")
    return np.array(img, dtype=np.float32)


def _fit(src: np.ndarray, shape: tuple) -> np.ndarray:
    """Crop/pad src to exactly match shape (no rescaling)."""
    out = np.zeros(shape, dtype=np.float32)
    slices_src = tuple(slice(0, min(s, d)) for s, d in zip(src.shape, shape))
    slices_dst = tuple(slice(0, min(s, d)) for s, d in zip(src.shape, shape))
    out[slices_dst] = src[slices_src]
    return out
