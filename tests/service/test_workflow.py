from pathlib import Path

from service.workflow import (
    BUNDLE_EXTENSION,
    WORKFLOW_FILENAME,
    StepType,
    Workflow,
    WorkflowBundle,
    WorkflowStep,
    list_bundles,
)


class TestWorkflowStep:
    def test_round_trip_all_fields(self):
        step = WorkflowStep(
            step_type=StepType.WAIT_IMAGE,
            label="手順2：画面待ち",
            recording="step1_login.json",
            image="btn_document_open.png",
            max_wait_sec=30,
            message="患者氏名を目視確認",
        )
        restored = WorkflowStep.from_dict(step.to_dict())
        assert restored == step

    def test_to_dict_omits_empty_fields(self):
        step = WorkflowStep(step_type=StepType.HUMAN_CONFIRM, label="確認")
        assert step.to_dict() == {"type": "human_confirm", "label": "確認"}

    def test_from_dict_defaults(self):
        step = WorkflowStep.from_dict({"type": "play_recording"})
        assert step.step_type == StepType.PLAY_RECORDING
        assert step.label == ""
        assert step.max_wait_sec == 0


class TestWorkflow:
    def test_round_trip(self):
        workflow = Workflow(
            name="入院診療計画書 作成手順",
            steps=[
                WorkflowStep(
                    step_type=StepType.PLAY_RECORDING,
                    label="手順1：患者検索",
                    recording="step1.json",
                ),
                WorkflowStep(step_type=StepType.HUMAN_CONFIRM, label="確認"),
            ],
        )
        restored = Workflow.from_dict(workflow.to_dict())
        assert restored == workflow

    def test_from_dict_empty(self):
        workflow = Workflow.from_dict({})
        assert workflow.name == ""
        assert workflow.steps == []


class TestWorkflowBundle:
    def test_save_and_load(self, tmp_path: Path):
        bundle_path = tmp_path / f"テスト{BUNDLE_EXTENSION}"
        bundle = WorkflowBundle(
            path=bundle_path,
            workflow=Workflow(
                name="テスト",
                steps=[
                    WorkflowStep(
                        step_type=StepType.WAIT_IMAGE,
                        label="画面待ち",
                        image="img.png",
                        max_wait_sec=10,
                    )
                ],
            ),
        )
        bundle.save()

        assert (bundle_path / WORKFLOW_FILENAME).exists()
        assert bundle.recordings_dir.is_dir()
        assert bundle.assets_dir.is_dir()

        restored = WorkflowBundle.load(bundle_path)
        assert restored.workflow == bundle.workflow

    def test_paths(self, tmp_path: Path):
        bundle = WorkflowBundle(path=tmp_path / f"a{BUNDLE_EXTENSION}")
        assert bundle.recording_path("s.json") == bundle.path / "recordings" / "s.json"
        assert bundle.asset_path("i.png") == bundle.path / "assets" / "i.png"


class TestListBundles:
    def test_lists_only_valid_bundles(self, tmp_path: Path):
        valid = tmp_path / f"b{BUNDLE_EXTENSION}"
        valid.mkdir()
        (valid / WORKFLOW_FILENAME).write_text("{}", encoding="utf-8")
        no_json = tmp_path / f"a{BUNDLE_EXTENSION}"
        no_json.mkdir()
        (tmp_path / "not_bundle").mkdir()
        (tmp_path / f"file{BUNDLE_EXTENSION}").write_text("", encoding="utf-8")

        assert list_bundles(tmp_path) == [valid]

    def test_missing_root_returns_empty(self, tmp_path: Path):
        assert list_bundles(tmp_path / "nothing") == []
