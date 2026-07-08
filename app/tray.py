"""トレイアイコン＋トレイランチャー: 登録した.parファイルを選択と同時に再生する。"""

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app import constants
from utils.config_manager import ConfigManager

_LAUNCHER_SECTION = "TrayLauncher"


def _icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app.png"  # type: ignore[attr-defined]
    return Path(__file__).parent.parent / "assets" / "app.png"


class AppTrayIcon(QSystemTrayIcon):
    show_main_requested = Signal()
    exit_requested = Signal()
    launch_file_requested = Signal(str)  # ランチャーで選択されたファイルパス
    add_current_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QObject | None = None) -> None:
        super().__init__(QIcon(str(_icon_path())), parent)
        self._config = config
        self.setToolTip(constants.APP_NAME)
        self._rebuild_menu()
        self.activated.connect(self._on_activated)

    def add_launcher_entry(self, name: str, path: str) -> None:
        self._config.set_value(_LAUNCHER_SECTION, name, path)
        self._rebuild_menu()

    def _launcher_entries(self) -> list[tuple[str, str]]:
        if _LAUNCHER_SECTION not in self._config.config:
            return []
        return list(self._config.config[_LAUNCHER_SECTION].items())

    def _rebuild_menu(self) -> None:
        menu = QMenu()
        for name, path in self._launcher_entries():
            menu.addAction(
                name, lambda _checked=False, p=path: self.launch_file_requested.emit(p)
            )
        if self._launcher_entries():
            menu.addSeparator()
        menu.addAction(constants.TRAY_MENU_ADD_CURRENT, self.add_current_requested.emit)
        menu.addSeparator()
        menu.addAction(constants.TRAY_MENU_SHOW, self.show_main_requested.emit)
        menu.addAction(constants.TRAY_MENU_EXIT, self.exit_requested.emit)
        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # 左クリックでもランチャーメニューを表示（資料準拠）
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            menu = self.contextMenu()
            if menu is not None:
                menu.popup(QCursor.pos())
