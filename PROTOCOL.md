# Protocol (lab notebook) — viewer-vidi

> Running record of every experiment/iteration: **Assumption → What we did → What we got → Try next**.
> Newest entry on top. This is the journey, dead-ends included — settled conclusions get promoted to
> `MILESTONES.md`, and the link is two-way (each entry gets `· → M<k>` once promoted; the milestone
> carries a `Derived from: P…` line back here). Add entries with the `/protocol` skill.
>
> Keep entries **rich** — this is the document-grade source you compile reports/methods/manuscripts
> from (exact configs, numbers, what failed and why), with *more* detail than Claude memory, not less.

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
