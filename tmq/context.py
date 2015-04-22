from collections import deque

import tmq.define as td

class Context:
    '''The core handler for sockets. Does the asyncio loop'''
    def __init__(self, broker):
        self._broker = broker
        self.sockets = []
        self._remove = deque()
        self._thread = Thread(target=self.thread_process)
        self._thread.start()

    def thread_process(self):
        while True:
            start = time()
            # process socket removals during thread execution
            while self._remove:
                self.sockets.remove(self._remove.pop())

            for s in self.sockets:
                if s.context is None: continue  # socket was closed
                self.process_socket(s)

            start = time() - start
            try:
                sleep(td.TMQ_LOOP_TIME - start)
            except ValueError:
                pass

    def remove_socket(self, socket):
        self._remove.appendleft(socket)

    @staticmethod
    def process_socket(socket):
        # accept and process connections until they are done
        while True:
            if socket.role == td.TMQ_BROKER:
                return Context._process_broker(socket)
            else:
                return Context._process_client(socket)

    @staticmethod
    def _process_client(socket):
        while True:
            try:
                conn, addr = socket.listener.accept()
            except BlockingIOError:
                return

            data = conn.recv(td.TMQ_MSG_LEN)
            data = td.tmq_unpack(data)
            type, pattern, data = data
            if type == td.TMQ_SUB:
                socket.received[pattern] = data
            elif type == (td.TMQ_PUB | td.TMQ_CACHE):
                if pattern not in socket.subscribers: raise KeyError
                socket.subscribers[pattern] = socket.subscribers.union(
                    td.tmq_unpack_addresses(data))
            elif type == td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_REMOVE:
                if pattern not in socket.subscribers: raise KeyError
                socket.subscribers[pattern] = socket.subscribers.difference(
                    td.tmq_unpack_addresses(data))
            else: assert(0)

    @staticmethod
    def _process_broker(socket):
        return
