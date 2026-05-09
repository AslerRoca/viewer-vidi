import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from .main_window import MainWindow


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
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
