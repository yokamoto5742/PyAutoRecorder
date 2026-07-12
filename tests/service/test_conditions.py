from datetime import datetime
from pathlib import Path

import pytest

from service import conditions
from service.conditions import (
    ConditionContext,
    parse_button_spec,
    parse_color_spec,
    parse_datetime_spec,
    parse_file_size_spec,
    repeat_index_matches,
    should_run,
    title_matches,
)
from service.models import Condition, ConditionType


class TestTitleMatches:
    def test_partial_match(self):
        assert title_matches(["無題 - ペイント"], "ペイント")

    def test_partial_no_match(self):
        assert not title_matches(["無題 - ペイント"], "メモ帳")

    def test_exact_match_with_quotes(self):
        assert title_matches(["無題 - ペイント"], '"無題 - ペイント"')
        assert not title_matches(["無題 - ペイント"], '"ペイント"')


class TestRepeatIndexMatches:
    def test_number_list(self):
        assert repeat_index_matches("2|5|17", 5)
        assert not repeat_index_matches("2|5|17", 3)

    def test_odd_even(self):
        assert repeat_index_matches("奇数", 3)
        assert repeat_index_matches("偶数", 4)
        assert not repeat_index_matches("奇数", 4)

    def test_multiple_of_n(self):
        assert repeat_index_matches("7n", 14)
        assert not repeat_index_matches("7n", 15)

    def test_combined(self):
        # 資料の例: 1|5|偶数
        assert repeat_index_matches("1|5|偶数", 1)
        assert repeat_index_matches("1|5|偶数", 6)
        assert not repeat_index_matches("1|5|偶数", 7)


class TestSpecParsers:
    def test_color_with_coords(self):
        assert parse_color_spec("008080,10,18") == ((0, 128, 128), 10, 18)

    def test_color_without_coords(self):
        assert parse_color_spec("FF0000") == ((255, 0, 0), None, None)

    def test_datetime_full(self):
        now = datetime(2026, 7, 8, 10, 0)
        assert parse_datetime_spec("2026-07-09 08:30", now) == datetime(
            2026, 7, 9, 8, 30
        )

    def test_datetime_time_only_future(self):
        now = datetime(2026, 7, 8, 10, 0)
        assert parse_datetime_spec("23:00", now) == datetime(2026, 7, 8, 23, 0)

    def test_datetime_time_only_past_moves_to_tomorrow(self):
        now = datetime(2026, 7, 8, 10, 0)
        assert parse_datetime_spec("08:00", now) == datetime(2026, 7, 9, 8, 0)

    def test_file_size_spec(self):
        path, size = parse_file_size_spec(r"C:\readme.txt,500")
        assert path == Path(r"C:\readme.txt")
        assert size == 500

    def test_button_name_only(self):
        assert parse_button_spec("OK") == ("OK", "", "")

    def test_button_with_parent_title(self):
        assert parse_button_spec("OK, 保存の確認") == ("OK", "保存の確認", "")

    def test_button_with_parent_class(self):
        assert parse_button_spec("OK,class:#32770") == ("OK", "", "#32770")


class TestShouldRun:
    def test_no_condition_runs(self):
        assert should_run(None, ConditionContext())

    def test_window_shown_skip(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(conditions, "get_window_titles", lambda: ["無題 - メモ帳"])
        skip_if_shown = Condition(ConditionType.WINDOW_SHOWN_SKIP, "メモ帳")
        assert not should_run(skip_if_shown, ConditionContext())

    def test_window_not_shown_skip(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(conditions, "get_window_titles", lambda: [])
        skip_if_not_shown = Condition(ConditionType.WINDOW_NOT_SHOWN_SKIP, "メモ帳")
        assert not should_run(skip_if_not_shown, ConditionContext())

    def test_window_shown_wait_returns_immediately_when_shown(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(conditions, "get_window_titles", lambda: ["無題 - メモ帳"])
        wait = Condition(ConditionType.WINDOW_SHOWN_WAIT, "メモ帳", max_wait_sec=5)
        assert should_run(wait, ConditionContext())

    def test_clipboard_regex(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(conditions, "get_clipboard_text", lambda: "abc123")
        contains = Condition(ConditionType.CLIP_CONTAINS_RUN, "123|xyz")
        not_contains = Condition(ConditionType.CLIP_NOT_CONTAINS_RUN, "123|xyz")
        assert should_run(contains, ConditionContext())
        assert not should_run(not_contains, ConditionContext())

    def test_color_match_run(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(conditions, "get_pixel_color", lambda x, y: (0, 128, 128))
        match = Condition(ConditionType.COLOR_MATCH_RUN, "008080,10,18")
        assert should_run(match, ConditionContext())

    def test_file_exists(self, tmp_path: Path):
        existing = tmp_path / "a.txt"
        existing.write_text("x")
        assert should_run(
            Condition(ConditionType.FILE_EXISTS_RUN, str(existing)), ConditionContext()
        )
        assert not should_run(
            Condition(ConditionType.FILE_EXISTS_RUN, str(tmp_path / "b.txt")),
            ConditionContext(),
        )

    def test_file_size(self, tmp_path: Path):
        file = tmp_path / "a.txt"
        file.write_bytes(b"x" * 100)
        larger = Condition(ConditionType.FILE_LARGER_RUN, f"{file},50")
        smaller = Condition(ConditionType.FILE_SMALLER_RUN, f"{file},50")
        assert should_run(larger, ConditionContext())
        assert not should_run(smaller, ConditionContext())

    def test_repeat_index(self):
        run_on = Condition(ConditionType.REPEAT_INDEX_RUN, "2|5")
        assert should_run(run_on, ConditionContext(repeat_index=2))
        assert not should_run(run_on, ConditionContext(repeat_index=3))

    def test_button_shown_skip(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            conditions, "button_shown", lambda name, title, cls: name == "OK"
        )
        skip_if_shown = Condition(ConditionType.BUTTON_SHOWN_SKIP, "OK")
        assert not should_run(skip_if_shown, ConditionContext())

    def test_button_not_shown_skip(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(conditions, "button_shown", lambda name, title, cls: False)
        skip_if_not_shown = Condition(ConditionType.BUTTON_NOT_SHOWN_SKIP, "OK")
        assert not should_run(skip_if_not_shown, ConditionContext())

    def test_button_shown_wait_returns_immediately_when_shown(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(conditions, "button_shown", lambda name, title, cls: True)
        wait = Condition(ConditionType.BUTTON_SHOWN_WAIT, "OK,メモ帳", max_wait_sec=5)
        assert should_run(wait, ConditionContext())

    def test_button_hidden_wait_returns_immediately_when_hidden(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(conditions, "button_shown", lambda name, title, cls: False)
        wait = Condition(ConditionType.BUTTON_HIDDEN_WAIT, "OK", max_wait_sec=5)
        assert should_run(wait, ConditionContext())

    def test_button_enabled_wait_returns_immediately_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            conditions, "button_enabled", lambda name, title, cls: name == "id:SaveBtn"
        )
        wait = Condition(
            ConditionType.BUTTON_ENABLED_WAIT, "id:SaveBtn,id:FormPat", max_wait_sec=5
        )
        assert should_run(wait, ConditionContext())

    def test_image_shown_wait(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(conditions, "image_shown", lambda image: image == "abc")
        wait = Condition(ConditionType.IMAGE_SHOWN_WAIT, image="abc")
        assert should_run(wait, ConditionContext())
