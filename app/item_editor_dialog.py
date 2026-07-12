"""項目編集ダイアログ: 間隔・座標・クリック方法・キーボード操作・条件判断を編集する。"""

import base64
import threading

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import constants
from app.image_capture_dialog import capture_screen_region, load_image_file
from service.key_notation import SPECIAL_KEYS, parse
from service.models import ActionItem, ActionType, Condition, ConditionType
from service.ui_selector import UiSelector, selector_from_cursor

_COORD_MIN = -10000
_COORD_MAX = 20000
_PICK_COUNTDOWN_SEC = 3
_PICK_TIMEOUT_SEC = 5.0

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
        # 拡大率が高い環境でもOK/キャンセルボタンが隠れないよう、入力項目をスクロール領域に入れる
        scroll_content = QWidget()
        form_layout = QVBoxLayout(scroll_content)
        form_layout.addLayout(self._build_form(item))
        form_layout.addWidget(self._build_selector_group(item.selector))
        form_layout.addWidget(self._build_condition_group(item.condition))
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
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

        self._app_path = QLineEdit(item.app_path)
        browse = QPushButton(constants.BUTTON_BROWSE_APP)
        browse.clicked.connect(self._browse_app_path)
        form.addRow(constants.LABEL_APP_PATH, self._pair(self._app_path, browse))
        return form

    def _browse_app_path(self) -> None:
        path_str, _filter = QFileDialog.getOpenFileName(
            self,
            constants.FILE_DIALOG_APP_TITLE,
            self._app_path.text(),
            constants.FILE_DIALOG_APP_FILTER,
        )
        if path_str:
            self._app_path.setText(path_str)

    @staticmethod
    def _coord_spinbox(value: int | None) -> QSpinBox:
        box = QSpinBox()
        box.setRange(_COORD_MIN, _COORD_MAX)
        box.setValue(value if value is not None else 0)
        return box

    @staticmethod
    def _pair(*widgets: QWidget) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            row.addWidget(widget)
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

    def _build_selector_group(self, selector: UiSelector | None) -> QGroupBox:
        group = QGroupBox(constants.GROUP_SELECTOR)
        group.setCheckable(True)
        group.setChecked(selector is not None)
        form = QFormLayout(group)
        self._selector_group = group
        current = selector or UiSelector()
        self._selector_class_name = current.class_name  # 表示せずそのまま引き継ぐ

        self._sel_automation_id = QLineEdit(current.automation_id)
        self._sel_name = QLineEdit(current.name)
        self._sel_control_type = QLineEdit(current.control_type)
        self._sel_window_id = QLineEdit(current.window_automation_id)
        self._sel_window_name = QLineEdit(current.window_name)
        self._sel_index = QSpinBox()
        self._sel_index.setRange(1, 999)
        self._sel_index.setValue(current.found_index)
        self._pick_button = QPushButton(constants.BUTTON_PICK_ELEMENT)
        self._pick_button.clicked.connect(self._start_pick)
        self._pick_timer = QTimer(self)
        self._pick_timer.setInterval(1000)
        self._pick_timer.timeout.connect(self._on_pick_tick)
        self._pick_remaining = 0

        form.addRow("", self._pick_button)
        form.addRow(constants.LABEL_SELECTOR_AUTOMATION_ID, self._sel_automation_id)
        form.addRow(constants.LABEL_SELECTOR_NAME, self._sel_name)
        form.addRow(constants.LABEL_SELECTOR_CONTROL_TYPE, self._sel_control_type)
        form.addRow(constants.LABEL_SELECTOR_WINDOW_ID, self._sel_window_id)
        form.addRow(constants.LABEL_SELECTOR_WINDOW_NAME, self._sel_window_name)
        form.addRow(constants.LABEL_SELECTOR_INDEX, self._sel_index)
        return group

    # --- 要素ピッカー: カウントダウン後にカーソル位置のコントロールを取り込む ---

    def _start_pick(self) -> None:
        self._pick_button.setEnabled(False)
        self._pick_remaining = _PICK_COUNTDOWN_SEC
        self._pick_button.setText(
            constants.BUTTON_PICK_COUNTDOWN.format(sec=self._pick_remaining)
        )
        self._pick_timer.start()

    def _on_pick_tick(self) -> None:
        self._pick_remaining -= 1
        if self._pick_remaining > 0:
            self._pick_button.setText(
                constants.BUTTON_PICK_COUNTDOWN.format(sec=self._pick_remaining)
            )
            return
        self._pick_timer.stop()
        self._pick_button.setText(constants.BUTTON_PICK_ELEMENT)
        self._pick_button.setEnabled(True)
        self._apply_picked_selector()

    def _apply_picked_selector(self) -> None:
        # COMのアパートメント競合を避けるため専用スレッドで取得する
        result: list[UiSelector | None] = []
        worker = threading.Thread(
            target=lambda: result.append(selector_from_cursor()), daemon=True
        )
        worker.start()
        worker.join(timeout=_PICK_TIMEOUT_SEC)
        selector = result[0] if result else None
        if selector is None:
            QMessageBox.warning(
                self, constants.DIALOG_EDIT_TITLE, constants.MSG_PICK_FAILED
            )
            return
        self._sel_automation_id.setText(selector.automation_id)
        self._sel_name.setText(selector.name)
        self._sel_control_type.setText(selector.control_type)
        self._sel_window_id.setText(selector.window_automation_id)
        self._sel_window_name.setText(selector.window_name)
        self._sel_index.setValue(selector.found_index)
        self._selector_class_name = selector.class_name

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

        self._condition_image = condition.image if condition else ""
        self._capture_button = QPushButton(constants.BUTTON_CAPTURE_IMAGE)
        self._capture_button.clicked.connect(self._capture_image)
        self._load_image_button = QPushButton(constants.BUTTON_LOAD_IMAGE)
        self._load_image_button.clicked.connect(self._load_image)
        self._image_preview = QLabel()
        form.addRow(
            constants.LABEL_CONDITION_IMAGE,
            self._pair(
                self._capture_button, self._load_image_button, self._image_preview
            ),
        )
        self._update_image_preview()

        if condition is not None:
            index = self._condition_type.findData(condition.condition_type.value)
            self._condition_type.setCurrentIndex(index)
            self._condition_value.setText(condition.value)
            self._condition_max_wait.setValue(condition.max_wait_sec)
        self._on_condition_type_changed()
        return group

    def _is_image_condition(self) -> bool:
        return (
            self._condition_type.currentData() == ConditionType.IMAGE_SHOWN_WAIT.value
        )

    def _capture_image(self) -> None:
        image = capture_screen_region(self)
        if image:
            self._condition_image = image
            self._update_image_preview()

    def _load_image(self) -> None:
        image = load_image_file(self)
        if image:
            self._condition_image = image
            self._update_image_preview()

    def _update_image_preview(self) -> None:
        if not self._condition_image:
            self._image_preview.clear()
            return
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(self._condition_image))
        self._image_preview.setPixmap(pixmap.scaledToHeight(min(pixmap.height(), 48)))

    def _on_action_changed(self) -> None:
        action = ActionType(self._action.currentData())
        has_coords = action not in (
            ActionType.KEY_ONLY,
            ActionType.LAUNCH_APP,
            ActionType.SET_TEXT,
            ActionType.GET_TEXT,
        )
        self._x.setEnabled(has_coords)
        self._y.setEnabled(has_coords)
        is_drag = action == ActionType.DRAG
        self._drag_x.setEnabled(is_drag)
        self._drag_y.setEnabled(is_drag)
        self._app_path.setEnabled(action == ActionType.LAUNCH_APP)
        self._selector_group.setEnabled(
            action not in (ActionType.KEY_ONLY, ActionType.LAUNCH_APP)
        )
        self._keys.setEnabled(action != ActionType.GET_TEXT)
        self._keys.setPlaceholderText(
            constants.HINT_SET_TEXT_KEYS if action == ActionType.SET_TEXT else ""
        )

    def _on_condition_type_changed(self) -> None:
        hint = constants.CONDITION_VALUE_HINTS.get(
            self._condition_type.currentData(), ""
        )
        self._condition_value.setPlaceholderText(hint)
        is_image = self._is_image_condition()
        self._condition_value.setEnabled(not is_image)
        self._capture_button.setEnabled(is_image)
        self._load_image_button.setEnabled(is_image)

    def _on_accept(self) -> None:
        action = ActionType(self._action.currentData())
        if action != ActionType.SET_TEXT:  # SET_TEXTのkeysは平文なので解析しない
            try:
                parse(self._keys.text())
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    constants.DIALOG_EDIT_TITLE,
                    constants.MSG_INVALID_KEYS.format(error=e),
                )
                return
        if action == ActionType.LAUNCH_APP and not self._app_path.text().strip():
            QMessageBox.warning(
                self, constants.DIALOG_EDIT_TITLE, constants.MSG_APP_PATH_REQUIRED
            )
            return
        if (
            action in (ActionType.SET_TEXT, ActionType.GET_TEXT)
            and self._edited_selector() is None
        ):
            QMessageBox.warning(
                self, constants.DIALOG_EDIT_TITLE, constants.MSG_SELECTOR_REQUIRED
            )
            return
        if (
            self._condition_group.isChecked()
            and self._is_image_condition()
            and not self._condition_image
        ):
            QMessageBox.warning(
                self, constants.DIALOG_EDIT_TITLE, constants.MSG_IMAGE_REQUIRED
            )
            return
        self.accept()

    def edited_item(self) -> ActionItem:
        """編集結果を新しいActionItemとして返す。"""
        action = ActionType(self._action.currentData())
        has_coords = action not in (
            ActionType.KEY_ONLY,
            ActionType.LAUNCH_APP,
            ActionType.SET_TEXT,
            ActionType.GET_TEXT,
        )
        uses_selector = action not in (ActionType.KEY_ONLY, ActionType.LAUNCH_APP)
        return ActionItem(
            interval=self._interval.value(),
            x=self._x.value() if has_coords else None,
            y=self._y.value() if has_coords else None,
            action=action,
            keys="" if action == ActionType.GET_TEXT else self._keys.text(),
            drag_to=(
                (self._drag_x.value(), self._drag_y.value())
                if action == ActionType.DRAG
                else None
            ),
            repeat_offset=(self._offset_x.value(), self._offset_y.value()),
            key_repeat_increase=self._key_repeat.isChecked(),
            condition=self._edited_condition(),
            app_path=(
                self._app_path.text().strip() if action == ActionType.LAUNCH_APP else ""
            ),
            selector=self._edited_selector() if uses_selector else None,
        )

    def _edited_selector(self) -> UiSelector | None:
        if not self._selector_group.isChecked():
            return None
        selector = UiSelector(
            window_automation_id=self._sel_window_id.text().strip(),
            window_name=self._sel_window_name.text().strip(),
            control_type=self._sel_control_type.text().strip(),
            automation_id=self._sel_automation_id.text().strip(),
            name=self._sel_name.text().strip(),
            class_name=self._selector_class_name,
            found_index=self._sel_index.value(),
        )
        return selector if selector.has_criteria() else None

    def _edited_condition(self) -> Condition | None:
        if not self._condition_group.isChecked():
            return None
        return Condition(
            condition_type=ConditionType(self._condition_type.currentData()),
            value=self._condition_value.text(),
            max_wait_sec=self._condition_max_wait.value(),
            image=self._condition_image if self._is_image_condition() else "",
        )
