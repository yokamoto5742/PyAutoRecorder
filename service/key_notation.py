"""キーボード操作のトークン記法のパース・生成。

記法（参考資料互換）:
- 通常の文字はそのまま記述する（例: abc、こんにちは）
- 特殊キーは {ENTER} {TAB} {DOWN} {F1} などで表す
- 修飾キーは直後のキーに適用: +(Shift) ^(Ctrl) %(Alt) `(Win)
- ( ) { } , + ^ ~ % ` と半角スペースを文字として渡すには {(} {+} {SPACE} のように囲む
- {WAIT}=0.5秒待ち {CLIP}=クリップボード貼り付け {CLEAR}=クリップボードを空にする
- {IME}=IMEトグル {IMEON} {IMEOFF}
- {VAR:キー名} {VAR:キー名:日付} {VAR:キー名:時刻} =クリップボード変数（Excelコピー取込）
"""

from dataclasses import dataclass, field

WAIT_SECONDS = 0.5

MODIFIER_CHARS: dict[str, str] = {
    "+": "shift",
    "^": "ctrl",
    "%": "alt",
    "`": "win",
}

# トークン名 -> pyautoguiのキー名
SPECIAL_KEYS: dict[str, str] = {
    "ENTER": "enter",
    "TAB": "tab",
    "ESC": "esc",
    "BS": "backspace",
    "BACKSPACE": "backspace",
    "DEL": "delete",
    "DELETE": "delete",
    "INS": "insert",
    "HOME": "home",
    "END": "end",
    "PGUP": "pageup",
    "PGDN": "pagedown",
    "UP": "up",
    "DOWN": "down",
    "LEFT": "left",
    "RIGHT": "right",
    "SPACE": "space",
    "WIN": "win",
    "MENU": "apps",
    "ALT": "alt",
    "SHIFT": "shift",
    "CTRL": "ctrl",
    "CAPSLOCK": "capslock",
    "NUMLOCK": "numlock",
    "PRTSC": "printscreen",
    "PAUSE": "pause",
    **{f"F{n}": f"f{n}" for n in range(1, 13)},
}

# 文字として渡すために{}で囲む必要がある文字
ESCAPED_CHARS = "(){},+^~%` "

_COMMANDS = {"WAIT", "CLIP", "CLEAR", "IME", "IMEON", "IMEOFF"}


@dataclass(frozen=True)
class KeyToken:
    """パース結果の1トークン。

    kind: "key"=単一キー押下 / "text"=文字列入力 /
          "var"=クリップボード変数（valueは"キー名"または"キー名:書式"） /
          "wait" "clip" "clear" "ime_toggle" "ime_on" "ime_off"=コマンド
    """

    kind: str
    value: str = ""
    modifiers: tuple[str, ...] = field(default=())


def parse(notation: str) -> list[KeyToken]:
    """トークン記法の文字列をKeyTokenのリストに変換する。不正な記法はValueError。"""
    tokens: list[KeyToken] = []
    text_buffer: list[str] = []
    modifiers: list[str] = []
    i = 0

    def flush_text() -> None:
        if text_buffer:
            tokens.append(KeyToken(kind="text", value="".join(text_buffer)))
            text_buffer.clear()

    while i < len(notation):
        char = notation[i]
        if char in MODIFIER_CHARS:
            flush_text()
            modifiers.append(MODIFIER_CHARS[char])
            i += 1
            continue
        if char == "{":
            content, i = _read_braced(notation, i)
            token = _braced_token(content, tuple(modifiers))
            if token.kind == "text" and not modifiers:
                text_buffer.append(token.value)
            else:
                flush_text()
                tokens.append(token)
            modifiers.clear()
            continue
        if modifiers:
            tokens.append(
                KeyToken(kind="key", value=char.lower(), modifiers=tuple(modifiers))
            )
            modifiers.clear()
        else:
            text_buffer.append(char)
        i += 1

    if modifiers:
        raise ValueError(f"修飾キーの後にキーがありません: {notation}")
    flush_text()
    return tokens


def _read_braced(notation: str, start: int) -> tuple[str, int]:
    """start位置の '{' から閉じ括弧までを読み、(中身, 次の位置)を返す。"""
    if start + 1 < len(notation) and notation[start + 1] == "}":
        # "{}}" は literal '}'
        if start + 2 < len(notation) and notation[start + 2] == "}":
            return "}", start + 3
        raise ValueError(f"空のトークンです: 位置{start}")
    end = notation.find("}", start + 1)
    if end < 0:
        raise ValueError(f"閉じ括弧がありません: {notation[start:]}")
    return notation[start + 1 : end], end + 1


def _braced_token(content: str, modifiers: tuple[str, ...]) -> KeyToken:
    upper = content.upper()
    if upper.startswith("VAR:"):
        spec = content[4:].strip()
        if not spec:
            raise ValueError(f"変数名がありません: {{{content}}}")
        if modifiers:
            raise ValueError(f"修飾キーは変数に使えません: {{{content}}}")
        return KeyToken(kind="var", value=spec)
    if upper in SPECIAL_KEYS:
        return KeyToken(kind="key", value=SPECIAL_KEYS[upper], modifiers=modifiers)
    if upper in _COMMANDS:
        kind = {
            "WAIT": "wait",
            "CLIP": "clip",
            "CLEAR": "clear",
            "IME": "ime_toggle",
            "IMEON": "ime_on",
            "IMEOFF": "ime_off",
        }[upper]
        return KeyToken(kind=kind)
    if len(content) == 1 and content in ESCAPED_CHARS:
        if modifiers:
            return KeyToken(kind="key", value=content, modifiers=modifiers)
        return KeyToken(kind="text", value=content)
    raise ValueError(f"不明なトークンです: {{{content}}}")


def escape_char(char: str) -> str:
    """1文字をトークン記法で表す（特殊文字は{}で囲む）。"""
    if char == "}":
        return "{}}"
    if char in ESCAPED_CHARS:
        return "{" + char + "}"
    return char


def escape_text(text: str) -> str:
    """文字列全体をトークン記法で表す。"""
    return "".join(escape_char(c) for c in text)
