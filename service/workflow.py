"""ワークフローのデータモデル: 複数のレコーディングと制御ステップを1つのバンドルで管理する。

バンドルは以下のフォルダ構成を持つ:
    [名前].bundle/
    ├── workflow.json   # 実行手順・日本語ラベル・待機設定
    ├── recordings/     # 操作再生ステップが呼び出すMacroFile(JSON)
    └── assets/         # 画面待ちステップが使うテンプレート画像(PNG)
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

BUNDLE_EXTENSION = ".bundle"
WORKFLOW_FILENAME = "workflow.json"
RECORDINGS_DIRNAME = "recordings"
ASSETS_DIRNAME = "assets"


class StepType(Enum):
    PLAY_RECORDING = "play_recording"  # レコーディングデータの再生
    WAIT_IMAGE = "wait_image"  # 指定画像が表示されるまで待機
    HUMAN_CONFIRM = "human_confirm"  # 一時停止して人間の目視確認を待つ


@dataclass
class WorkflowStep:
    step_type: StepType
    label: str = ""  # 日本語の手順名（例: 手順1：患者検索とカルテ展開）
    recording: str = ""  # PLAY_RECORDING: recordings/内のファイル名
    image: str = ""  # WAIT_IMAGE: assets/内のファイル名
    max_wait_sec: int = 0  # WAIT_IMAGE: 最大待機秒。0は無限待機
    message: str = ""  # HUMAN_CONFIRM: 確認メッセージ

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.step_type.value, "label": self.label}
        if self.recording:
            data["recording"] = self.recording
        if self.image:
            data["image"] = self.image
        if self.max_wait_sec:
            data["max_wait_sec"] = self.max_wait_sec
        if self.message:
            data["message"] = self.message
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowStep":
        return cls(
            step_type=StepType(data["type"]),
            label=data.get("label", ""),
            recording=data.get("recording", ""),
            image=data.get("image", ""),
            max_wait_sec=int(data.get("max_wait_sec", 0)),
            message=data.get("message", ""),
        )


@dataclass
class Workflow:
    name: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workflow":
        return cls(
            name=data.get("name", ""),
            steps=[WorkflowStep.from_dict(d) for d in data.get("steps", [])],
        )


@dataclass
class WorkflowBundle:
    path: Path  # [名前].bundle フォルダのパス
    workflow: Workflow = field(default_factory=Workflow)

    @property
    def recordings_dir(self) -> Path:
        return self.path / RECORDINGS_DIRNAME

    @property
    def assets_dir(self) -> Path:
        return self.path / ASSETS_DIRNAME

    def recording_path(self, filename: str) -> Path:
        return self.recordings_dir / filename

    def asset_path(self, filename: str) -> Path:
        return self.assets_dir / filename

    def save(self) -> None:
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        (self.path / WORKFLOW_FILENAME).write_text(
            json.dumps(self.workflow.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | str) -> "WorkflowBundle":
        bundle_path = Path(path)
        data = json.loads((bundle_path / WORKFLOW_FILENAME).read_text(encoding="utf-8"))
        return cls(path=bundle_path, workflow=Workflow.from_dict(data))


def list_bundles(root: Path | str) -> list[Path]:
    """共有フォルダ直下のバンドルフォルダを名前順に列挙する。"""
    root_path = Path(root)
    if not root_path.is_dir():
        return []
    return sorted(
        p
        for p in root_path.iterdir()
        if p.is_dir()
        and p.suffix == BUNDLE_EXTENSION
        and (p / WORKFLOW_FILENAME).exists()
    )
