from pathlib import Path

from app import constants
from service.manual_generator import (
    describe_action,
    describe_condition,
    describe_keys,
    describe_selector,
    generate_macro_manual,
    write_bundle_manual,
    write_macro_manual,
)
from service.models import ActionItem, ActionType, Condition, ConditionType, MacroFile
from service.ui_selector import UiSelector
from service.workflow import StepType, Workflow, WorkflowBundle, WorkflowStep
from tests.service.test_models import build_sample_macro


class TestDescribeKeys:
    def test_special_key(self):
        assert describe_keys("{ENTER}") == "[ENTER]"

    def test_ctrl_combo(self):
        assert describe_keys("^c") == "[Ctrl+C]"

    def test_alt_f4(self):
        assert describe_keys("%{F4}") == "[Alt+F4]"

    def test_plain_text(self):
        assert describe_keys("こんにちは") == "「こんにちは」と入力"

    def test_var(self):
        assert describe_keys("{VAR:氏名}") == "クリップボード変数「氏名」を入力"

    def test_var_with_format(self):
        assert describe_keys("{VAR:実施日:日付}") == "クリップボード変数「実施日」を入力"

    def test_commands(self):
        assert describe_keys("{WAIT}{CLIP}") == "0.5秒待機、クリップボード貼り付け"

    def test_invalid_notation_falls_back_to_raw(self):
        assert describe_keys("^") == "^"

    def test_empty(self):
        assert describe_keys("") == ""


class TestDescribeCondition:
    def test_window_with_max_wait(self):
        condition = Condition(ConditionType.WINDOW_SHOWN_WAIT, "メモ帳", max_wait_sec=10)
        text = describe_condition(condition)
        assert "次のウィンドウが表示されるまで待機" in text
        assert "「メモ帳」" in text
        assert "（最大待機10秒）" in text

    def test_infinite_wait(self):
        condition = Condition(ConditionType.WINDOW_SHOWN_WAIT, "メモ帳", max_wait_sec=0)
        assert describe_condition(condition).endswith("（無限待機）")

    def test_run_condition_has_no_wait_suffix(self):
        condition = Condition(ConditionType.CLIP_CONTAINS_RUN, "123|abc")
        text = describe_condition(condition)
        assert "正規表現「123|abc」" in text
        assert "待機" not in text.split("実行")[-1]

    def test_color_with_position(self):
        condition = Condition(ConditionType.COLOR_MATCH_RUN, "008080,10,18")
        assert "色 #008080（座標(10,18)）" in describe_condition(condition)

    def test_color_without_position(self):
        condition = Condition(ConditionType.COLOR_MATCH_RUN, "008080")
        assert "色 #008080（カーソル位置）" in describe_condition(condition)

    def test_file_larger(self):
        condition = Condition(ConditionType.FILE_LARGER_RUN, r"C:\readme.txt,500")
        assert "「C:\\readme.txt」（500バイト）" in describe_condition(condition)

    def test_button(self):
        condition = Condition(ConditionType.BUTTON_SHOWN_WAIT, "OK", max_wait_sec=5)
        assert "ボタン「OK」" in describe_condition(condition)

    def test_image_base64_not_embedded(self):
        condition = Condition(
            ConditionType.IMAGE_SHOWN_WAIT, max_wait_sec=30, image="aGVsbG8="
        )
        text = describe_condition(condition)
        assert "aGVsbG8=" not in text
        assert "（画像はファイル内に保存）" in text


class TestDescribeSelector:
    def test_window_and_control(self):
        selector = UiSelector(
            window_automation_id="FormPat",
            control_type="ButtonControl",
            automation_id="OpeClearButton",
        )
        assert (
            describe_selector(selector)
            == "ウィンドウ『FormPat』のButtonControl『OpeClearButton』"
        )

    def test_name_fallback_and_found_index(self):
        selector = UiSelector(control_type="ButtonControl", name="OK", found_index=2)
        assert describe_selector(selector) == "ButtonControl『OK』（2番目）"


