"""One window per user: a second launch opens a tab in the first (CD-09).

The mechanism is a ``QLocalServer`` named after the user and the application:
the first process listens, every later process connects, writes the paths it
was given, and exits.  If the socket cannot be created or reached, the new
process simply becomes a normal instance — a broken socket must never stop the
editor from starting.

Qt types are used here, but nothing needs a display: the tests drive the
server and the client directly.
"""

from __future__ import annotations

import getpass
import os
from typing import List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

#: How long a client waits for the running instance to accept the connection.
CONNECT_TIMEOUT_MS = 700

#: How long the server keeps reading after the first line.
READ_TIMEOUT_MS = 700


def server_name(suffix: str = "") -> str:
    """A socket name that is unique per user and per application."""
    try:
        user = getpass.getuser()
    except Exception:                      # pragma: no cover - exotic hosts
        user = str(os.getuid()) if hasattr(os, "getuid") else "user"
    base = f"mishkah-note-{user}"
    return f"{base}-{suffix}" if suffix else base


def paths_to_payload(paths: List[str]) -> bytes:
    return ("\n".join(str(p) for p in paths) + "\n").encode("utf-8") if paths else b""


def payload_to_paths(payload: bytes) -> List[str]:
    text = payload.decode("utf-8", "replace")
    return [line for line in text.splitlines() if line.strip()]


def send_to_running_instance(paths: List[str], name: Optional[str] = None,
                             timeout_ms: int = CONNECT_TIMEOUT_MS) -> bool:
    """True when a running instance accepted our paths (CD-09).

    Returning ``False`` is the normal "nobody is listening" answer, and the
    caller then starts a window of its own.
    """
    socket = QLocalSocket()
    socket.connectToServer(name or server_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    payload = paths_to_payload(paths) or b"\n"
    socket.write(payload)
    socket.flush()
    socket.waitForBytesWritten(READ_TIMEOUT_MS)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """The first process's end of the channel."""

    paths_received = Signal(list)

    def __init__(self, parent: Optional[QObject] = None, name: Optional[str] = None):
        super().__init__(parent)
        self._name = name or server_name()
        self._server = QLocalServer(self)
        # A stale socket file from a crashed process would block the name.
        QLocalServer.removeServer(self._name)

    def start(self) -> bool:
        return bool(self._server.listen(self._name))

    def name(self) -> str:
        return self._name

    def close(self) -> None:
        self._server.close()
        QLocalServer.removeServer(self._name)

    # -- slots -----------------------------------------------------------
    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda s=socket: self._read(s))
        socket.disconnected.connect(socket.deleteLater)

    def _read(self, socket: QLocalSocket) -> None:
        data = bytes(socket.readAll())
        if not data:
            return
        paths = payload_to_paths(data)
        if paths:
            self.paths_received.emit(paths)

    def _wire(self) -> None:
        self._server.newConnection.connect(self._on_new_connection)


def start_server(parent: Optional[QObject] = None,
                 name: Optional[str] = None) -> Optional[InstanceServer]:
    """Listen for later launches; ``None`` when the channel is unavailable."""
    server = InstanceServer(parent, name)
    if not server.start():
        return None
    server._wire()                          # noqa: SLF001 - part of the class
    return server
