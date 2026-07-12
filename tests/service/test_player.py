import pytest

from service import ui_selector
from service.models import ActionItem, ActionType, MacroFile, MacroSettings
from service.player import MacroPlayer
from service.ui_selector import UiSelector


def build_player(speed_percent: int = 100) -> MacroPlayer:
    macro = MacroFile(settings=MacroSettings(speed_percent=speed_percent))
    return MacroPlayer(macro)


class TestScaledInterval:
    def test_100_percent_keeps_interval(self):
        assert build_player(100)._scaled_interval(2.0) == 2.0

    def test_200_percent_halves_interval(self):
        assert build_player(200)._scaled_interval(2.0) == 1.0

    def test_300_percent(self):
        assert build_player(300)._scaled_interval(3.0) == 1.0

    def test_out_of_range_is_clamped(self):
        assert build_player(50)._scaled_interval(2.0) == 2.0
        assert build_player(500)._scaled_interval(3.0) == 1.0


class TestUiaTextActions:
    def test_set_text_writes_via_selector(self, monkeypatch: pytest.MonkeyPatch):
        written: dict[str, str] = {}

        def fake_set(selector: UiSelector, text: str) -> bool:
            written["id"] = selector.automation_id
            written["text"] = text
            return True

        monkeypatch.setattr(ui_selector, "set_element_text", fake_set)
        item = ActionItem(
            action=ActionType.SET_TEXT,
            keys="診療情報提供書",
            selector=UiSelector(automation_id="SumDiagBox"),
        )
        build_player()._execute_item(item, 0)
        assert written == {"id": "SumDiagBox", "text": "診療情報提供書"}

    def test_set_text_without_selector_raises(self):
        item = ActionItem(action=ActionType.SET_TEXT, keys="x")
        with pytest.raises(ValueError):
            build_player()._execute_item(item, 0)

    def test_set_text_element_not_found_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(ui_selector, "set_element_text", lambda s, t: False)
        item = ActionItem(
            action=ActionType.SET_TEXT,
            keys="x",
            selector=UiSelector(automation_id="SumDiagBox"),
        )
        with pytest.raises(ValueError):
            build_player()._execute_item(item, 0)

    def test_get_text_copies_to_clipboard(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(ui_selector, "get_element_text", lambda s: "読み取り結果")
        copied: list[str] = []
        monkeypatch.setattr("service.player.pyperclip.copy", copied.append)
        item = ActionItem(
            action=ActionType.GET_TEXT, selector=UiSelector(automation_id="PatIdBox1")
        )
        build_player()._execute_item(item, 0)
        assert copied == ["読み取り結果"]


class TestResolvePoint:
    def test_prefers_element_point(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(ui_selector, "find_clickable_point", lambda s: (500, 600))
        item = ActionItem(
            x=10,
            y=20,
            action=ActionType.LEFT_CLICK,
            selector=UiSelector(automation_id="OpeClearButton"),
        )
        assert build_player()._resolve_point(item, 0, 0) == (500, 600)

    def test_falls_back_to_coordinates_when_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ui_selector, "find_clickable_point", lambda s: None)
        item = ActionItem(
            x=10,
            y=20,
            action=ActionType.LEFT_CLICK,
            selector=UiSelector(automation_id="OpeClearButton"),
        )
        assert build_player()._resolve_point(item, 5, 5) == (15, 25)

    def test_without_selector_uses_coordinates(self):
        item = ActionItem(x=10, y=20, action=ActionType.LEFT_CLICK)
        assert build_player()._resolve_point(item, 0, 0) == (10, 20)
