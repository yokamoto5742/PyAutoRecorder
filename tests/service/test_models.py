from pathlib import Path

from service.models import (
    ActionItem,
    ActionType,
    Condition,
    ConditionType,
    MacroFile,
    MacroSettings,
)
from service.ui_selector import UiSelector


def build_sample_macro() -> MacroFile:
    return MacroFile(
        settings=MacroSettings(
            repeat_count=5,
            play_timer="08:00",
            pause_hotkey="<ctrl>+<f9>",
            speed_percent=150,
        ),
        initial=[
            ActionItem(interval=1, x=100, y=200, action=ActionType.LEFT_CLICK),
            ActionItem(
                interval=1,
                x=240,
                y=80,
                action=ActionType.LEFT_CLICK,
                selector=UiSelector(
                    window_automation_id="FormPat",
                    control_type="ButtonControl",
                    automation_id="OpeClearButton",
                ),
            ),
            ActionItem(
                interval=1,
                action=ActionType.SET_TEXT,
                keys="診療情報提供書",
                selector=UiSelector(
                    window_automation_id="FormPat",
                    control_type="ComboBoxControl",
                    automation_id="SumDiagBox",
                ),
            ),
        ],
        loop=[
            ActionItem(
                interval=1,
                x=300,
                y=400,
                action=ActionType.DOUBLE_CLICK,
                keys="{ENTER}",
                repeat_offset=(0, 20),
                key_repeat_increase=True,
                condition=Condition(
                    condition_type=ConditionType.WINDOW_SHOWN_WAIT,
                    value="メモ帳",
                    max_wait_sec=10,
                ),
            ),
            ActionItem(
                interval=2,
                x=10,
                y=20,
                action=ActionType.DRAG,
                drag_to=(50, 60),
            ),
        ],
        final=[
            ActionItem(interval=1, action=ActionType.KEY_ONLY, keys="%{F4}"),
            ActionItem(
                interval=1,
                action=ActionType.LAUNCH_APP,
                app_path=r"C:\Shinseikai\TextFileLog\TextFileLog.exe",
            ),
            ActionItem(
                interval=1,
                action=ActionType.NONE,
                condition=Condition(
                    condition_type=ConditionType.IMAGE_SHOWN_WAIT,
                    max_wait_sec=30,
                    image="aGVsbG8=",
                ),
            ),
        ],
    )


class TestSerialization:
    def test_roundtrip_via_dict(self):
        macro = build_sample_macro()
        restored = MacroFile.from_dict(macro.to_dict())
        assert restored == macro

    def test_save_and_load(self, tmp_path: Path):
        macro = build_sample_macro()
        file_path = tmp_path / "test.par"
        macro.save(file_path)
        assert MacroFile.load(file_path) == macro

    def test_saved_file_is_utf8_json(self, tmp_path: Path):
        macro = build_sample_macro()
        file_path = tmp_path / "test.par"
        macro.save(file_path)
        content = file_path.read_text(encoding="utf-8")
        assert "メモ帳" in content  # ensure_ascii=False

    def test_defaults_from_empty_dict(self):
        macro = MacroFile.from_dict({})
        assert macro.settings.repeat_count == 1
        assert macro.settings.pause_hotkey == ""
        assert macro.settings.speed_percent == 100
        assert macro.initial == []
        assert macro.loop == []
        assert macro.final == []

    def test_minimal_item_omits_optional_fields(self):
        item = ActionItem(interval=1, x=1, y=2, action=ActionType.LEFT_CLICK)
        data = item.to_dict()
        assert "drag_to" not in data
        assert "repeat_offset" not in data
        assert "condition" not in data
        assert "app_path" not in data
        assert "selector" not in data

    def test_legacy_item_without_selector_loads(self):
        # 旧形式の.par（selectorキーなし）が読み込めること
        item = ActionItem.from_dict({"interval": 1.0, "x": 1, "y": 2, "action": "left"})
        assert item.selector is None

    def test_legacy_float_interval_rounds_to_int(self):
        # 旧形式の.par（小数の間隔）は四捨五入して整数へ変換されること
        item = ActionItem.from_dict({"interval": 1.4, "action": "none"})
        assert item.interval == 1

    def test_condition_without_image_omits_image_key(self):
        condition = Condition(ConditionType.WINDOW_SHOWN_WAIT, "メモ帳")
        assert "image" not in condition.to_dict()

    def test_legacy_condition_without_image_loads(self):
        # 旧形式の.par（imageキーなし）が読み込めること
        condition = Condition.from_dict({"type": "window_shown_wait", "value": "x"})
        assert condition.image == ""
