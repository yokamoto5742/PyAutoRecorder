"""メインウィンドウ: ツールバー＋3ページのリスト表示・編集・記録・再生を統括する。"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QCloseEvent, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import constants
from app.field_confirm import confirm_fields
from app.item_editor_dialog import ItemEditorDialog
from app.options_dialog import OptionsDialog
from app.recorder_child_window import RecorderChildWindow
from app.recording_stop_button import RecordingStopButton
from app.timer_dialog import TimerDialog
from app.tray import AppTrayIcon
from app.workflow_editor_window import WorkflowEditorWindow
from service.hotkey_manager import (
    DEFAULT_PAUSE_KEY,
    DEFAULT_PLAY_STOP_KEY,
    HotkeyManager,
    SingleHotkeyListener,
)
from service.clipboard_fields import collect_var_specs
from service.manual_generator import write_macro_manual
from service.models import ActionItem, ActionType, MacroFile
from service.player import MacroPlayer
from service.recorder import MacroRecorder
from service.single_instance import SingleInstanceServer
from service.timer_scheduler import TimerScheduler
from utils.config_manager import ConfigManager

_PAGES = ("initial", "loop", "final")
_CONDITION_TEXT_COLOR = QColor("red")


class MainWindow(QMainWindow):
    # pynputリスナースレッドからメインスレッドへ橋渡しするシグナル
    hotkey_play_stop = Signal()
    hotkey_pause = Signal()

    def __init__(self, launch_file_path: str | None = None) -> None:
        super().__init__()
        self._config = ConfigManager()
        self._macro = MacroFile()
        self._file_path: Path | None = None
        self._dirty = False
        self._recorder: MacroRecorder | None = None
        self._player: MacroPlayer | None = None
        self._pause_hotkey_listener: SingleHotkeyListener | None = None
        self._child_window: RecorderChildWindow | None = None
        self._workflow_editor: WorkflowEditorWindow | None = None
        self._auto_quit_after_playback = launch_file_path is not None

        self._stop_button = RecordingStopButton()
        self._stop_button.stop_requested.connect(self._finish_recording)

        self._build_toolbar()
        self._build_central()
        self._update_window_title()
        self.statusBar()

        self.hotkey_play_stop.connect(self._toggle_play_stop)
        self.hotkey_pause.connect(self._toggle_pause)
        self._hotkeys = HotkeyManager(
            on_play_stop=self.hotkey_play_stop.emit,
            on_pause=self.hotkey_pause.emit,
            play_stop_key=self._config.config.get(
                "Hotkeys", "play_stop", fallback=DEFAULT_PLAY_STOP_KEY
            ),
            pause_key=self._config.config.get(
                "Hotkeys", "pause", fallback=DEFAULT_PAUSE_KEY
            ),
        )
        self._hotkeys.start()

        self._scheduler = TimerScheduler(self)
        self._scheduler.play_triggered.connect(self._on_timer_play)
        self._scheduler.stop_triggered.connect(self._on_timer_stop)

        self._tray = AppTrayIcon(self._config, self)
        self._tray.show_main_requested.connect(self._show_from_tray)
        self._tray.exit_requested.connect(self.close)
        self._tray.launch_file_requested.connect(self._launch_file)
        self._tray.add_current_requested.connect(self._add_current_to_launcher)
        self._tray.show()

        self._single_instance_server = SingleInstanceServer(self)
        self._single_instance_server.file_received.connect(self._launch_file)

        if launch_file_path is not None:
            self._launch_file(launch_file_path)

    # --- UI構築 ---

    def _build_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction(constants.TOOLBAR_NEW, self._new_file)
        toolbar.addAction(constants.TOOLBAR_OPEN, self._open_file)
        toolbar.addAction(constants.TOOLBAR_SAVE, self._save_file)
        toolbar.addSeparator()
        toolbar.addWidget(self._build_record_button())
        toolbar.addAction(constants.TOOLBAR_PLAY, self._start_playback)
        toolbar.addAction(constants.TOOLBAR_PAUSE, self._toggle_pause)
        toolbar.addAction(constants.TOOLBAR_STOP, self._stop_playback)
        toolbar.addSeparator()
        toolbar.addAction(constants.TOOLBAR_TIMER, self._edit_timers)
        toolbar.addAction(constants.TOOLBAR_OPTIONS, self._edit_options)
        toolbar.addAction(constants.TOOLBAR_MANUAL, self._generate_manual)
        toolbar.addSeparator()
        toolbar.addAction(constants.TOOLBAR_WORKFLOW, self._show_workflow_editor)

    def _build_record_button(self) -> QToolButton:
        button = QToolButton()
        button.setText(constants.TOOLBAR_RECORD)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        menu.addAction(constants.MENU_RECORD_AUTO, self._start_auto_recording)
        menu.addAction(constants.MENU_RECORD_MANUAL_MOUSE, self._show_child_window)
        menu.addAction(constants.MENU_RECORD_MANUAL_KEY, self._add_manual_key_item)
        button.setMenu(menu)
        return button

    def _build_central(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        repeat_row = QHBoxLayout()
        repeat_row.addWidget(QLabel(constants.LABEL_REPEAT_COUNT))
        self._repeat_spin = QSpinBox()
        self._repeat_spin.setRange(1, 2_000_000_000)
        self._repeat_spin.valueChanged.connect(self._on_repeat_count_changed)
        repeat_row.addWidget(self._repeat_spin)
        repeat_row.addSpacing(20)
        repeat_row.addWidget(QLabel(constants.LABEL_BULK_INTERVAL))
        self._bulk_interval_spin = QSpinBox()
        self._bulk_interval_spin.setRange(0, 99999)
        self._bulk_interval_spin.setValue(0)
        repeat_row.addWidget(self._bulk_interval_spin)
        bulk_button = QPushButton(constants.BUTTON_BULK_INTERVAL)
        bulk_button.clicked.connect(self._apply_bulk_interval)
        repeat_row.addWidget(bulk_button)
        repeat_row.addStretch()
        layout.addLayout(repeat_row)

        self._tabs = QTabWidget()
        self._trees: dict[str, QTreeWidget] = {}
        for page, title in zip(
            _PAGES, (constants.TAB_INITIAL, constants.TAB_LOOP, constants.TAB_FINAL)
        ):
            tree = self._build_tree()
            self._trees[page] = tree
            self._tabs.addTab(tree, title)
        layout.addWidget(self._tabs)
        self.setCentralWidget(central)
        self.resize(*self._config.get_window_size("main", (800, 500)))

    def _build_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(
            [
                constants.COLUMN_INTERVAL,
                constants.COLUMN_X,
                constants.COLUMN_Y,
                constants.COLUMN_ACTION,
                constants.COLUMN_KEYS,
                constants.COLUMN_CONDITION,
            ]
        )
        tree.setRootIsDecorated(False)
        tree.itemDoubleClicked.connect(lambda _item, _col: self._edit_item())
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(
            lambda pos, t=tree: self._show_context_menu(t, pos)
        )
        return tree

    # --- モデルとビューの同期 ---

    def _current_page(self) -> str:
        return _PAGES[self._tabs.currentIndex()]

    def _current_items(self) -> list[ActionItem]:
        return getattr(self._macro, self._current_page())

    def _refresh_tree(self, page: str) -> None:
        tree = self._trees[page]
        tree.clear()
        for item in getattr(self._macro, page):
            tree.addTopLevelItem(self._to_row(item))

    def _to_row(self, item: ActionItem) -> QTreeWidgetItem:
        condition_label = (
            constants.CONDITION_LABELS[item.condition.condition_type.value]
            if item.condition
            else ""
        )
        row = QTreeWidgetItem(
            [
                str(item.interval),
                "" if item.x is None else str(item.x),
                "" if item.y is None else str(item.y),
                constants.ACTION_LABELS[item.action.value],
                item.keys,
                condition_label,
            ]
        )
        if item.condition is not None:
            # 条件判断を使用している項目は赤文字で表示（資料準拠）
            for column in range(row.columnCount()):
                row.setForeground(column, QBrush(_CONDITION_TEXT_COLOR))
        return row

    def _set_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        self._update_window_title()

    def _update_window_title(self) -> None:
        name = self._file_path.name if self._file_path else constants.UNTITLED_FILE
        mark = constants.MODIFIED_MARK if self._dirty else ""
        self.setWindowTitle(f"{name}{mark} - {constants.WINDOW_TITLE}")

    # --- 項目操作 ---

    def add_item_to_current_page(self, item: ActionItem) -> None:
        """現在表示中のページへ項目を追加する（子機・手動記録からも使う）。"""
        self._current_items().append(item)
        self._refresh_tree(self._current_page())
        self._set_dirty()

    def _selected_index(self, tree: QTreeWidget) -> int:
        selected = tree.selectedItems()
        if not selected:
            return -1
        return tree.indexOfTopLevelItem(selected[0])

    def _edit_item(self) -> None:
        page = self._current_page()
        tree = self._trees[page]
        index = self._selected_index(tree)
        if index < 0:
            return
        items = getattr(self._macro, page)
        dialog = ItemEditorDialog(items[index], self)
        if dialog.exec():
            items[index] = dialog.edited_item()
            self._refresh_tree(page)
            self._set_dirty()

    def _show_context_menu(self, tree: QTreeWidget, pos) -> None:
        index = self._selected_index(tree)
        if index < 0:
            return
        menu = QMenu(tree)
        menu.addAction(constants.MENU_EDIT_ITEM, self._edit_item)
        menu.addAction(constants.MENU_DELETE_ITEM, lambda: self._delete_item(index))
        menu.addAction(constants.MENU_MOVE_UP, lambda: self._move_item(index, -1))
        menu.addAction(constants.MENU_MOVE_DOWN, lambda: self._move_item(index, 1))
        menu.exec(tree.viewport().mapToGlobal(pos))

    def _delete_item(self, index: int) -> None:
        page = self._current_page()
        del getattr(self._macro, page)[index]
        self._refresh_tree(page)
        self._set_dirty()

    def _move_item(self, index: int, delta: int) -> None:
        page = self._current_page()
        items = getattr(self._macro, page)
        new_index = index + delta
        if not (0 <= new_index < len(items)):
            return
        items[index], items[new_index] = items[new_index], items[index]
        self._refresh_tree(page)
        moved_row = self._trees[page].topLevelItem(new_index)
        if moved_row is not None:
            self._trees[page].setCurrentItem(moved_row)
        self._set_dirty()

    def _on_repeat_count_changed(self, value: int) -> None:
        if value != self._macro.settings.repeat_count:
            self._macro.settings.repeat_count = value
            self._set_dirty()

    def _apply_bulk_interval(self) -> None:
        """表示中のタブの全項目の間隔(秒)を指定値に一括設定する。"""
        page = self._current_page()
        items = getattr(self._macro, page)
        if not items:
            return
        value = self._bulk_interval_spin.value()
        for item in items:
            item.interval = value
        self._refresh_tree(page)
        self._set_dirty()
        self.statusBar().showMessage(
            constants.MSG_BULK_INTERVAL_APPLIED.format(value=value), 5000
        )

    # --- 記録 ---

    def _start_auto_recording(self) -> None:
        if self._recorder is not None or self._is_playing():
            return
        self._hotkeys.stop()  # 記録中のホットキー誤動作を防ぐ
        self.showMinimized()
        self._recorder = MacroRecorder(ignore_region=self._stop_button.contains_point)
        self._recorder.start()
        self._stop_button.show_blinking()
        self.statusBar().showMessage(constants.MSG_RECORDING)

    def _finish_recording(self) -> None:
        if self._recorder is None:
            return
        items = self._recorder.stop()
        self._recorder = None
        self._stop_button.hide_and_stop_blinking()
        self._hotkeys.start()
        page = self._current_page()
        getattr(self._macro, page).extend(items)
        self._refresh_tree(page)
        if items:
            self._set_dirty()
        self.statusBar().clearMessage()
        self.showNormal()
        self.activateWindow()

    def _show_child_window(self) -> None:
        if self._child_window is None:
            self._child_window = RecorderChildWindow(
                on_item_added=self.add_item_to_current_page
            )
        self._child_window.show()

    def _show_workflow_editor(self) -> None:
        if self._workflow_editor is None:
            self._workflow_editor = WorkflowEditorWindow(self._config)
        self._workflow_editor.show()
        self._workflow_editor.activateWindow()

    def _add_manual_key_item(self) -> None:
        item = ActionItem(interval=1, action=ActionType.KEY_ONLY)
        dialog = ItemEditorDialog(item, self)
        if dialog.exec():
            self.add_item_to_current_page(dialog.edited_item())

    # --- 再生 ---

    def _is_playing(self) -> bool:
        return self._player is not None and self._player.isRunning()

    def _start_playback(self) -> None:
        if self._is_playing() or self._recorder is not None:
            return
        fields = None
        specs = collect_var_specs(self._macro)
        if specs:
            fields = confirm_fields(specs, self, constants.WINDOW_TITLE)
            if fields is None:
                return
        self._player = MacroPlayer(self._macro, fields=fields)
        self._player.playback_finished.connect(self._on_playback_finished)
        self._player.error_occurred.connect(self._on_playback_error)
        self._start_pause_hotkey_listener()
        if not self._auto_quit_after_playback:
            self.showMinimized()
        self._player.start()

    def _start_pause_hotkey_listener(self) -> None:
        if self._macro.settings.pause_hotkey:
            self._pause_hotkey_listener = SingleHotkeyListener(
                self._macro.settings.pause_hotkey, self.hotkey_pause.emit
            )
            self._pause_hotkey_listener.start()

    def _stop_pause_hotkey_listener(self) -> None:
        if self._pause_hotkey_listener is not None:
            self._pause_hotkey_listener.stop()
            self._pause_hotkey_listener = None

    def _stop_playback(self) -> None:
        if self._player is not None:
            self._player.stop()

    def _toggle_play_stop(self) -> None:
        if self._recorder is not None:
            return
        if self._is_playing():
            self._stop_playback()
        else:
            self._start_playback()

    def _toggle_pause(self) -> None:
        if self._player is not None:
            self._player.toggle_pause()

    def _on_playback_finished(self, completed: bool) -> None:
        self._stop_pause_hotkey_listener()
        if self._player is not None:
            self._player.wait()
            self._player = None
        if self._auto_quit_after_playback:
            self.close()
            return
        self.showNormal()
        self.activateWindow()
        message = (
            constants.MSG_PLAYBACK_FINISHED
            if completed
            else constants.MSG_PLAYBACK_STOPPED
        )
        self.statusBar().showMessage(message, 5000)

    def _on_playback_error(self, error: str) -> None:
        QMessageBox.warning(
            self,
            constants.WINDOW_TITLE,
            constants.MSG_PLAYBACK_ERROR.format(error=error),
        )

    # --- ファイル操作 ---

    def _maybe_discard(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self, constants.WINDOW_TITLE, constants.MSG_CONFIRM_DISCARD
        )
        return answer == QMessageBox.StandardButton.Yes

    def _new_file(self) -> None:
        if not self._maybe_discard():
            return
        self._macro = MacroFile()
        self._file_path = None
        self._apply_loaded_macro()

    def _open_file(self) -> None:
        if not self._maybe_discard():
            return
        path_str, _filter = QFileDialog.getOpenFileName(
            self, constants.FILE_DIALOG_OPEN_TITLE, "", constants.FILE_DIALOG_FILTER
        )
        if not path_str:
            return
        try:
            self._macro = MacroFile.load(path_str)
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.warning(
                self,
                constants.WINDOW_TITLE,
                constants.MSG_FILE_LOAD_ERROR.format(error=e),
            )
            return
        self._file_path = Path(path_str)
        self._apply_loaded_macro()

    def _apply_loaded_macro(self) -> None:
        for page in _PAGES:
            self._refresh_tree(page)
        self._repeat_spin.setValue(self._macro.settings.repeat_count)
        self._configure_scheduler()
        self._set_dirty(False)

    def _save_file(self) -> None:
        if self._file_path is None:
            self._save_file_as()
            return
        try:
            self._macro.save(self._file_path)
        except OSError as e:
            QMessageBox.warning(
                self,
                constants.WINDOW_TITLE,
                constants.MSG_FILE_SAVE_ERROR.format(error=e),
            )
            return
        self._set_dirty(False)
        self._confirm_open_folder(self._file_path.parent)

    def _save_file_as(self) -> None:
        path_str, _filter = QFileDialog.getSaveFileName(
            self,
            constants.FILE_DIALOG_SAVE_TITLE,
            str(self._config.get_par_dir()),
            constants.FILE_DIALOG_FILTER,
        )
        if not path_str:
            return
        self._file_path = Path(path_str)
        self._save_file()

    def _generate_manual(self) -> None:
        """保存済みの.parから操作手順書(.md)を手順書フォルダへ出力する。"""
        if self._file_path is None or self._dirty:
            QMessageBox.information(
                self, constants.WINDOW_TITLE, constants.MSG_MANUAL_NO_FILE
            )
            return
        try:
            output_path = write_macro_manual(
                self._file_path, self._config.get_manual_dir()
            )
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.warning(
                self,
                constants.WINDOW_TITLE,
                constants.MSG_MANUAL_ERROR.format(error=e),
            )
            return
        self.statusBar().showMessage(
            constants.MSG_MANUAL_SAVED.format(path=output_path), 5000
        )
        self._confirm_open_folder(output_path.parent)

    def _confirm_open_folder(self, folder: Path) -> None:
        answer = QMessageBox.question(
            self, constants.WINDOW_TITLE, constants.MSG_OPEN_FOLDER_CONFIRM
        )
        if answer == QMessageBox.StandardButton.Yes:
            os.startfile(folder)

    # --- タイマー・トレイ ---

    def _configure_scheduler(self) -> None:
        settings = self._macro.settings
        self._scheduler.configure(
            settings.play_timer, settings.stop_timer, settings.stop_timer_mode
        )

    def _edit_timers(self) -> None:
        dialog = TimerDialog(self._macro.settings, self)
        if dialog.exec():
            dialog.apply_to(self._macro.settings)
            self._configure_scheduler()
            self._set_dirty()

    def _edit_options(self) -> None:
        dialog = OptionsDialog(self._macro.settings, self)
        if dialog.exec():
            dialog.apply_to(self._macro.settings)
            self._set_dirty()

    def _on_timer_play(self) -> None:
        if not self._is_playing() and self._recorder is None:
            self.statusBar().showMessage(constants.MSG_TIMER_PLAY_STARTED, 5000)
            self._start_playback()

    def _on_timer_stop(self, mode: str) -> None:
        if self._player is None:
            return
        if mode == "final":
            self._player.skip_to_final()
        else:
            self._player.stop()
        self.statusBar().showMessage(constants.MSG_TIMER_STOPPED, 5000)

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _launch_file(self, path: str) -> None:
        """トレイランチャー: ファイルを開き即座に再生する（資料準拠）。"""
        if self._is_playing() or self._recorder is not None:
            return
        if not self._maybe_discard():
            return
        try:
            self._macro = MacroFile.load(path)
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.warning(
                self,
                constants.WINDOW_TITLE,
                constants.MSG_FILE_LOAD_ERROR.format(error=e),
            )
            if self._auto_quit_after_playback:
                self.close()
            return
        self._file_path = Path(path)
        self._apply_loaded_macro()
        self._start_playback()

    def _add_current_to_launcher(self) -> None:
        if self._file_path is None:
            self.statusBar().showMessage(constants.MSG_TRAY_NO_FILE, 5000)
            return
        self._tray.add_launcher_entry(self._file_path.stem, str(self._file_path))
        self.statusBar().showMessage(
            constants.MSG_TRAY_ADDED.format(name=self._file_path.stem), 5000
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._maybe_discard():
            event.ignore()
            return
        self._tray.hide()
        self._hotkeys.stop()
        self._stop_pause_hotkey_listener()
        if self._recorder is not None:
            self._recorder.stop()
        if self._player is not None:
            self._player.stop()
            self._player.wait()
        self._stop_button.close()
        if self._child_window is not None:
            self._child_window.close()
        if self._workflow_editor is not None:
            self._workflow_editor.close()
        event.accept()
