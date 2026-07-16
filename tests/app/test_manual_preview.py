import pytest
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication

from app.manual_preview import ManualPreviewWidget, build_step_map
from service.manual_generator import generate_macro_manual
from service.models import ActionItem, ActionType, Condition, ConditionType, MacroFile


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    application = QApplication.instance() or QApplication([])
    yield application


def build_preview_macro() -> MacroFile:
    return MacroFile(
        initial=[ActionItem(action=ActionType.LEFT_CLICK, x=1, y=2)],
        loop=[
            ActionItem(action=ActionType.LEFT_CLICK, x=10, y=20),
            ActionItem(
                action=ActionType.KEY_ONLY,
                keys="{ENTER}",
                condition=Condition(ConditionType.CLIP_CONTAINS_RUN, value="abc"),
            ),
            ActionItem(action=ActionType.DOUBLE_CLICK, x=5, y=6),
        ],
    )


def build_document() -> QTextDocument:
    document = QTextDocument()
    document.setMarkdown(
        generate_macro_manual(build_preview_macro(), title="操作手順書: sample")
    )
    return document


class TestBuildStepMap:
    def test_counts_numbered_items_per_page(self):
        step_map = build_step_map(build_document())
        assert set(step_map) == {
            ("initial", 1),
            ("loop", 1),
            ("loop", 2),
            ("loop", 3),
        }

    def test_nested_bullets_are_not_counted(self):
        # loop 2番目の項目は条件・キー操作の入れ子付きだが手順は3つのまま
        step_map = build_step_map(build_document())
        assert ("loop", 4) not in step_map

    def test_positions_are_ascending_within_page(self):
        step_map = build_step_map(build_document())
        positions = [step_map[("loop", n)] for n in (1, 2, 3)]
        assert positions == sorted(positions)

    def test_empty_macro_has_no_steps(self):
        document = QTextDocument()
        document.setMarkdown(
            generate_macro_manual(MacroFile(), title="操作手順書: empty")
        )
        assert build_step_map(document) == {}


class TestManualPreviewWidget:
    def test_set_macro_renders_manual(self):
        widget = ManualPreviewWidget()
        widget.set_macro(build_preview_macro(), "sample")
        assert "操作手順書: sample" in widget._browser.toPlainText()

    def test_highlight_step_sets_selection(self):
        widget = ManualPreviewWidget()
        widget.set_macro(build_preview_macro(), "sample")
        widget.highlight_step("loop", 2)
        assert len(widget._browser.extraSelections()) == 1

    def test_highlight_unknown_step_clears_selection(self):
        widget = ManualPreviewWidget()
        widget.set_macro(build_preview_macro(), "sample")
        widget.highlight_step("loop", 2)
        widget.highlight_step("final", 1)
        assert widget._browser.extraSelections() == []
