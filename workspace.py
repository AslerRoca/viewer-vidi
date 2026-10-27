"""Annotation workspace: item discovery, list parsing and the output manifest.

Pure Python, no Qt (same convention as data_model.py / dicom_info.py).

A workspace is one directory the user picks. Two modes decide where the
items come from:

  image mode — the directory holds the images themselves; every DICOM, NIfTI
               or raster file below it (recursively) is one item
  list mode  — a text/CSV file lists the image paths, one per line (absolute,
               or relative to the list file); only the list is needed to start

Outputs land in <workspace>/<out_dir_name>/<format>/ and every saved item is
recorded in <workspace>/<out_dir_name>/manifest.csv, which is also how a
reopened workspace knows which items are already done. Rows are matched to
items by their *source* path (relative to the workspace when inside it), so
done flags follow the file, not the output stem.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime

from .dicom_sniff import is_dicom_file, list_dicom_files

IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"})
NIFTI_EXTS = (".nii.gz", ".nii")
LIST_EXTS  = frozenset({".txt", ".lst", ".csv", ".tsv"})

DEFAULT_OUT_DIR = "vidi_output"
MANIFEST_NAME   = "manifest.csv"
MANIFEST_FIELDS = ("stem", "source", "status", "saved_at", "view", "mask_pixels",
                   "x0", "y0", "x1", "y1", "formats", "files")
STATUS_SAVED    = "saved"
STATUS_DELETED  = "deleted"          # the image was marked wrong; no products on disk
FILES_SEP       = ";"                 # separator of the manifest 'files' column

MAX_LIST_BYTES  = 20 * 1024 * 1024    # larger text files are never treated as lists
MAX_STEM_LEN    = 96                  # longer stems are shortened with a hash tail

# Column names that mark a header row in a list file (case-insensitive).
_PATH_HEADERS = ("path", "file", "filename", "filepath", "image", "img", "dicom")


@dataclass
class Item:
    path: str
    stem: str
    done: bool = False
    deleted: bool = False    # marked as a wrong picture (the file itself is kept)
    error: str = ""          # set when the viewer could not open the file


@dataclass
class Workspace:
    root: str
    mode: str                       # "image" | "list"
    items: list[Item] = field(default_factory=list)
    out_dir_name: str = DEFAULT_OUT_DIR
    list_file: str | None = None
    missing: list[str] = field(default_factory=list)   # list entries not found
    manifest_warning: str = ""                          # manifest present but unreadable

    @property
    def out_dir(self) -> str:
        return os.path.join(self.root, self.out_dir_name)

    @property
    def manifest_path(self) -> str:
        return os.path.join(self.out_dir, MANIFEST_NAME)

    @property
    def n_done(self) -> int:
        return sum(1 for it in self.items if it.done)

    @property
    def n_deleted(self) -> int:
        return sum(1 for it in self.items if it.deleted)

    @property
    def n_pending(self) -> int:
        return sum(1 for it in self.items if not it.done and not it.deleted)


# ── File classification ──────────────────────────────────────────────────────

def file_stem(path: str) -> str:
    """Basename without extension; '.nii.gz' is stripped as one extension."""
    name = os.path.basename(path.rstrip(os.sep))
    if name.lower().endswith(".nii.gz"):
        return name[:-7]
    return os.path.splitext(name)[0]


def is_image_path(path: str) -> bool:
    """True for an existing DICOM / NIfTI / raster *file* (never a bare name)."""
    if not os.path.isfile(path):
        return False
    low = path.lower()
    if low.endswith(NIFTI_EXTS) or os.path.splitext(low)[1] in IMAGE_EXTS:
        return True
    return is_dicom_file(path)


def is_loadable(path: str) -> bool:
    """An image file, or a directory holding a DICOM series (the viewer opens both)."""
    if os.path.isdir(path):
        return bool(list_dicom_files(path))
    return is_image_path(path)


def scan_images(root: str, skip_dirs: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """All image files below *root*, sorted. Skipped: hidden dirs, the
    top-level dirs named in *skip_dirs* (the output dir — only directly
    under root, so a source subfolder with the same name is still scanned)
    and any directory holding a manifest.csv (an output dir, whatever it is
    called now)."""
    root = os.path.abspath(root)
    skip_names = {os.path.normpath(d) for d in skip_dirs if d}
    skip_paths = {os.path.normpath(os.path.join(root, d)) for d in skip_names}
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".")
            and os.path.normpath(os.path.join(dirpath, d)) not in skip_paths
            and not looks_like_output_dir(os.path.join(dirpath, d), d in skip_names))
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            p = os.path.join(dirpath, fn)
            if is_image_path(p):
                found.append(p)
    return found


def looks_like_output_dir(path: str, named_like_out: bool = False) -> bool:
    """A directory the exporter wrote: it holds a manifest.csv, or it carries
    the output dir's name and has a png/jpeg/nifti subfolder (a product tree
    whose manifest write failed). A source folder that merely shares the
    name keeps its images."""
    if os.path.isfile(os.path.join(path, MANIFEST_NAME)):
        return True
    if named_like_out:
        return any(os.path.isdir(os.path.join(path, f)) for f in ("png", "jpeg", "nifti"))
    return False


# ── List files ───────────────────────────────────────────────────────────────

def _read_text(path: str) -> str:
    """Decode a text file leniently: UTF-16 by BOM, else UTF-8 (BOM stripped,
    bad bytes replaced); embedded NULs are dropped so csv never chokes."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    return text.replace("\x00", "")


