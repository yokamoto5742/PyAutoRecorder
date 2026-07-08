"""項目編集ダイアログ: 間隔・座標・クリック方法・キーボード操作・条件判断を編集する。"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import constants
from service.key_notation import SPECIAL_KEYS, parse
from service.models import ActionItem, ActionType, Condition, ConditionType

_COORD_MIN = -10000
_COORD_MAX = 20000

# キーボード操作欄への挿入ボタン: (表示名, 挿入文字列)
_INSERT_BUTTONS = [
    ("Shift+", "+"),
    ("Ctrl+", "^"),
    ("Alt+", "%"),
    ("Win+", "`"),
    ("Wait", "{WAIT}"),
    ("Clip", "{CLIP}"),
    ("Clear", "{CLEAR}"),
    ("IME", "{IME}"),
]


class ItemEditorDialog(QDialog):
    def __init__(self, item: ActionItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(constants.DIALOG_EDIT_TITLE)
        self._item = item
        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(item))
        layout.addWidget(self._build_condition_group(item.condition))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._on_action_changed()

    def _build_form(self, item: ActionItem) -> QFormLayout:
        form = QFormLayout()
        self._interval = QDoubleSpinBox()
        self._interval.setRange(0.0, 99999.0)
        self._interval.setDecimals(2)
        self._interval.setValue(item.interval)
        form.addRow(constants.LABEL_INTERVAL, self._interval)

        self._action = QComboBox()
        for value, label in constants.ACTION_LABELS.items():
            self._action.addItem(label, value)
        self._action.setCurrentIndex(self._action.findData(item.action.value))
        self._action.currentIndexChanged.connect(self._on_action_changed)
        form.addRow(constants.LABEL_ACTION, self._action)

        self._x = self._coord_spinbox(item.x)
        self._y = self._coord_spinbox(item.y)
        form.addRow(constants.LABEL_POSITION_X, self._x)
        form.addRow(constants.LABEL_POSITION_Y, self._y)

        drag_to = item.drag_to or (0, 0)
        self._drag_x = self._coord_spinbox(drag_to[0])
        self._drag_y = self._coord_spinbox(drag_to[1])
        form.addRow(constants.LABEL_DRAG_TO, self._pair(self._drag_x, self._drag_y))

        self._keys = QLineEdit(item.keys)
        form.addRow(constants.LABEL_KEYS, self._keys)
        form.addRow("", self._build_key_buttons())

        self._offset_x = self._coord_spinbox(item.repeat_offset[0])
        self._offset_y = self._coord_spinbox(item.repeat_offset[1])
        form.addRow(
            constants.LABEL_REPEAT_OFFSET, self._pair(self._offset_x, self._offset_y)
        )

        self._key_repeat = QCheckBox(constants.LABEL_KEY_REPEAT_INCREASE)
        self._key_repeat.setChecked(item.key_repeat_increase)
        form.addRow("", self._key_repeat)
        return form

    @staticmethod
    def _coord_spinbox(value: int | None) -> QSpinBox:
        box = QSpinBox()
        box.setRange(_COORD_MIN, _COORD_MAX)
        box.setValue(value if value is not None else 0)
        return box

    @staticmethod
    def _pair(first: QWidget, second: QWidget) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(first)
        row.addWidget(second)
        return container

    def _build_key_buttons(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        special_combo = QComboBox()
        for name in SPECIAL_KEYS:
            special_combo.addItem("{" + name + "}")
        insert_button = QPushButton("挿入")
        insert_button.clicked.connect(
            lambda: self._keys.insert(special_combo.currentText())
        )
        row.addWidget(special_combo)
        row.addWidget(insert_button)
        for label, text in _INSERT_BUTTONS:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, t=text: self._keys.insert(t))
            row.addWidget(button)
        return container

    def _build_condition_group(self, condition: Condition | None) -> QGroupBox:
        group = QGroupBox(constants.GROUP_CONDITION)
        group.setCheckable(True)
        group.setChecked(condition is not None)
        form = QFormLayout(group)
        self._condition_group = group

        self._condition_type = QComboBox()
        for value, label in constants.CONDITION_LABELS.items():
            self._condition_type.addItem(label, value)
        self._condition_type.currentIndexChanged.connect(
            self._on_condition_type_changed
        )
        form.addRow(constants.LABEL_CONDITION_TYPE, self._condition_type)

        self._condition_value = QLineEdit()
        form.addRow(constants.LABEL_CONDITION_VALUE, self._condition_value)

        self._condition_max_wait = QSpinBox()
        self._condition_max_wait.setRange(0, 99999)
        form.addRow(constants.LABEL_CONDITION_MAX_WAIT, self._condition_max_wait)

        if condition is not None:
            index = self._condition_type.findData(condition.condition_type.value)
            self._condition_type.setCurrentIndex(index)
            self._condition_value.setText(condition.value)
            self._condition_max_wait.setValue(condition.max_wait_sec)
        self._on_condition_type_changed()
        return group

    def _on_action_changed(self) -> None:
        action = ActionType(self._action.currentData())
        has_coords = action != ActionType.KEY_ONLY
        self._x.setEnabled(has_coords)
        self._y.setEnabled(has_coords)
        is_drag = action == ActionType.DRAG
        self._drag_x.setEnabled(is_drag)
        self._drag_y.setEnabled(is_drag)

    def _on_condition_type_changed(self) -> None:
        hint = constants.CONDITION_VALUE_HINTS.get(
            self._condition_type.currentData(), ""
        )
        self._condition_value.setPlaceholderText(hint)

    def _on_accept(self) -> None:
        try:
            parse(self._keys.text())
        except ValueError as e:
            QMessageBox.warning(
                self,
                constants.DIALOG_EDIT_TITLE,
                constants.MSG_INVALID_KEYS.format(error=e),
            )
            return
        self.accept()

    def edited_item(self) -> ActionItem:
        """編集結果を新しいActionItemとして返す。"""
        action = ActionType(self._action.currentData())
        has_coords = action != ActionType.KEY_ONLY
        return ActionItem(
            interval=self._interval.value(),
            x=self._x.value() if has_coords else None,
            y=self._y.value() if has_coords else None,
            action=action,
            keys=self._keys.text(),
            drag_to=(
                (self._drag_x.value(), self._drag_y.value())
                if action == ActionType.DRAG
                else None
            ),
            repeat_offset=(self._offset_x.value(), self._offset_y.value()),
            key_repeat_increase=self._key_repeat.isChecked(),
            condition=self._edited_condition(),
        )

    def _edited_condition(self) -> Condition | None:
        if not self._condition_group.isChecked():
            return None
        return Condition(
            condition_type=ConditionType(self._condition_type.currentData()),
            value=self._condition_value.text(),
            max_wait_sec=self._condition_max_wait.value(),
        )
