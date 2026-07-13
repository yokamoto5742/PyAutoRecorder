"""要素ハイライト: カーソル下のUIA要素の矩形に赤枠オーバーレイを重ねて表示する。

要素ピッカーの実行中に、どのコントロールが取得対象かをユーザーへ示す。
矩形の取得はワーカースレッドで行い、GUIスレッドへはSignalで通知する
（UIAの応答待ちでマウスやGUIがカクつくのを防ぐ）。
"""

import threading

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from service.ui_selector import rect_from_cursor

_POLL_INTERVAL_SEC = 0.2
_BORDER_WIDTH = 3
_BORDER_COLOR = "#d40000"


class _HighlightOverlay(QWidget):
    """入力を透過する赤枠だけのウィンドウ。UIAの要素判定にも映らない。"""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        pen = QPen(QColor(_BORDER_COLOR))
        pen.setWidth(_BORDER_WIDTH)
        painter.setPen(pen)
        half = _BORDER_WIDTH // 2
        painter.drawRect(self.rect().adjusted(half, half, -half - 1, -half - 1))


class ElementHighlighter(QObject):
    """カーソル下の要素をポーリングして赤枠を追従させる。start()/stop()で制御する。"""

    _rect_polled = Signal(object)  # (left, top, right, bottom) | None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlay = _HighlightOverlay()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._rect_polled.connect(self._on_rect_polled)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread = None
        self._overlay.hide()

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(_POLL_INTERVAL_SEC):
            try:
                rect = rect_from_cursor()
            except Exception:
                rect = None  # 取得失敗時は枠を消すだけで継続する
            self._rect_polled.emit(rect)

    def _on_rect_polled(self, rect: tuple[int, int, int, int] | None) -> None:
        if self._stop_event.is_set():
            return  # stop()後に届いた通知は無視する
        if rect is None:
            self._overlay.hide()
            return
        self._overlay.setGeometry(_physical_to_logical(*rect))
        if not self._overlay.isVisible():
            self._overlay.show()


def _physical_to_logical(left: int, top: int, right: int, bottom: int) -> QRect:
    """UIAの物理ピクセル矩形をQtの論理座標矩形へ変換する。"""
    ratio = QGuiApplication.primaryScreen().devicePixelRatio()
    return QRect(
        round(left / ratio),
        round(top / ratio),
        round((right - left) / ratio),
        round((bottom - top) / ratio),
    )
