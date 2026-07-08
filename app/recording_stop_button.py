"""自動記録中に画面右下へ表示する記録停止ボタン（赤く点滅）。"""

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPushButton, QWidget

from app import constants

_BLINK_INTERVAL_MS = 500
_BUTTON_SIZE = 40
_MARGIN = 20

_STYLE_ON = (
    "QPushButton { background-color: #d40000; color: white; border-radius: 20px;"
    " font-size: 16px; }"
)
_STYLE_OFF = (
    "QPushButton { background-color: #7a0000; color: white; border-radius: 20px;"
    " font-size: 16px; }"
)


class RecordingStopButton(QWidget):
    stop_requested = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        self._button = QPushButton("■", self)
        self._button.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        self._button.setToolTip(constants.STOP_BUTTON_TOOLTIP)
        self._button.setStyleSheet(_STYLE_ON)
        self._button.clicked.connect(self.stop_requested)
        self._blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._move_to_bottom_right()

    def show_blinking(self) -> None:
        self.show()
        self._blink_timer.start(_BLINK_INTERVAL_MS)

    def hide_and_stop_blinking(self) -> None:
        self._blink_timer.stop()
        self.hide()

    def contains_point(self, x: int, y: int) -> bool:
        """スクリーン座標がこのボタン上かどうか（記録から除外するために使う）。"""
        return self.frameGeometry().contains(x, y)

    def _toggle_blink(self) -> None:
        self._blink_on = not self._blink_on
        self._button.setStyleSheet(_STYLE_ON if self._blink_on else _STYLE_OFF)

    def _move_to_bottom_right(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.right() - _BUTTON_SIZE - _MARGIN,
            screen.bottom() - _BUTTON_SIZE - _MARGIN,
        )
