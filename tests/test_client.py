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
        context = Context(None)
        context.event_loop.set_debug(True)
        ts = tmq_socket(context, 0)
        tmq_bind(ts, (ip, ports[1]))
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
        context = Context(None)
        context.event_loop.set_debug(True)
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
        pub = tmq_socket(context, 0)
        pub.subscribed[pattern] = [addr]
        tmq_bind(pub, (ip, ports[1]))
        send_task = context.event_loop.create_task(
            tmq_send_async(pub, pattern, expected))
        context.event_loop.run_until_complete(send_task)
        tasks = context._process_tsocket(sub)

        for task in tasks:
            context.event_loop.run_until_complete(task)
        tasks.append(send_task)

        result = sub.published[pattern].pop()

        self.assertEqual(result, expected)

        close_all(pub, sub)
        tasks.extend(context.failures)
        for t in tasks:
            e = t.exception()
            if e: raise e
