import socket
from enum import Enum
from operator import xor
import struct

HEADER_BYTES = 4
TMQ_MSG_LEN = 2056

# Flags
TMQ_DONTWAIT        = 0x01

'''
Each packet is consructed as:

bytes   : 1     | 1    | 2    | tlen   | dlen
name    : type  | tlen | dlen | tokens | data

Each packet has a type which is a combination of the below
bit mappings. Commands are always directed TO what they reference

So for instance:

type                                | Result
------------------------------------|------------------------------------------
(TMQ_SUB)                           | message from a pub client->sub client
(TMQ_SUB|TMQ_CACHE|TMQ_BROKER)      | Add self as subscriber of tokens
(TMQ_PUB|TMQ_CACHE|TMQ_BROKER)      | Add self as publisher of tokens
(TMQ_SUB|TMQ_CACHE)                 | Add token:end to client cache of subs
(TMQ_SUB|TMQ_CACHE|TMQ_REMOVE)      | Remove token:end from client cache of subs
'''

# Command Types
TMQ_PUB             = 0x01      # Publisher type
TMQ_SUB             = 0x02      # Subscriber type
TMQ_CACHE           = 0x04      # call to update jkjthe cache
TMQ_REMOVE          = 0x08      # remove command
TMQ_                = 0x10
TMQ_                = 0x20

# Role Types
TMQ_CLIENT          = 0x00      # Client role
TMQ_BROKER          = 0x40      # Broker role
TMQ_BRIDGE          = 0x80      # Bridge role


def tmq_hash(value):
    '''Standard hasing function to generate a token from a string'''
    h = 0
    for c in value:
        h = (65599 * h + ord(c)) & 0xFFFFFFFF
    return xor(h, h >> 16)


def tmq_pack(type, tokens, data=b''):
    '''Constructs packet:
    bytes   : 1     | 1    | 2    | tlen   | dlen
    name    : type  | tlen | dlen | tokens | data
    where:
        type: bitmap of message type
        tlen: tokens length (number of tokens)
        dlen: data length (in bytes)
        tokens: actual tokens
        data: actual data

    Args:
        type (int): bitmap of message type
        tokens (tuple of ints): tokens message is for
        data (bytes): binary data
    '''
    return (struct.pack(">bbH{}L".format(len(tokens)),
                       type, len(tokens), len(data), *tokens)
             + data)


def tmq_unpack(data):
    type, tlen, dlen = struct.unpack('>bbH', data[:HEADER_BYTES])
    tokens = struct.unpack('>{}L'.format(tlen),
                           data[HEADER_BYTES:HEADER_BYTES + tlen * 4])
    data = data[HEADER_BYTES + tlen * 4:]
    return type, tokens, data


def tmq_pack_address_t(address, port):
    '''The socket data type is packed as follows:

    bytes: 1            | 2     | addr_len |
    name : addr_type    | port  | address  |

    Various socket implementations can use the address and port however
    they wish. It is intended that address point to a area network location
    and port be a local location in the machine
    '''
    sfmt = '>HH{}H'
    if isinstance(address, str):
        address = address.split('.')
    address = tuple(int(a) for a in address)
    if len(address) == 4:
        atype = socket.AF_INET
    else: raise ValueError(len(address))
    return struct.pack(sfmt.format(len(address)), atype, port,
                       *address)


def tmq_unpack_address_t(packed_addr):
    atype, port = struct.unpack('>HH', packed_addr[:4])
    if atype == socket.AF_INET:
        alen = 4
    else: raise ValueError(atype)
    return ((struct.unpack('>{}H'.format(alen), packed_addr[4:4 + 2 * alen]),
             port), 4 + 2 * alen)


def tmq_pack_addresses(packed_addresses):
    return b''.join(tmq_pack_address_t(*a) for a in packed_addresses)


def tmq_unpack_addresses(packed_addresses):
    addresses = []
    i = 0
    while i < len(packed_addresses):
        addr, l = tmq_unpack_address_t(packed_addresses[i:])
        addresses.append(addr)
        i += l
    return addresses
