"""Report sources for the Reports panel (no Qt).

A source is a folder (its own files, subfolders are not searched) or one file:

    .txt / .rtf   one report per file
    .csv / .tsv   one report per row — the report text is the column with the
                  longest values (among those named like text / report /
                  Bericht, if any); the other columns are the report's header

Report text may be plain or RTF (converted by rtf_text.py). Nothing is ever
written. Table rows are indexed by byte offset and read on demand, so an
export of several hundred MB costs a few MB of memory.
"""
from __future__ import annotations

import csv
import itertools
import os
import re
from dataclasses import dataclass

from .rtf_text import clean_text, rtf_to_text

TEXT_EXTS = (".txt", ".rtf")
TABLE_EXTS = (".csv", ".tsv")
MAX_REPORT_BYTES = 2_000_000     # a text file is read up to here; reports are a few KB

# A report column holds whole documents, far beyond the csv default of 128 KB
# per field. The limit is global to the csv module.
csv.field_size_limit(1 << 30)

_ID_NAME = re.compile(r"(?:^|_)(?:pacs|patient|pat|subject|case|study)_?(?:id|nr|no)$|^p?id$", re.I)
_DATE_NAME = re.compile(r"date|datum|termin|time|zeit", re.I)
_TEXT_NAME = re.compile(r"text|report|bericht", re.I)
_STAMP = re.compile(r"(.+?)_(\d{4})(\d\d)(\d\d)[-_T]?(\d\d)(\d\d)(\d\d)?")
_ISO_TIME = re.compile(r"(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d)(?::\d\d(?:\.\d+)?)?")
_SEP = "  ·  "


class ReportError(Exception):
    """A report cannot be shown; the message is meant for the user."""


@dataclass(frozen=True)
class ReportEntry:
    label: str                 # list text: patient ID and examination time when known
    path: str                  # file holding the report
    offset: int = -1           # table row: byte offset of its record; -1 = the whole file
    column: int = -1           # table row: index of the report-text column
    delimiter: str = ","
    fields: tuple = ()         # table row: ((column name, value), …) without the text


# ── Discovery ──────────────────────────────────────────────────────────────────

def scan_reports(path: str, progress=None, cancelled=None) -> tuple[list[ReportEntry], list[str]]:
    """Index the reports of a folder or of one file.

    Returns (entries sorted by label, notes for the user). *progress(text)* is
    called while tables are read; *cancelled()* returning True stops early.
    """
    progress = progress or (lambda _text: None)
    cancelled = cancelled or (lambda: False)
    if os.path.isdir(path):
        with os.scandir(path) as it:        # "._x" AppleDouble files litter exFAT drives
            files = sorted(e.path for e in it if not e.name.startswith(".") and e.is_file())
        chosen = False
    elif os.path.isfile(path):
        files, chosen = [path], True
    else:
        return [], [f"Not a file or folder: {path}"]

    entries: list[ReportEntry] = []
    notes: list[str] = []
    seen: set[int] = set()
    duplicates = 0
    for fp in files:
        if cancelled():
            break
        ext = os.path.splitext(fp)[1].lower()
        if ext in TABLE_EXTS:
            try:
                duplicates += _index_table(fp, entries, seen, progress, cancelled)
            except (OSError, csv.Error) as exc:
                notes.append(f"{os.path.basename(fp)}: {exc}")
        elif ext in TEXT_EXTS or chosen:    # a file picked by hand is read as text
            entries.append(ReportEntry(_file_label(fp), fp))
    if duplicates:
        notes.append(f"{duplicates:,} duplicate rows skipped")
    entries.sort(key=lambda e: (e.label, e.path, e.offset))
    return entries, notes


