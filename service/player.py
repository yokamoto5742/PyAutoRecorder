"""再生エンジン: MacroFileの項目を 最初の処理→繰り返し処理×N→最後の処理 の順に実行する。"""

import subprocess
import threading
import time

import pyautogui
import pyperclip
from PySide6.QtCore import QThread, Signal

from service import ime_control, ui_selector
from service.conditions import ConditionContext, should_run
from service.key_notation import WAIT_SECONDS, KeyToken, parse
from service.models import ActionItem, ActionType, MacroFile

MSG_ELEMENT_NOT_FOUND = "対象コントロールが見つかりませんでした: {name}"
MSG_SELECTOR_REQUIRED = "対象コントロールが指定されていません"

pyautogui.PAUSE = 0.0
pyautogui.FAILSAFE = True  # 画面左上隅へのマウス移動で緊急停止

KEY_INTERVAL_SEC = 0.02
POINTER_CLICK_INTERVAL_SEC = 0.05
MOVE_DURATION_SEC = 0.0  # マウスの軌道はトレースせず瞬間移動する
DRAG_DURATION_SEC = 0.3
_TICK_SEC = 0.05

_MOUSE_BUTTONS = {
    ActionType.LEFT_CLICK: ("left", 1),
    ActionType.RIGHT_CLICK: ("right", 1),
    ActionType.DOUBLE_CLICK: ("left", 2),
    ActionType.MIDDLE_CLICK: ("middle", 1),
}


