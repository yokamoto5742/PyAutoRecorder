"""タイマー設定ダイアログ: 再生タイマー・停止タイマー("HH:MM")と停止時の動作を設定する。"""

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTimeEdit,
    QWidget,
)

from app import constants
from service.models import MacroSettings

_TIME_FORMAT = "HH:mm"


class TimerDialog(QDialog):
    def __init__(self, settings: MacroSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(constants.DIALOG_TIMER_TITLE)
        form = QFormLayout(self)

        self._use_play = QCheckBox(constants.LABEL_USE_PLAY_TIMER)
        self._use_play.setChecked(bool(settings.play_timer))
        self._play_time = self._time_edit(settings.play_timer)
        form.addRow(self._use_play, self._play_time)

        self._use_stop = QCheckBox(constants.LABEL_USE_STOP_TIMER)
        self._use_stop.setChecked(bool(settings.stop_timer))
        self._stop_time = self._time_edit(settings.stop_timer)
        form.addRow(self._use_stop, self._stop_time)

        self._stop_mode = QComboBox()
        for value, label in constants.STOP_MODE_LABELS.items():
            self._stop_mode.addItem(label, value)
        self._stop_mode.setCurrentIndex(
            self._stop_mode.findData(settings.stop_timer_mode)
        )
        form.addRow(constants.LABEL_STOP_TIMER_MODE, self._stop_mode)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _time_edit(value: str) -> QTimeEdit:
        edit = QTimeEdit()
        edit.setDisplayFormat(_TIME_FORMAT)
        if value:
            edit.setTime(QTime.fromString(value, _TIME_FORMAT))
        return edit

    def apply_to(self, settings: MacroSettings) -> None:
        """ダイアログの入力内容をMacroSettingsへ反映する。"""
        settings.play_timer = (
            self._play_time.time().toString(_TIME_FORMAT)
            if self._use_play.isChecked()
            else ""
        )
        settings.stop_timer = (
            self._stop_time.time().toString(_TIME_FORMAT)
            if self._use_stop.isChecked()
            else ""
        )
        settings.stop_timer_mode = self._stop_mode.currentData()
