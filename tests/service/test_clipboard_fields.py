import pytest

from service.clipboard_fields import (
    collect_bundle_var_specs,
    collect_var_specs,
    format_value,
    parse_fields,
    resolve,
    resolve_all,
    substitute_raw,
    var_name,
)
from service.models import ActionItem, ActionType, MacroFile
from service.workflow import StepType, Workflow, WorkflowBundle, WorkflowStep

# Excelで2列範囲をコピーした際のクリップボード内容（タブ区切り）
SAMPLE_TEXT = (
    "術眼\t左\n"
    "手術日\t2026/7/4\n"
    "種別\t1 ベッド２\n"
    "時刻\t930\n"
    "手術室\t2\n"
    "術者\t山本\n"
    "予定時間\t30\n"
    "麻酔\t点眼麻酔\n"
    "病名\t白内障\n"
    "術式\tＰＥＡ＋ＩＯＬ\n"
    "入外\tあやめ\n"
    "病室\t342\n"
    "入院日\t2026/7/12\n"
)


class TestParseFields:
    def test_sample_data(self):
        fields = parse_fields(SAMPLE_TEXT)
        assert fields["術者"] == "山本"
        assert fields["手術日"] == "2026/7/4"
        assert fields["時刻"] == "930"
        assert fields["術式"] == "ＰＥＡ＋ＩＯＬ"
        assert len(fields) == 13

    def test_strips_whitespace(self):
        assert parse_fields(" 術者 \t 山本 \r\n") == {"術者": "山本"}

    def test_skips_lines_without_tab(self):
        assert parse_fields("見出しだけの行\n術者\t山本") == {"術者": "山本"}

    def test_three_columns_uses_second(self):
        assert parse_fields("術者\t山本\t備考") == {"術者": "山本"}

    def test_duplicate_key_last_wins(self):
        assert parse_fields("術者\t山本\n術者\t田中") == {"術者": "田中"}

    def test_empty_text(self):
        assert parse_fields("") == {}


class TestFormatValue:
    def test_date_zero_pads(self):
        assert format_value("手術日", "2026/7/4", "日付") == "2026/07/04"

    def test_date_already_padded(self):
        assert format_value("手術日", "2026/07/04", "日付") == "2026/07/04"

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError, match="手術日"):
            format_value("手術日", "あした", "日付")

    def test_time_3_digits(self):
        assert format_value("時刻", "930", "時刻") == "09:30"

    def test_time_4_digits(self):
        assert format_value("時刻", "1330", "時刻") == "13:30"

    def test_invalid_time_raises(self):
        for value in ("70", "2560", "1275", "abc"):
            with pytest.raises(ValueError, match="時刻"):
                format_value("時刻", value, "時刻")

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="不明な書式"):
            format_value("時刻", "930", "金額")


class TestResolve:
    def test_plain(self):
        assert resolve("術者", {"術者": "山本"}) == "山本"

    def test_with_format(self):
        assert resolve("時刻:時刻", {"時刻": "930"}) == "09:30"

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="術者"):
            resolve("術者", {})

    def test_resolve_all(self):
        fields = parse_fields(SAMPLE_TEXT)
        resolved = resolve_all(["術者", "手術日:日付", "時刻:時刻"], fields)
        assert resolved == {
            "術者": "山本",
            "手術日:日付": "2026/07/04",
            "時刻:時刻": "09:30",
        }

    def test_var_name(self):
        assert var_name("手術日:日付") == "手術日"
        assert var_name("術者") == "術者"


class TestSubstituteRaw:
    def test_replaces_multiple_vars(self):
        fields = parse_fields(SAMPLE_TEXT)
        text = substitute_raw("術者:{VAR:術者} 病室:{VAR:病室}", fields)
        assert text == "術者:山本 病室:342"

    def test_applies_format(self):
        assert substitute_raw("{VAR:時刻:時刻}", {"時刻": "930"}) == "09:30"

    def test_leaves_other_text(self):
        assert substitute_raw("そのまま{ENTER}", {"術者": "山本"}) == "そのまま{ENTER}"

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="病室"):
            substitute_raw("{VAR:病室}", {})


class TestCollectVarSpecs:
    def test_collects_across_pages_in_order(self):
        macro = MacroFile(
            initial=[ActionItem(keys="{VAR:術者}")],
            loop=[ActionItem(keys="{VAR:時刻:時刻}{VAR:術者}")],
            final=[ActionItem(action=ActionType.SET_TEXT, keys="{VAR:病室}")],
        )
        assert collect_var_specs(macro) == ["術者", "時刻:時刻", "病室"]

    def test_no_vars(self):
        macro = MacroFile(initial=[ActionItem(keys="abc{ENTER}")])
        assert collect_var_specs(macro) == []


class TestCollectBundleVarSpecs:
    def test_collects_from_recordings(self, tmp_path):
        bundle = WorkflowBundle(
            path=tmp_path / "test.bundle",
            workflow=Workflow(
                name="テスト",
                steps=[
                    WorkflowStep(StepType.PLAY_RECORDING, recording="a.par"),
                    WorkflowStep(StepType.HUMAN_CONFIRM, message="確認"),
                    WorkflowStep(StepType.PLAY_RECORDING, recording="b.par"),
                ],
            ),
        )
        bundle.save()
        MacroFile(initial=[ActionItem(keys="{VAR:術者}")]).save(
            bundle.recording_path("a.par")
        )
        MacroFile(loop=[ActionItem(keys="{VAR:術者}{VAR:病室}")]).save(
            bundle.recording_path("b.par")
        )
        assert collect_bundle_var_specs(bundle) == ["術者", "病室"]