class TestDescribeAction:
    def test_coordinate_click(self):
        item = ActionItem(x=100, y=200, action=ActionType.LEFT_CLICK)
        assert describe_action(item) == "座標(100, 200)を左クリック"

    def test_selector_click(self):
        item = ActionItem(
            x=240,
            y=80,
            action=ActionType.LEFT_CLICK,
            selector=UiSelector(
                window_automation_id="FormPat",
                control_type="ButtonControl",
                automation_id="OpeClearButton",
            ),
        )
        assert (
            describe_action(item)
            == "ウィンドウ『FormPat』のButtonControl『OpeClearButton』を左クリック"
        )

    def test_drag(self):
        item = ActionItem(x=10, y=20, action=ActionType.DRAG, drag_to=(50, 60))
        assert describe_action(item) == "座標(10, 20)から座標(50, 60)へドラッグ"

    def test_launch_app(self):
        item = ActionItem(action=ActionType.LAUNCH_APP, app_path=r"C:\app.exe")
        assert describe_action(item) == r"アプリ起動: C:\app.exe"

    def test_set_text(self):
        item = ActionItem(
            action=ActionType.SET_TEXT,
            keys="診療情報提供書",
            selector=UiSelector(control_type="ComboBoxControl", automation_id="Box"),
        )
        assert describe_action(item) == "ComboBoxControl『Box』にテキスト書込(UIA)"

    def test_key_only(self):
        item = ActionItem(action=ActionType.KEY_ONLY, keys="{ENTER}")
        assert describe_action(item) == "キー操作のみ"


class TestGenerateMacroManual:
    def test_sample_macro_full_text(self):
        text = generate_macro_manual(build_sample_macro(), title="操作手順書: sample")
        assert "操作手順書" in text
        assert constants.TAB_INITIAL in text
        assert constants.TAB_LOOP in text
        assert constants.TAB_FINAL in text
        assert "左クリック" in text
        assert "| 繰り返し回数 | 5 |" in text
        assert "| 一時停止キー | `<ctrl>+<f9>` |" in text
        assert "[Alt+F4]" in text
        assert "（画像はファイル内に保存）" in text

    def test_empty_macro_has_no_items_marker(self):
        text = generate_macro_manual(MacroFile(), title="空マクロ")
        assert text.count("（操作なし）") == 3

    def test_heading_level(self):
        text = generate_macro_manual(MacroFile(), title="埋込", heading_level=3)
        assert text.startswith("### 埋込")
        assert "\n#### 再生設定" in text


class TestWriteMacroManual:
    def test_writes_md_next_to_par(self, tmp_path: Path):
        par_path = tmp_path / "sample.par"
        build_sample_macro().save(par_path)
        output_path = write_macro_manual(par_path)
        assert output_path == tmp_path / "sample.md"
        text = output_path.read_text(encoding="utf-8")
        assert "sample.par" in text
        assert "左クリック" in text


class TestBundleManual:
    @staticmethod
    def _build_bundle(tmp_path: Path) -> WorkflowBundle:
        bundle = WorkflowBundle(
            path=tmp_path / "テスト.bundle",
            workflow=Workflow(
                name="テスト",
                steps=[
                    WorkflowStep(
                        step_type=StepType.PLAY_RECORDING,
                        label="患者検索",
                        recording="rec1.json",
                    ),
                    WorkflowStep(
                        step_type=StepType.WAIT_IMAGE,
                        label="画面待ち",
                        image="image_001.png",
                        max_wait_sec=30,
                    ),
                    WorkflowStep(
                        step_type=StepType.HUMAN_CONFIRM,
                        label="確認",
                        message="内容を目視確認してください",
                    ),
                    WorkflowStep(
                        step_type=StepType.PLAY_RECORDING,
                        label="欠損参照",
                        recording="missing.json",
                    ),
                ],
            ),
        )
        bundle.save()
        build_sample_macro().save(bundle.recording_path("rec1.json"))
        bundle.asset_path("image_001.png").write_bytes(b"\x89PNG")
        return bundle

    def test_writes_manual_md_into_bundle(self, tmp_path: Path):
        bundle = self._build_bundle(tmp_path)
        output_path = write_bundle_manual(bundle.path)
        assert output_path == bundle.path / "manual.md"
        assert output_path.exists()

    def test_manual_content(self, tmp_path: Path):
        bundle = self._build_bundle(tmp_path)
        text = write_bundle_manual(bundle.path).read_text(encoding="utf-8")
        assert "操作手順書: テスト" in text
        assert "- ステップ数: 4" in text
        # 相対画像リンク
        assert "![image_001.png](assets/image_001.png)" in text
        assert "（最大待機30秒）" in text
        # レコーディングの再帰展開
        assert "手順1: 患者検索（操作再生）" in text
        assert "左クリック" in text
        # 人間確認は引用表示
        assert "> 内容を目視確認してください" in text
        # 欠損レコーディング参照は例外にせずフォールバック
        assert "（レコーディングファイルが見つかりません: missing.json）" in text
