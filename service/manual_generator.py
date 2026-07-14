"""保存済みの.par / .bundleから日本語の操作手順書(Markdown)を生成する。

Qt非依存の静的解析モジュール。ラベルはapp/constants.pyの既存辞書を再利用する
（constants.pyはQt importを持たない純文字列モジュール）。
write_*は既存の.mdを黙って上書きする（手順書は常に再生成できるため）。
"""

from datetime import datetime
from pathlib import Path

from app.constants import (
    ACTION_LABELS,
    CONDITION_LABELS,
    MSG_CONFIRM_DEFAULT,
    STOP_MODE_LABELS,
    TAB_FINAL,
    TAB_INITIAL,
    TAB_LOOP,
    WORKFLOW_STEP_TYPE_LABELS,
)
from service import key_notation
from service.key_notation import KeyToken
from service.models import ActionItem, ActionType, Condition, MacroFile, MacroSettings
from service.ui_selector import UiSelector
from service.workflow import ASSETS_DIRNAME, StepType, WorkflowBundle, WorkflowStep

MANUAL_FILENAME = "manual.md"

_NO_VALUE = "なし"
_NO_ITEMS = "（操作なし）"
_IMAGE_IN_FILE = "（画像はファイル内に保存）"
_MISSING_RECORDING = "（レコーディングファイルが見つかりません: {name}）"
_INFINITE_WAIT = "（無限待機）"
_MAX_WAIT = "（最大待機{sec}秒）"

