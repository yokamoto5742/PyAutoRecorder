"""MacroRecorderのキー入力へのフォーカス要素付与を検証する。

グローバルフック（pynputリスナー）は起動せず、内部メソッドを直接呼んで確認する。
"""

import time
from concurrent.futures import ThreadPoolExecutor

from pytest import MonkeyPatch

from service import recorder as recorder_module
from service.models import ActionType
from service.recorder import MacroRecorder
from service.ui_selector import UiSelector


def _make_recorder() -> MacroRecorder:
    recorder = MacroRecorder()
    recorder._selector_executor = ThreadPoolExecutor(max_workers=1)
    recorder._last_event_time = time.monotonic()
    return recorder


class TestKeySelectorAttachment:
    def test_key_item_gets_focus_selector(self, monkeypatch: MonkeyPatch) -> None:
        selector = UiSelector(automation_id="PatIdBox1", control_type="EditControl")
        monkeypatch.setattr(recorder_module, "selector_from_focus", lambda: selector)
        recorder = _make_recorder()
        recorder._append_keys("a")
        recorder._append_keys("b")
        recorder._flush_key_buffer()
        recorder._attach_selectors()
        assert len(recorder._items) == 1
        item = recorder._items[0]
        assert item.action == ActionType.KEY_ONLY
        assert item.keys == "ab"
        assert item.selector == selector

    def test_selector_fetched_once_per_buffer(self, monkeypatch: MonkeyPatch) -> None:
        calls: list[int] = []
        monkeypatch.setattr(
            recorder_module,
            "selector_from_focus",
            lambda: calls.append(1) or UiSelector(automation_id="Box"),
        )
        recorder = _make_recorder()
        recorder._append_keys("a")
        recorder._append_keys("b")
        recorder._append_keys("c")
        recorder._flush_key_buffer()
        # バッファが区切られたら次の入力開始で再取得する
        recorder._append_keys("d")
        recorder._flush_key_buffer()
        recorder._attach_selectors()
        assert len(calls) == 2
        assert all(item.selector is not None for item in recorder._items)

    def test_fetch_failure_leaves_selector_none(self, monkeypatch: MonkeyPatch) -> None:
        def boom() -> UiSelector:
            raise RuntimeError("uia error")

        monkeypatch.setattr(recorder_module, "selector_from_focus", boom)
        recorder = _make_recorder()
        recorder._append_keys("a")
        recorder._flush_key_buffer()
        recorder._attach_selectors()
        assert recorder._items[0].selector is None

    def test_no_selector_without_executor(self, monkeypatch: MonkeyPatch) -> None:
        # 記録開始前（executorなし）の呼び出しでは取得を試みない
        monkeypatch.setattr(
            recorder_module,
            "selector_from_focus",
            lambda: UiSelector(automation_id="Box"),
        )
        recorder = MacroRecorder()
        recorder._last_event_time = time.monotonic()
        recorder._append_keys("a")
        recorder._flush_key_buffer()
        recorder._attach_selectors()
        assert recorder._items[0].selector is None
