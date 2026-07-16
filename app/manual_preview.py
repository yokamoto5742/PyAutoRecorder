"""手順書プレビュー: メモリ上のマクロから生成した手順書(Markdown)を表示し、
一覧で選択された行に対応する手順へスクロール・ハイライトする（閲覧専用）。"""

from PySide6.QtGui import (
    QColor,
    QTextBlock,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import QTextBrowser, QTextEdit, QVBoxLayout, QWidget

from app import constants
from service.manual_generator import generate_macro_manual
from service.models import MacroFile

# 手順書のセクション見出し -> 一覧のページ名
_PAGE_BY_HEADING = {
    constants.TAB_INITIAL: "initial",
    constants.TAB_LOOP: "loop",
    constants.TAB_FINAL: "final",
}
_HIGHLIGHT_COLOR = QColor("#ffe066")


def build_step_map(document: QTextDocument) -> dict[tuple[str, int], int]:
    """(ページ名, 通し番号) -> ブロック先頭位置の対応表を文書構造から作る。

    見出しテキストでセクションを判定し、その配下の番号付きリスト項目だけを
    数える（入れ子の箇条書き・表・段落は対象外）。
    """
    step_map: dict[tuple[str, int], int] = {}
    counts: dict[str, int] = {}
    page: str | None = None
    block = document.begin()
    while block.isValid():
        if block.blockFormat().headingLevel() > 0:
            page = _PAGE_BY_HEADING.get(block.text())
        elif page is not None and _is_numbered_item(block):
            counts[page] = counts.get(page, 0) + 1
            step_map[(page, counts[page])] = block.position()
        block = block.next()
    return step_map


def _is_numbered_item(block: QTextBlock) -> bool:
    text_list = block.textList()
    return (
        text_list is not None
        and text_list.format().style() == QTextListFormat.Style.ListDecimal
    )


class ManualPreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._browser = QTextBrowser()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._browser)
        self._step_map: dict[tuple[str, int], int] = {}

    def set_macro(self, macro: MacroFile, name: str) -> None:
        """マクロから手順書を再生成して表示する。"""
        text = generate_macro_manual(
            macro, title=constants.MANUAL_PREVIEW_TITLE.format(name=name)
        )
        self._browser.setMarkdown(text)
        self._step_map = build_step_map(self._browser.document())
        self._browser.setExtraSelections([])

    def highlight_step(self, page: str, number: int) -> None:
        """該当手順へスクロールしてハイライトする。対応する手順がなければ解除のみ。"""
        position = self._step_map.get((page, number))
        if position is None:
            self._browser.setExtraSelections([])
            return
        cursor = QTextCursor(self._browser.document())
        cursor.setPosition(position)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(_HIGHLIGHT_COLOR)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        self._browser.setExtraSelections([selection])
        scroll_cursor = QTextCursor(self._browser.document())
        scroll_cursor.setPosition(position)
        self._browser.setTextCursor(scroll_cursor)
        self._browser.ensureCursorVisible()
