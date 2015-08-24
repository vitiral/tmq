import socket
from collections import deque
import asyncio

from tmq import define as td


class tsocket:
    '''The core socket class for Token Message Queue

    Args:
        context: the context manager for this socket. Get a context with
            tmq.tmq_init() function
        type (int): the socket type to use. Use a constant from the socket
            module. Default is socket.AF_INET
        role (int): the role this socket plays for the network

            Options are:
                tmq_TMQ_CLIENT, tmq.TMQ_BROKER or tmq.TMQ_BRIDGE

            The operation of the socket depends on the role type selected.

    Notes:
        - Intended to mimick future C implementation as much as possible
        - Future implementation will have socket_methods pointer
            which is a `struct tmq_socket_methods` that has the following
            function pointers defined:
            bind, connect, listen, accept, send, recv (non-blocking)
        - Each of these functions can take the pointer given by
            tsocket.socket() and communicate with it
    '''
    def __init__(self, context, listener, broker=None, role=td.TMQ_CLIENT,
                 socket_constructor=socket.socket):
        if role not in {td.TMQ_CLIENT, td.TMQ_BROKER, td.TMQ_BRIDGE}:
            raise TypeError(role)
        if broker is None and role != td.TMQ_BROKER:
            raise TypeError("All roles must have a broker except broker")
        self.role = role
        self._socket_constructor = socket_constructor
        self.context = context
        self._listener = None
        self._broker = None
        self.published = {}  # published data
        self.subscribed = {}  # subscribers
        self.context.tsockets.append(self)
        self.bind(listener)
        if broker:
            self.setbroker(broker)

    def socket(self):
        '''create a new standard socket of the same type

        Returns:
            A standard nonblocking socket. NOT a tsocket!
        '''
        s = self._socket_constructor()
        s.setblocking(0)
        return s

    def accept(self):
        '''accepts connection on the listener

        Returns:
            A standard nonblocking socket. NOT a tsocket!
        '''
        conn, addr = self._listener.accept()
        conn.setblocking(0)
        return conn, addr

    def subscribe(self, pattern):
        return self.context.event_loop.run_until_complete(
            self.subscribe_async(pattern))

    @asyncio.coroutine
    def subscribe_async(self, pattern):
        if pattern in self.published:
            raise KeyError("Subscribing to {} twice".format(pattern))
        eloop = self.context.event_loop
        s = self.socket()
        try:
            yield from eloop.sock_connect(s, self.broker)
            data = td.tmq_pack(
                td.TMQ_SUB | td.TMQ_CACHE | td.TMQ_BROKER,
                pattern,
                td.tmq_pack_address_t(*self.getsockname()))
            yield from eloop.sock_sendall(s, data)
        finally: s.close()
        self.published[pattern] = deque()

    def publish(self, pattern):
        return self.context.event_loop.run_until_complete(
            self.publish_async(pattern))

    @asyncio.coroutine
    def publish_async(self, pattern):
        '''Inform the broker we are a publisher and ask for subscribers'''
        if not isinstance(pattern, td.pattern):
            pattern = td.pattern(*pattern)
        if pattern not in self.subscribed:
            # inform broker we are a publisher
            eloop = self.context.event_loop
            s = self.socket()
            try:
                yield from eloop.sock_connect(s, self.broker)
                yield from eloop.sock_sendall(s, td.tmq_pack(
                    td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_BROKER, pattern,
                    td.tmq_pack_address_t(*self.getsockname())))
            finally: s.close()
            self.subscribed[pattern] = set()

    def getsockname(self):
        return self._listener.getsockname()

    def bind(self, endpoint, backlog=5):
        '''Bind the tsocket to listen/subscribe on a specific endpoint.

        Note: this is done in init. Use this to change the value'''
        if self._listener:
            try:
                self._listener.close()
                raise NotImplementedError("TODO: cannot rebind socket")
            finally:
                self._listener = None

        s = self.socket()
        try:
            s.setblocking(0)
            s.bind(endpoint)
            s.listen(backlog)
            self._listener = s
        except Exception:
            s.close()
            raise

    @property
    def broker(self):
        '''Return the broker address the socket is using'''
        return self._broker

    def setbroker(self, endpoint):
        '''Set the tsocket's broker

        Note: this is automatically done in init, use this to change the broker
        '''
        self._broker = endpoint

    def close(self):
        '''Close the tsocket. Can still retrieve data already received'''
        try:
            self.context.remove_tsocket(self)
        finally:
            try:
                if self._listener:
                    self._listener.close()
            finally:
                self._listener = None
                self._broker = None
                self.subscribed = None
                self.context = None

    def send(self, pattern, data, flags=0):
        self.context.event_loop.run_until_complete(
            self.send_async(pattern, data, flags))

    @asyncio.coroutine
    def send_async(self, pattern, data, flags=0):
        '''Publish data to subscribers of pattern asyncronously'''
        if not isinstance(pattern, td.pattern):
            pattern = td.pattern(*pattern)
        if pattern not in self.subscribed:
            raise ValueError("Pattern not marked as a publish pattern: {}".format(
                pattern))
        endpoints = self.subscribed[pattern]
        if not endpoints:
            return 1
        packet = td.tmq_pack(td.TMQ_SUB, pattern, data)
        for addr in endpoints:
            s = self.socket()
            try:
                yield from self.context.event_loop.sock_connect(s, addr)
                # TODO: this should be return
                yield from self.context.event_loop.sock_sendall(s, packet)
            finally: s.close()

    def recv(self, pattern):
        '''Non blocking receive call from pattern

        Returns:
            bytes: if there is data
            None: if there is no data
        '''
        queue = self.published[pattern]
        if queue:
            return queue.pop()
        else:
            return None

    def __del__(self):
        try: self.close()
        except Exception as E: pass

