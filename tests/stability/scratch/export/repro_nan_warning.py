"""Repro: NaN pixels reach (alpha*255+0.5).astype(uint8) -> numpy RuntimeWarning 'invalid value encountered in cast' on stderr; NaN -> 0 (255 when inverted)."""
import sys, warnings; sys.path.insert(0, "/tmp/claude-1000/-home-zsk/714d8704-0f43-42f9-ba79-d4ec2a9ad51f/scratchpad/stab")
import harness as H; H.register_package()
import numpy as np
from viewer_vidi.annotation_export import window_to_uint8
px = np.array([[np.nan, np.inf, -np.inf, 500.0]], np.float32)
print("plain  :", window_to_uint8(px, 500.0, 1000.0)[0].tolist())
print("invert :", window_to_uint8(px, 500.0, 1000.0, True)[0].tolist())
