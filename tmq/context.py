from collections import deque

import tmq.define as td

class Context:
    '''The core handler for sockets. Does the asyncio loop'''
    LOOP_TIME = 5e-3
    def __init__(self, broker):
        self._broker = broker
        self.sockets = []
        self._remove = deque()
        self._thread = Thread(target=self.thread_process)
        self._thread.start()

    @staticmethod
    def process_socket(socket):
        # accept and process connections until they are done
        while True:
            try:
                conn, addr = socket.accept()
            except BlockingIOError:
                return

            data = conn.recv(td.TMQ_MSG_LEN)
            data = td.tmq_unpack(data)
            type, pattern, data = data
            assert type == td.TMQ_SUB
            print("Sub:", pattern, data)
            yield pattern, data

    def thread_process(self):
        while True:
            start = time()
            # process socket removals during thread execution
            while self._remove:
                self.sockets.remove(self._remove.pop())

            for s in self.sockets:
                if s.context is None: continue  # socket was closed
                for pattern, data in self.process_socket(s):
                    s.received[pattern] = data

            start = time() - start
            try:
                sleep(self.LOOP_TIME - start)
            except ValueError:
                pass

    def remove_socket(self, socket):
        self._remove.appendleft(socket)
