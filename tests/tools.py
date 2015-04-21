import socket
from unittest.mock import MagicMock

from tmq.context import Context


def mock_context():
    m = MagicMock(spec=Context)
    m.sockets = []
    return m


def mock_socket():
    return MagicMock(spec=socket.socket)


def close_all(*sockets):
    for s in sockets:
        s.close()
