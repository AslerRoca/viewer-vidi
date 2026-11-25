"""Minimal RTF → plain text converter (stdlib only, no Qt).

Keeps the text and its paragraph / tab structure and drops everything else
(font and colour tables, style sheets, list tables, embedded theme data).
Character formatting (bold, italic, sizes) is not carried over.

Same rules as the converter that produced the single-file PET/CT report
export, so a report reads the same from the RTF column of the CSV export as
from its converted .txt file.
"""
from __future__ import annotations

import codecs
import re

# Destination groups whose content is not report text.
_IGNORED_DESTINATIONS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer",
    "generator", "themedata", "datastore", "latentstyles", "listtable",
    "listoverridetable", "rsidtbl", "xmlnstbl", "object", "filetbl", "revtbl",
}
_SPECIAL = {
    "par": "\n", "line": "\n", "sect": "\n", "page": "\n", "row": "\n",
    "tab": "\t", "cell": " | ",
    "emdash": "—", "endash": "–", "bullet": "*",
    "lquote": "'", "rquote": "'", "ldblquote": '"', "rdblquote": '"',
}
_TOKEN = re.compile(
    r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?"  # control word (+ numeric argument)
    r"|\\'([0-9a-f]{2})"                 # hex-escaped byte
    r"|\\([^a-z])"                       # control symbol
    r"|([{}])"                           # group open / close
    r"|[\r\n]+"                          # raw newlines carry no meaning in RTF
    r"|([^\\{}\r\n]+)",                  # run of literal characters
    re.I | re.S,
)
_CODEPAGE = re.compile(r"\\ansicpg(\d+)")


def rtf_to_text(rtf: str, encoding: str | None = None) -> str:
    """Text of an RTF document. *encoding* decodes the \\'hh bytes; by default
    it is the code page the document declares (\\ansicpgN), else cp1252."""
    if encoding is None:
        m = _CODEPAGE.search(rtf, 0, 400)
        encoding = f"cp{m.group(1)}" if m else "cp1252"
        try:
            codecs.lookup(encoding)
        except LookupError:
            encoding = "cp1252"

    stack = []          # (unicode skip count, ignoring) per open group
    ignoring = False
    uc = 1              # characters to skip after a \uN escape
    skip = 0
    out = []
    for m in _TOKEN.finditer(rtf):
        word, arg, hexbyte, symbol, brace, run = m.groups()
        if brace:
            skip = 0
            if brace == "{":
                stack.append((uc, ignoring))
            elif stack:
                uc, ignoring = stack.pop()
        elif symbol:
            skip = 0
            if symbol == "*":
                ignoring = True
            elif ignoring:
                pass
            elif symbol == "~":
                out.append("\u00a0")
            elif symbol in "{}\\":
                out.append(symbol)
        elif word:
            skip = 0
            if word in _IGNORED_DESTINATIONS:
                ignoring = True
            elif ignoring:
                pass
            elif word in _SPECIAL:
                out.append(_SPECIAL[word])
            elif word == "uc":
                uc = int(arg or 1)
            elif word == "u":
                code = int(arg or 0)
                out.append(chr(code + 65536 if code < 0 else code))
                skip = uc
        elif hexbyte:
            if skip > 0:
                skip -= 1
            elif not ignoring:
                out.append(bytes.fromhex(hexbyte).decode(encoding, "replace"))
        elif run:
            if skip > 0:                     # fallback characters of a \uN escape
                n = min(skip, len(run))
                run, skip = run[n:], skip - n
            if run and not ignoring:
                out.append(run)
    return "".join(out)


def clean_text(text: str) -> str:
    """Trim line ends and collapse runs of blank lines."""
    lines = [ln.rstrip() for ln in text.replace("\u00a0", " ").splitlines()]
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text) + "\n"
