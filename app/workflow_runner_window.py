"""ワークフロー実行画面: 一般ユーザー向けの実行専用UI（編集機能なし）。

共有フォルダ上のバンドル一覧から選択し、日本語手順の進捗を表示しながら
再生・一時停止・停止・（人間確認時の）再開のみを操作できる。
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import constants
from service.workflow import WorkflowBundle, list_bundles
from service.workflow_player import CONFIRM_KIND_HUMAN, WorkflowPlayer
from utils.config_manager import ConfigManager

_CONFIRM_MESSAGE_STYLE = "color: #b45309; font-weight: bold;"


class WorkflowRunnerWindow(QMainWindow):
    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._bundle: WorkflowBundle | None = None
        self._player: WorkflowPlayer | None = None
        self.setWindowTitle(constants.WORKFLOW_RUNNER_TITLE)
        self._build_ui()
        self.resize(800, 500)
        self._refresh_bundles()

    # --- UI構築 ---

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addLayout(self._build_bundle_panel(), stretch=1)
        layout.addLayout(self._build_step_panel(), stretch=2)
        self.setCentralWidget(central)
        self.statusBar()

    def _build_bundle_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.addWidget(QLabel(constants.LABEL_WORKFLOW_LIST))
        self._bundle_list = QListWidget()
        self._bundle_list.currentItemChanged.connect(self._on_bundle_selected)
        panel.addWidget(self._bundle_list)
        refresh_button = QPushButton(constants.BUTTON_WORKFLOW_REFRESH)
        refresh_button.clicked.connect(self._refresh_bundles)
        panel.addWidget(refresh_button)
        return panel

    def _build_step_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        self._flow_label = QLabel("")
        panel.addWidget(self._flow_label)
        self._step_list = QListWidget()
        self._step_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        panel.addWidget(self._step_list)

        self._confirm_label = QLabel("")
        self._confirm_label.setStyleSheet(_CONFIRM_MESSAGE_STYLE)
        self._confirm_label.setWordWrap(True)
        self._confirm_label.hide()
        panel.addWidget(self._confirm_label)

        buttons = QHBoxLayout()
        self._play_button = QPushButton(constants.BUTTON_WORKFLOW_PLAY)
        self._play_button.clicked.connect(self._start_playback)
        self._pause_button = QPushButton(constants.BUTTON_WORKFLOW_PAUSE)
        self._pause_button.clicked.connect(self._toggle_pause)
        self._stop_button = QPushButton(constants.BUTTON_WORKFLOW_STOP)
        self._stop_button.clicked.connect(self._stop_playback)
        self._resume_button = QPushButton(constants.BUTTON_WORKFLOW_RESUME)
        self._resume_button.clicked.connect(self._resume_confirmation)
        for button in (
            self._play_button,
            self._pause_button,
            self._stop_button,
            self._resume_button,
        ):
            buttons.addWidget(button)
        panel.addLayout(buttons)
        self._set_running_state(False)
        return panel

    # --- バンドル一覧 ---

    def _bundle_dir(self) -> str:
        return self._config.config.get("Workflow", "bundle_dir", fallback="")

    def _refresh_bundles(self) -> None:
        self._bundle_list.clear()
        bundle_dir = self._bundle_dir()
        if not bundle_dir or not Path(bundle_dir).is_dir():
            self.statusBar().showMessage(constants.MSG_BUNDLE_DIR_NOT_SET)
            return
        for path in list_bundles(bundle_dir):
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._bundle_list.addItem(item)

    def _on_bundle_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None or self._is_playing():
            return
        try:
            self._bundle = WorkflowBundle.load(current.data(Qt.ItemDataRole.UserRole))
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.warning(
                self,
                constants.WORKFLOW_RUNNER_TITLE,
                constants.MSG_BUNDLE_LOAD_ERROR.format(error=e),
            )
            self._bundle = None
            return
        self._flow_label.setText(
            constants.LABEL_CURRENT_FLOW.format(name=self._bundle.workflow.name)
        )
        self._populate_steps()

    def _populate_steps(self, current_index: int = -1, all_done: bool = False) -> None:
        self._step_list.clear()
        if self._bundle is None:
            return
        for index, step in enumerate(self._bundle.workflow.steps):
            if all_done or index < current_index:
                status = constants.WORKFLOW_STATUS_DONE
            elif index == current_index:
                status = constants.WORKFLOW_STATUS_RUNNING
            else:
                status = constants.WORKFLOW_STATUS_WAITING
            icon = constants.WORKFLOW_STEP_ICONS[step.step_type.value]
            self._step_list.addItem(f"{status} {icon} {step.label}")
        if current_index >= 0:
            self._step_list.scrollToItem(self._step_list.item(current_index))

    # --- 再生制御 ---

    def _is_playing(self) -> bool:
        return self._player is not None and self._player.isRunning()

    def _set_running_state(self, running: bool) -> None:
        self._play_button.setEnabled(not running)
        self._pause_button.setEnabled(running)
        self._stop_button.setEnabled(running)
        self._resume_button.setEnabled(False)
        self._bundle_list.setEnabled(not running)

    def _start_playback(self) -> None:
        if self._bundle is None or self._is_playing():
            return
        self._player = WorkflowPlayer(self._bundle)
        self._player.step_started.connect(self._on_step_started)
        self._player.confirmation_required.connect(self._on_confirmation_required)
        self._player.error_occurred.connect(self._on_error)
        self._player.workflow_finished.connect(self._on_finished)
        self._set_running_state(True)
        self._confirm_label.hide()
        self.statusBar().clearMessage()
        self._player.start()

    def _toggle_pause(self) -> None:
        if self._player is None:
            return
        self._player.toggle_pause()
        if self._player.is_paused:
            self.statusBar().showMessage(constants.MSG_WORKFLOW_PAUSED)
        else:
            self.statusBar().clearMessage()

    def _stop_playback(self) -> None:
        if self._player is not None:
            self._player.stop()

    def _resume_confirmation(self) -> None:
        if self._player is None:
            return
        self._confirm_label.hide()
        self._resume_button.setEnabled(False)
        self._player.resume_confirmation()

    # --- プレイヤーからの通知 ---

    def _on_step_started(self, index: int) -> None:
        self._populate_steps(current_index=index)

    def _on_confirmation_required(self, index: int, kind: str) -> None:
        if self._bundle is not None and kind == CONFIRM_KIND_HUMAN:
            step = self._bundle.workflow.steps[index]
            message = step.message or constants.MSG_CONFIRM_DEFAULT
        else:
            message = constants.MSG_WAIT_TIMEOUT_CONFIRM
        self._confirm_label.setText(message)
        self._confirm_label.show()
        self._resume_button.setEnabled(True)
        self.showNormal()
        self.activateWindow()

    def _on_error(self, error: str) -> None:
        QMessageBox.warning(
            self,
            constants.WORKFLOW_RUNNER_TITLE,
            constants.MSG_PLAYBACK_ERROR.format(error=error),
        )

    def _on_finished(self, completed: bool) -> None:
        if self._player is not None:
            self._player.wait()
            self._player = None
        self._set_running_state(False)
        self._confirm_label.hide()
        self._populate_steps(all_done=completed)
        message = (
            constants.MSG_WORKFLOW_FINISHED
            if completed
            else constants.MSG_WORKFLOW_STOPPED
        )
        self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._player is not None:
            self._player.stop()
            self._player.wait()
        event.accept()
