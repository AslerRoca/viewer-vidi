"""Curated DICOM header info for the corner overlay. No Qt imports.

Reads header-only (stop_before_pixels) with a small LRU cache so the overlay
stays cheap while scrubbing slices/time. The tag selection lives here in one
place — extend the corner lists to surface more fields.
"""
from __future__ import annotations

from collections import OrderedDict

import pydicom

# Header fields fetched per file, grouped by the screen corner they feed.
_TL_TAGS = ("PatientName", "PatientID", "PatientBirthDate", "PatientSex",
            "StudyDate", "StudyTime")
_TR_TAGS = ("Modality", "Manufacturer", "ManufacturerModelName",
            "StudyDescription", "SeriesDescription", "SeriesNumber",
            "InstanceNumber")
_BR_TAGS = ("KVP", "ExposureTime", "XRayTubeCurrent", "Exposure",
            "RepetitionTime", "EchoTime", "SliceThickness", "AcquisitionTime")
# Expandable detail groups (bottom-right, collapsed by default)
_GROUP_TAGS = (
    "StationName", "DeviceSerialNumber", "SoftwareVersions",
    "InstitutionName", "InstitutionalDepartmentName", "InstitutionAddress",
    "PlateID", "PlateType", "CassetteSize", "CassetteOrientation",
    "Sensitivity", "ExposuresOnPlate", "AcquisitionDeviceProcessingCode",
    "ReferringPhysicianName", "PerformingPhysicianName",
    "NameOfPhysiciansReadingStudy",
    "ImageType", "BodyPartExamined", "ViewPosition", "PatientOrientation",
    "Laterality", "BitsStored", "PhotometricInterpretation",
    "RescaleSlope", "RescaleIntercept", "RescaleType",
    "LossyImageCompression", "InstanceCreationDate", "InstanceCreationTime",
    "AccessionNumber", "StudyID", "IssuerOfPatientID",
    "DeidentificationMethod", "StudyInstanceUID", "SeriesInstanceUID",
    "SOPInstanceUID",
)
_ALL_TAGS = list(_TL_TAGS + _TR_TAGS + _BR_TAGS + _GROUP_TAGS)

_CACHE: OrderedDict[str, pydicom.Dataset] = OrderedDict()
_CACHE_MAX = 256


def _dataset(path: str) -> pydicom.Dataset:
    ds = _CACHE.get(path)
    if ds is None:
        ds = pydicom.dcmread(path, stop_before_pixels=True,
                             specific_tags=_ALL_TAGS)
        _CACHE[path] = ds
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    else:
        _CACHE.move_to_end(path)
    return ds


def _text(ds, keyword: str) -> str:
    v = ds.get(keyword)
    return "" if v is None else str(v).strip()


def _num(ds, keyword: str):
    v = ds.get(keyword)
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _person(ds, keyword: str) -> str:
    return _text(ds, keyword).replace("^", " ").strip()


def _fmt_date(raw: str) -> str:
    """DICOM DA 'YYYYMMDD' → 'YYYY-MM-DD'."""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}" if len(raw) >= 8 else raw


def _fmt_time(raw: str) -> str:
    """DICOM TM 'HHMMSS.frac' → 'HH:MM:SS'."""
    raw = raw.split(".")[0]
    return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}" if len(raw) >= 6 else raw


def corner_texts(path: str, slice_line: str = "") -> tuple[str, str, str]:
    """(top_left, top_right, bottom_right) overlay text blocks for one file.

    top_left     — patient / study identity
    top_right    — modality, descriptions, series/instance position
    bottom_right — acquisition parameters (CT/CR/DX exposure, MR TR/TE)

    slice_line is appended to the series/instance row (e.g. "z 12/40").
    Returns empty strings when the file cannot be read.
    """
    try:
        ds = _dataset(path)
    except Exception:
        return "", "", ""

    tl = []
    if _text(ds, "PatientName"):
        tl.append(_text(ds, "PatientName").replace("^", " ").strip())
    if _text(ds, "PatientID"):
        tl.append(_text(ds, "PatientID"))
    row = " ".join(x for x in (_fmt_date(_text(ds, "PatientBirthDate")),
                               _text(ds, "PatientSex")) if x)
    if row:
        tl.append(row)
    row = " ".join(x for x in (_fmt_date(_text(ds, "StudyDate")),
                               _fmt_time(_text(ds, "StudyTime"))) if x)
    if row:
        tl.append(row)

    tr = []
    row = " · ".join(x for x in (
        _text(ds, "Modality"),
        _text(ds, "ManufacturerModelName") or _text(ds, "Manufacturer")) if x)
    if row:
        tr.append(row)
    for kw in ("StudyDescription", "SeriesDescription"):
        if _text(ds, kw):
            tr.append(_text(ds, kw))
    parts = []
    if _text(ds, "SeriesNumber"):
        parts.append(f"Se {_text(ds, 'SeriesNumber')}")
    if _text(ds, "InstanceNumber"):
        parts.append(f"Im {_text(ds, 'InstanceNumber')}")
    if slice_line:
        parts.append(slice_line)
    if parts:
        tr.append(" · ".join(parts))

    br = []
    kvp = _num(ds, "KVP")
    if kvp:
        br.append(f"{kvp:g} kV")
    mas = _num(ds, "Exposure")
    cur = _num(ds, "XRayTubeCurrent")
    ms  = _num(ds, "ExposureTime")
    if mas:
        br.append(f"{mas:g} mAs")
    elif cur or ms:
        br.append(" · ".join(x for x in (
            f"{cur:g} mA" if cur else "", f"{ms:g} ms" if ms else "") if x))
    tr_ms = _num(ds, "RepetitionTime")
    te_ms = _num(ds, "EchoTime")
    if tr_ms or te_ms:
        br.append(f"TR {tr_ms:g}/TE {te_ms:g} ms" if tr_ms and te_ms
                  else f"TR {tr_ms:g} ms" if tr_ms else f"TE {te_ms:g} ms")
    thk = _num(ds, "SliceThickness")
    if thk:
        br.append(f"thk {thk:g} mm")
    acq = _fmt_time(_text(ds, "AcquisitionTime"))
    if acq:
        br.append(f"acq {acq}")

    return "\n".join(tl), "\n".join(tr), "\n".join(br)


