import logging
import sys
from types import TracebackType

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.workflow_runner_window import WorkflowRunnerWindow
from service.single_instance import forward_to_running_instance
from utils.config_manager import ConfigManager
from utils.log_rotation import setup_logging


def log_uncaught_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """未処理例外をエラーログに記録してから標準の例外表示を行う。"""
    if not issubclass(exc_type, KeyboardInterrupt):
        logging.critical(
            "未処理の例外が発生しました", exc_info=(exc_type, exc_value, exc_traceback)
        )
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main() -> None:
    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None

    if file_path and forward_to_running_instance(file_path):
        return

    config = ConfigManager()
    try:
        setup_logging(config.config)
    except Exception as e:
        print(f"ログ設定の初期化に失敗しました: {e}", file=sys.stderr)
    sys.excepthook = log_uncaught_exception
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
