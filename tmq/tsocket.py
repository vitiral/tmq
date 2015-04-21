from time import time, sleep
from threading import Thread
import socket
from collections import deque
from contextlib import closing

from tmq import define as td


class Pattern(tuple):
    '''In python pattern is just a tuple. In C, this stores the hash
    information as well'''
    pass


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
    def __init__(self, context, role=td.TMQ_CLIENT,
                 socket_constructor=socket.socket):
        if role not in {td.TMQ_CLIENT, td.TMQ_BROKER, td.TMQ_BRIDGE}:
            raise TypeError(role)
        self.role = role
        self._socket_constructor = socket_constructor
        self.context = context
        self.listener = None
        self._broker = None
        self.received = {}
        self.subscribers = {}
        self.context.sockets.append(self)

    def socket(self):
        '''create a new standard socket of the same type'''
        return self._socket_constructor()

    @property
    def broker(self):
        return self._broker

    def close(self):
        '''Close the socket. Can still retrieve data already receieved'''
        self.context.remove_socket(self)
        if self.listener:
            self.listener.close()
        self.listener = None
        self._broker = None
        self.subscribers = None
        self.context = None

    def __del__(self):
        try: self.close()
        except Exception as E: pass


def tmq_socket(context, role=td.TMQ_CLIENT, socket_constructor=socket.socket):
    return tsocket(context, role, socket_constructor)


def tmq_send(tsocket, pattern, data):
    '''Publish data to subscribers of pattern'''
    if not isinstance(pattern, Pattern):
        pattern = Pattern(pattern)
    endpoints = tmq_endpoints(tsocket, pattern)
    packet = td.tmq_pack(td.TMQ_SUB, pattern, data)
    for addr in endpoints:
        with closing(tsocket.socket()) as s:
            s.connect(addr)
            s.send(packet)


def tmq_recv(tsocket, pattern):
    '''Non blocking receive call from pattern

    Returns:
        bytes: if there is data, returns a byte string of the data

        If there is no data, None is returned
    '''
    queue = tsocket.received[pattern]
    if queue:
        return queue.pop()
    else:
        return None


def tmq_bind(tsocket, endpoint, backlog=5):
    '''Bind the tsocket to listen/subscribe on a specific endpoint'''
    if tsocket.listener:
        tsocket.listener.close()
        tsocket.listener = None

    s = tsocket.socket()
    try:
        s.settimeout(0)
        s.bind(endpoint)
        s.listen(backlog)
        tsocket.listener = s
    except Exception:
        s.close()
        raise


def tmq_broker(tsocket, endpoint):
    '''Set the tsocket's broker'''
    tsocket._broker = endpoint


def tmq_subscribe(tsocket, pattern):
    with closing(tsocket.socket()) as s:
        s.connect(tsocket.broker)
        s.send(td.tmq_pack(
            td.TMQ_SUB | td.TMQ_CACHE | td.TMQ_BROKER, pattern))
    tsocket.received[pattern] = deque()


################################################################################
## Internal Functions

def tmq_endpoints(tsocket, pattern):
    '''Get the endpoints (subscribers) associated with pattern'''
    if pattern not in tsocket.subscribers:
        # retrieve the subscribers from broker
        with closing(tsocket.socket()) as s:
            s.connect(tsocket.broker)
            s.send(td.tmq_pack(
                td.TMQ_PUB | td.TMQ_CACHE | td.TMQ_BROKER, pattern))
            type, t, addresses = td.tmq_unpack(s.recv())
        assert type == td.TMQ_SUB | td.TMQ_CACHE
        assert pattern == t
        tsocket.subscribers[pattern] = td.tmq_unpack_addresses(addresses)
    return tsocket.subscribers[pattern]