def parse_list_file(path: str) -> list[str]:
    """Image paths named in a .txt/.lst/.csv/.tsv list, resolved to absolute.

    One entry per line; blank lines and '#' comments are skipped. CSV/TSV
    rows use the column headed path/file/filename/… when there is a header,
    else the first column. Relative entries resolve against the list's dir.
    Entries are returned whether or not the file exists — the caller decides.
    Never raises on odd content (NUL bytes, huge fields, bad encodings).
    """
    ext = os.path.splitext(path)[1].lower()
    delim = {".csv": ",", ".tsv": "\t"}.get(ext)
    base = os.path.dirname(os.path.abspath(path))

    try:
        if os.path.getsize(path) > MAX_LIST_BYTES:
            return []
        text = _read_text(path)
    except OSError:
        return []

    rows: list[list[str]] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if delim:
            try:
                rows.append(next(csv.reader([ln], delimiter=delim)))
            except csv.Error:
                rows.append(ln.split(delim))
        else:
            rows.append([s])
    if not rows:
        return []

    col = 0
    first = [c.strip().lower() for c in rows[0]]
    header_idx = next((i for i, c in enumerate(first) if c in _PATH_HEADERS), None)
    if header_idx is not None:
        col, rows = header_idx, rows[1:]
    elif delim and len(rows) > 1 and _looks_like_header(rows[0][0].strip(), base):
        rows = rows[1:]

    out: list[str] = []
    for r in rows:
        if col >= len(r):
            continue
        cell = r[col].strip().strip('"').strip("'")
        if cell:
            out.append(_resolve(cell, base))
    return out


def _looks_like_header(cell: str, base: str) -> bool:
    """A first CSV cell that is a bare word (no separator, no extension) and
    names no existing file is a header. A missing *path* (with a separator or
    an extension) is kept, so it shows up as 'not found' instead of vanishing."""
    if not cell or "/" in cell or "\\" in cell or "." in cell:
        return False
    return not os.path.exists(_resolve(cell, base))


def _resolve(entry: str, base: str) -> str:
    try:
        entry = os.path.expanduser(entry)
    except (ValueError, KeyError):
        pass
    if os.path.isabs(entry):
        return os.path.normpath(entry)
    return os.path.normpath(os.path.join(base, entry))


