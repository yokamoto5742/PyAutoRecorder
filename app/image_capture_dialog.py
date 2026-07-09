"""画像取得ダイアログ: 全画面スクリーンショットから認識対象の矩形を切り抜く。"""

import base64

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from app import constants

_MIN_CAPTURE_PX = 4


def capture_screen_region(parent: QWidget | None = None) -> str:
    """スクリーンショットから矩形を選択させ、PNGのbase64を返す。中止時は空文字。"""
    screen = QGuiApplication.primaryScreen()
    screenshot = screen.grabWindow(0)
    dialog = _RegionSelectDialog(screenshot, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return ""
    return _pixmap_to_base64(dialog.selected_pixmap())


def load_image_file(parent: QWidget | None = None) -> str:
    """保存済み画像ファイルを選択させ、PNGのbase64を返す。中止・失敗時は空文字。"""
    path, _ = QFileDialog.getOpenFileName(
        parent, constants.DIALOG_LOAD_IMAGE_TITLE, "", constants.FILTER_IMAGE_FILES
    )
    if not path:
        return ""
    pixmap = QPixmap(path)
    if pixmap.isNull():
        QMessageBox.warning(
            parent, constants.DIALOG_LOAD_IMAGE_TITLE, constants.MSG_IMAGE_LOAD_FAILED
        )
        return ""
    return _pixmap_to_base64(pixmap)


def _pixmap_to_base64(pixmap: QPixmap) -> str:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return base64.b64encode(buffer.data().data()).decode("ascii")


class _RegionSelectDialog(QDialog):
    """全画面にスクリーンショットを表示し、ドラッグで矩形を選択させる。"""

    def __init__(self, screenshot: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(constants.DIALOG_CAPTURE_TITLE)
        # Qt.Window を指定しないと親の子ウィジェット扱いになり全画面表示されない
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._screenshot = screenshot
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.setGeometry(QGuiApplication.primaryScreen().geometry())
        self.showFullScreen()

    def selected_pixmap(self) -> QPixmap:
        rect = self._selection_rect()
        # 高DPI環境ではスクリーンショットが論理座標より大きいため比率で変換する
        ratio = self._screenshot.width() / self.width()
        source = QRect(
            round(rect.x() * ratio),
            round(rect.y() * ratio),
            round(rect.width() * ratio),
            round(rect.height() * ratio),
        )
        return self._screenshot.copy(source)

    def _selection_rect(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._screenshot)
        painter.setPen(Qt.GlobalColor.red)
        rect = self._selection_rect()
        if not rect.isNull():
            painter.drawRect(rect)
        painter.drawText(
            self.rect().adjusted(10, 10, -10, -10),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            constants.MSG_CAPTURE_INSTRUCTION,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._origin = event.position().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._current = event.position().toPoint()
        rect = self._selection_rect()
        if rect.width() >= _MIN_CAPTURE_PX and rect.height() >= _MIN_CAPTURE_PX:
            self.accept()
        else:
            self._origin = None
            self._current = None
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
