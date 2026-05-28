"""Built-in and user-saved Window/Level presets.

Built-in values are standard Hounsfield-unit CT presets. They apply directly as
WC/WW regardless of file format — on non-HU data (PNG, MRI, some NIfTI) they
will look off, and the user can fall back to Reset W/L.
"""
from __future__ import annotations

import json

from PyQt5.QtCore import QSettings


BUILTIN_PRESETS: list[tuple[str, float, float]] = [
    ("Lung",         -600.0, 1500.0),
    ("Soft tissue",    40.0,  400.0),
    ("Bone",          300.0, 1500.0),
    ("Abdomen",        60.0,  400.0),
    ("Brain",          40.0,   80.0),
]

_SETTINGS_KEY = "wl_presets/custom"


def _qsettings() -> QSettings:
    return QSettings("viewer-vidi", "viewer-vidi")


def load_custom_presets() -> list[tuple[str, float, float]]:
    raw = _qsettings().value(_SETTINGS_KEY, "[]", type=str)
    try:
        data = json.loads(raw)
    except Exception:
        return []
    out: list[tuple[str, float, float]] = []
    for d in data:
        name = str(d.get("name", "")).strip()
        try:
            wc = float(d.get("wc", 0.0))
            ww = float(d.get("ww", 0.0))
        except (TypeError, ValueError):
            continue
        if name and ww > 0:
            out.append((name, wc, ww))
    return out


def save_custom_presets(presets: list[tuple[str, float, float]]) -> None:
    data = [{"name": n, "wc": float(c), "ww": float(w)} for n, c, w in presets]
    s = _qsettings()
    s.setValue(_SETTINGS_KEY, json.dumps(data))
    s.sync()
