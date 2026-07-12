"""子機: 手動記録用の常時最前面小窓。

左上角の赤いポインタ位置がクリック座標になる。ドラッグで移動し、
右クリックメニューからクリック方法を選ぶと本体リストに項目が追加される。
"""

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QMouseEvent, QMoveEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QMenu, QSpinBox, QVBoxLayout, QWidget

from app import constants
from service.models import ActionItem, ActionType

_POINTER_SIZE = 8
_BACKGROUND_COLOR = QColor("#ffff99")
_POINTER_COLOR = QColor("red")

_MENU_ACTIONS = [
    (constants.CHILD_MENU_LEFT, ActionType.LEFT_CLICK),
    (constants.CHILD_MENU_RIGHT, ActionType.RIGHT_CLICK),
    (constants.CHILD_MENU_DOUBLE, ActionType.DOUBLE_CLICK),
    (constants.CHILD_MENU_MIDDLE, ActionType.MIDDLE_CLICK),
    (constants.CHILD_MENU_MOVE_ONLY, ActionType.NONE),
]


class RecorderChildWindow(QWidget):
    def __init__(self, on_item_added: Callable[[ActionItem], None]) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._on_item_added = on_item_added
        self._drag_offset = QPoint()
        self.setWindowTitle(constants.CHILD_WINDOW_TITLE)
        self.setFixedSize(100, 70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_POINTER_SIZE + 4, _POINTER_SIZE + 4, 4, 4)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(0, 99999)
        self._interval_spin.setValue(1)
        layout.addWidget(self._interval_spin)
        self._coords_label = QLabel()
        self._coords_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._coords_label)
        self._update_coords_label()

    # --- 描画・座標表示 ---

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BACKGROUND_COLOR)
        painter.fillRect(0, 0, _POINTER_SIZE, _POINTER_SIZE, _POINTER_COLOR)

    def moveEvent(self, event: QMoveEvent) -> None:
        self._update_coords_label()
        super().moveEvent(event)

    def _update_coords_label(self) -> None:
        pointer = self.pos()
        self._coords_label.setText(f"{pointer.x()},{pointer.y()}")

    # --- ドラッグ移動と右クリックメニュー ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def _show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        for label, action_type in _MENU_ACTIONS:
            menu.addAction(
                label, lambda _checked=False, a=action_type: self._add_item(a)
            )
        menu.addSeparator()
        menu.addAction(constants.CHILD_MENU_CLOSE, self.close)
        menu.exec(global_pos)

    def _add_item(self, action_type: ActionType) -> None:
        pointer = self.pos()
        self._on_item_added(
            ActionItem(
                interval=self._interval_spin.value(),
                x=pointer.x(),
                y=pointer.y(),
                action=action_type,
            )
        )
