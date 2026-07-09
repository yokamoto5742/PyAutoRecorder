import uuid

from PySide6.QtCore import QCoreApplication

from service.single_instance import SingleInstanceServer, forward_to_running_instance

_app = QCoreApplication.instance() or QCoreApplication([])


def _unique_server_name() -> str:
    return f"PyAutoRecorderTest-{uuid.uuid4().hex}"


class TestForwardToRunningInstance:
    def test_returns_false_when_no_server_running(self):
        assert forward_to_running_instance("dummy.par", _unique_server_name()) is False

    def test_delivers_path_to_running_server(self):
        server_name = _unique_server_name()
        server = SingleInstanceServer(server_name=server_name)
        received: list[str] = []
        server.file_received.connect(received.append)

        assert forward_to_running_instance("C:/macros/sample.par", server_name) is True

        for _ in range(50):
            if received:
                break
            _app.processEvents()

        assert received == ["C:/macros/sample.par"]
