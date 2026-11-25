"""Headless checks for the Reports panel (rtf_text.py, reports.py, report_panel.py).

Run: QT_QPA_PLATFORM=offscreen python tests/reports/test_reports.py   (viewer_vidi env)

All fixtures are synthetic and written to a temp dir — no patient data here.
"""
import os, sys, shutil, tempfile, time, types, importlib.util

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pkg = types.ModuleType("viewer_vidi"); pkg.__path__ = [SRC]; pkg.__package__ = "viewer_vidi"
pkg.__file__ = os.path.join(SRC, "__init__.py"); sys.modules["viewer_vidi"] = pkg
importlib.util.spec_from_file_location("viewer_vidi", pkg.__file__).loader.exec_module(pkg)

from viewer_vidi import reports as R
from viewer_vidi.rtf_text import clean_text, rtf_to_text

results = []
def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info and not cond else ""))

T = tempfile.mkdtemp(prefix="vidi_reports_")

# ── Fixtures ────────────────────────────────────────────────────────────────
NEW = """Klinische Angaben:\tV.a. Raumforderung <rechts> & Husten
Fragestellung:\tStaging

PET/CT - CT-Befundung/Konsil vom 02.01.2020:
Strukturierter Befund: PET-CT (CT-Anteil)

ALLGEMEINE ANGABEN

Vergleich
•\tErstbefund

Kontrastmittel/Tracer
•\tTracer: FDG
•\tKeine Kontrastmittelapplikation

BEFUND

Lunge
•\tRundherd 12 x 9 mm im Oberlappen.
·\tKein Erguss.

Die Beurteilung erfolgt im Konsens.
"""
OLD = """Verlaufskontrolle nach Therapie, Befund größenkonstant bis leicht regredient im Vergleich.

PET/CT - Konsiliarische CT-Befundung vom 04.03.2021

Version: ID0001_2

ALLGEMEINE ANGABEN

Prozedur
PET-Tracer: FDG
CT-Technik: Low-Dose CT

BEFUND

Lunge
Pulmonaler Herdbefund:
Größenkonstanter Rundherd.

Andere Organsysteme
Thorax: unauffällig
Abdomen: Nierenzyste links
"""
MULTI = ("===== BEFUND 1/2 | befund_datum 2019-05-06 10:00:00.000 =====\n"
         "Klinische Angaben:\tErster Befund\n\nBEFUND\n\nLunge\n- frei\n\n"
         "===== BEFUND 2/2 | befund_datum 2019-05-07 11:00:00.000 =====\n"
         "Nachtrag: zweiter Befund\n")

def rtf_doc(text):
    """An RTF document as a word processor writes it: tables first, then one
    paragraph per line, non-ASCII as \\'hh or \\uN? escapes."""
    body = []
    for line in text.rstrip("\n").split("\n"):
        out = []
        for ch in line:
            if ch == "\t": out.append("\\tab ")
            elif ch in "{}\\": out.append("\\" + ch)
            elif ord(ch) < 128: out.append(ch)
            elif ch == "ß": out.append("\\'df")
            else: out.append(f"\\u{ord(ch)}?")
        body.append("{\\rtlch\\fcs1 \\af0 \\ltrch\\fcs0 \\f0\\fs22 " + "".join(out) + "}\\par\n")
    return ("{\\rtf1\\adeflang1025\\ansi\\ansicpg1252\\uc1\\deff0\n"
            "{\\fonttbl{\\f0\\froman\\fcharset0 Times New Roman;}{\\f1 Symbol;}}\n"
            "{\\colortbl;\\red0\\green0\\blue0;}\n"
            "{\\stylesheet{\\s0 Normal;}{\\s1 heading 1;}}\n"
            "{\\*\\listtable{\\list\\listtemplateid1{\\listlevel{\\leveltext\\'01\\u-3913 ?;}}}}\n"
            "{\\*\\themedata 504b0304\n1400060008000000}\n"
            "\\pard\\plain " + "".join(body) + "}")

TXT = os.path.join(T, "txt"); os.makedirs(os.path.join(TXT, "sub"))
def put(path, data, mode="w", **kw):
    with open(path, mode, **kw) as fh:
        fh.write(data)