def find_list_files(root: str) -> list[str]:
    """List files directly in *root* whose first entries name an image file."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    out = []
    for n in names:
        p = os.path.join(root, n)
        if n.startswith(".") or os.path.splitext(n)[1].lower() not in LIST_EXTS:
            continue
        if not os.path.isfile(p):
            continue
        try:
            if os.path.getsize(p) > MAX_LIST_BYTES:
                continue
        except OSError:
            continue
        entries = parse_list_file(p)
        if any(is_loadable(e) for e in entries[:500]):
            out.append(p)
    return out


def probe_workspace(root: str, out_dir_name: str = DEFAULT_OUT_DIR
                    ) -> tuple[list[str], list[str]]:
    """(image files, usable list files) found in *root* — lets the UI pick a mode."""
    return scan_images(root, {out_dir_name}), find_list_files(root)


# ── Building ─────────────────────────────────────────────────────────────────

def build_workspace(root: str, mode: str, paths: list[str],
                    out_dir_name: str = DEFAULT_OUT_DIR,
                    list_file: str | None = None) -> Workspace:
    """Assemble a Workspace: absolute, de-duplicated paths, stems that stay
    stable for items already in the manifest, done flags matched by source."""
    root = os.path.abspath(root)
    ws = Workspace(root=root, mode=mode, out_dir_name=out_dir_name or DEFAULT_OUT_DIR,
                   list_file=list_file)

    seen: set[str] = set()
    uniq: list[str] = []
    for p in paths:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            uniq.append(ap)
    existing = [p for p in uniq if is_loadable(p)]
    ws.missing = [p for p in uniq if p not in existing]

    rows = read_manifest(ws.manifest_path)
    if manifest_unreadable(ws.manifest_path):
        ws.manifest_warning = ("manifest.csv could not be read — all items shown as pending; "
                               "the file is backed up on the next save")
    by_source: dict[str, dict] = {}
    for row in rows.values():
        for k in source_keys(row.get("source", ""), root):
            by_source.setdefault(k, row)

    reserved: dict[str, str] = {}      # path → stem recorded in the manifest
    for p in existing:
        row = next((by_source[k] for k in source_keys(p, root) if k in by_source), None)
        if row is not None and row.get("stem"):
            reserved[p] = row["stem"]
    stems = unique_stems(existing, root, reserved)
    ws.items = []
    for p, s in zip(existing, stems):
        row = rows.get(s) if (p in reserved or (s in rows and not rows[s].get("source"))) else None
        deleted = bool(row) and row.get("status", "") == STATUS_DELETED
        ws.items.append(Item(path=p, stem=s, done=bool(row) and not deleted, deleted=deleted))
    return ws


def source_keys(path: str, root: str) -> list[str]:
    """Normalised forms under which a manifest 'source' matches an item path:
    the relative path (when inside the workspace) and the absolute path."""
    if not path:
        return []
    keys = []
    if os.path.isabs(path):
        ap = os.path.normpath(path)
        rel = os.path.relpath(ap, root)
        if not (rel == ".." or rel.startswith(".." + os.sep)):
            keys.append("rel:" + rel)
        keys.append("abs:" + ap)
    else:
        rel = os.path.normpath(path)
        keys.append("rel:" + rel)
        keys.append("abs:" + os.path.normpath(os.path.join(root, rel)))
    return keys


def manifest_source(path: str, root: str) -> str:
    """What to record as 'source': relative to the workspace when inside it
    (survives moving the workspace between devices), else absolute."""
    rel = os.path.relpath(path, root)
    if rel == ".." or rel.startswith(".." + os.sep):
        return os.path.abspath(path)
    return rel


def unique_stems(paths: list[str], root: str,
                 reserved: dict[str, str] | None = None) -> list[str]:
    """One output stem per path.

    Duplicate basenames (compared case-insensitively, so case-insensitive
    filesystems stay safe) fall back to the path relative to *root* with
    separators replaced by '__'. Over-long stems get a hash tail. Whatever
    still collides gets a '_N' suffix that is checked against every other
    stem. Paths in *reserved* keep the stem the manifest already recorded.
    """
    reserved = reserved or {}
    stems = [file_stem(p) for p in paths]
    counts: dict[str, int] = {}
    for s in stems:
        counts[s.lower()] = counts.get(s.lower(), 0) + 1
    for i, (p, s) in enumerate(zip(paths, stems)):
        if p in reserved:
            stems[i] = reserved[p]
            continue
        if counts[s.lower()] > 1:
            rel = os.path.relpath(p, root)
            if rel == ".." or rel.startswith(".." + os.sep):
                rel = os.path.abspath(p).lstrip(os.sep)
            rel_dir = os.path.dirname(rel)
            stems[i] = (rel_dir.replace(os.sep, "__") + "__" + s) if rel_dir else s
        if len(stems[i]) > MAX_STEM_LEN:
            tail = hashlib.sha1(stems[i].encode("utf-8")).hexdigest()[:10]
            stems[i] = stems[i][:MAX_STEM_LEN - 11] + "_" + tail

    taken = {reserved[p].lower() for p in paths if p in reserved}
    out = list(stems)
    for i, (p, s) in enumerate(zip(paths, stems)):
        if p in reserved:
            continue
        cand, n = s, 0
        while cand.lower() in taken:
            n += 1
            cand = f"{s}_{n}"
        taken.add(cand.lower())
        out[i] = cand
    return out


# ── Manifest ─────────────────────────────────────────────────────────────────

def read_manifest(path: str) -> dict[str, dict]:
    """stem → row for every item recorded in the manifest. {} when the file
    is absent or cannot be parsed (never raises)."""
    if not os.path.isfile(path):
        return {}
    try:
        text = _read_text(path)
        rows: dict[str, dict] = {}
        for r in csv.DictReader(io.StringIO(text)):
            stem = (r.get("stem") or "").strip()
            if stem:
                rows[stem] = {k: (v or "") for k, v in r.items() if k is not None}
        return rows
    except (OSError, csv.Error, UnicodeDecodeError, ValueError):
        return {}


def manifest_unreadable(path: str) -> bool:
    """A manifest file exists with content but yields no rows."""
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0 and not read_manifest(path)
    except OSError:
        return False


def write_manifest_row(path: str, row: dict) -> str | None:
    """Insert or replace *row* (keyed by 'stem') and rewrite the manifest
    atomically. Unknown columns already in the file are preserved. An
    existing manifest that cannot be read is moved aside first (never
    overwritten); the backup path is returned in that case. Raises OSError
    when the directory is not writable — the caller reports it."""
    backup = None
    rows = read_manifest(path)
    if not rows and manifest_unreadable(path):
        backup = path + ".unreadable-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        os.replace(path, backup)
    rows[row["stem"]] = {**{k: "" for k in MANIFEST_FIELDS},
                         **{k: str(v) for k, v in row.items()}}
    _write_rows(path, rows)
    return backup


def remove_manifest_row(path: str, stem: str) -> bool:
    """Drop the row for *stem* (e.g. restoring a deleted mark). Returns
    whether a row was removed. Raises OSError when not writable."""
    rows = read_manifest(path)
    if stem not in rows:
        return False
    del rows[stem]
    _write_rows(path, rows)
    return True


def _write_rows(path: str, rows: dict[str, dict]) -> None:
    extra = sorted({k for r in rows.values() for k in r} - set(MANIFEST_FIELDS))
    fields = list(MANIFEST_FIELDS) + extra

    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="manifest.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for stem in sorted(rows):
                w.writerow({k: rows[stem].get(k, "") for k in fields})
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
