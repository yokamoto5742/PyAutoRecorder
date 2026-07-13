import sys
from types import SimpleNamespace

from pytest import MonkeyPatch

from service import ui_selector
from service.ui_selector import UiSelector, build_selector, window_matches


class _NullInitializer:
    """UIAutomationInitializerInThreadの代替（COM初期化を行わない）。"""

    def __enter__(self) -> "_NullInitializer":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TestSerialization:
    def test_roundtrip_via_dict(self):
        selector = UiSelector(
            window_automation_id="FormPat",
            control_type="ButtonControl",
            automation_id="OpeClearButton",
            class_name="WindowsForms10.BUTTON.app.0",
            found_index=2,
        )
        assert UiSelector.from_dict(selector.to_dict()) == selector

    def test_to_dict_omits_defaults(self):
        selector = UiSelector(automation_id="OpeClearButton")
        assert selector.to_dict() == {"automation_id": "OpeClearButton"}

    def test_from_empty_dict(self):
        selector = UiSelector.from_dict({})
        assert selector == UiSelector()
        assert selector.found_index == 1


class TestHasCriteria:
    def test_automation_id(self):
        assert UiSelector(automation_id="x").has_criteria()

    def test_name(self):
        assert UiSelector(name="新規作成").has_criteria()

    def test_empty(self):
        assert not UiSelector(control_type="ButtonControl").has_criteria()


class TestBuildSelector:
    def test_automation_id_takes_precedence_over_name(self):
        # Edit系のNameは入力テキストで変動するためAutomationIdがあれば捨てる
        selector = build_selector(
            control_type="EditControl",
            automation_id="PatIdBox1",
            name="佐藤 一郎",
            class_name="WindowsForms10.EDIT.app.0",
            window_automation_id="FormPat",
            window_name="佐藤 一郎",
        )
        assert selector is not None
        assert selector.automation_id == "PatIdBox1"
        assert selector.name == ""
        assert selector.window_automation_id == "FormPat"
        assert selector.window_name == ""

    def test_name_fallback_without_automation_id(self):
        selector = build_selector(
            control_type="ButtonControl",
            automation_id="",
            name="新規作成",
            class_name="",
            window_automation_id="",
            window_name="メモ帳",
        )
        assert selector is not None
        assert selector.name == "新規作成"
        assert selector.window_name == "メモ帳"

    def test_returns_none_without_identifier(self):
        assert (
            build_selector(
                control_type="PaneControl",
                automation_id="",
                name="",
                class_name="x",
                window_automation_id="FormPat",
                window_name="",
            )
            is None
        )


class TestWindowMatches:
    @staticmethod
    def _window(automation_id: str = "", name: str = "") -> SimpleNamespace:
        return SimpleNamespace(AutomationId=automation_id, Name=name)

    def test_automation_id_exact_match(self):
        selector = UiSelector(window_automation_id="FormPat")
        assert window_matches(self._window(automation_id="FormPat"), selector)
        assert not window_matches(self._window(automation_id="FormMain"), selector)

    def test_automation_id_ignores_name(self):
        # ウィンドウ名（患者名等）が変わってもAutomationIdで特定できる
        selector = UiSelector(window_automation_id="FormPat", window_name="佐藤")
        assert window_matches(
            self._window(automation_id="FormPat", name="鈴木 花子"), selector
        )

    def test_name_partial_match(self):
        selector = UiSelector(window_name="メモ帳")
        assert window_matches(self._window(name="無題 - メモ帳"), selector)
        assert not window_matches(self._window(name="ペイント"), selector)

    def test_no_window_criteria_matches_all(self):
        assert window_matches(self._window(name="任意"), UiSelector())


class TestSelectorFromFocus:
    def test_uses_focused_control(self, monkeypatch: MonkeyPatch) -> None:
        focused = object()
        expected = UiSelector(automation_id="PatIdBox1")
        fake_uia = SimpleNamespace(
            UIAutomationInitializerInThread=_NullInitializer,
            GetFocusedControl=lambda: focused,
        )
        monkeypatch.setitem(sys.modules, "uiautomation", fake_uia)
        received: list[object] = []
        monkeypatch.setattr(
            ui_selector,
            "_selector_from_control",
            lambda control: received.append(control) or expected,
        )
        assert ui_selector.selector_from_focus() == expected
        assert received == [focused]


class TestRectFromCursor:
    def test_returns_bounding_rectangle(self, monkeypatch: MonkeyPatch) -> None:
        rect = SimpleNamespace(left=10, top=20, right=110, bottom=220)
        control = SimpleNamespace(BoundingRectangle=rect)
        fake_uia = SimpleNamespace(
            UIAutomationInitializerInThread=_NullInitializer,
            ControlFromCursor=lambda: control,
        )
        monkeypatch.setitem(sys.modules, "uiautomation", fake_uia)
        assert ui_selector.rect_from_cursor() == (10, 20, 110, 220)

    def test_returns_none_without_control(self, monkeypatch: MonkeyPatch) -> None:
        fake_uia = SimpleNamespace(
            UIAutomationInitializerInThread=_NullInitializer,
            ControlFromCursor=lambda: None,
        )
        monkeypatch.setitem(sys.modules, "uiautomation", fake_uia)
        assert ui_selector.rect_from_cursor() is None
