"""ワークフロー実行エンジン: バンドル内のステップを上から順に実行する。

医療安全のため、人間確認ステップと画面待ちタイムアウト時は
処理を一時停止し、UI側の「再開」操作を待つ。
"""

import base64
import threading
import time

from PySide6.QtCore import QThread, Signal

from service.conditions import POLL_INTERVAL_SEC, image_shown
from service.models import MacroFile
from service.player import MacroPlayer
from service.workflow import StepType, WorkflowBundle, WorkflowStep

_TICK_SEC = 0.05

# confirmation_requiredシグナルで通知する確認の種類
CONFIRM_KIND_HUMAN = "human"  # 人間確認ステップによる一時停止
CONFIRM_KIND_TIMEOUT = "timeout"  # 画面待ちの最大待機超過による一時停止


class WorkflowPlayer(QThread):
    step_started = Signal(int)  # 実行を開始したステップのインデックス
    confirmation_required = Signal(int, str)  # インデックス, 確認の種類
    error_occurred = Signal(str)
    workflow_finished = Signal(bool)  # Trueなら最後まで実行された

    def __init__(self, bundle: WorkflowBundle, parent=None) -> None:
        super().__init__(parent)
        self._bundle = bundle
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._resume_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.clear()

    def toggle_pause(self) -> None:
        if self._pause_event.is_set():
            self._pause_event.clear()
        else:
            self._pause_event.set()

    def resume_confirmation(self) -> None:
        """人間確認・タイムアウト確認からの再開（UIの「再開」ボタン用）。"""
        self._resume_event.set()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def run(self) -> None:
        try:
            completed = self._run_steps()
        except (OSError, ValueError, KeyError) as e:  # バンドル内ファイルの読込失敗等
            self.error_occurred.emit(str(e))
            completed = False
        self.workflow_finished.emit(completed)

    def _run_steps(self) -> bool:
        for index, step in enumerate(self._bundle.workflow.steps):
            if self._stop_event.is_set():
                return False
            self.step_started.emit(index)
            if not self._execute_step(index, step):
                return False
        return True

    def _execute_step(self, index: int, step: WorkflowStep) -> bool:
        if step.step_type == StepType.PLAY_RECORDING:
            return self._play_recording(step)
        if step.step_type == StepType.WAIT_IMAGE:
            return self._wait_image(index, step)
        return self._wait_for_confirmation(index, CONFIRM_KIND_HUMAN)

    def _play_recording(self, step: WorkflowStep) -> bool:
        macro = MacroFile.load(self._bundle.recording_path(step.recording))
        player = MacroPlayer(
            macro, stop_event=self._stop_event, pause_event=self._pause_event
        )
        player.error_occurred.connect(self.error_occurred)
        return player.play_blocking()

    def _wait_image(self, index: int, step: WorkflowStep) -> bool:
        image_b64 = base64.b64encode(
            self._bundle.asset_path(step.image).read_bytes()
        ).decode("ascii")
        started = time.monotonic()
        while True:
            if self._stop_event.is_set():
                return False
            if self._pause_event.is_set():
                started += POLL_INTERVAL_SEC  # 一時停止中はタイムアウトを凍結
            elif image_shown(image_b64):
                return True
            elif (
                step.max_wait_sec > 0
                and time.monotonic() - started >= step.max_wait_sec
            ):
                # 最大待機超過時は強制続行せず、人間の目視確認を求める
                return self._wait_for_confirmation(index, CONFIRM_KIND_TIMEOUT)
            time.sleep(POLL_INTERVAL_SEC)

    def _wait_for_confirmation(self, index: int, kind: str) -> bool:
        self._resume_event.clear()
        self.confirmation_required.emit(index, kind)
        while not self._resume_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(_TICK_SEC)
        return True
