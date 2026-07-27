# Protocol (lab notebook) — viewer-vidi

> Running record of every experiment/iteration: **Assumption → What we did → What we got → Try next**.
> Newest entry on top. This is the journey, dead-ends included — settled conclusions get promoted to
> `MILESTONES.md`, and the link is two-way (each entry gets `· → M<k>` once promoted; the milestone
> carries a `Derived from: P…` line back here). Add entries with the `/protocol` skill.
>
> Keep entries **rich** — this is the document-grade source you compile reports/methods/manuscripts
> from (exact configs, numbers, what failed and why), with *more* detail than Claude memory, not less.

---

## P4 — Sidebar hide/show handle  ·  2026-07-27
- **Anchor:** `6921c2b`

**Assumption.** The study-list sidebar could be dismissed but not recovered: `Ctrl+B` toggled it with no on-screen control, and the 1px `QSplitter` handle let a drag collapse the tree to an invisible sliver with no way to pull it back.

**What we did.** In `main_window.py`: added a checkable **☰** button at the left of the toolbar as the permanent visible handle (accent-blue `#7c8fbd` when open, restores the tree at its previous width via the retained `_tree_width`); set `setCollapsible(0, False)` on the splitter so a drag now stops at the tree's 200px minimum instead of vanishing; kept button state in sync with `Ctrl+B` through `_on_sidebar_btn`/`_toggle_sidebar` (mutually re-entrant, guarded by `blockSignals`). In `style.qss`: widened the main `QSplitter::handle` 1px→3px with a hover highlight (matching the quad-view dividers), and styled `#sidebarBtn`.

**What we got.** Both loss paths closed — deliberate hide via ☰/Ctrl+B is reversible; accidental drag-collapse is prevented. Import check passes; viewer relaunched clean.

**Try next.** None outstanding for this fix (feature-complete).

---

## P3 — DICOM info overlay with collapsible detail groups  ·  2026-07-27
- **Anchor:** `6921c2b`

**Assumption.** Users need to read key DICOM header fields for whatever image is on screen without leaving the viewer. A corner overlay (clinical-viewer style) beats a separate panel/dialog because the info sits where the eyes already are during scrubbing, and costs no layout space.

**What we did.** Three sub-iterations driven by user feedback within one session:
1. **Corner overlay (initial).** New pure-Python `dicom_info.py` (no Qt, matching the `data_model.py` convention): `corner_texts(path, slice_line)` reads a curated tag set header-only via `pydicom.dcmread(..., stop_before_pixels=True, specific_tags=...)` behind a 256-entry LRU cache (`OrderedDict`, move-to-end on hit, popitem on overflow). Returns three formatted blocks — top-left (patient/study identity: name, ID, birthdate/sex, study date/time), top-right (modality · model, study/series descriptions, `Se·Im·slice` line), bottom-right (acquisition params: KVP/mAs for CR/DX, TR/TE for MR, SliceThickness, AcquisitionTime). `ImageCanvas.set_overlay()` + `_draw_overlay()` render four corners in `paintEvent` via QPainter, each block drawn twice (black shadow offset 1px, then theme text `#cdd6f4`) for contrast over both lung fields and black background. Bottom-left carries geometry (dims, px spacing, gap) with the live `W…L…` line appended by the *canvas itself* so it never lags during a W/L drag. `ViewCell` got a checkable **i** button + **I** keyboard shortcut (in the canvas `eventFilter`); `_current_file_entry()` maps the on-screen picture back to its source `FileEntry` — first entry for 2D, per-timepoint for 2D-T, position-sorted z-index for 3D/3D-T (falling back to t=0 for grouped 4D that only indexes the first timepoint), orient-group for MULTI, representative mid-slice for MPR reformats. NIfTI/plain images fall back to name+format+geometry so behaviour is uniform.
2. **Tag survey (user request "give me a list").** Dumped the full header from a real fixture (`alldata_backup/dicom/original/bpd3_20100419_1.dcm`, AGFA CR) and presented the ~40 available fields grouped (equipment, plate/detector, personnel, image details, identifiers, plus AGFA private dose tags) for the user to choose additions.
3. **Collapsible detail groups (user choice: extras in lower-right, expand on click).** Added `detail_groups(path)` returning five `(title, [lines])` sections — **Equipment / Plate / Staff / Image / IDs** — from ~36 additional tags fetched in the *same* cached read (extended `_ALL_TAGS`). Only populated fields appear; person names de-caret via `_person()`; UIDs shortened to last 14 chars. The canvas bottom-right column now renders **line-by-line** (unlike the other three corners, which draw as one block) so each group header gets a recorded hit-rect (`_ov_header_rects`); a left click toggles expand/collapse (`_ov_expanded` set) and is consumed in `mousePressEvent` *before* the W/L-drag/ROI/TC modes can react, so toggling a group never disturbs windowing. Expansion state lives on the canvas and persists across slice/time scrubbing and series reloads. Headers drawn in accent blue `#7c8fbd` to signal clickability; detail lines in normal overlay text.

**What we got.** Working overlay verified on the AGFA CR fixture. Header-read cost measured **~1 ms cold, ~90 µs cached** (with `_CACHE.clear()` between) — scrubbing stays smooth. All five groups format cleanly: Equipment (`AGFA ADC_51xx`, Station `WQ11PE30I29X`, S/N 1013, SW VIPS1300, institution/dept/address); Plate (`JH04CE (code35)`, `24CMX30CM PORTRAIT`, Sensitivity 400, Exposures 781, Proc code); Staff (Ref/Perf/Read physicians); Image (`DERIVED/PRIMARY`, CHEST, View AP, 12-bit MONOCHROME1, `Rescale ×1 +0 LOG_E REL`, created 2008-09-06 18:39:51); IDs (Acc `3S6OV97JFMHY`, ID issuer + Deident `DICOGNITO`, shortened Study/Series/SOP UIDs). Missing/unreadable files degrade to empty strings, no crash. `py_compile` + full import chain pass in the `viewer_vidi` conda env. README updated (control docs + package-layout line).

