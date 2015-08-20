import asyncio
from collections import deque

import tmq.define as td

class Context:
    '''The core handler for tsockets. Does the asyncio loop'''
    def __init__(self, broker, event_loop=Nonejk):
        self._broker = broker
        self.tsockets = []
        if event_loop is None:
            event_loop = asyncio.get_event_loop()
        self._event_loop = event_loop
        self._event_loop.create_task(self._loop())

    def remove_tsocket(self, tsocket):
        self.tsockets.remove(self._remove.pop())

    @asyncio.coroutine
    def _loop(self):
        while True:
            start = time()
            for s in self.tsockets:
                assert s.context
                self._process_tsocket(s)

            start = time() - start
            try:
                yield from asyncio.sleep(td.TMQ_LOOP_TIME - start)
            except ValueError:
                pass

    def _process_tsocket(self, tsocket):
        # accept and process connections until they are done
        if tsocket.role == td.TMQ_BROKER:
            self._process_broker(tsocket)
        else:
            self._process_client(tsocket)

    def _process_client(self, tsocket):
        while True:
            try:
                conn, addr = tsocket.listener.accept()
            except BlockingIOError:
                return  # process done
            self._event_loop.create_task(self._process_client_data(conn, addr))

    @asyncio.coroutine
    def _process_client_data(self, conn, addr):
        try:
            # TODO: get all data in socket
            data = yield from self._event_loop.sock_recv(conn, td.TMQ_MSG_LEN)
            type, pattern, data = td.tmq_unpack(data)
            if type == td.TMQ_SUB:
                # it is data that this socket subscribed to
                tsocket.published[pattern].appendleft(data)
            elif type == (td.TMQ_PUB | td.TMQ_CACHE):
                # it is new subscribers to publish to
                if pattern not in tsocket.subscribed: raise KeyError
                tsocket.subscribed[pattern].update(
                    td.tmq_unpack_addresses(data))
            elif type == td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_REMOVE:
                # it is subscribers to remove from publishing to
                if pattern not in tsocket.subscribed: raise KeyError
                subscribed = tsocket.subscribed[pattern]
                for addr in td.tmq_unpack_addresses(data):
                    try: subscribed.remove(addr)
                    except KeyError: pass
            else: assert(0)
        finally:
            conn.close()

    def _process_broker(self, tsocket):
        while True:
            # TODO: process things that need to be sent out
            try:
                conn, addr = tsocket.listener.accept()
            except BlockingIOError:
                return
            self._event_loop.create_task(self._process_broker_data(conn, addr))

    @asyncio.coroutine
    def _process_broker_data(self, conn, addr):
        try:
            # TODO: get all the data
            data = yield from self._event_loop.sock_recv(conn, td.TMQ_MSG_LEN)
            type, pattern, data = td.tmq_unpack(data)
            if type == td.TMQ_SUB | td.TMQ_CACHE | td.TMQ_BROKER:
                self._event_loop.create_task(
                    self._new_subscriber(tsocket, pattern, data))
            elif type == td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_BROKER:
                self._event_loop.create_task(
                    self._new_publisher(tsocket, pattern, data))
        finally:
            conn.close()

    @asyncio.coroutine
    def _new_publisher(self, tsocket, pattern, data):
        if pattern not in tsocket.published:
            tsocket.published[pattern] = set()
        addr = td.tmq_unpack_addresses(data)[0]
        tsocket.published[pattern].add(addr)

        # send current subscribers of that token to the new publisher
        addresses = tsocket.subscribed[pattern]
        packet = td.tmq_pack(td.TMQ_PUB | td.TMQ_CACHE, pattern,
                             td.tmq_pack_addresses(addresses))
        s = tsocket.socket()
        try:    # TODO: handle failure
            yield from self._event_loop.sock_connect(s, addr)
            yield from self._event_loop.sock_send_all(s, packet)
        finally: s.close()

    @asyncio.coroutine
    def _new_subscriber(self, tsocket, pattern, data):
        if pattern not in tsocket.subscribed:
            tsocket.subscribed[pattern] = set()
        addr = td.tmq_unpack_addresses(data)[0]

        if pattern not in tsocket.published:
            return  # no publishers for that subscriber (yet)

        # send out subscriber to all publishers of that token
        # TODO: also send out for subsets of the token
        packet = td.tmq_pack(td.TMQ_PUB | td.TMQ_CACHE, pattern,
                             td.tmq_pack_address_t(*addr))
        for addr in tsocket.published[pattern]:
            s = tsocket.socket()
            try:    # TODO: handle failure
                yield from self._event_loop.sock_connect(s, addr)
                yield from self._event_loop.sock_send_all(s, packet)
            else:
                tsocket.subscribed[pattern].add(addr)
            finally: s.close()
