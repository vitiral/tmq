import socket
from unittest.mock import MagicMock

from tmq.context import Context

ip = '127.0.0.1'
ports = range(9000, 9200)


def mock_context():
    m = MagicMock(spec=Context)
    m.sockets = []
    return m


def mock_socket():
    return MagicMock(spec=socket.socket)


def close_all(*sockets):
    for s in sockets:
        s.close()


def convert_addr(addr):
    '''python requires addresses to be in strings'''
    if isinstance(addr[0], str):
        addr = tuple(int(a) for a in addr[0].split('.')), addr[1]
    return addr
