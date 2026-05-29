"""Categorical colors for segmentation label overlays."""
from __future__ import annotations

# Distinct, saturated colors that read well over greyscale anatomy.
MASK_PALETTE: list[tuple[int, int, int]] = [
    (239,  83,  80),   # red
    (66, 165, 245),    # blue
    (102, 187, 106),   # green
    (255, 167,  38),   # orange
    (171,  71, 188),   # purple
    (38, 198, 218),    # cyan
    (255, 238,  88),   # yellow
    (236,  64, 122),   # pink
]


def color_for_label(label: int, index: int) -> tuple[int, int, int]:
    """Deterministic RGB for a label. `index` is the label's rank among a mask's
    sorted nonzero labels, so the first label is always palette[0], and so on."""
    return MASK_PALETTE[index % len(MASK_PALETTE)]
