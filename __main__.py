import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter

from .main_window import MainWindow

_ICON_PATH = os.path.join(os.path.dirname(__file__), "icons", "vidi.svg")


def _make_icon() -> QIcon:
    try:
        from PyQt5.QtSvg import QSvgRenderer
        renderer = QSvgRenderer(_ICON_PATH)
        pm = QPixmap(256, 256)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        renderer.render(p)
        p.end()
        return QIcon(pm)
    except Exception:
        return QIcon(_ICON_PATH)


def main():
    # Set backend before QApplication so matplotlib finds Qt5 on all platforms.
    try:
        import matplotlib
        matplotlib.use('Qt5Agg')
    except ImportError:
        pass

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setWindowIcon(_make_icon())   # controls the macOS dock icon
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