def _clip(s: str, n: int = 42) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def detail_groups(path: str) -> list[tuple[str, list[str]]]:
    """Collapsible (title, lines) groups for the bottom-right overlay.

    Only groups with at least one populated field are returned.
    """
    try:
        ds = _dataset(path)
    except Exception:
        return []

    groups: list[tuple[str, list[str]]] = []

    g = []
    row = " ".join(x for x in (_text(ds, "Manufacturer"),
                               _text(ds, "ManufacturerModelName")) if x)
    if row:
        g.append(row)
    if _text(ds, "StationName"):
        g.append(f"Station {_text(ds, 'StationName')}")
    if _text(ds, "DeviceSerialNumber"):
        g.append(f"S/N {_text(ds, 'DeviceSerialNumber')}")
    if _text(ds, "SoftwareVersions"):
        g.append(f"SW {_clip(_text(ds, 'SoftwareVersions'))}")
    for kw in ("InstitutionName", "InstitutionalDepartmentName",
               "InstitutionAddress"):
        if _text(ds, kw):
            g.append(_clip(_text(ds, kw)))
    if g:
        groups.append(("Equipment", g))

    g = []
    if _text(ds, "PlateID"):
        row = f"Plate {_text(ds, 'PlateID')}"
        if _text(ds, "PlateType"):
            row += f" ({_text(ds, 'PlateType')})"
        g.append(row)
    row = " ".join(x for x in (_text(ds, "CassetteSize"),
                               _text(ds, "CassetteOrientation")) if x)
    if row:
        g.append(row)
    if _num(ds, "Sensitivity") is not None:
        g.append(f"Sensitivity {_num(ds, 'Sensitivity'):g}")
    if _text(ds, "ExposuresOnPlate"):
        g.append(f"Exposures on plate {_text(ds, 'ExposuresOnPlate')}")
    if _text(ds, "AcquisitionDeviceProcessingCode"):
        g.append(f"Proc {_text(ds, 'AcquisitionDeviceProcessingCode')}")
    if g:
        groups.append(("Plate", g))

    g = []
    for label, kw in (("Ref", "ReferringPhysicianName"),
                      ("Perf", "PerformingPhysicianName"),
                      ("Read", "NameOfPhysiciansReadingStudy")):
        if _person(ds, kw):
            g.append(f"{label} {_clip(_person(ds, kw))}")
    if g:
        groups.append(("Staff", g))

    g = []
    it = ds.get("ImageType")
    if it:
        g.append("/".join(str(x) for x in it) if isinstance(it, (list, pydicom.multival.MultiValue)) else str(it))
    if _text(ds, "BodyPartExamined"):
        g.append(f"Body part {_text(ds, 'BodyPartExamined')}")
    if _text(ds, "ViewPosition"):
        g.append(f"View {_text(ds, 'ViewPosition')}")
    if _text(ds, "PatientOrientation"):
        g.append(f"Orient {_text(ds, 'PatientOrientation')}")
    if _text(ds, "Laterality"):
        g.append(f"Laterality {_text(ds, 'Laterality')}")
    row = " ".join(x for x in (
        f"{_text(ds, 'BitsStored')} bit" if _text(ds, "BitsStored") else "",
        _text(ds, "PhotometricInterpretation")) if x)
    if row:
        g.append(row)
    slope = _num(ds, "RescaleSlope")
    icept = _num(ds, "RescaleIntercept")
    if slope is not None or icept is not None:
        row = f"Rescale ×{slope:g} +{icept:g}" if slope is not None and icept is not None else "Rescale"
        if _text(ds, "RescaleType"):
            row += f" {_text(ds, 'RescaleType')}"
        g.append(row)
    if _text(ds, "LossyImageCompression") == "01":
        g.append("Lossy compressed")
    row = " ".join(x for x in (_fmt_date(_text(ds, "InstanceCreationDate")),
                               _fmt_time(_text(ds, "InstanceCreationTime"))) if x)
    if row:
        g.append(f"Created {row}")
    if g:
        groups.append(("Image", g))

    g = []
    if _text(ds, "AccessionNumber"):
        g.append(f"Acc {_text(ds, 'AccessionNumber')}")
    if _text(ds, "StudyID") and _text(ds, "StudyID") != _text(ds, "AccessionNumber"):
        g.append(f"Study ID {_text(ds, 'StudyID')}")
    if _text(ds, "IssuerOfPatientID"):
        g.append(f"ID issuer {_text(ds, 'IssuerOfPatientID')}")
    if _text(ds, "DeidentificationMethod"):
        g.append(f"Deident {_clip(_text(ds, 'DeidentificationMethod'))}")
    for label, kw in (("Study UID", "StudyInstanceUID"),
                      ("Series UID", "SeriesInstanceUID"),
                      ("SOP UID", "SOPInstanceUID")):
        v = _text(ds, kw)
        if v:
            g.append(f"{label} …{v[-14:]}")
    if g:
        groups.append(("IDs", g))

    return groups
