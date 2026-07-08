from pathlib import Path

from service.models import (
    ActionItem,
    ActionType,
    Condition,
    ConditionType,
    MacroFile,
    MacroSettings,
)


def build_sample_macro() -> MacroFile:
    return MacroFile(
        settings=MacroSettings(repeat_count=5, play_timer="08:00"),
        initial=[
            ActionItem(interval=1.0, x=100, y=200, action=ActionType.LEFT_CLICK),
        ],
        loop=[
            ActionItem(
                interval=0.5,
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
                interval=2.0,
                x=10,
                y=20,
                action=ActionType.DRAG,
                drag_to=(50, 60),
            ),
        ],
        final=[
            ActionItem(interval=1.0, action=ActionType.KEY_ONLY, keys="%{F4}"),
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
        assert macro.initial == []
        assert macro.loop == []
        assert macro.final == []

    def test_minimal_item_omits_optional_fields(self):
        item = ActionItem(interval=1.0, x=1, y=2, action=ActionType.LEFT_CLICK)
        data = item.to_dict()
        assert "drag_to" not in data
        assert "repeat_offset" not in data
        assert "condition" not in data