**Try next.** Known limitation: expanding all five groups on a small panel can run the bottom-right column up into the top-right block — clips gracefully but overlaps. Candidate fixes if it bites in practice: a scroll region, an "only one group open at a time" accordion, or a max-height clamp. Also open: whether to surface AGFA private dose indicators (`0019,xxxx`, e.g. `0.93/2.10`, `0.52`) as an optional group. Privacy note flagged to user: PatientName/ID render top-left, so toggle off before screenshots that leave the machine.

---

## P2 — Layer-by-layer input probe; bypass Qt via kernel evdev  ·  2026-07-17
- **Anchor:** `2a91e4f`

**Assumption.** Some layer between mouse and app accumulates tilt detents and flushes only on a full/second detent. Initial hypothesis: libinput's hi-res (v120) wheel handling, or the kernel `hid-logitech-hidpp` multiplier.

**What we did.** Probed every layer of the Linux input stack in isolation (all probe scripts in session scratchpad, results reproduced here):
1. **Kernel (evdev):** raw read of `/dev/input/event7` (G502 via Lightspeed receiver, `hid-logitech-hidpp`, HID++ 4.2) decoding `struct input_event`. 
2. **libinput config:** toggled `libinput High Resolution Wheel Scroll Enabled` 0/1 via `xinput` (Ubuntu 24.04, libinput 1.25.0, xf86-input-libinput 1.4.0, X11 session).
3. **Qt delivery:** probe window logging every `QWheelEvent` (`angleDelta`, `pixelDelta`, phase, source); repeated with `Qt.AA_CompressHighFrequencyEvents` disabled.
4. **X server delivery:** `xev`, watching legacy scroll buttons 6/7.

Findings: kernel emits `REL_HWHEEL ±1` + `REL_HWHEEL_HI_RES ±120` immediately for **every** single click (nothing accumulated; hold auto-repeats at ~100 ms; wheel wobble adds stray vertical ±15 hi-res events). Hi-res toggle: no effect. `xev`: X server delivers every detent 1:1 as button 6/7. Qt probe: isolated clicks **never delivered**; first event of a burst arrives as −240/−360 (2–3 detents flushed at once), proving Qt's scroll-valuator baseline goes stale during idle. Event compression off: no change. **Conclusion: Qt 5.15 xcb loses isolated horizontal scroll detents; not fixable from app-level Qt code.**

Fix: new `tilt_evdev.py` (stdlib-only) — `find_tilt_devices()` parses `/proc/bus/input/devices` for the `REL_HWHEEL` capability bit; `TiltWheelReader` reads `/dev/input/event*` on a daemon thread (select loop, 3 s hotplug rescan for receiver reconnects) and emits one Qt signal per detent (+1 right / −1 left). `MainWindow` routes it to `active_cell().step_time(steps, wrap=True)`, gated on `QApplication.activeWindow()` (evdev is global). `ViewCell.qt_tilt_suppressed` makes the Qt wheel path consume tilt events without stepping (no double-steps during holds). Without read permission (`input` group) it prints a hint and falls back to the Qt path. One-time setup: `sudo usermod -aG input $USER`.

**What we got.** User-confirmed on hardware: every single tilt click steps exactly one frame, both directions, no warm-up, direction changes instant. 12/12 headless checks pass (wrap both ways, suppression, discovery finds `event7`, fallback boot without permissions). macOS path untouched (pure Qt).

**Try next.** Soak-test in daily use, then merge `wip/wheel-tilt-scrub` → `master`. Open: single-click tilt behavior on macOS Qt (may or may not share the Qt 5.15 bug — different QPA plugin); revisit if the G502 is ever used there.

## P1 — Wheel-tilt time scrub via Qt horizontal wheel events  ·  2026-07-17
- **Anchor:** `8bb91c7`

**Assumption.** The G502 tilt wheel reaches the app as ordinary horizontal scroll (`QWheelEvent.angleDelta().x()`, tilt-left = +120), so routing it in the existing wheel path to the time slider is sufficient; holding the tilt auto-repeats at OS level giving continuous scrubbing for free.

**What we did.** In `ViewCell.eventFilter` (Wheel branch): if `abs(angleDelta.x()) >= abs(angleDelta.y())`, treat as tilt → `_scroll_time(tilt, wrap=True)`; tilt right = forward, wrap-around at series ends like a clinical cine loop (user-approved design). `_scroll_time` gained a `wrap` parameter; Shift+scroll (clamped time), plain scroll (slices), Ctrl+scroll (zoom) unchanged. Verified headlessly (offscreen QPA, synthetic `QWheelEvent`s): 7/7 checks (step both directions, wrap both ends, axis non-interference).

**What we got.** Feature worked under synthetic events and partially on hardware: holds and rapid clicking scrub correctly, but the first 2–3 isolated clicks did nothing and a direction change reset the "warm-up" — classic accumulator signature, located somewhere upstream of the app.

**Try next.** Probe each layer of the input stack (kernel evdev → libinput/X server → Qt) with isolated instrumentation to find which one buffers the first detent. → became P2.
