import socket
from unittest import TestCase
from unittest.mock import MagicMock
from operator import attrgetter

from tmq import define as td
from tmq.tsocket import *
from tmq.context import Context

from .tools import *


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
        ts.subscribed[pattern] = [addr]
        tmq_send(ts, pattern, expected)

        # make sure it is correct for the subscriber
        conn, addr = s.accept()
        self.assertNotEqual(addr, s.getsockname())
        data = conn.recv(2048)
        type, result_p, data = td.tmq_unpack(data)
        self.assertEqual(type, td.TMQ_SUB)
        self.assertEqual(result_p, pattern)
        self.assertEqual(data, expected)

        close_all(s, ts, conn)

    def test_sub(self):
        addr = ip, ports[0]
        pattern = (0, 1)
        expected = b'houston we have lift off'

        mocked_socket = mock_socket()

        # create subscriber and subscribe to pattern
        context = mock_context()
        sub = tmq_socket(context, 0)
        tmq_bind(sub, addr)
        self.assertTrue(sub.listener)

        # just make sure the listener socket is functioning
        s2 = socket.socket()
        s = socket.socket()
        s.connect(addr)
        s.send(b'hi there')
        conn, _ = sub.listener.accept()
        self.assertEqual(conn.recv(256), b'hi there')
        close_all(s, conn)
        del s, conn, _

        sub.socket = MagicMock(return_value = mocked_socket)
        tmq_subscribe(sub, pattern)
        mocked_socket.connect.assert_called_with(None)
        self.assertTrue(mocked_socket.send.called)

        # "publish" the data
        context = mock_context()
        pub = tmq_socket(context, 0)
        pub.subscribed[pattern] = [addr]
        tmq_send(pub, pattern, expected)

        Context.process_socket(sub)
        result = sub.published[pattern].pop()

        self.assertEqual(result, expected)

        close_all(pub, sub)

