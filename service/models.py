import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from service.ui_selector import UiSelector

FILE_EXTENSION = ".par"


class ActionType(Enum):
    NONE = "none"
    LEFT_CLICK = "left"
    RIGHT_CLICK = "right"
    DOUBLE_CLICK = "double"
    MIDDLE_CLICK = "middle"
    DRAG = "drag"
    KEY_ONLY = "key_only"
    LAUNCH_APP = "launch_app"
    SET_TEXT = "set_text"  # UIA要素にテキストを直接書き込む（keysが書き込む文字列）
    GET_TEXT = "get_text"  # UIA要素のテキストをクリップボードへ読み取る


class ConditionType(Enum):
    # ウィンドウタイトル（value=タイトル文字列、"..."で完全一致）
    WINDOW_SHOWN_WAIT = "window_shown_wait"
    WINDOW_CLOSED_WAIT = "window_closed_wait"
    WINDOW_SHOWN_SKIP = "window_shown_skip"
    WINDOW_NOT_SHOWN_SKIP = "window_not_shown_skip"
    # クリップボード（value=正規表現）
    CLIP_CONTAINS_RUN = "clip_contains_run"
    CLIP_NOT_CONTAINS_RUN = "clip_not_contains_run"
    # 指定座標の色（value="RRGGBB,x,y"、座標省略時はカーソル位置）
    COLOR_MATCH_WAIT = "color_match_wait"
    COLOR_NOT_MATCH_WAIT = "color_not_match_wait"
    COLOR_MATCH_RUN = "color_match_run"
    COLOR_NOT_MATCH_RUN = "color_not_match_run"
    # ファイル（value=フルパス、サイズ比較は"パス,バイト数"）
    FILE_EXISTS_RUN = "file_exists_run"
    FILE_NOT_EXISTS_RUN = "file_not_exists_run"
    FILE_CREATED_WAIT = "file_created_wait"
    FILE_LARGER_RUN = "file_larger_run"
    FILE_SMALLER_RUN = "file_smaller_run"
    # 日時（value="YYYY-MM-DD HH:MM"または"HH:MM"）
    DATETIME_WAIT = "datetime_wait"
    DATETIME_MATCH_RUN = "datetime_match_run"
    # 繰り返し回目（value="2|5|17"、"奇数"、"偶数"、"7n"）
    REPEAT_INDEX_RUN = "repeat_index_run"
    # ボタン（value="ボタン名 or id:AutomationId[,親タイトル or id:… or class:…]"）
    BUTTON_SHOWN_WAIT = "button_shown_wait"
    BUTTON_HIDDEN_WAIT = "button_hidden_wait"
    BUTTON_SHOWN_SKIP = "button_shown_skip"
    BUTTON_NOT_SHOWN_SKIP = "button_not_shown_skip"
    BUTTON_ENABLED_WAIT = "button_enabled_wait"
    # 画像認識（imageフィールドのbase64 PNGが画面に表示されるまで待機）
    IMAGE_SHOWN_WAIT = "image_shown_wait"


@dataclass
class Condition:
    condition_type: ConditionType
    value: str = ""
    max_wait_sec: int = 0  # 待機系のみ有効。0は無限待機
    image: str = ""  # 画像認識条件用のテンプレート画像（PNGのbase64）

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.condition_type.value,
            "value": self.value,
            "max_wait_sec": self.max_wait_sec,
        }
        if self.image:
            data["image"] = self.image
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Condition":
        return cls(
            condition_type=ConditionType(data["type"]),
            value=data.get("value", ""),
            max_wait_sec=int(data.get("max_wait_sec", 0)),
            image=data.get("image", ""),
        )


@dataclass
class ActionItem:
    interval: float = 1.0
    x: int | None = None
    y: int | None = None
    action: ActionType = ActionType.NONE
    keys: str = ""
    drag_to: tuple[int, int] | None = None  # DRAG時の終点座標
    repeat_offset: tuple[int, int] = (0, 0)  # 繰り返すたびに移動する量
    key_repeat_increase: bool = False  # 繰り返すたびにキー操作の実行回数を増加
    condition: Condition | None = None
    app_path: str = ""  # LAUNCH_APP時に起動するアプリのフルパス
    selector: UiSelector | None = None  # UIA要素指定。クリック時は座標より優先

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "interval": self.interval,
            "x": self.x,
            "y": self.y,
            "action": self.action.value,
            "keys": self.keys,
        }
        if self.drag_to is not None:
            data["drag_to"] = list(self.drag_to)
        if self.repeat_offset != (0, 0):
            data["repeat_offset"] = list(self.repeat_offset)
        if self.key_repeat_increase:
            data["key_repeat_increase"] = True
        if self.condition is not None:
            data["condition"] = self.condition.to_dict()
        if self.app_path:
            data["app_path"] = self.app_path
        if self.selector is not None:
            data["selector"] = self.selector.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionItem":
        drag_to = data.get("drag_to")
        repeat_offset = data.get("repeat_offset", [0, 0])
        condition = data.get("condition")
        selector = data.get("selector")
        return cls(
            interval=float(data.get("interval", 1.0)),
            x=data.get("x"),
            y=data.get("y"),
            action=ActionType(data.get("action", "none")),
            keys=data.get("keys", ""),
            drag_to=(drag_to[0], drag_to[1]) if drag_to else None,
            repeat_offset=(repeat_offset[0], repeat_offset[1]),
            key_repeat_increase=bool(data.get("key_repeat_increase", False)),
            condition=Condition.from_dict(condition) if condition else None,
            app_path=data.get("app_path", ""),
            selector=UiSelector.from_dict(selector) if selector else None,
        )


@dataclass
class MacroSettings:
    repeat_count: int = 1
    play_timer: str = ""  # "HH:MM" 空文字は無効
    stop_timer: str = ""
    stop_timer_mode: str = "all"  # "all"=すべて停止 / "final"=最後の処理へ移行
    pause_hotkey: str = ""  # pynput記法（例 "<f5>", "<ctrl>+<f9>"）。空は無効
    speed_percent: int = 100  # 全体の再生速度率（100〜300%）

    def to_dict(self) -> dict[str, Any]:
        return {
            "repeat_count": self.repeat_count,
            "play_timer": self.play_timer,
            "stop_timer": self.stop_timer,
            "stop_timer_mode": self.stop_timer_mode,
            "pause_hotkey": self.pause_hotkey,
            "speed_percent": self.speed_percent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroSettings":
        return cls(
            repeat_count=int(data.get("repeat_count", 1)),
            play_timer=data.get("play_timer", ""),
            stop_timer=data.get("stop_timer", ""),
            stop_timer_mode=data.get("stop_timer_mode", "all"),
            pause_hotkey=data.get("pause_hotkey", ""),
            speed_percent=int(data.get("speed_percent", 100)),
        )


@dataclass
class MacroFile:
    settings: MacroSettings = field(default_factory=MacroSettings)
    initial: list[ActionItem] = field(default_factory=list)
    loop: list[ActionItem] = field(default_factory=list)
    final: list[ActionItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings": self.settings.to_dict(),
            "initial": [item.to_dict() for item in self.initial],
            "loop": [item.to_dict() for item in self.loop],
            "final": [item.to_dict() for item in self.final],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroFile":
        return cls(
            settings=MacroSettings.from_dict(data.get("settings", {})),
            initial=[ActionItem.from_dict(d) for d in data.get("initial", [])],
            loop=[ActionItem.from_dict(d) for d in data.get("loop", [])],
            final=[ActionItem.from_dict(d) for d in data.get("final", [])],
        )

    def save(self, path: Path | str) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | str) -> "MacroFile":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)