_MODIFIER_NAMES = {"shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "win": "Win"}

# pyautoguiキー名 -> 表示名（SPECIAL_KEYSの逆引き、同名キーは先勝ち）
_KEY_NAMES: dict[str, str] = {}
for _name, _key in key_notation.SPECIAL_KEYS.items():
    _KEY_NAMES.setdefault(_key, _name)

_COMMAND_TEXTS = {
    "wait": "0.5秒待機",
    "clip": "クリップボード貼り付け",
    "clear": "クリップボードを空にする",
    "ime_toggle": "IME切り替え",
    "ime_on": "IMEオン",
    "ime_off": "IMEオフ",
}


# --- 要素単位の日本語化 ---


def describe_keys(keys: str) -> str:
    """キーボード操作の記法を日本語文にする。不正な記法は生文字列を返す。"""
    if not keys:
        return ""
    try:
        tokens = key_notation.parse(keys)
    except ValueError:
        return keys
    return "、".join(_describe_token(token) for token in tokens)


def _describe_token(token: KeyToken) -> str:
    if token.kind == "key":
        names = [_MODIFIER_NAMES[m] for m in token.modifiers]
        names.append(_KEY_NAMES.get(token.value, token.value.upper()))
        return f"[{'+'.join(names)}]"
    if token.kind == "text":
        return f"「{token.value}」と入力"
    if token.kind == "var":
        return f"クリップボード変数「{token.value.split(':')[0]}」を入力"
    return _COMMAND_TEXTS[token.kind]


def describe_selector(selector: UiSelector) -> str:
    """UIA要素セレクタを日本語文にする。"""
    control = selector.control_type or "コントロール"
    identifier = selector.automation_id or selector.name
    text = f"{control}『{identifier}』"
    window = selector.window_automation_id or selector.window_name
    if window:
        text = f"ウィンドウ『{window}』の{text}"
    if selector.found_index != 1:
        text += f"（{selector.found_index}番目）"
    return text


def _describe_target(item: ActionItem) -> str:
    if item.selector is not None:
        return describe_selector(item.selector)
    return f"座標({item.x}, {item.y})"


def describe_action(item: ActionItem) -> str:
    """項目のマウス・アプリ操作を1文にする。"""
    label = ACTION_LABELS[item.action.value]
    if item.action == ActionType.DRAG:
        to_x, to_y = item.drag_to if item.drag_to else (item.x, item.y)
        return f"座標({item.x}, {item.y})から座標({to_x}, {to_y})へドラッグ"
    if item.action == ActionType.LAUNCH_APP:
        return f"{label}: {item.app_path}"
    if item.action == ActionType.KEY_ONLY:
        return "キー操作のみ"
    if item.action == ActionType.NONE:
        if item.selector is None and item.x is None and item.y is None:
            return "（マウス操作なし）"
        return f"{_describe_target(item)}へ移動のみ"
    if item.action in (ActionType.SET_TEXT, ActionType.GET_TEXT):
        return f"{_describe_target(item)}に{label}"
    return f"{_describe_target(item)}を{label}"


def describe_condition(condition: Condition) -> str:
    """条件判断を1文にする。"""
    text = CONDITION_LABELS[condition.condition_type.value]
    value_text = _condition_value_text(condition)
    if value_text:
        text += f": {value_text}"
    if condition.condition_type.value.endswith("_wait"):
        text += (
            _INFINITE_WAIT
            if condition.max_wait_sec == 0
            else _MAX_WAIT.format(sec=condition.max_wait_sec)
        )
    return text


def _condition_value_text(condition: Condition) -> str:
    kind = condition.condition_type.value
    value = condition.value
    if kind == "image_shown_wait":
        return _IMAGE_IN_FILE
    if kind.startswith("clip_"):
        return f"正規表現「{value}」"
    if kind.startswith("color_"):
        parts = [p.strip() for p in value.split(",")]
        if len(parts) >= 3:
            return f"色 #{parts[0]}（座標({parts[1]},{parts[2]})）"
        return f"色 #{parts[0]}（カーソル位置）"
    if kind in ("file_larger_run", "file_smaller_run"):
        path, _, size = value.rpartition(",")
        return f"「{path}」（{size}バイト）"
    if kind.startswith("button_"):
        return f"ボタン「{value}」"
    return f"「{value}」"


# --- マクロ手順書 ---


def generate_macro_manual(
    macro: MacroFile, title: str, source_name: str = "", heading_level: int = 1
) -> str:
    """マクロの操作手順書(Markdown)を生成する。"""
    heading = "#" * heading_level
    lines = [f"{heading} {title}", ""]
    if source_name:
        lines.append(f"- 元ファイル: {source_name}")
    lines += [f"- 生成日時: {_timestamp()}", ""]
    lines += _settings_table(macro.settings, heading_level)
    for tab_title, items in (
        (TAB_INITIAL, macro.initial),
        (TAB_LOOP, macro.loop),
        (TAB_FINAL, macro.final),
    ):
        lines += _items_section(tab_title, items, heading_level)
    return "\n".join(lines).rstrip("\n") + "\n"


def _settings_table(settings: MacroSettings, heading_level: int) -> list[str]:
    stop_mode = STOP_MODE_LABELS.get(settings.stop_timer_mode, settings.stop_timer_mode)
    rows = [
        ("繰り返し回数", str(settings.repeat_count)),
        ("再生タイマー", settings.play_timer or _NO_VALUE),
        ("停止タイマー", settings.stop_timer or _NO_VALUE),
        ("停止タイマーの動作", stop_mode),
        # <ctrl>等がHTMLタグ扱いで非表示にならないようコード表記にする
        ("一時停止キー", f"`{settings.pause_hotkey}`" if settings.pause_hotkey else _NO_VALUE),
        ("速度率", f"{settings.speed_percent}%"),
    ]
    lines = [
        f"{'#' * (heading_level + 1)} 再生設定",
        "",
        "| 設定 | 値 |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | {value} |" for name, value in rows]
    lines.append("")
    return lines


def _items_section(
    title: str, items: list[ActionItem], heading_level: int
) -> list[str]:
    lines = [f"{'#' * (heading_level + 1)} {title}", ""]
    if not items:
        return lines + [_NO_ITEMS, ""]
    for number, item in enumerate(items, start=1):
        lines += _item_lines(number, item)
    lines.append("")
    return lines


def _item_lines(number: int, item: ActionItem) -> list[str]:
    lines = [f"{number}. {describe_action(item)}（間隔{item.interval}秒）"]
    if item.condition is not None:
        lines.append(f"    - 条件判断: {describe_condition(item.condition)}")
    if item.keys:
        if item.action == ActionType.SET_TEXT:
            lines.append(f"    - 書き込むテキスト: {item.keys}")
        else:
            lines.append(f"    - キーボード操作: {describe_keys(item.keys)}")
    if item.repeat_offset != (0, 0):
        offset_x, offset_y = item.repeat_offset
        lines.append(f"    - 繰り返すたびに移動する量: (X{offset_x:+d}, Y{offset_y:+d})")
    if item.key_repeat_increase:
        lines.append("    - 繰り返すたびにキー操作の実行回数を増加")
    return lines


# --- バンドル手順書 ---


def generate_bundle_manual(bundle: WorkflowBundle) -> str:
    """ワークフローバンドルの操作手順書(Markdown)を生成する。"""
    steps = bundle.workflow.steps
    lines = [
        f"# 操作手順書: {bundle.workflow.name}",
        "",
        f"- 生成日時: {_timestamp()}",
        f"- ステップ数: {len(steps)}",
        "",
    ]
    for number, step in enumerate(steps, start=1):
        type_label = WORKFLOW_STEP_TYPE_LABELS[step.step_type.value]
        lines += [f"## 手順{number}: {step.label}（{type_label}）", ""]
        lines += _step_body(step, bundle)
    return "\n".join(lines).rstrip("\n") + "\n"


def _step_body(step: WorkflowStep, bundle: WorkflowBundle) -> list[str]:
    if step.step_type == StepType.PLAY_RECORDING:
        return _recording_section(step, bundle)
    if step.step_type == StepType.WAIT_IMAGE:
        wait = (
            _INFINITE_WAIT
            if step.max_wait_sec == 0
            else _MAX_WAIT.format(sec=step.max_wait_sec)
        )
        return [
            f"![{step.image}]({ASSETS_DIRNAME}/{step.image})",
            "",
            f"上の画像が表示されるまで待機{wait}",
            "",
        ]
    return [f"> {step.message or MSG_CONFIRM_DEFAULT}", ""]


def _recording_section(step: WorkflowStep, bundle: WorkflowBundle) -> list[str]:
    try:
        macro = MacroFile.load(bundle.recording_path(step.recording))
    except (OSError, ValueError, KeyError):
        return [_MISSING_RECORDING.format(name=step.recording), ""]
    text = generate_macro_manual(
        macro, title=f"レコーディング: {step.recording}", heading_level=3
    )
    return [text.rstrip("\n"), ""]


# --- ファイル出力 ---


def write_macro_manual(par_path: Path, output_dir: Path | None = None) -> Path:
    """`foo.par`を読み、`foo.md`を書き出してそのパスを返す。

    output_dir省略時は.parと同じフォルダに書き出す。
    """
    par_path = Path(par_path)
    macro = MacroFile.load(par_path)
    text = generate_macro_manual(
        macro, title=f"操作手順書: {par_path.stem}", source_name=par_path.name
    )
    output_dir = Path(output_dir) if output_dir is not None else par_path.parent
    output_path = output_dir / f"{par_path.stem}.md"
    output_path.write_text(text, encoding="utf-8")
    return output_path


def write_bundle_manual(bundle_path: Path) -> Path:
    """バンドルを読み、バンドル内へ`manual.md`を書き出してそのパスを返す。"""
    bundle = WorkflowBundle.load(bundle_path)
    output_path = bundle.path / MANUAL_FILENAME
    output_path.write_text(generate_bundle_manual(bundle), encoding="utf-8")
    return output_path


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
