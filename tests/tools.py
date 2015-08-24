import socket
from unittest.mock import MagicMock
import asyncio

from tmq.context import Context

ip = '127.0.0.1'
ports = range(49300, 50400)


class MockContext(Context):
    '''Context without the loop (test should do all the work directy)'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_loop.set_debug(True)

    @asyncio.coroutine
    def _loop(self):
        return

def mock_context():
    m = MagicMock(spec=Context)
    m.tsockets = []
    m.event_loop = asyncio.get_event_loop()
    m._process_client = Context._process_client
    m._process_client_data = Context._process_client_data
    return m


def mock_socket():
    s = MagicMock(spec=socket.socket)
    s.gettimeout.return_value = 0.0
    s.connect.return_value = True
    send = lambda x: len(x)
    s.sendall.side_effect = send
    s.send.side_effect = send
    return s


def close_all(*sockets):
    for s in sockets:
        s.close()


def convert_addr(addr):
    '''python requires addresses to be in strings'''
    if isinstance(addr[0], str):
        addr = tuple(int(a) for a in addr[0].split('.')), addr[1]
    return addr