class MacroPlayer(QThread):
    item_started = Signal(str, int)  # ページ名("initial"/"loop"/"final"), インデックス
    error_occurred = Signal(str)
    playback_finished = Signal(bool)  # Trueなら最後まで実行された

    def __init__(
        self,
        macro: MacroFile,
        parent=None,
        stop_event: threading.Event | None = None,
        pause_event: threading.Event | None = None,
    ) -> None:
        super().__init__(parent)
        self._macro = macro
        # ワークフローから同期実行する際は停止・一時停止イベントを共有する
        self._stop_event = stop_event if stop_event is not None else threading.Event()
        self._pause_event = (
            pause_event if pause_event is not None else threading.Event()
        )
        self._final_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.clear()

    def toggle_pause(self) -> None:
        if self._pause_event.is_set():
            self._pause_event.clear()
        else:
            self._pause_event.set()

    def skip_to_final(self) -> None:
        """繰り返し処理を打ち切り、最後の処理へ移行する（停止タイマー用）。"""
        self._final_event.set()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def run(self) -> None:
        self.playback_finished.emit(self.play_blocking())

    def play_blocking(self) -> bool:
        """呼び出し元スレッドで同期実行する（ワークフロー用）。Trueなら完走。"""
        try:
            return self._run_all()
        except pyautogui.FailSafeException:
            return False
        except (ValueError, OSError) as e:  # OSErrorはアプリ起動失敗時
            self.error_occurred.emit(str(e))
            return False

    def _run_all(self) -> bool:
        if not self._play_page("initial", self._macro.initial, 0):
            return False
        for index in range(1, self._macro.settings.repeat_count + 1):
            if self._final_event.is_set():
                break
            if not self._play_page("loop", self._macro.loop, index):
                return False
        return self._play_page("final", self._macro.final, 0)

    def _play_page(self, page: str, items: list[ActionItem], repeat_index: int) -> bool:
        """1ページ分の項目を実行する。停止された場合のみFalse。"""
        for index, item in enumerate(items):
            if self._stop_event.is_set():
                return False
            if page == "loop" and self._final_event.is_set():
                return True
            self.item_started.emit(page, index)
            context = ConditionContext(
                repeat_index=repeat_index, stop_event=self._stop_event
            )
            if not should_run(item.condition, context):
                if self._stop_event.is_set():
                    return False
                continue  # 条件不成立によるスキップ
            if not self._sleep(self._scaled_interval(item.interval)):
                return False
            self._wait_while_paused()
            if self._stop_event.is_set():
                return False
            self._execute_item(item, repeat_index)
        return True

    def _scaled_interval(self, interval: float) -> float:
        """速度率（100〜300%）に応じて間隔を短縮する。"""
        percent = max(100, min(300, self._macro.settings.speed_percent))
        return interval * 100 / percent

    def _execute_item(self, item: ActionItem, repeat_index: int) -> None:
        if item.action == ActionType.LAUNCH_APP:
            if item.app_path:
                subprocess.Popen([item.app_path])
            return
        if item.action == ActionType.SET_TEXT:
            self._execute_set_text(item)
            return
        if item.action == ActionType.GET_TEXT:
            self._execute_get_text(item)
            return
        offset_count = max(0, repeat_index - 1)
        dx = item.repeat_offset[0] * offset_count
        dy = item.repeat_offset[1] * offset_count
        if (
            item.x is not None
            and item.y is not None
            and item.action != ActionType.KEY_ONLY
        ):
            self._execute_mouse(item, *self._resolve_point(item, dx, dy))
        if item.keys:
            times = (
                repeat_index if item.key_repeat_increase and repeat_index >= 1 else 1
            )
            tokens = parse(item.keys)
            for _ in range(times):
                if self._stop_event.is_set():
                    return
                self._send_tokens(tokens)

    def _resolve_point(self, item: ActionItem, dx: int, dy: int) -> tuple[int, int]:
        """クリック座標を決める。UIA要素が見つかればその中心、なければ記録座標。"""
        if item.selector is not None and item.action != ActionType.DRAG:
            point = ui_selector.find_clickable_point(item.selector)
            if point is not None:
                return point
        assert item.x is not None and item.y is not None
        return item.x + dx, item.y + dy

    def _execute_set_text(self, item: ActionItem) -> None:
        if item.selector is None:
            raise ValueError(MSG_SELECTOR_REQUIRED)
        if not ui_selector.set_element_text(item.selector, item.keys):
            raise ValueError(self._element_not_found(item))

    def _execute_get_text(self, item: ActionItem) -> None:
        if item.selector is None:
            raise ValueError(MSG_SELECTOR_REQUIRED)
        text = ui_selector.get_element_text(item.selector)
        if text is None:
            raise ValueError(self._element_not_found(item))
        pyperclip.copy(text)

    @staticmethod
    def _element_not_found(item: ActionItem) -> str:
        assert item.selector is not None
        name = item.selector.automation_id or item.selector.name
        return MSG_ELEMENT_NOT_FOUND.format(name=name)

    def _execute_mouse(self, item: ActionItem, x: int, y: int) -> None:
        pyautogui.moveTo(x, y, duration=MOVE_DURATION_SEC)
        if item.action == ActionType.NONE:
            return
        time.sleep(POINTER_CLICK_INTERVAL_SEC)
        if item.action == ActionType.DRAG:
            if item.drag_to is not None:
                pyautogui.mouseDown()
                pyautogui.moveTo(
                    item.drag_to[0], item.drag_to[1], duration=DRAG_DURATION_SEC
                )
                pyautogui.mouseUp()
            return
        button, clicks = _MOUSE_BUTTONS[item.action]
        pyautogui.click(button=button, clicks=clicks, interval=0.1)

    def _send_tokens(self, tokens: list[KeyToken]) -> None:
        for token in tokens:
            if self._stop_event.is_set():
                return
            self._wait_while_paused()
            self._send_token(token)
            time.sleep(KEY_INTERVAL_SEC)

    def _send_token(self, token: KeyToken) -> None:
        if token.kind == "text":
            self._type_text(token.value)
        elif token.kind == "key":
            if token.modifiers:
                pyautogui.hotkey(*token.modifiers, token.value)
            else:
                pyautogui.press(token.value)
        elif token.kind == "wait":
            self._sleep(WAIT_SECONDS)
        elif token.kind == "clip":
            pyautogui.hotkey("ctrl", "v")
        elif token.kind == "clear":
            pyperclip.copy("")
        elif token.kind == "ime_toggle":
            ime_control.toggle_ime()
        elif token.kind == "ime_on":
            ime_control.set_ime(True)
        elif token.kind == "ime_off":
            ime_control.set_ime(False)

    @staticmethod
    def _type_text(text: str) -> None:
        # 非ASCII文字（日本語等）はpyautogui.writeで入力できないためクリップボード経由で貼り付ける
        if text.isascii():
            pyautogui.write(text, interval=KEY_INTERVAL_SEC)
        else:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")

    def _sleep(self, seconds: float) -> bool:
        """停止・一時停止を監視しながら待機する。停止されたらFalse。"""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop_event.is_set():
                return False
            if self._pause_event.is_set():
                end += _TICK_SEC  # 一時停止中は残り時間を凍結する
            time.sleep(_TICK_SEC)
        return True

    def _wait_while_paused(self) -> None:
        while self._pause_event.is_set() and not self._stop_event.is_set():
            time.sleep(_TICK_SEC)
