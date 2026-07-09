import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from service.single_instance import forward_to_running_instance


def main() -> None:
    app = QApplication(sys.argv)
    file_path = sys.argv[1] if len(sys.argv) > 1 else None

    if file_path and forward_to_running_instance(file_path):
        return  # 既存インスタンスに転送済みのため、このプロセスは何もせず終了する

    window = MainWindow(launch_file_path=file_path)
    if file_path is None:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
