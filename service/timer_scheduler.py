"""再生・停止タイマー: 設定時刻("HH:MM")になったらシグナルを発行する。"""

from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

_CHECK_INTERVAL_MS = 10_000


class TimerScheduler(QObject):
    play_triggered = Signal()
    stop_triggered = Signal(str)  # 停止モード("all"=すべて停止 / "final"=最後の処理へ)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._play_time = ""
        self._stop_time = ""
        self._stop_mode = "all"
        self._last_fired: set[str] = set()  # "play:HH:MM" 同一分内の再発火を防ぐ
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)
        self._timer.start(_CHECK_INTERVAL_MS)

    def configure(self, play_time: str, stop_time: str, stop_mode: str) -> None:
        self._play_time = play_time
        self._stop_time = stop_time
        self._stop_mode = stop_mode
        self._last_fired.clear()

    def _check(self) -> None:
        now = datetime.now().strftime("%H:%M")
        if self._play_time == now and f"play:{now}" not in self._last_fired:
            self._last_fired.add(f"play:{now}")
            self.play_triggered.emit()
        if self._stop_time == now and f"stop:{now}" not in self._last_fired:
            self._last_fired.add(f"stop:{now}")
            self.stop_triggered.emit(self._stop_mode)
        # 過去の発火記録を掃除（当該分以外は不要）
        self._last_fired = {k for k in self._last_fired if k.endswith(now)}
