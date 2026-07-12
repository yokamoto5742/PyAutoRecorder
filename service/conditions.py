"""条件判断機能: 項目実行前に評価し、実行(True)かスキップ(False)を返す。

待機系の条件は満たされるまでポーリングし、最大待機秒(0=無限)を超えるか
停止イベントが立った時点で打ち切る。最大待機超過時は強制再開（実行）する。
"""

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from service.models import Condition, ConditionType

POLL_INTERVAL_SEC = 1.0
IMAGE_CONFIDENCE = 0.9


@dataclass
class ConditionContext:
    repeat_index: int = 0  # 繰り返し処理の現在回目(1始まり)。他ページは0
    stop_event: threading.Event | None = None


def should_run(condition: Condition | None, context: ConditionContext) -> bool:
    """条件を評価する。Falseの場合はその項目をスキップする。"""
    if condition is None:
        return True
    handler = _HANDLERS[condition.condition_type]
    return handler(condition, context)


# --- 判定プリミティブ（テスト時はここを差し替える） ---


def get_window_titles() -> list[str]:
    import win32gui

    titles: list[str] = []

    def collect(hwnd: int, _param: object) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                titles.append(title)

    win32gui.EnumWindows(collect, None)
    return titles


def get_clipboard_text() -> str:
    import pyperclip

    return pyperclip.paste()


def get_pixel_color(x: int | None, y: int | None) -> tuple[int, int, int]:
    import pyautogui

    if x is None or y is None:
        x, y = pyautogui.position()
    return pyautogui.pixel(x, y)


def _query_button(
    button_name: str, parent_title: str, parent_class: str, check
) -> bool:
    """UI Automationでボタンを探してcheckを適用する（親ウィンドウ指定は省略可）。

    ボタン名・親タイトルは "id:AutomationId" 形式でAutomationId指定もできる
    （ウィンドウタイトルが患者名等で変動するアプリ向け）。
    """
    import uiautomation

    # 再生スレッドから呼ばれるためスレッドごとにCOMを初期化する
    with uiautomation.UIAutomationInitializerInThread():
        for window in uiautomation.GetRootControl().GetChildren():
            if parent_title:
                if parent_title.startswith("id:"):
                    if window.AutomationId != parent_title[len("id:") :]:
                        continue
                elif not title_matches([window.Name], parent_title):
                    continue
            if parent_class and window.ClassName != parent_class:
                continue
            if button_name.startswith("id:"):
                button = window.ButtonControl(
                    searchDepth=0xFFFFFFFF, AutomationId=button_name[len("id:") :]
                )
            else:
                button = window.ButtonControl(searchDepth=0xFFFFFFFF, Name=button_name)
            if button.Exists(maxSearchSeconds=0, searchIntervalSeconds=0):
                return check(button)
    return False


def button_shown(button_name: str, parent_title: str, parent_class: str) -> bool:
    return _query_button(
        button_name, parent_title, parent_class, lambda b: not b.IsOffscreen
    )


def button_enabled(button_name: str, parent_title: str, parent_class: str) -> bool:
    return _query_button(
        button_name,
        parent_title,
        parent_class,
        lambda b: not b.IsOffscreen and b.IsEnabled,
    )


def image_shown(image_base64: str) -> bool:
    """base64のPNGテンプレートが画面上に表示されているかを判定する。"""
    import base64
    import io

    import pyautogui
    from PIL import Image

    template = Image.open(io.BytesIO(base64.b64decode(image_base64)))
    try:
        return (
            pyautogui.locateOnScreen(template, confidence=IMAGE_CONFIDENCE) is not None
        )
    except pyautogui.ImageNotFoundException:
        return False


# --- 純ロジック ---


def title_matches(titles: list[str], pattern: str) -> bool:
    """ "..."で囲むと完全一致、そうでなければ部分一致。"""
    if len(pattern) >= 2 and pattern.startswith('"') and pattern.endswith('"'):
        exact = pattern[1:-1]
        return any(title == exact for title in titles)
    return any(pattern in title for title in titles)


