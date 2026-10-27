"""Repro: annotation_export.window_to_uint8 rounds (+0.5) while the canvas (windowing.render_to_rgb) truncates,
so the saved PNG/JPEG differ from the on-screen render by +1 grey level (−1 when inverted) on ~half the pixels."""
import sys; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np
from viewer_vidi.annotation_export import window_to_uint8
from viewer_vidi.windowing import render_to_rgb, wl_from_percentiles
from viewer_vidi.colormaps import COLORMAPS, COLORMAPS_INV
ramp = np.linspace(-100, 4200, 512 * 512, dtype=np.float32).reshape(512, 512)
for inv in (False, True):
    ex = window_to_uint8(ramp, 2048.0, 4096.0, inv)
    cv = render_to_rgb(ramp, 2048.0, 4096.0, (COLORMAPS_INV if inv else COLORMAPS)["Gray"])[..., 0]
    d = ex.astype(int) - cv.astype(int)
    print(f"invert={inv}: {(d != 0).sum()}/{d.size} px differ, export-canvas in [{d.min()},{d.max()}]")
const = np.full((4, 4), 100.0, np.float32); wc, ww = wl_from_percentiles(const)
print(f"constant image wl=({wc},{ww}): export={window_to_uint8(const, wc, ww)[0,0]} canvas={render_to_rgb(const, wc, ww, COLORMAPS['Gray'])[0,0,0]}")
hu = np.array([[40.0]], np.float32)
print(f"HU 40 @ wc40/ww400: export={window_to_uint8(hu, 40, 400)[0,0]} canvas={render_to_rgb(hu, 40, 400, COLORMAPS['Gray'])[0,0,0]}")
