import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.workflow_runner_window import WorkflowRunnerWindow
from service.single_instance import forward_to_running_instance
from utils.config_manager import ConfigManager


def main() -> None:
    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None

    if file_path and forward_to_running_instance(file_path):
        return

    # 実行専用モード（一般ユーザー向け）ではワークフロー実行画面のみを表示する
    config = ConfigManager()
    mode = config.config.get("Workflow", "mode", fallback="runner")
    if file_path is None and mode != "editor":
        window: MainWindow | WorkflowRunnerWindow = WorkflowRunnerWindow(config)
        window.show()
    else:
        window = MainWindow(launch_file_path=file_path)
        if file_path is None:
            window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
