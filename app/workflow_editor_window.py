"""ワークフロー編集画面: 作成者向けのフル機能UI。

バンドルの新規作成・読込・保存、ステップの追加・編集・削除・並び替えを行う。
レコーディング(.par)はrecordings/へコピーし、認識画像はassets/へPNG保存する。
"""

import base64
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import constants
from app.image_capture_dialog import capture_screen_region, load_image_file
from service.workflow import (
    BUNDLE_EXTENSION,
    WORKFLOW_FILENAME,
    StepType,
    Workflow,
    WorkflowBundle,
    WorkflowStep,
)
from utils.config_manager import ConfigManager

_IMAGE_PREVIEW_MAX = 240


def _unique_filename(directory: Path, filename: str) -> str:
    """同名ファイルがある場合は連番を付けて衝突を避ける。"""
    if not (directory / filename).exists():
        return filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    number = 2
    while (directory / f"{stem}_{number}{suffix}").exists():
        number += 1
    return f"{stem}_{number}{suffix}"


def _next_image_filename(assets_dir: Path) -> str:
    return _unique_filename(assets_dir, "image_001.png")


class WorkflowEditorWindow(QMainWindow):
    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._bundle: WorkflowBundle | None = None
        self._dirty = False
        self._build_toolbar()
        self._build_central()
        self._update_window_title()
        self.statusBar()
        self.resize(*self._config.get_window_size("workflow_editor", (700, 500)))

    # --- UI構築 ---

    def _build_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction(constants.TOOLBAR_NEW, self._new_bundle)
        toolbar.addAction(constants.TOOLBAR_OPEN, self._open_bundle)
        toolbar.addAction(constants.TOOLBAR_SAVE, self._save_bundle)

    def _build_central(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(constants.LABEL_WORKFLOW_NAME))
        self._name_edit = QLineEdit()
        self._name_edit.textEdited.connect(lambda _text: self._set_dirty())
        name_row.addWidget(self._name_edit)
        layout.addLayout(name_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            [
                constants.COLUMN_STEP_TYPE,
                constants.COLUMN_STEP_LABEL,
                constants.COLUMN_STEP_DETAIL,
            ]
        )
        self._tree.setRootIsDecorated(False)
        self._tree.itemDoubleClicked.connect(lambda _item, _col: self._edit_step())
        layout.addWidget(self._tree)

        layout.addLayout(self._build_step_buttons())
        self.setCentralWidget(central)

    def _build_step_buttons(self) -> QHBoxLayout:
        buttons = QHBoxLayout()
        buttons.addWidget(self._build_add_button())
        for text, handler in (
            (constants.MENU_EDIT_ITEM, self._edit_step),
            (constants.MENU_DELETE_ITEM, self._delete_step),
            (constants.MENU_MOVE_UP, lambda: self._move_step(-1)),
            (constants.MENU_MOVE_DOWN, lambda: self._move_step(1)),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        buttons.addStretch()
        return buttons

    def _build_add_button(self) -> QToolButton:
        button = QToolButton()
        button.setText(constants.BUTTON_ADD_STEP)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        menu.addAction(
            constants.MENU_ADD_STEP_PLAY,
            lambda: self._add_step(StepType.PLAY_RECORDING),
        )
        menu.addAction(
            constants.MENU_ADD_STEP_WAIT_IMAGE,
            lambda: self._add_step(StepType.WAIT_IMAGE),
        )
        menu.addAction(
            constants.MENU_ADD_STEP_CONFIRM,
            lambda: self._add_step(StepType.HUMAN_CONFIRM),
        )
        button.setMenu(menu)
        return button

    # --- モデルとビューの同期 ---

    def _set_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        self._update_window_title()

    def _update_window_title(self) -> None:
        name = self._bundle.path.stem if self._bundle else constants.UNTITLED_FILE
        mark = constants.MODIFIED_MARK if self._dirty else ""
        self.setWindowTitle(f"{name}{mark} - {constants.WORKFLOW_EDITOR_TITLE}")

    def _refresh_tree(self) -> None:
        self._tree.clear()
        if self._bundle is None:
            return
        for step in self._bundle.workflow.steps:
            self._tree.addTopLevelItem(self._to_row(step))

    def _to_row(self, step: WorkflowStep) -> QTreeWidgetItem:
        return QTreeWidgetItem(
            [
                constants.WORKFLOW_STEP_TYPE_LABELS[step.step_type.value],
                step.label,
                self._step_detail(step),
            ]
        )

    @staticmethod
    def _step_detail(step: WorkflowStep) -> str:
        if step.step_type == StepType.PLAY_RECORDING:
            return step.recording
        if step.step_type == StepType.WAIT_IMAGE:
            return f"{step.image} (最大待機: {step.max_wait_sec}秒)"
        return step.message

    def _selected_index(self) -> int:
        selected = self._tree.selectedItems()
        if not selected:
            return -1
        return self._tree.indexOfTopLevelItem(selected[0])

    # --- ステップ操作 ---

    def _add_step(self, step_type: StepType) -> None:
        if self._bundle is None:
            return
        dialog = WorkflowStepDialog(
            WorkflowStep(step_type=step_type), self._bundle, self
        )
        if dialog.exec():
            self._bundle.workflow.steps.append(dialog.edited_step())
            self._refresh_tree()
            self._set_dirty()

    def _edit_step(self) -> None:
        index = self._selected_index()
        if self._bundle is None or index < 0:
            return
        steps = self._bundle.workflow.steps
        dialog = WorkflowStepDialog(steps[index], self._bundle, self)
        if dialog.exec():
            steps[index] = dialog.edited_step()
            self._refresh_tree()
            self._set_dirty()

    def _delete_step(self) -> None:
        index = self._selected_index()
        if self._bundle is None or index < 0:
            return
        del self._bundle.workflow.steps[index]
        self._refresh_tree()
        self._set_dirty()

    def _move_step(self, delta: int) -> None:
        index = self._selected_index()
        if self._bundle is None or index < 0:
            return
        steps = self._bundle.workflow.steps
        new_index = index + delta
        if not (0 <= new_index < len(steps)):
            return
        steps[index], steps[new_index] = steps[new_index], steps[index]
        self._refresh_tree()
        moved_row = self._tree.topLevelItem(new_index)
        if moved_row is not None:
            self._tree.setCurrentItem(moved_row)
        self._set_dirty()

    # --- バンドル操作 ---

    def _default_dir(self) -> str:
        return self._config.config.get("Workflow", "bundle_dir", fallback="")

    def _maybe_discard(self) -> bool:
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self, constants.WORKFLOW_EDITOR_TITLE, constants.MSG_CONFIRM_DISCARD
        )
        return answer == QMessageBox.StandardButton.Yes

    def _new_bundle(self) -> None:
        if not self._maybe_discard():
            return
        parent_dir = QFileDialog.getExistingDirectory(
            self, constants.DIALOG_BUNDLE_DIR_TITLE, self._default_dir()
        )
        if not parent_dir:
            return
        name, ok = QInputDialog.getText(
            self, constants.DIALOG_NEW_BUNDLE_TITLE, constants.LABEL_NEW_BUNDLE_NAME
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        bundle_path = Path(parent_dir) / f"{name}{BUNDLE_EXTENSION}"
        if bundle_path.exists():
            QMessageBox.warning(
                self,
                constants.WORKFLOW_EDITOR_TITLE,
                constants.MSG_BUNDLE_EXISTS.format(name=name),
            )
            return
        self._bundle = WorkflowBundle(path=bundle_path, workflow=Workflow(name=name))
        self._apply_loaded_bundle()
        self._save_bundle()

    def _open_bundle(self) -> None:
        if not self._maybe_discard():
            return
        path_str = QFileDialog.getExistingDirectory(
            self, constants.DIALOG_OPEN_BUNDLE_TITLE, self._default_dir()
        )
        if not path_str:
            return
        if not (Path(path_str) / WORKFLOW_FILENAME).exists():
            QMessageBox.warning(
                self, constants.WORKFLOW_EDITOR_TITLE, constants.MSG_INVALID_BUNDLE
            )
            return
        try:
            self._bundle = WorkflowBundle.load(path_str)
        except (OSError, ValueError, KeyError) as e:
            QMessageBox.warning(
                self,
                constants.WORKFLOW_EDITOR_TITLE,
                constants.MSG_BUNDLE_LOAD_ERROR.format(error=e),
            )
            return
        self._apply_loaded_bundle()

    def _apply_loaded_bundle(self) -> None:
        if self._bundle is not None:
            self._name_edit.setText(self._bundle.workflow.name)
        self._refresh_tree()
        self._set_dirty(False)

    def _save_bundle(self) -> None:
        if self._bundle is None:
            return
        self._bundle.workflow.name = self._name_edit.text().strip()
        try:
            self._bundle.save()
        except OSError as e:
            QMessageBox.warning(
                self,
                constants.WORKFLOW_EDITOR_TITLE,
                constants.MSG_BUNDLE_SAVE_ERROR.format(error=e),
            )
            return
        self._set_dirty(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._maybe_discard():
            event.ignore()
            return
        event.accept()


class WorkflowStepDialog(QDialog):
    """1ステップの編集ダイアログ。OK時にレコーディング・画像をバンドルへ保存する。"""

    def __init__(self, step: WorkflowStep, bundle: WorkflowBundle, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(constants.DIALOG_STEP_TITLE)
        self._step = step
        self._bundle = bundle
        self._recording_source: Path | None = None  # 新たに選択された.parファイル
        self._captured_image_b64 = ""  # 新たに取得された画像
        self._build_ui()

    # --- UI構築 ---

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._label_edit = QLineEdit(self._step.label)
        form.addRow(constants.LABEL_STEP_LABEL, self._label_edit)

        if self._step.step_type == StepType.PLAY_RECORDING:
            self._build_recording_row(form)
        elif self._step.step_type == StepType.WAIT_IMAGE:
            self._build_image_rows(form)
        else:
            self._message_edit = QLineEdit(self._step.message)
            self._message_edit.setPlaceholderText(constants.MSG_CONFIRM_DEFAULT)
            form.addRow(constants.LABEL_STEP_MESSAGE, self._message_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_recording_row(self, form: QFormLayout) -> None:
        row = QHBoxLayout()
        self._recording_label = QLabel(self._step.recording)
        row.addWidget(self._recording_label, stretch=1)
        browse_button = QPushButton(constants.BUTTON_BROWSE_RECORDING)
        browse_button.clicked.connect(self._browse_recording)
        row.addWidget(browse_button)
        form.addRow(constants.LABEL_STEP_RECORDING, row)

    def _build_image_rows(self, form: QFormLayout) -> None:
        self._image_preview = QLabel()
        self._image_preview.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if self._step.image:
            self._show_preview(QPixmap(str(self._bundle.asset_path(self._step.image))))
        form.addRow(constants.LABEL_STEP_IMAGE, self._image_preview)

        buttons = QHBoxLayout()
        capture_button = QPushButton(constants.BUTTON_CAPTURE_IMAGE)
        capture_button.clicked.connect(self._capture_image)
        buttons.addWidget(capture_button)
        load_button = QPushButton(constants.BUTTON_LOAD_IMAGE)
        load_button.clicked.connect(self._load_image)
        buttons.addWidget(load_button)
        buttons.addStretch()
        form.addRow("", buttons)

        self._max_wait_spin = QSpinBox()
        self._max_wait_spin.setRange(0, 86_400)
        self._max_wait_spin.setValue(self._step.max_wait_sec)
        form.addRow(constants.LABEL_STEP_MAX_WAIT, self._max_wait_spin)

    # --- 入力操作 ---

    def _browse_recording(self) -> None:
        path_str, _filter = QFileDialog.getOpenFileName(
            self, constants.DIALOG_RECORDING_TITLE, "", constants.FILE_DIALOG_FILTER
        )
        if not path_str:
            return
        self._recording_source = Path(path_str)
        self._recording_label.setText(self._recording_source.name)

    def _capture_image(self) -> None:
        # 全画面キャプチャ中はダイアログを隠す
        self.hide()
        try:
            image_b64 = capture_screen_region(self)
        finally:
            self.show()
        self._apply_image(image_b64)

    def _load_image(self) -> None:
        self._apply_image(load_image_file(self))

    def _apply_image(self, image_b64: str) -> None:
        if not image_b64:
            return
        self._captured_image_b64 = image_b64
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(image_b64))
        self._show_preview(pixmap)

    def _show_preview(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        if pixmap.width() > _IMAGE_PREVIEW_MAX or pixmap.height() > _IMAGE_PREVIEW_MAX:
            pixmap = pixmap.scaled(
                _IMAGE_PREVIEW_MAX,
                _IMAGE_PREVIEW_MAX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._image_preview.setPixmap(pixmap)

    # --- 確定 ---

    def accept(self) -> None:
        if not self._validate():
            return
        try:
            self._materialize_files()
        except OSError as e:
            QMessageBox.warning(
                self,
                constants.DIALOG_STEP_TITLE,
                constants.MSG_BUNDLE_SAVE_ERROR.format(error=e),
            )
            return
        super().accept()

    def _validate(self) -> bool:
        if self._step.step_type == StepType.PLAY_RECORDING:
            if self._recording_source is None and not self._step.recording:
                QMessageBox.warning(
                    self,
                    constants.DIALOG_STEP_TITLE,
                    constants.MSG_RECORDING_REQUIRED,
                )
                return False
        if self._step.step_type == StepType.WAIT_IMAGE:
            if not self._captured_image_b64 and not self._step.image:
                QMessageBox.warning(
                    self,
                    constants.DIALOG_STEP_TITLE,
                    constants.MSG_STEP_IMAGE_REQUIRED,
                )
                return False
        return True

    def _materialize_files(self) -> None:
        """新たに選択されたレコーディング・画像をバンドル内へ保存する。"""
        if self._recording_source is not None:
            self._bundle.recordings_dir.mkdir(parents=True, exist_ok=True)
            filename = _unique_filename(
                self._bundle.recordings_dir,
                self._recording_source.stem + ".json",
            )
            shutil.copyfile(
                self._recording_source, self._bundle.recording_path(filename)
            )
            self._step.recording = filename
        if self._captured_image_b64:
            self._bundle.assets_dir.mkdir(parents=True, exist_ok=True)
            filename = (
                self._step.image
                if self._step.image
                else _next_image_filename(self._bundle.assets_dir)
            )
            self._bundle.asset_path(filename).write_bytes(
                base64.b64decode(self._captured_image_b64)
            )
            self._step.image = filename

    def edited_step(self) -> WorkflowStep:
        step = self._step
        step.label = self._label_edit.text().strip()
        if step.step_type == StepType.WAIT_IMAGE:
            step.max_wait_sec = self._max_wait_spin.value()
        elif step.step_type == StepType.HUMAN_CONFIRM:
            step.message = self._message_edit.text().strip()
        return step
