"""Core image rendering widget with W/L drag and ROI W/L modes."""
from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QColor, QFont, QPen
from PyQt5.QtWidgets import QWidget, QSizePolicy

from .windowing import render_to_rgb, wl_from_percentiles
from .colormaps import COLORMAPS
from .gpu import GPU

# Palette for TC point markers (visible on dark background)
TC_COLORS = [
    "#f5c842", "#ff6b8a", "#7dd3fc", "#86efac",
    "#c4b5fd", "#fb923c", "#a3e635", "#67e8f9",
]
_MARKER_R = 6   # marker radius in screen pixels


class ImageCanvas(QWidget):
    """Displays a single 2-D float32 image slice via QPainter.

    Two interaction modes (set via set_wl_mode):
      "drag" — left-drag adjusts window/level (default)
      "roi"  — drag a rectangle; release sets W/L from region stats
    """

    wl_changed          = pyqtSignal(float, float)
    pixel_hovered       = pyqtSignal(int, int, float)
    tc_points_changed   = pyqtSignal(list)    # list of (ix, iy) image coords
    roi_tc_polys_changed = pyqtSignal(object) # list of np.ndarray each (N,2) image (x,y)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canvas")
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self._pixels:   Optional[np.ndarray] = None   # float32 (H, W)
        self._qimage:   Optional[QImage]     = None
        self._rgb_buf:  Optional[np.ndarray] = None   # kept alive for QImage

        self._wc: float = 2048.0
        self._ww: float = 4096.0
        self._cmap_name: str = "Gray"
        self._aspect: float = 1.0

        self._wl_mode: str = "drag"   # "drag" | "roi" | "roi_tc" | "tc"

        # drag-mode state
        self._drag_start: Optional[QPoint] = None
        self._drag_wc:    float = 0.0
        self._drag_ww:    float = 0.0

        # roi mode state (rectangular W/L selection)
        self._roi_start: Optional[QPoint] = None
        self._roi_end:   Optional[QPoint] = None

        # roi_tc mode state (freehand lasso, multiple polygons)
        self._roi_tc_polys: list[np.ndarray] = []   # stored, (N,2) image (x,y) each
        self._lasso_screen: list[tuple[int,int]] = []  # current drag path, screen coords

        # tc-mode state (persists across mode switches so markers stay visible)
        self._tc_points: list[tuple[int, int]] = []

        # GPU-resident copy of the current slice (None on CPU-only systems)
        self._pixels_gpu = None

        # pan/zoom state
        self._pan_x:         int   = 0
        self._pan_y:         int   = 0
        self._zoom:          float = 1.0
        self._right_press:   Optional[QPoint] = None
        self._pan_at_press:  tuple[int, int]  = (0, 0)
        self._right_dragged: bool  = False

        self._label: str = ""

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_image(self, pixels: Optional[np.ndarray], aspect: float = 1.0,
                  reset_view: bool = True) -> None:
        self._pixels = pixels
        self._aspect = aspect
        if reset_view:
            self._pan_x = 0
            self._pan_y = 0
            self._zoom  = 1.0
        # Upload to GPU once; every subsequent _rebuild reuses it without
        # re-transferring, so W/L drag and slice navigation stay fast.
        self._pixels_gpu = GPU.to_device(pixels) if pixels is not None else None
        self._rebuild()

    def set_wl(self, wc: float, ww: float) -> None:
        self._wc = wc
        self._ww = max(1.0, ww)
        self._rebuild()

    def set_colormap(self, name: str) -> None:
        if name in COLORMAPS:
            self._cmap_name = name
            self._rebuild()

    def set_label(self, text: str) -> None:
        self._label = text
        self.update()

    def set_wl_mode(self, mode: str) -> None:
        """Switch between "drag", "roi", "roi_tc", and "tc" interaction modes."""
        self._wl_mode      = mode
        self._roi_start    = None
        self._roi_end      = None
        self._lasso_screen = []
        self.setCursor(Qt.CrossCursor if mode in ("roi", "roi_tc", "tc") else Qt.ArrowCursor)
        self.update()

    def clear_roi_tc_polys(self) -> None:
        self._roi_tc_polys = []
        self._lasso_screen = []
        self.roi_tc_polys_changed.emit([])
        self.update()

    def clear_tc_points(self) -> None:
        self._tc_points.clear()
        self.tc_points_changed.emit([])
        self.update()

    def tc_points(self) -> list[tuple[int, int]]:
        return list(self._tc_points)

    def wl(self) -> tuple[float, float]:
        return self._wc, self._ww

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        if self._pixels is None:
            self._qimage = None
            self.update()
            return
        cmap = COLORMAPS[self._cmap_name]
        src  = self._pixels_gpu if self._pixels_gpu is not None else self._pixels
        self._rgb_buf = render_to_rgb(src, self._wc, self._ww, cmap)
        h, w = self._rgb_buf.shape[:2]
        self._qimage = QImage(self._rgb_buf.data, w, h, w * 3, QImage.Format_RGB888)
        self.update()

    def _dest_rect(self) -> QRect:
        """Compute where the image is drawn inside the widget (accounts for zoom/pan)."""
        if self._qimage is None:
            return QRect(0, 0, self.width(), self.height())
        img_w = self._qimage.width()
        img_h = self._qimage.height()
        phys_w = float(img_w)
        phys_h = float(img_h) * self._aspect
        scale  = min(self.width() / phys_w, self.height() / phys_h) * self._zoom
        dw = int(phys_w * scale)
        dh = int(phys_h * scale)
        x0 = (self.width()  - dw) // 2 + self._pan_x
        y0 = (self.height() - dh) // 2 + self._pan_y
        return QRect(x0, y0, dw, dh)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        if self._qimage is None:
            painter.setPen(QColor(69, 71, 90))
            painter.setFont(QFont("Segoe UI", 14))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image")
            painter.end()
            return

        r = self._dest_rect()
        painter.drawImage(r, self._qimage)

        # ROI rubber-band (rectangular W/L mode)
        if self._roi_start is not None and self._roi_end is not None:
            rx = min(self._roi_start.x(), self._roi_end.x())
            ry = min(self._roi_start.y(), self._roi_end.y())
            rw = abs(self._roi_end.x() - self._roi_start.x())
            rh = abs(self._roi_end.y() - self._roi_start.y())
            painter.setPen(QPen(QColor(255, 220, 0, 220), 1, Qt.DashLine))
            painter.setBrush(QColor(255, 220, 0, 25))
            painter.drawRect(rx, ry, rw, rh)

        # Stored ROI-TC polygons (freehand, multiple)
        for i, poly_img in enumerate(self._roi_tc_polys):
            c = QColor(TC_COLORS[i % len(TC_COLORS)])
            pts_screen = [QPoint(*self._screen_coords(int(px), int(py))) for px, py in poly_img]
            if len(pts_screen) >= 2:
                painter.setPen(QPen(c, 2, Qt.SolidLine))
                painter.setBrush(QColor(c.red(), c.green(), c.blue(), 35))
                from PyQt5.QtGui import QPolygon
                painter.drawPolygon(QPolygon(pts_screen))

        # Current lasso path being drawn
        if self._lasso_screen and len(self._lasso_screen) >= 2:
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            from PyQt5.QtGui import QPolygon
            pts = [QPoint(x, y) for x, y in self._lasso_screen]
            painter.drawPolyline(QPolygon(pts))

        # TC point markers (always drawn when points exist)
        if self._tc_points:
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            for i, (ix, iy) in enumerate(self._tc_points):
                sx, sy = self._screen_coords(ix, iy)
                c = QColor(TC_COLORS[i % len(TC_COLORS)])
                painter.setPen(QPen(c, 2))
                painter.setBrush(QColor(c.red(), c.green(), c.blue(), 60))
                painter.drawEllipse(sx - _MARKER_R, sy - _MARKER_R,
                                    _MARKER_R * 2, _MARKER_R * 2)
                painter.setPen(c)
                painter.drawText(sx + _MARKER_R + 2, sy - _MARKER_R,
                                 str(i + 1))

        if self._label:
            painter.setPen(QColor(108, 112, 134))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(self.rect().adjusted(6, 4, -6, -4),
                             Qt.AlignTop | Qt.AlignLeft, self._label)

        painter.end()

    # ── Mouse interaction ──────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if self._wl_mode == "drag":
                self._drag_start = event.pos()
                self._drag_wc    = self._wc
                self._drag_ww    = self._ww
            elif self._wl_mode == "roi":
                self._roi_start = event.pos()
                self._roi_end   = event.pos()
            elif self._wl_mode == "roi_tc":
                self._lasso_screen = [(event.x(), event.y())]
            elif self._wl_mode == "tc":
                self._tc_handle_click(event.pos())
        elif event.button() == Qt.RightButton:
            self._right_press   = event.pos()
            self._pan_at_press  = (self._pan_x, self._pan_y)
            self._right_dragged = False

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            if self._wl_mode == "drag" and self._drag_start is not None:
                dx = event.x() - self._drag_start.x()
                dy = event.y() - self._drag_start.y()
                sensitivity = max(self._drag_ww / max(self.width(), 1), 1.0)
                self._ww = max(1.0, self._drag_ww + dx * sensitivity * 2.0)
                self._wc = self._drag_wc - dy * sensitivity
                self._rebuild()
                self.wl_changed.emit(self._wc, self._ww)
            elif self._wl_mode == "roi" and self._roi_start is not None:
                self._roi_end = event.pos()
                self.update()
            elif self._wl_mode == "roi_tc" and self._lasso_screen:
                # Throttle: only add point if moved > 3px from last
                lx, ly = self._lasso_screen[-1]
                if abs(event.x() - lx) > 3 or abs(event.y() - ly) > 3:
                    self._lasso_screen.append((event.x(), event.y()))
                    self.update()
            # TC mode: no drag action (clicks only)

        if event.buttons() & Qt.RightButton and self._right_press is not None:
            dx = event.x() - self._right_press.x()
            dy = event.y() - self._right_press.y()
            if not self._right_dragged and (abs(dx) > 4 or abs(dy) > 4):
                self._right_dragged = True
            if self._right_dragged:
                self._pan_x = self._pan_at_press[0] + dx
                self._pan_y = self._pan_at_press[1] + dy
                self.update()

        # Pixel value under cursor
        if self._pixels is not None:
            ix, iy = self._image_coords(event.x(), event.y())
            h, w = self._pixels.shape
            if 0 <= iy < h and 0 <= ix < w:
                self.pixel_hovered.emit(ix, iy, float(self._pixels[iy, ix]))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if self._wl_mode == "drag":
                self._drag_start = None
            elif self._wl_mode == "roi":
                if self._roi_start is not None and self._roi_end is not None:
                    self._apply_roi_wl()
                self._roi_start = None
                self._roi_end   = None
                self.update()
            elif self._wl_mode == "roi_tc":
                self._finish_lasso()
        elif event.button() == Qt.RightButton:
            if not self._right_dragged and self._right_press is not None:
                if self._wl_mode == "tc":
                    self._tc_handle_right(self._right_press)
                elif self._wl_mode == "roi_tc":
                    self._roi_tc_remove_nearest(self._right_press)
            self._right_press   = None
            self._right_dragged = False

    def wheelEvent(self, event) -> None:
        event.ignore()

    def zoom_wheel(self, delta: int) -> None:
        """Zoom in/out (called from parent eventFilter on Ctrl+scroll)."""
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._zoom = max(0.1, min(20.0, self._zoom * factor))
        self.update()

    # ── Coordinate helpers ─────────────────────────────────────────────────────

    def _image_coords(self, wx: int, wy: int) -> tuple[int, int]:
        """Convert widget pixel coords to image array (col, row) indices."""
        if self._qimage is None:
            return 0, 0
        r = self._dest_rect()
        if r.width() == 0 or r.height() == 0:
            return 0, 0
        img_w = self._qimage.width()
        img_h = self._qimage.height()
        ix = int((wx - r.x()) * img_w / r.width())
        iy = int((wy - r.y()) * img_h / r.height())
        return ix, iy

    def _screen_coords(self, ix: int, iy: int) -> tuple[int, int]:
        """Convert image (col, row) to widget pixel coords."""
        if self._qimage is None:
            return 0, 0
        r = self._dest_rect()
        img_w = self._qimage.width()
        img_h = self._qimage.height()
        if img_w == 0 or img_h == 0:
            return 0, 0
        sx = r.x() + int(ix * r.width()  / img_w)
        sy = r.y() + int(iy * r.height() / img_h)
        return sx, sy

    def _tc_handle_click(self, pos: QPoint) -> None:
        """Add a point, or remove it if clicking within marker radius."""
        if self._pixels is None:
            return
        # Check if clicking near an existing marker (in screen space)
        for i, (px, py) in enumerate(self._tc_points):
            sx, sy = self._screen_coords(px, py)
            if abs(pos.x() - sx) <= _MARKER_R + 4 and abs(pos.y() - sy) <= _MARKER_R + 4:
                self._tc_points.pop(i)
                self.tc_points_changed.emit(list(self._tc_points))
                self.update()
                return
        # Add new point if inside image
        ix, iy = self._image_coords(pos.x(), pos.y())
        h, w = self._pixels.shape
        if 0 <= iy < h and 0 <= ix < w:
            self._tc_points.append((ix, iy))
            self.tc_points_changed.emit(list(self._tc_points))
            self.update()

    def _tc_handle_right(self, pos: QPoint) -> None:
        """Right-click removes the nearest point."""
        if not self._tc_points:
            return
        nearest = min(range(len(self._tc_points)),
                      key=lambda i: (self._screen_coords(*self._tc_points[i])[0] - pos.x()) ** 2
                                  + (self._screen_coords(*self._tc_points[i])[1] - pos.y()) ** 2)
        self._tc_points.pop(nearest)
        self.tc_points_changed.emit(list(self._tc_points))
        self.update()

    def _finish_lasso(self) -> None:
        """Close the freehand lasso path, convert to image coords, add to polygon list."""
        pts = self._lasso_screen
        self._lasso_screen = []
        if self._pixels is None or len(pts) < 3:
            self.update()
            return
        # Convert screen → image coords, removing duplicates
        img_pts = []
        for sx, sy in pts:
            ix, iy = self._image_coords(sx, sy)
            if not img_pts or (ix, iy) != img_pts[-1]:
                img_pts.append((ix, iy))
        if len(img_pts) < 3:
            self.update()
            return
        poly = np.array(img_pts, dtype=np.float32)   # (N, 2) as (x, y)
        self._roi_tc_polys.append(poly)
        self.roi_tc_polys_changed.emit(list(self._roi_tc_polys))
        self.update()

    def _roi_tc_remove_nearest(self, pos: QPoint) -> None:
        """Right-click: remove the polygon whose centroid is nearest to click."""
        if not self._roi_tc_polys:
            return
        try:
            from matplotlib.path import Path as MplPath
            # Prefer the polygon that contains the click
            ix, iy = self._image_coords(pos.x(), pos.y())
            click_pt = np.array([[ix, iy]], dtype=np.float32)
            for i, poly in enumerate(self._roi_tc_polys):
                if MplPath(poly).contains_point((ix, iy)):
                    self._roi_tc_polys.pop(i)
                    self.roi_tc_polys_changed.emit(list(self._roi_tc_polys))
                    self.update()
                    return
        except ImportError:
            pass
        # Fallback: remove by nearest centroid in screen space
        sx, sy = pos.x(), pos.y()
        def centroid_dist(poly):
            cx = np.mean([self._screen_coords(int(p[0]), int(p[1]))[0] for p in poly])
            cy = np.mean([self._screen_coords(int(p[0]), int(p[1]))[1] for p in poly])
            return (cx - sx) ** 2 + (cy - sy) ** 2
        idx = min(range(len(self._roi_tc_polys)), key=lambda i: centroid_dist(self._roi_tc_polys[i]))
        self._roi_tc_polys.pop(idx)
        self.roi_tc_polys_changed.emit(list(self._roi_tc_polys))
        self.update()

    def _apply_roi_wl(self) -> None:
        """Compute W/L from pixel intensities inside the drawn rectangle."""
        if self._pixels is None or self._roi_start is None or self._roi_end is None:
            return

        x1, y1 = self._image_coords(self._roi_start.x(), self._roi_start.y())
        x2, y2 = self._image_coords(self._roi_end.x(),   self._roi_end.y())

        h, w = self._pixels.shape
        r0, r1 = sorted([max(0, min(h - 1, y1)), max(0, min(h - 1, y2))])
        c0, c1 = sorted([max(0, min(w - 1, x1)), max(0, min(w - 1, x2))])

        if r1 <= r0 or c1 <= c0:
            return   # degenerate rect

        roi = self._pixels[r0:r1 + 1, c0:c1 + 1]
        wc, ww = wl_from_percentiles(roi)
        self._wc = wc
        self._ww = max(1.0, ww)
        self._rebuild()
        self.wl_changed.emit(self._wc, self._ww)
