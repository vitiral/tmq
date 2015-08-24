import socket
from unittest import TestCase
from unittest.mock import MagicMock
from operator import attrgetter

from tmq import define as td
from tmq.tsocket import *
from tmq.context import Context
from tmq.utils import run_tasks

from .tools import *


class TestBroker(TestCase):
    def test_fake_broker(self):
        '''Pretend to act as a broker between two sockets'''
        pattern = td.pattern("test", "pattern")
        data = b'this is test data'

        addr_pub = ip, ports[0]
        addr_sub = ip, ports[1]
        addr_broker = ip, ports[2]

        broker = socket.socket()
        broker.bind(addr_broker)
        broker.listen(5)

        context = MockContext(None)
        pub = tsocket(context, addr_pub, addr_broker)
        sub = tsocket(context, addr_sub, addr_broker)

        sub.subscribe(sub, pattern)
        # receive the request to be added to subscribers
        type, p, data = td.tmq_unpack(broker.accept()[0].recv(2048))
        self.assertEqual(p, pattern)
        addr, stype = td.tmq_unpack_address_t(data)
        self.assertEqual(addr, addr_sub)

        sub.publish(pattern)
        # receive the request to be added to publishers
        type, p, data = td.tmq_unpack(broker.accept()[0].recv(2048))
        self.assertEqual(p, pattern)
        addr, stype = td.tmq_unpack_address_t(data)
        self.assertEqual(addr, addr_pub)

        # send back subscriber addresses to publisher
        packed = td.tmq_pack(td.TMQ_PUB | td.TMQ_CACHE, pattern,
                             td.tmq_pack_address_t(*addr_sub))
        s = socket.socket()
        s.connect(addr_pub)
        s.send(packed)
        s.close()

        # receive addresses
        eloop = context.event_loop
        run_tasks(context._process_tsocket(pub))
        self.assertSetEqual(pub.subscribed[pattern], set((addr_sub,)))

        # now send some data, no more broker necessary!
        pub.send(pattern, data)
        run_tasks(context._process_tsocket(sub))
        result = sub.recv(pattern)

        self.assertEqual(data, result)

        close_all(pub, sub, broker)

    def test_broker(self):
        '''now do all of the above, but with a real broker'''
        pattern = td.pattern("test", "pattern")
        data = b'this is test data'

        addr_pub = ip, ports[0]
        addr_sub = ip, ports[1]
        addr_broker = ip, ports[2]

        context = MockContext(None)
        eloop = context.event_loop
        broker = tsocket(context, addr_broker, role=td.TMQ_BROKER)
        assert broker.role == td.TMQ_BROKER
        pub = tsocket(context, addr_pub, addr_broker)
        sub = tsocket(context, addr_sub, addr_broker)

        # subscribe
        sub.subscribe(pattern)
        run_tasks(eloop, context._process_tsocket(broker))
        run_tasks(eloop, context._process_tsocket(pub))
        # the context records that there is a subscriber
        assert context.subscribers[pattern] == set((addr_sub,))
        return

        # publish
        pub.publish(pattern)
        run_tasks(eloop, context._process_tsocket(broker))
        self.assertEqual(sub.published[pattern], set((addr_pub,)))
        run_tasks(eloop, context._process_tsocket(broker))
        self.assertEqual(pub.subscribed[pattern], set((addr_sub,)))
        return

        # publish data
        tmq_send(pub, pattern, data)
        Context.process_tsocket(sub)
        result = tmq_recv(sub, pattern)
        self.assertEqual(data, result)

        close_all(pub, sub, broker)
        return
