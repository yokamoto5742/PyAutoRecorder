"""クリップボード変数の実行前確認: クリップボードを解析・検証し、取り込む値を一覧提示する。"""

import pyperclip
from PySide6.QtWidgets import QMessageBox, QWidget

from app import constants
from service import clipboard_fields


def confirm_fields(
    specs: list[str], parent: QWidget, title: str
) -> dict[str, str] | None:
    """使用する全変数を解決して確認ダイアログを表示する。

    OKなら変数辞書を返す。キャンセル・キー欠損・書式不正はNone（再生を開始しない）。
    """
    fields = clipboard_fields.parse_fields(pyperclip.paste())
    try:
        resolved = clipboard_fields.resolve_all(specs, fields)
    except ValueError as e:
        QMessageBox.warning(parent, title, constants.MSG_FIELDS_ERROR.format(error=e))
        return None
    lines = "\n".join(
        f"{clipboard_fields.var_name(spec)}：{value}"
        for spec, value in resolved.items()
    )
    answer = QMessageBox.question(
        parent, title, constants.MSG_FIELDS_CONFIRM.format(values=lines)
    )
    if answer != QMessageBox.StandardButton.Yes:
        return None
    return fields