def repeat_index_matches(spec: str, index: int) -> bool:
    """ "2|5|17"、"奇数"、"偶数"、"7n"(倍数)の記法で回目を判定する。"""
    for part in spec.split("|"):
        part = part.strip()
        if not part:
            continue
        if part == "奇数":
            if index % 2 == 1:
                return True
        elif part == "偶数":
            if index % 2 == 0:
                return True
        elif part.endswith("n") and part[:-1].isdigit():
            if index % int(part[:-1]) == 0:
                return True
        elif part.isdigit():
            if index == int(part):
                return True
    return False


def parse_color_spec(spec: str) -> tuple[tuple[int, int, int], int | None, int | None]:
    """ "RRGGBB,x,y"形式（座標省略可）をパースする。"""
    parts = [p.strip() for p in spec.split(",")]
    rgb_hex = parts[0]
    color = (int(rgb_hex[0:2], 16), int(rgb_hex[2:4], 16), int(rgb_hex[4:6], 16))
    if len(parts) >= 3:
        return color, int(parts[1]), int(parts[2])
    return color, None, None


def parse_datetime_spec(spec: str, now: datetime) -> datetime:
    """ "YYYY-MM-DD HH:MM"または"HH:MM"（本日、過去なら翌日）をパースする。"""
    spec = spec.strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", spec):
        hour, minute = map(int, spec.split(":"))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now.replace(second=0, microsecond=0):
            target += timedelta(days=1)
        return target
    return datetime.strptime(spec, "%Y-%m-%d %H:%M")


def parse_file_size_spec(spec: str) -> tuple[Path, int]:
    """ "パス,バイト数"形式をパースする。"""
    path_str, size_str = spec.rsplit(",", 1)
    return Path(path_str.strip()), int(size_str.strip())


def parse_button_spec(spec: str) -> tuple[str, str, str]:
    """ "ボタン名[,親タイトル or class:クラス名]"形式をパースする。

    戻り値は (ボタン名, 親タイトル, 親クラス名)。親指定省略時は全ウィンドウ対象。
    """
    if "," not in spec:
        return spec.strip(), "", ""
    button_name, parent = spec.split(",", 1)
    parent = parent.strip()
    if parent.startswith("class:"):
        return button_name.strip(), "", parent[len("class:") :].strip()
    return button_name.strip(), parent, ""


# --- 待機ループ ---


def _wait_until(predicate, condition: Condition, context: ConditionContext) -> bool:
    """条件が満たされるまで待機する。停止時のみFalse（最大待機超過は強制再開）。"""
    started = time.monotonic()
    while not predicate():
        if context.stop_event is not None and context.stop_event.is_set():
            return False
        if condition.max_wait_sec > 0:
            if time.monotonic() - started >= condition.max_wait_sec:
                return True
        time.sleep(POLL_INTERVAL_SEC)
    return True


# --- 各条件のハンドラ ---


def _window_shown(condition: Condition) -> bool:
    return title_matches(get_window_titles(), condition.value)


def _color_matches(condition: Condition) -> bool:
    color, x, y = parse_color_spec(condition.value)
    return get_pixel_color(x, y) == color


def _handle_window(condition: Condition, context: ConditionContext) -> bool:
    kind = condition.condition_type
    if kind == ConditionType.WINDOW_SHOWN_WAIT:
        return _wait_until(lambda: _window_shown(condition), condition, context)
    if kind == ConditionType.WINDOW_CLOSED_WAIT:
        return _wait_until(lambda: not _window_shown(condition), condition, context)
    if kind == ConditionType.WINDOW_SHOWN_SKIP:
        return not _window_shown(condition)
    return _window_shown(condition)  # WINDOW_NOT_SHOWN_SKIP


def _handle_clipboard(condition: Condition, _context: ConditionContext) -> bool:
    found = re.search(condition.value, get_clipboard_text()) is not None
    if condition.condition_type == ConditionType.CLIP_CONTAINS_RUN:
        return found
    return not found


def _handle_color(condition: Condition, context: ConditionContext) -> bool:
    kind = condition.condition_type
    if kind == ConditionType.COLOR_MATCH_WAIT:
        return _wait_until(lambda: _color_matches(condition), condition, context)
    if kind == ConditionType.COLOR_NOT_MATCH_WAIT:
        return _wait_until(lambda: not _color_matches(condition), condition, context)
    if kind == ConditionType.COLOR_MATCH_RUN:
        return _color_matches(condition)
    return not _color_matches(condition)  # COLOR_NOT_MATCH_RUN