def _file_label(path: str) -> str:
    """'<id>_<YYYYMMDD>-<HHMMSS>.txt' → 'id · YYYY-MM-DD HH:MM'; else the file stem."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = _STAMP.fullmatch(stem)
    if not m:
        return stem
    ident, y, mo, d, h, mi, _s = m.groups()
    return f"{ident}{_SEP}{y}-{mo}-{d} {h}:{mi}"


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _records(fh, pos: int, delimiter: str):
    """(byte offset, fields) of every record of a binary table file from *pos*.

    csv.reader pulls exactly the physical lines of one record per step, so the
    position before a step is where that record starts — also for records
    whose quoted fields span many lines.
    """
    fh.seek(pos)
    state = [pos]

    def lines():
        for raw in fh:
            state[0] += len(raw)
            yield _decode(raw)

    reader = csv.reader(lines(), delimiter=delimiter)
    while True:
        offset = state[0]
        try:
            row = next(reader)
        except StopIteration:
            return
        yield offset, row


def _index_table(path: str, entries: list, seen: set, progress, cancelled) -> int:
    """Append one entry per data row of *path*; returns the number of rows that
    were skipped as exact duplicates of a row already indexed."""
    name = os.path.basename(path)
    duplicates = 0
    with open(path, "rb") as fh:
        start = 3 if fh.read(3) == b"\xef\xbb\xbf" else 0
        fh.seek(start)
        first = _decode(fh.readline())
        delimiter = "\t" if path.lower().endswith(".tsv") else max(",;\t", key=first.count)
        records = _records(fh, start, delimiter)
        header = [h.strip() or f"column {i + 1}"
                  for i, h in enumerate(next(records, (0, []))[1])]
        head = list(itertools.islice(records, 20))
        if not header or not head:
            return 0
        named = [i for i, h in enumerate(header)
                 if _TEXT_NAME.search(h) and not _DATE_NAME.search(h)]
        column = max(named or range(len(header)),
                     key=lambda i: sum(len(r[i]) for _, r in head if i < len(r)))
        others = [i for i in range(len(header)) if i != column]
        id_col = next((i for i in others if _ID_NAME.search(header[i])),
                      others[0] if others else None)
        date_col = next((i for i in others if i != id_col and _DATE_NAME.search(header[i])), None)

        for n, (offset, row) in enumerate(itertools.chain(head, records), 1):
            if cancelled():
                break
            if n % 250 == 0:
                progress(f"{name}: row {n:,}")
            if not row:
                continue
            key = hash(tuple(row))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            cell = lambda i: row[i].strip() if i is not None and i < len(row) else ""
            label = _SEP.join(x for x in (cell(id_col), _ISO_TIME.sub(r"\1 \2", cell(date_col))) if x)
            entries.append(ReportEntry(
                label=label or f"{name} #{n}", path=path, offset=offset,
                column=column, delimiter=delimiter,
                fields=tuple((header[i], cell(i)) for i in others)))
    return duplicates


# ── Reading one report ─────────────────────────────────────────────────────────

def load_report(entry: ReportEntry) -> str:
    """Plain text of one report (RTF converted). Raises ReportError or OSError."""
    if entry.offset < 0:
        with open(entry.path, "rb") as fh:
            raw = fh.read(MAX_REPORT_BYTES + 1)
        truncated = len(raw) > MAX_REPORT_BYTES
        if truncated:                       # cut at a line end, never inside a character
            raw = raw[:MAX_REPORT_BYTES].rsplit(b"\n", 1)[0]
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = raw.decode("utf-16", "replace")
        else:
            text = _decode(raw[3:] if raw[:3] == b"\xef\xbb\xbf" else raw)
        if "\x00" in text:
            raise ReportError("This does not look like a text file.")
    else:
        truncated = False
        with open(entry.path, "rb") as fh:
            row = next(_records(fh, entry.offset, entry.delimiter), (0, []))[1]
        width = len(entry.fields) + 1
        meta = tuple(row[i].strip() if i < len(row) else ""
                     for i in range(width) if i != entry.column)
        if meta != tuple(v for _, v in entry.fields):
            raise ReportError(f"{os.path.basename(entry.path)} has changed since it was "
                              "indexed — open the source again.")
        text = row[entry.column] if entry.column < len(row) else ""

    if text.lstrip().startswith("{\\rtf"):
        text = rtf_to_text(text)
    text = clean_text(text)
    if truncated:
        text += f"\n[The file is longer than {MAX_REPORT_BYTES:,} bytes; the rest is not shown.]\n"
    return text


# ── Structure ──────────────────────────────────────────────────────────────────

_RULE = re.compile(r"={3,}\s*(.*?)\s*={3,}")
_BULLET = re.compile(r"[•·\-*»§][ \t]+(\S.*)")
_CAPS = re.compile(r"[A-ZÄÖÜ][A-ZÄÖÜ0-9 /&\-]{4,}")
_FIELD = re.compile(r"([^\t:]{2,40}):[ \t]+(\S.*)")
_SHORT = 60          # longest line still taken for a heading or label


def parse_report(text: str) -> list[list[tuple[str, str, str]]]:
    """Structure of a report: blocks (separated by blank lines) of
    (kind, text, value) lines. The rules are layout-only, so they fit any
    template that is written as headings over lists and 'key: value' lines.

        rule     '===== title ====='           separator between reports of one file
        section  'ALLGEMEINE ANGABEN'          line in capitals
        sub      short first line of a block   heading of the lines below it
        label    'Thorax:'                     short line ending with a colon
        field    'Key: value'                  value in the third slot
        bullet   '•⇥text', '- text'
        text     anything else
    """
    blocks = []
    for chunk in re.split(r"\n[ \t]*\n", text.strip("\n")):
        lines = [ln.strip() for ln in chunk.split("\n") if ln.strip()]
        block = []
        for i, s in enumerate(lines):
            if m := _RULE.fullmatch(s):
                block.append(("rule", m.group(1), ""))
            elif m := _BULLET.fullmatch(s):
                block.append(("bullet", m.group(1), ""))
            elif _CAPS.fullmatch(s) and sum(c.isalpha() for c in s) >= 4:
                block.append(("section", s, ""))
            elif m := _FIELD.fullmatch(s):
                block.append(("field", m.group(1), m.group(2)))
            elif s.endswith(":") and len(s) <= _SHORT:
                block.append(("label", s, ""))
            elif i == 0 and len(lines) > 1 and len(s) <= _SHORT and s[-1] not in ".,;!?":
                block.append(("sub", s, ""))
            else:
                block.append(("text", s, ""))
        if block:
            blocks.append(block)
    return blocks
