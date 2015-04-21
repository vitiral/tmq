import socket
from unittest import TestCase
from unittest.mock import MagicMock

from tmq import define as td
from tmq.tsocket import *
from tmq.context import Context

from .tools import mock_context

ip = 'localhost'
ports = range(9000, 9200)


class TestSocket(TestCase):
    def test_pub(self):
        # create fake subscriber
        addr = ip, ports[0]
        pattern = (0, 1)
        expected = b'houston we have lift off'
        s = socket.socket()
        s.bind(addr)
        s.listen(5)

        # "publish" the data
        context = mock_context()
        ts = tmq_socket(context, 0)
        ts.subscribers[pattern] = [addr]
        tmq_send(ts, pattern, expected)

        # make sure it is correct for the subscriber
        conn, addr = s.accept()
        self.assertNotEqual(addr, s.getsockname())
        data = conn.recv(2048)
        type, result_p, data = td.tmq_unpack(data)
        self.assertEqual(type, td.TMQ_SUB)
        self.assertEqual(result_p, pattern)
        self.assertEqual(data, expected)

        s.close()
        ts.close()
        conn.close()

    def test_sub(self):
        addr = ip, ports[0]
        pattern = (0, 1)
        expected = b'houston we have lift off'

        # create subscriber
        context = mock_context()
        ts = tmq_socket(context, 0)
        ts.socket = MagicMock()
        tmq_bind(ts, addr)
        tmq_subscribe(ts, pattern)

        s = socket.socket()


