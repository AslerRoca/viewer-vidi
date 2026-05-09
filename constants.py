import os

def _default_data_root():
    candidates = [
        "/Volumes/ressd/research",   # macOS
        "/media/zsk/ressd/research", # Linux
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return os.path.expanduser("~")

DATA_ROOT = _default_data_root()

STYLE_PATH = os.path.join(os.path.dirname(__file__), "style.qss")

TREE_WIDTH = 300
TOOLBAR_HEIGHT = 36

# Dark palette colours (also referenced in style.qss)
BG_DARK    = "#1e1e2e"
BG_PANEL   = "#2a2a3e"
BG_CANVAS  = "#000000"
ACCENT     = "#7c8fbd"
TEXT       = "#cdd6f4"
TEXT_DIM   = "#6c7086"
BORDER     = "#45475a"

BADGE_COLORS = {
    "2D":    "#a6e3a1",
    "2D-T":  "#89dceb",
    "3D":    "#cba6f7",
    "3D-T":  "#fab387",
    "MULTI": "#f38ba8",
}

DEFAULT_FPS = 10
MAX_FPS     = 30
