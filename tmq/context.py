from collections import deque

import tmq.define as td

class Context:
    '''The core handler for tsockets. Does the asyncio loop'''
    def __init__(self, broker):
        self._broker = broker
        self.tsockets = []
        self._remove = deque()
        self._thread = Thread(target=self.thread_process)
        self._thread.start()

    def thread_process(self):
        while True:
            start = time()
            # process socket removals during thread execution
            while self._remove:
                self.tsockets.remove(self._remove.pop())

            for s in self.tsockets:
                if s.context is None: continue  # socket was closed
                self.process_tsocket(s)

            start = time() - start
            try:
                sleep(td.TMQ_LOOP_TIME - start)
            except ValueError:
                pass

    def remove_tsocket(self, tsocket):
        self._remove.appendleft(tsocket)

    @staticmethod
    def process_tsocket(tsocket):
        # accept and process connections until they are done
        if tsocket.role == td.TMQ_BROKER:
            return Context._process_broker(tsocket)
        else:
            return Context._process_client(tsocket)

    @staticmethod
    def _process_client(tsocket):
        while True:
            try:
                conn, addr = tsocket.listener.accept()
            except BlockingIOError:
                return

            data = conn.recv(td.TMQ_MSG_LEN)
            data = td.tmq_unpack(data)
            type, pattern, data = data
            if type == td.TMQ_SUB:
                tsocket.published[pattern].appendleft(data)
            elif type == (td.TMQ_PUB | td.TMQ_CACHE):
                if pattern not in tsocket.subscribed: raise KeyError
                tsocket.subscribed[pattern] = tsocket.subscribed[pattern].\
                    union(td.tmq_unpack_addresses(data))
            elif type == td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_REMOVE:
                if pattern not in tsocket.subscribed: raise KeyError
                tsocket.subscribed[pattern] = tsocket.subscribed[pattern].\
                    difference(td.tmq_unpack_addresses(data))
            else: assert(0)

    @staticmethod
    def _process_broker(tsocket):
        while True:
            # TODO: process things that need to be sent out

            try:
                conn, addr = tsocket.listener.accept()
            except BlockingIOError:
                return

            data = conn.recv(td.TMQ_MSG_LEN)
            data = td.tmq_unpack(data)
            type, pattern, data = data
            if type == td.TMQ_SUB | td.TMQ_CACHE | td.TMQ_BROKER:
                Context._new_subscriber(tsocket, pattern, data)
            elif type == td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_BROKER:
                Context._new_publisher(tsocket, pattern, data)

    @staticmethod
    def _new_publisher(tsocket, pattern, data):
        if pattern not in tsocket.published:
            tsocket.published[pattern] = set()
        pub_addr = td.tmq_unpack_address_t(data)
        tsocket.published[pattern].add(pub_addr)

        # send current subscribers of that token to the new publisher
        addresses = tsocket.subscribed[pattern]
        packet = td.tmq_pack(td.TMQ_PUB | td.TMQ_CACHE, pattern,
                             td.tmq_pack_addresses(addresses))
        s = tsocket.socket()
        try:    # TODO: handle failure
            s.connect(pub_addr)
            s.send(packet)
        finally: s.close()

    @staticmethod
    def _new_subscriber(tsocket, pattern, data):
        if pattern not in tsocket.subscribed:
            tsocket.subscribed[pattern] = set()
        addr = td.tmq_unpack_address_t(data)
        tsocket.subscribed[pattern].add(addr)

        # send out subscriber to all publishers of that token
        # TODO: also send out for subsets of the token
        packet = td.tmq_pack(td.TMQ_PUB | td.TMQ_CACHE, pattern,
                             td.tmq_pack_address_t(*addr))
        for pub_addr in tsocket.published[pattern]:
            s = tsocket.socket()
            try:    # TODO: handle failure
                s.connect(pub_addr)
                s.send(packet)
            finally: s.close()