put(os.path.join(TXT, "0000000001_20200102-093000.txt"), NEW, encoding="utf-8")
put(os.path.join(TXT, "0000000001_20210304-101500.txt"), OLD, encoding="utf-8")
put(os.path.join(TXT, "0000000002_20190506-080000.txt"), MULTI, encoding="utf-8")
put(os.path.join(TXT, "notes.rtf"), rtf_doc("Freitext ohne Stempel\nzweite Zeile"), encoding="ascii")
put(os.path.join(TXT, "._0000000001_20200102-093000.txt"), b"\x00\x05\x16\x07" * 40, "wb")
put(os.path.join(TXT, "image.dcm"), b"\x00" * 200, "wb")
put(os.path.join(TXT, "sub", "0000000009_20200101-000000.txt"), "nicht gelistet\n")

HEADER = ["request_id", "patient_schluessel", "pacs_id", "unters_schluessel", "unters_termin",
          "unters_name", "ueberweiser", "befund_schluessel", "befund_datum", "befund_text_full"]
ROWS = [  # deliberately not in label order; the texts hold quotes, commas and line breaks
    ["901", "71", "0000000002", "5001", "2019-05-06 08:00:00.000", "PET/CT", "Ambulanz A", "8001",
     "2019-05-06 10:00:00.000", 'Erster "Befund", mit Komma\n\nBEFUND\n\nLunge\n- frei\n'],
    ["900", "70", "0000000001", "5000", "2020-01-02 09:30:00.000", "PET/CT", "Ambulanz B", "8000",
     "2020-01-02 14:26:46.000", NEW],
    ["902", "70", "0000000001", "5002", "2021-03-04 10:15:00.000", "PET/CT", "", "8002",
     "2021-03-04 12:00:00.000", OLD],
]
import csv
CSVD = os.path.join(T, "csv"); os.makedirs(CSVD)
def write_table(path, header, rows, rtf=True, **kw):
    with open(path, "w", newline="", encoding=kw.pop("encoding", "utf-8")) as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL, **kw)
        w.writerow(header)
        w.writerows([r[:-1] + [rtf_doc(r[-1]) if rtf else r[-1]] for r in rows])
write_table(os.path.join(CSVD, "part_001.csv"), HEADER, ROWS[:2])
write_table(os.path.join(CSVD, "part_002.csv"), HEADER, ROWS[2:])
shutil.copy(os.path.join(CSVD, "part_001.csv"), os.path.join(CSVD, "dami.csv"))

# ── RTF → text ──────────────────────────────────────────────────────────────
check("rtf: text survives, tables and theme data are dropped",
      clean_text(rtf_to_text(rtf_doc(NEW))) == NEW, repr(clean_text(rtf_to_text(rtf_doc(NEW)))[:300]))
check("rtf: \\'hh byte, \\uN with fallback, escaped braces, \\~",
      rtf_to_text(r"{\rtf1\ansi Gr\'f6\'dfe \u8226?x \{a\}\~b}") == "Größe •x {a}\u00a0b")
check("rtf: \\ucN sets how many fallback characters are skipped",
      rtf_to_text(r"{\rtf1\uc2 \u228 aeb\uc0 \u246 c}") == "äböc")
check("rtf: negative \\uN is a 16-bit code", rtf_to_text(r"{\rtf1 \u-3913?}") == "\uf0b7")
check("rtf: declared code page decodes the bytes",
      rtf_to_text(r"{\rtf1\ansi\ansicpg1251 \'cf\'f0\'e8}") == "При"
      and rtf_to_text(r"{\rtf1\ansi\ansicpg99999 \'e4}") == "ä")
check("rtf: \\par / \\line / \\tab, raw newlines ignored",
      rtf_to_text("{\\rtf1 a\\par b\\line c\\tab d\ne}") == "a\nb\nc\tde")
check("rtf: unbalanced or empty input does not raise",
      rtf_to_text("}}{\\rtf1 x") == "x" and rtf_to_text("") == "")
check("clean_text trims line ends and collapses blank runs",
      clean_text("a  \n\n\n\n b\u00a0\n") == "a\n\n b\n")

# ── Discovery ───────────────────────────────────────────────────────────────
entries, notes = R.scan_reports(TXT)
check("folder: .txt/.rtf of the folder only (no dotfiles, other types, subfolders)",
      len(entries) == 4 and not notes, str([e.label for e in entries]))