def _handle_file(condition: Condition, context: ConditionContext) -> bool:
    kind = condition.condition_type
    if kind == ConditionType.FILE_EXISTS_RUN:
        return Path(condition.value).exists()
    if kind == ConditionType.FILE_NOT_EXISTS_RUN:
        return not Path(condition.value).exists()
    if kind == ConditionType.FILE_CREATED_WAIT:
        return _wait_until(lambda: Path(condition.value).exists(), condition, context)
    path, size = parse_file_size_spec(condition.value)
    if not path.exists():
        return False
    if kind == ConditionType.FILE_LARGER_RUN:
        return path.stat().st_size > size
    return path.stat().st_size < size  # FILE_SMALLER_RUN


def _handle_datetime(condition: Condition, context: ConditionContext) -> bool:
    if condition.condition_type == ConditionType.DATETIME_WAIT:
        target = parse_datetime_spec(condition.value, datetime.now())
        return _wait_until(lambda: datetime.now() >= target, condition, context)
    return datetime.now().strftime("%H:%M") == condition.value.strip()


def _handle_repeat_index(condition: Condition, context: ConditionContext) -> bool:
    return repeat_index_matches(condition.value, context.repeat_index)


def _button_shown(condition: Condition) -> bool:
    return button_shown(*parse_button_spec(condition.value))


def _button_enabled(condition: Condition) -> bool:
    return button_enabled(*parse_button_spec(condition.value))


def _handle_button(condition: Condition, context: ConditionContext) -> bool:
    kind = condition.condition_type
    if kind == ConditionType.BUTTON_SHOWN_WAIT:
        return _wait_until(lambda: _button_shown(condition), condition, context)
    if kind == ConditionType.BUTTON_HIDDEN_WAIT:
        return _wait_until(lambda: not _button_shown(condition), condition, context)
    if kind == ConditionType.BUTTON_ENABLED_WAIT:
        return _wait_until(lambda: _button_enabled(condition), condition, context)
    if kind == ConditionType.BUTTON_SHOWN_SKIP:
        return not _button_shown(condition)
    return _button_shown(condition)  # BUTTON_NOT_SHOWN_SKIP


def _handle_image(condition: Condition, context: ConditionContext) -> bool:
    return _wait_until(lambda: image_shown(condition.image), condition, context)


_HANDLERS = {
    ConditionType.WINDOW_SHOWN_WAIT: _handle_window,
    ConditionType.WINDOW_CLOSED_WAIT: _handle_window,
    ConditionType.WINDOW_SHOWN_SKIP: _handle_window,
    ConditionType.WINDOW_NOT_SHOWN_SKIP: _handle_window,
    ConditionType.CLIP_CONTAINS_RUN: _handle_clipboard,
    ConditionType.CLIP_NOT_CONTAINS_RUN: _handle_clipboard,
    ConditionType.COLOR_MATCH_WAIT: _handle_color,
    ConditionType.COLOR_NOT_MATCH_WAIT: _handle_color,
    ConditionType.COLOR_MATCH_RUN: _handle_color,
    ConditionType.COLOR_NOT_MATCH_RUN: _handle_color,
    ConditionType.FILE_EXISTS_RUN: _handle_file,
    ConditionType.FILE_NOT_EXISTS_RUN: _handle_file,
    ConditionType.FILE_CREATED_WAIT: _handle_file,
    ConditionType.FILE_LARGER_RUN: _handle_file,
    ConditionType.FILE_SMALLER_RUN: _handle_file,
    ConditionType.DATETIME_WAIT: _handle_datetime,
    ConditionType.DATETIME_MATCH_RUN: _handle_datetime,
    ConditionType.REPEAT_INDEX_RUN: _handle_repeat_index,
    ConditionType.BUTTON_SHOWN_WAIT: _handle_button,
    ConditionType.BUTTON_HIDDEN_WAIT: _handle_button,
    ConditionType.BUTTON_ENABLED_WAIT: _handle_button,
    ConditionType.BUTTON_SHOWN_SKIP: _handle_button,
    ConditionType.BUTTON_NOT_SHOWN_SKIP: _handle_button,
    ConditionType.IMAGE_SHOWN_WAIT: _handle_image,
}
