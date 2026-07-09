"""グローバルホットキー: アプリが非アクティブでも再生/停止・一時停止を受け付ける。"""

from collections.abc import Callable

from pynput import keyboard

DEFAULT_PLAY_STOP_KEY = "<f10>"
DEFAULT_PAUSE_KEY = "<f11>"


class HotkeyManager:
    def __init__(
        self,
        on_play_stop: Callable[[], None],
        on_pause: Callable[[], None],
        play_stop_key: str = DEFAULT_PLAY_STOP_KEY,
        pause_key: str = DEFAULT_PAUSE_KEY,
    ) -> None:
        self._hotkeys = {
            play_stop_key: on_play_stop,
            pause_key: on_pause,
        }
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        if self._listener is None:
            self._listener = keyboard.GlobalHotKeys(self._hotkeys)
            self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


class SingleHotkeyListener:
    """parファイル別の一時停止キーなど、1つのホットキーだけを監視する。"""

    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        self._hotkeys = {hotkey: callback}
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        if self._listener is None:
            self._listener = keyboard.GlobalHotKeys(self._hotkeys)
            self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