check("folder: '<id>_<stamp>' names become 'id · date time', sorted",
      [e.label for e in entries] == ["0000000001  ·  2020-01-02 09:30", "0000000001  ·  2021-03-04 10:15",
                                     "0000000002  ·  2019-05-06 08:00", "notes"], str([e.label for e in entries]))
check("folder: text and RTF files read", R.load_report(entries[0]) == NEW
      and R.load_report(entries[3]) == "Freitext ohne Stempel\nzweite Zeile\n")

rows, notes = R.scan_reports(CSVD)
check("tables: one entry per distinct row, copies skipped and reported",
      len(rows) == 3 and notes == ["2 duplicate rows skipped"], f"{len(rows)} {notes}")
check("tables: label from the patient-ID and first date column, sorted like the files",
      [e.label for e in rows] == [e.label for e in entries[:3]], str([e.label for e in rows]))
check("tables: the long column is the report, the others are its header",
      all(e.column == 9 for e in rows) and [k for k, _ in rows[0].fields] == HEADER[:-1]
      and dict(rows[0].fields)["ueberweiser"] == "Ambulanz B")
by_label = {r[2] + "  ·  " + r[4][:16]: r[-1] for r in ROWS}
check("tables: every row reads back its own text (multi-line quoted RTF fields)",
      all(R.load_report(e) == clean_text(by_label[e.label]) for e in rows))

one = os.path.join(T, "semi.csv")       # BOM, ';' delimiter, plain text, ragged rows, no ID column
put(one, "\ufeffnr;befund;datum\n1;\"Zeile eins\nZeile zwei; mit Semikolon\";2020-01-01\n2;kurz\n\n3;;2020-01-03\n",
    encoding="utf-8", newline="")
semi, notes = R.scan_reports(one)
check("table file: BOM, ';' delimiter, ragged and empty rows",
      [e.label for e in semi] == ["1  ·  2020-01-01", "2", "3  ·  2020-01-03"] and not notes
      and semi[0].column == 1 and R.load_report(semi[0]) == "Zeile eins\nZeile zwei; mit Semikolon\n"
      and R.load_report(semi[1]) == "kurz\n" and R.load_report(semi[2]) == "\n",
      str([(e.label, e.column) for e in semi]))
tsv = os.path.join(T, "t.tsv")
put(tsv, "PatientID\tStudyDate\tReport\nA,1\t2020-02-02 10:00:00\tBefund, mit Komma\n", encoding="cp1252")
tab, _ = R.scan_reports(tsv)
check(".tsv is tab-delimited; a column named like a report wins over a longer one",
      len(tab) == 1 and tab[0].label == "A,1  ·  2020-02-02 10:00" and R.load_report(tab[0]) == "Befund, mit Komma\n",
      str(tab))

put(os.path.join(T, "latin.txt"), "Größe: 3 mm\n".encode("cp1252"), "wb")
put(os.path.join(T, "u16.txt"), "Größe: 4 mm\n".encode("utf-16"), "wb")
put(os.path.join(T, "bom.txt"), b"\xef\xbb\xbf" + "Größe: 5 mm\n".encode("utf-8"), "wb")
put(os.path.join(T, "report.log"), "frei gewählte Datei\n", encoding="utf-8")
read = lambda name: R.load_report(R.scan_reports(os.path.join(T, name))[0][0])
check("text file encodings: cp1252, UTF-16, UTF-8 BOM",
      (read("latin.txt"), read("u16.txt"), read("bom.txt")) == ("Größe: 3 mm\n", "Größe: 4 mm\n", "Größe: 5 mm\n"))
check("a file picked by hand is read as text whatever its extension", read("report.log") == "frei gewählte Datei\n")
try:
    read(os.path.join("txt", "image.dcm")); check("binary file is refused", False)
except R.ReportError as exc:
    check("binary file is refused", "text file" in str(exc))
