"""シングルインスタンス制御: 後続プロセスが起動された際、既存インスタンスへファイルパスを転送する。"""

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

_SERVER_NAME = "PyAutoRecorder-SingleInstance"
_CONNECT_TIMEOUT_MS = 1000
_WRITE_TIMEOUT_MS = 1000


class SingleInstanceServer(QObject):
    """既存インスタンス側で、後続プロセスから転送されたファイルパスを受信する。"""

    file_received = Signal(str)

    def __init__(
        self, parent: QObject | None = None, server_name: str = _SERVER_NAME
    ) -> None:
        super().__init__(parent)
        self._pending_sockets: list[QLocalSocket] = []
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._server.listen(server_name)

    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        self._pending_sockets.append(socket)
        socket.readyRead.connect(lambda: self._on_ready_read(socket))
        socket.disconnected.connect(lambda: self._forget_socket(socket))

    def _on_ready_read(self, socket: QLocalSocket) -> None:
        path = bytes(socket.readAll().data()).decode("utf-8")
        if path:
            self.file_received.emit(path)

    def _forget_socket(self, socket: QLocalSocket) -> None:
        # nextPendingConnection()が返すソケットはサーバーが所有し、切断時に自動破棄されるため
        # ここでは明示的なdeleteLater()を呼ばない（二重削除を避ける）。
        if socket in self._pending_sockets:
            self._pending_sockets.remove(socket)


def forward_to_running_instance(
    file_path: str, server_name: str = _SERVER_NAME
) -> bool:
    """既存インスタンスへファイルパスを送信する。送信できればTrue、既存インスタンスがなければFalse。"""
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        return False
    socket.write(file_path.encode("utf-8"))
    if socket.bytesToWrite() > 0:
        # QLocalSocket.waitForBytesWritten()はWindowsの名前付きパイプで
        # 接続直後は書き込み完了を検知できないことがあるため、イベントループで待つ。
        loop = QEventLoop()
        socket.bytesWritten.connect(loop.quit)
        QTimer.singleShot(_WRITE_TIMEOUT_MS, loop.quit)
        loop.exec()
    socket.disconnectFromServer()
    return True
