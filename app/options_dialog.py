"""オプション設定ダイアログ: parファイル別の一時停止キーと全体の速度率を設定する。"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QSpinBox,
    QWidget,
)

from app import constants
from service.models import MacroSettings

_MODIFIERS = ("<ctrl>", "<shift>", "<alt>")
_FUNCTION_KEYS = tuple(f"<f{n}>" for n in range(1, 13))

SPEED_PERCENT_MIN = 100
SPEED_PERCENT_MAX = 300


def build_hotkey(modifiers: list[str], key: str) -> str:
    """修飾キーとキーからpynput記法（例 "<ctrl>+<f5>"）を組み立てる。"""
    return "+".join([*modifiers, key])


def split_hotkey(hotkey: str) -> tuple[list[str], str]:
    """pynput記法を（修飾キーのリスト, キー）に分解する。"""
    parts = hotkey.split("+")
    return parts[:-1], parts[-1]


class OptionsDialog(QDialog):
    def __init__(self, settings: MacroSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(constants.DIALOG_OPTIONS_TITLE)
        form = QFormLayout(self)

        self._use_pause_key = QCheckBox(constants.LABEL_USE_PAUSE_HOTKEY)
        self._use_pause_key.setChecked(bool(settings.pause_hotkey))
        form.addRow(self._use_pause_key, self._build_hotkey_row(settings.pause_hotkey))

        self._speed = QSpinBox()
        self._speed.setRange(SPEED_PERCENT_MIN, SPEED_PERCENT_MAX)
        self._speed.setValue(
            max(SPEED_PERCENT_MIN, min(SPEED_PERCENT_MAX, settings.speed_percent))
        )
        form.addRow(constants.LABEL_SPEED_PERCENT, self._speed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _build_hotkey_row(self, hotkey: str) -> QWidget:
        modifiers, key = split_hotkey(hotkey) if hotkey else ([], _FUNCTION_KEYS[0])
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        self._modifier_checks: dict[str, QCheckBox] = {}
        for modifier in _MODIFIERS:
            check = QCheckBox(modifier.strip("<>").capitalize())
            check.setChecked(modifier in modifiers)
            self._modifier_checks[modifier] = check
            row.addWidget(check)
        self._key_combo = QComboBox()
        for fkey in _FUNCTION_KEYS:
            self._key_combo.addItem(fkey.strip("<>").upper(), fkey)
        index = self._key_combo.findData(key)
        if index >= 0:
            self._key_combo.setCurrentIndex(index)
        row.addWidget(self._key_combo)
        return container

    def apply_to(self, settings: MacroSettings) -> None:
        """ダイアログの入力内容をMacroSettingsへ反映する。"""
        if self._use_pause_key.isChecked():
            modifiers = [
                m for m, check in self._modifier_checks.items() if check.isChecked()
            ]
            settings.pause_hotkey = build_hotkey(
                modifiers, self._key_combo.currentData()
            )
        else:
            settings.pause_hotkey = ""
        settings.speed_percent = self._speed.value()