big = os.path.join(T, "big.txt")
put(big, ("Zeile mit Umlaut ä\n" * (R.MAX_REPORT_BYTES // 19 + 10)), encoding="utf-8")
text = read("big.txt")
check("an oversized text file is cut at a line end and says so",
      len(text.encode()) < R.MAX_REPORT_BYTES + 200 and "rest is not shown" in text and "\ufffd" not in text
      and text.split("\n")[-4] == "Zeile mit Umlaut ä", repr(text[-120:]))

stale = os.path.join(T, "stale.csv")
write_table(stale, HEADER, ROWS, rtf=False)
st, _ = R.scan_reports(stale)
write_table(stale, HEADER, [ROWS[2], ROWS[0], ROWS[1]], rtf=False)
try:
    R.load_report(st[0]); check("a table changed after indexing is refused, not misread", False)
except R.ReportError as exc:
    check("a table changed after indexing is refused, not misread", "changed" in str(exc))
check("empty folder / header-only table / missing path give no entries",
      R.scan_reports(os.path.join(TXT, "sub", ".."))[0] and not R.scan_reports(os.makedirs(os.path.join(T, "e")) or os.path.join(T, "e"))[0]
      and not R.scan_reports(put(os.path.join(T, "h.csv"), "a,b\n") or os.path.join(T, "h.csv"))[0])
seen = []
part, _ = R.scan_reports(CSVD, progress=seen.append, cancelled=lambda: True)
check("a cancelled scan stops without raising", part == [])

# ── Structure ───────────────────────────────────────────────────────────────
kinds = lambda text: [[(k, a) for k, a, _ in block] for block in R.parse_report(text)]
k = kinds(NEW)
check("structure: fields, label, sections, sub-headings over bullets, closing text",
      k[0] == [("field", "Klinische Angaben"), ("field", "Fragestellung")]
      and k[1] == [("label", "PET/CT - CT-Befundung/Konsil vom 02.01.2020:"), ("field", "Strukturierter Befund")]
      and k[2] == [("section", "ALLGEMEINE ANGABEN")] and k[3] == [("sub", "Vergleich"), ("bullet", "Erstbefund")]
      and k[6] == [("sub", "Lunge"), ("bullet", "Rundherd 12 x 9 mm im Oberlappen."), ("bullet", "Kein Erguss.")]
      and k[7] == [("text", "Die Beurteilung erfolgt im Konsens.")], str(k))
k = kinds(OLD)
check("structure: older template — sub-headings over plain lines, labels, inline fields",
      k[0][0][0] == "text" and k[1] == [("text", "PET/CT - Konsiliarische CT-Befundung vom 04.03.2021")]
      and k[4] == [("sub", "Prozedur"), ("field", "PET-Tracer"), ("field", "CT-Technik")]
      and k[6] == [("sub", "Lunge"), ("label", "Pulmonaler Herdbefund:"), ("text", "Größenkonstanter Rundherd.")]
      and k[7] == [("sub", "Andere Organsysteme"), ("field", "Thorax"), ("field", "Abdomen")], str(k))
k = kinds(MULTI)
check("structure: '===== … =====' separates the reports of one file",
      k[0][0] == ("rule", "BEFUND 1/2 | befund_datum 2019-05-06 10:00:00.000") and k[3][0][0] == "rule"
      and k[2] == [("sub", "Lunge"), ("bullet", "frei")], str(k))
check("structure: field value kept, short capitals and sentences are plain text",
      R.parse_report("Thorax: frei\n\nCT\n\nKein Befund.\nZweite Zeile.")
      == [[("field", "Thorax", "frei")], [("text", "CT", "")], [("text", "Kein Befund.", ""), ("text", "Zweite Zeile.", "")]])
check("structure: empty text has no blocks", R.parse_report("\n \n") == [])

# ── Panel ───────────────────────────────────────────────────────────────────
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from viewer_vidi.report_panel import report_html
from viewer_vidi.main_window import MainWindow

h = report_html(NEW, (("pacs_id", "0000000001"), ("ueberweiser", ""), ("note", "a<b")))
check("html: text is escaped, empty header values dropped, bullets are a list",
      "&lt;rechts&gt; &amp; Husten" in h and "<rechts>" not in h and "a&lt;b" in h and "ueberweiser" not in h
      and h.count("<ul") == h.count("</ul>") == 3 and h.count("<li") == 5, h[:300])
check("html: empty report says so", "(empty report)" in report_html("\n"))

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow(); win.resize(1500, 900); win.show(); app.processEvents()
panel = win._report_panel

def wait(cond, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return False
def opened(path, n):
    panel.open_source(path)
    return wait(lambda: panel._worker is None) and len(panel._entries) == n
shown = lambda: panel._view.toPlainText()
visible = lambda: [panel._list.item(i).text() for i in range(panel._list.count()) if not panel._list.isRowHidden(i)]

quad = win._quad; cells = quad.cells()
on_screen = lambda: [c.isVisible() for c in cells]
widths = lambda: [c.width() for c in cells]
near = lambda a, b: all(abs(x - y) <= 2 for x, y in zip(a, b))
toggle = lambda cell: (quad._toggle_fullscreen(cell), app.processEvents())
w4 = widths()

check("panel starts hidden, button unchecked, four image panels",
      not panel.isVisible() and not win._report_btn.isChecked() and on_screen() == [True] * 4)
win._report_btn.setChecked(True); app.processEvents()
check("Reports button shows the panel in place of the right two image panels",
      panel.isVisible() and on_screen() == [True, False, True, False]
      and panel.x() >= quad.x() + quad.width(), f"{on_screen()} {panel.geometry()} {quad.geometry()}")
check("…wider than the column it replaces, and the left panels keep room",
      panel.width() > w4[1] and cells[0].width() == cells[2].width() >= 200, f"{panel.width()} {widths()}")
win._report_btn.setChecked(False); app.processEvents()
check("…and hides it again: the four image panels are back at their widths",
      not panel.isVisible() and on_screen() == [True] * 4 and near(widths(), w4), str(widths()))
win.activateWindow(); QTest.qWaitForWindowActive(win, 2000)
QTest.keyClick(win, Qt.Key_R, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
opened_by_key = panel.isVisible()
QTest.keyClick(panel._list, Qt.Key_R, Qt.ControlModifier | Qt.ShiftModifier); app.processEvents()
check("Ctrl+Shift+R toggles the panel, also with the focus inside it", opened_by_key and not panel.isVisible())

quad._set_active(cells[3]); toggle(cells[3]); was_marked = cells[3]._max_btn.isChecked()
win._report_btn.setChecked(True); app.processEvents()
check("Reports over an active, maximised right panel: its left neighbour takes over",
      not quad.is_fullscreen() and quad.active_cell() is cells[2] and on_screen() == [True, False, True, False]
      and was_marked and not cells[3]._max_btn.isChecked())
toggle(cells[0]); maximised = on_screen(); toggle(cells[0])
check("maximising a panel beside the reports and back keeps the right two hidden",
      maximised == [True, False, False, False] and on_screen() == [True, False, True, False])
t, q, r = win._splitter.sizes(); win._splitter.setSizes([t, q + 90, r - 90]); app.processEvents()
dragged = panel.width()
win._report_btn.setChecked(False); app.processEvents()
restored = on_screen() == [True] * 4 and near(widths(), w4)
win._report_btn.setChecked(True); app.processEvents()
check("the divider position is kept when Reports are closed and opened again",
      restored and abs(dragged - (r - 90)) <= 2 and abs(panel.width() - dragged) <= 2,
      f"{r} {dragged} {panel.width()} {widths()}")
win._sidebar_btn.setChecked(False); app.processEvents()
without_tree = panel.width()
win._sidebar_btn.setChecked(True); app.processEvents()
check("hiding and showing the study list leaves the report width alone",
      win._tree.isVisible() and without_tree == panel.width() == dragged, f"{dragged} {without_tree} {panel.width()}")

check("open a folder of text reports", opened(TXT, 4), panel._src_lbl.text())
check("first report is selected and shown formatted",
      panel._list.currentRow() == 0 and "ALLGEMEINE ANGABEN" in shown() and "<rechts> & Husten" in shown()
      and "Rundherd 12 x 9 mm" in shown(), shown()[:200])
check("source line and counter", panel._src_lbl.text() == "txt — 4 reports" and panel._count_lbl.text() == "1 / 4",
      panel._src_lbl.text() + " | " + panel._count_lbl.text())
check("Prev disabled on the first report, Next enabled", not panel._prev_btn.isEnabled() and panel._next_btn.isEnabled())
QTest.mouseClick(panel._next_btn, Qt.LeftButton); app.processEvents()
check("Next shows the following report", panel._list.currentRow() == 1 and "Pulmonaler Herdbefund:" in shown()
      and panel._count_lbl.text() == "2 / 4")
panel._list.setFocus(); QTest.keyClick(panel._list, Qt.Key_Down); app.processEvents()
check("arrow keys in the list browse reports", panel._list.currentRow() == 2 and "zweiter Befund" in shown())

panel._filter.setFocus(); QTest.keyClicks(panel._filter, "0000000001 2021x"); app.processEvents()
QTest.keyClick(panel._filter, Qt.Key_Backspace); app.processEvents()
check("typing and Backspace reach the filter field", panel._filter.text() == "0000000001 2021", panel._filter.text())
check("filter keeps rows holding every word and shows the first match",
      visible() == ["0000000001  ·  2021-03-04 10:15"] and panel._list.currentRow() == 1
      and panel._count_lbl.text() == "1 / 1 of 4" and not panel._next_btn.isEnabled(), str(visible()))
panel._filter.setText("0000000001"); app.processEvents()
check("a wider filter keeps the report on screen", panel._list.currentRow() == 1 and len(visible()) == 2
      and panel._prev_btn.isEnabled() and not panel._next_btn.isEnabled())
QTest.mouseClick(panel._prev_btn, Qt.LeftButton); app.processEvents()
check("Prev steps through the filtered rows", panel._list.currentRow() == 0 and panel._count_lbl.text() == "1 / 2 of 4")
panel._filter.setText("no such report"); app.processEvents()
check("no match: empty view, both buttons off", visible() == [] and shown() == "" and panel._list.currentRow() == -1
      and not panel._prev_btn.isEnabled() and not panel._next_btn.isEnabled() and panel._count_lbl.text() == "0 / 0 of 4")
panel._filter.clear(); app.processEvents()
check("clearing the filter brings the list back", len(visible()) == 4 and panel._list.currentRow() == 0)

check("open a folder of CSV tables", opened(CSVD, 3), panel._src_lbl.text())
check("rows listed like the files; duplicates reported",
      visible() == [e.label for e in entries[:3]] and panel._src_lbl.text() == "csv — 3 reports\n2 duplicate rows skipped",
      panel._src_lbl.text())
check("a row shows its header fields above the converted RTF text",
      "ueberweiser" in shown() and "Ambulanz B" in shown() and "befund_text_full" not in shown()
      and "ALLGEMEINE ANGABEN" in shown() and "rtf1" not in shown() and "<rechts> & Husten" in shown(), shown()[:300])
panel._filter.setText("AMBULANZ 8001"); app.processEvents()
check("filter also searches the header values", visible() == ["0000000002  ·  2019-05-06 08:00"]
      and 'Erster "Befund", mit Komma' in shown())
panel._filter.clear(); app.processEvents()

check("open one file", opened(os.path.join(TXT, "notes.rtf"), 1) and "zweite Zeile" in shown()
      and panel._src_lbl.text() == "notes.rtf — 1 report")
check("a folder without reports says so", opened(os.path.join(T, "e"), 0) and shown() == ""
      and panel._src_lbl.text().startswith("No reports found in e"), panel._src_lbl.text())
check("an unreadable source is reported, not raised", opened(os.path.join(T, "gone"), 0)
      and "gone" in panel._src_lbl.text(), panel._src_lbl.text())
check("a report that cannot be read is explained in the view",
      opened(os.path.join(TXT, "image.dcm"), 1) and "cannot be shown" in shown() and "text file" in shown())

panel.open_source(CSVD); panel.open_source(TXT)       # the first scan is superseded
check("reopening while indexing lists only the last source",
      wait(lambda: panel._worker is None) and (wait(lambda: False, 0.2) or True)
      and len(panel._entries) == 4 and panel._src_lbl.text() == "txt — 4 reports", panel._src_lbl.text())

# ── Drag from the study list ────────────────────────────────────────────────
from PyQt5.QtCore import QMimeData, QPointF
from PyQt5.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from viewer_vidi import drag_state, tree_panel

os.makedirs(os.path.join(T, "imgs")); open(os.path.join(T, "imgs", "a.png"), "wb").write(b"\x89PNG")
for sub in ("s1", "s2"):
    os.makedirs(os.path.join(T, "grp", sub)); open(os.path.join(T, "grp", sub, "x.dcm"), "wb").write(b"0")
open(os.path.join(T, "grp", "readme.txt"), "w").write("x")
grouped = tree_panel._make_series_meta(os.path.join(T, "grp"))
check("series probe: sub-series are still grouped, a report folder is no series",
      grouped is not None and [m.series_name for m in grouped.series_dirs] == ["s1", "s2"]
      and tree_panel._make_series_meta(CSVD) is None)

tree = win._tree
def drag(*paths):
    """What the tree hands to Qt when these entries are dragged. The indexes are made on the
    spot: the proxy drops its indexes whenever a folder has been classified."""
    drag_state.clear_payload()
    return tree._proxy.mimeData([tree._proxy.mapFromSource(tree._fs.index(p)) for p in paths])
def enters(mime, widget):
    event = QDragEnterEvent(widget.rect().center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, event)       # Qt offers it to the parents until one accepts
    return event.isAccepted()
def drop(mime, widget):
    if not enters(mime, widget):
        return False
    QApplication.sendEvent(widget, QDropEvent(QPointF(widget.rect().center()), Qt.CopyAction, mime,
                                              Qt.LeftButton, Qt.NoModifier))
    return True

mime = drag(CSVD)
check("dragging a report folder: the drag names its path and is no image series",
      mime is not None and drag_state.decode_paths(mime) == [CSVD]
      and not mime.hasFormat(drag_state.MIME_TYPE) and drag_state.get_payload() is None)
check("dropping it on the report text opens the folder",
      drop(mime, panel._view.viewport()) and wait(lambda: panel._worker is None)
      and len(panel._entries) == 3 and panel._src_lbl.text().startswith("csv — 3 reports"), panel._src_lbl.text())
check("dropping a file on the report list opens that file",
      drop(drag(os.path.join(TXT, "notes.rtf")), panel._list.viewport()) and wait(lambda: panel._worker is None)
      and panel._src_lbl.text() == "notes.rtf — 1 report" and "zweite Zeile" in shown(), panel._src_lbl.text())
other = QMimeData(); other.setText(CSVD)
check("several items at once and drags from elsewhere are refused",
      len(drag_state.decode_paths(drag(CSVD, TXT))) == 2 and not drop(drag(CSVD, TXT), panel)
      and not drop(other, panel) and panel._src_lbl.text() == "notes.rtf — 1 report", panel._src_lbl.text())
check("an image panel refuses a report drag", not enters(drag(CSVD), cells[0]))
img = drag(os.path.join(T, "imgs"))
check("an image folder still drags as a series for the image panels",
      img.hasFormat(drag_state.MIME_TYPE) and drag_state.get_payload().file_format == "image"
      and drag_state.decode_paths(img) == [os.path.join(T, "imgs")] and enters(img, cells[0]))
QApplication.sendEvent(cells[0], QDragLeaveEvent()); drag_state.clear_payload()

win._ws_btn.setChecked(True); app.processEvents(); wait(lambda: False, 0.2)
ws = win._dock
left = lambda w: w.mapToGlobal(QPoint(0, 0)).x()
ws_width = ws.width()
check("reports stand between the images and the workspace dock, images keep room",
      ws.isVisible() and panel.isVisible() and left(quad) < left(panel) and left(panel) + panel.width() <= left(ws)
      and cells[0].width() >= 200, f"{left(quad)} {left(panel)}+{panel.width()} {left(ws)} {widths()}")
win._report_btn.setChecked(False); app.processEvents(); wait(lambda: False, 0.2)
check("closing Reports leaves the workspace dock, its width and its button alone",
      ws.isVisible() and win._ws_btn.isChecked() and not panel.isVisible() and ws.width() == ws_width
      and on_screen() == [True] * 4, f"{ws_width} {ws.width()} {on_screen()}")
win._ws_btn.setChecked(False); app.processEvents()

win._report_btn.setChecked(True); app.processEvents()
panel.open_source(CSVD)
win.close(); app.processEvents()
check("closing the window stops a running scan", panel._worker is None)

shutil.rmtree(T, ignore_errors=True)
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
sys.exit(1 if n_fail else 0)
