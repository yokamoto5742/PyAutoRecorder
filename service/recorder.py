"""自動記録: pynputのグローバルフックでマウス・キーボード操作をActionItem列に変換する。

記録単位はクリック/キー入力（マウスの移動軌跡は記録しない）。
- press→release間の移動が閾値を超えたらドラッグとして記録する
- 短時間・近接の左クリック2回はダブルクリック1項目にまとめる
- 連続するキー入力は1項目のトークン文字列にまとめ、クリックで区切る
- クリック時は座標の、キー入力開始時はフォーカス中のUIA要素情報（セレクタ）を
  ワーカースレッドで取得し、停止時に各項目へ付与する（ハイブリッド記録）
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from pynput import keyboard, mouse

from service.key_notation import escape_char
from service.models import ActionItem, ActionType
from service.ui_selector import selector_from_focus, selector_from_point

DRAG_THRESHOLD_PX = 10
DOUBLE_CLICK_SEC = 0.4
DOUBLE_CLICK_DISTANCE_PX = 5
MAX_KEYS_PER_ITEM = 200  # 1項目に記録するキーボード操作の上限（資料準拠）
SELECTOR_RESULT_TIMEOUT_SEC = 3.0  # 停止時にセレクタ取得を待つ上限

_MODIFIER_PREFIXES: dict[keyboard.Key, str] = {
    keyboard.Key.shift: "+",
    keyboard.Key.shift_r: "+",
    keyboard.Key.ctrl_l: "^",
    keyboard.Key.ctrl_r: "^",
    keyboard.Key.alt_l: "%",
    keyboard.Key.alt_gr: "%",
    keyboard.Key.cmd: "`",
    keyboard.Key.cmd_r: "`",
}

# 修飾キーが単独で押されたときのトークン
_MODIFIER_ALONE_TOKENS: dict[str, str] = {
    "+": "{SHIFT}",
    "^": "{CTRL}",
    "%": "{ALT}",
    "`": "{WIN}",
}

_SPECIAL_TOKENS: dict[keyboard.Key, str] = {
    keyboard.Key.enter: "{ENTER}",
    keyboard.Key.tab: "{TAB}",
    keyboard.Key.esc: "{ESC}",
    keyboard.Key.backspace: "{BS}",
    keyboard.Key.delete: "{DEL}",
    keyboard.Key.insert: "{INS}",
    keyboard.Key.home: "{HOME}",
    keyboard.Key.end: "{END}",
    keyboard.Key.page_up: "{PGUP}",
    keyboard.Key.page_down: "{PGDN}",
    keyboard.Key.up: "{UP}",
    keyboard.Key.down: "{DOWN}",
    keyboard.Key.left: "{LEFT}",
    keyboard.Key.right: "{RIGHT}",
    keyboard.Key.space: "{SPACE}",
    keyboard.Key.menu: "{MENU}",
    keyboard.Key.caps_lock: "{CAPSLOCK}",
    **{getattr(keyboard.Key, f"f{n}"): f"{{F{n}}}" for n in range(1, 13)},
}

_MOUSE_ACTIONS: dict[mouse.Button, ActionType] = {
    mouse.Button.left: ActionType.LEFT_CLICK,
    mouse.Button.right: ActionType.RIGHT_CLICK,
    mouse.Button.middle: ActionType.MIDDLE_CLICK,
}


class MacroRecorder:
    def __init__(self, ignore_region: Callable[[int, int], bool] | None = None) -> None:
        self._ignore_region = ignore_region
        self._items: list[ActionItem] = []
        self._lock = threading.Lock()
        self._last_event_time = 0.0
        self._key_buffer = ""
        self._key_interval = 0
        self._active_modifiers: dict[
            str, bool
        ] = {}  # prefix -> 他キーと組み合わされたか
        self._press_pos: tuple[int, int] | None = None
        self._press_interval = 0.0
        self._last_click_time = 0.0
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None
        self._selector_executor: ThreadPoolExecutor | None = None
        self._press_selector: Future | None = None
        self._key_selector: Future | None = None
        self._pending_selectors: list[tuple[ActionItem, Future]] = []

    def start(self) -> None:
        self._items.clear()
        self._pending_selectors.clear()
        self._key_selector = None
        self._last_event_time = time.monotonic()
        self._selector_executor = ThreadPoolExecutor(max_workers=1)
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> list[ActionItem]:
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        with self._lock:
            self._flush_key_buffer()
            items = list(self._items)
        self._attach_selectors()
        return items

    def _attach_selectors(self) -> None:
        """ワーカーで取得したUIA要素情報をクリック項目へ付与する。"""
        if self._selector_executor is None:
            return
        for item, future in self._pending_selectors:
            try:
                item.selector = future.result(timeout=SELECTOR_RESULT_TIMEOUT_SEC)
            except Exception:
                item.selector = None  # 取得失敗時は従来どおり座標のみで記録する
        self._selector_executor.shutdown(wait=False)
        self._selector_executor = None
        self._pending_selectors.clear()

    # --- マウス ---

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if self._ignore_region is not None and self._ignore_region(x, y):
            return
        if button not in _MOUSE_ACTIONS:
            return
        now = time.monotonic()
        with self._lock:
            if pressed:
                self._press_pos = (int(x), int(y))
                self._press_interval = now - self._last_event_time
                self._last_event_time = now
                # クリックでUIが変化する前に要素を特定するため押下時点で取得を開始する
                if self._selector_executor is not None:
                    self._press_selector = self._selector_executor.submit(
                        selector_from_point, int(x), int(y)
                    )
                return
            if self._press_pos is None:
                return
            self._flush_key_buffer()
            self._add_mouse_item(int(x), int(y), button, now)
            self._press_pos = None
            self._last_event_time = now

    def _add_mouse_item(self, x: int, y: int, button: mouse.Button, now: float) -> None:
        press_x, press_y = self._press_pos  # type: ignore[misc]
        press_selector = self._press_selector
        self._press_selector = None
        interval = round(self._press_interval)
        moved = (
            abs(x - press_x) > DRAG_THRESHOLD_PX or abs(y - press_y) > DRAG_THRESHOLD_PX
        )
        if moved and button == mouse.Button.left:
            self._items.append(
                ActionItem(
                    interval=interval,
                    x=press_x,
                    y=press_y,
                    action=ActionType.DRAG,
                    drag_to=(x, y),
                )
            )
            return
        if button == mouse.Button.left and self._merge_double_click(x, y, now):
            return  # 統合先（1回目のクリック）のセレクタをそのまま使う
        item = ActionItem(interval=interval, x=x, y=y, action=_MOUSE_ACTIONS[button])
        self._items.append(item)
        if press_selector is not None:
            self._pending_selectors.append((item, press_selector))
        self._last_click_time = now

    def _merge_double_click(self, x: int, y: int, now: float) -> bool:
        """直前の左クリックと近接・短時間なら1つのダブルクリック項目に統合する。"""
        if not self._items:
            return False
        last = self._items[-1]
        if (
            last.action == ActionType.LEFT_CLICK
            and last.x is not None
            and last.y is not None
            and now - self._last_click_time <= DOUBLE_CLICK_SEC
            and abs(x - last.x) <= DOUBLE_CLICK_DISTANCE_PX
            and abs(y - last.y) <= DOUBLE_CLICK_DISTANCE_PX
        ):
            last.action = ActionType.DOUBLE_CLICK
            return True
        return False

    # --- キーボード ---

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        with self._lock:
            if isinstance(key, keyboard.Key) and key in _MODIFIER_PREFIXES:
                self._active_modifiers.setdefault(_MODIFIER_PREFIXES[key], False)
                return
            token = self._key_to_token(key)
            if token is None:
                return
            prefixes = "".join(self._active_modifiers.keys())
            for prefix in self._active_modifiers:
                self._active_modifiers[prefix] = True
            self._append_keys(prefixes + token)

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if not isinstance(key, keyboard.Key) or key not in _MODIFIER_PREFIXES:
            return
        prefix = _MODIFIER_PREFIXES[key]
        with self._lock:
            used = self._active_modifiers.pop(prefix, True)
            if not used:
                self._append_keys(_MODIFIER_ALONE_TOKENS[prefix])

    def _key_to_token(self, key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(key, keyboard.Key):
            return _SPECIAL_TOKENS.get(key)
        char = key.char
        if char is None:
            return None
        # Ctrl押下中は制御文字(\x01-\x1a)が渡るため元の文字に戻す
        if "^" in self._active_modifiers and 1 <= ord(char) <= 26:
            char = chr(ord(char) + 96)
        return escape_char(char)

    def _append_keys(self, tokens: str) -> None:
        now = time.monotonic()
        if not self._key_buffer:
            self._key_interval = round(now - self._last_event_time)
            # 入力先を特定するため、入力開始時点のフォーカス要素を取得する
            if self._selector_executor is not None:
                self._key_selector = self._selector_executor.submit(selector_from_focus)
        self._last_event_time = now
        self._key_buffer += tokens
        if len(self._key_buffer) >= MAX_KEYS_PER_ITEM:
            self._flush_key_buffer()

    def _flush_key_buffer(self) -> None:
        if not self._key_buffer:
            return
        item = ActionItem(
            interval=self._key_interval,
            action=ActionType.KEY_ONLY,
            keys=self._key_buffer,
        )
        self._items.append(item)
        if self._key_selector is not None:
            self._pending_selectors.append((item, self._key_selector))
            self._key_selector = None
        self._key_buffer = ""
