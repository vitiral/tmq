from enum import Enum
from operator import xor
import struct

HEADER_BYTES = 4
TMQ_MSG_LEN = 2056

# Flags
TMQ_DONTWAIT        = 0x01

# there can be up to 255 defined socket types
class SOCKET_TYPES(Enum):
    TCP_IP4 = 1
    TCP_IP6 = 2

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

TMQ_PUB             = 0x01      # Publisher type
TMQ_SUB             = 0x02      # Subscriber type
TMQ_CACHE           = 0x04      # call to update jkjthe cache
TMQ_REMOVE          = 0x08      # remove command
TMQ_                = 0x10
TMQ_BROKER          = 0x20      # Broker type
TMQ_BRIDGE          = 0x40      # Bridge type
TMQ_ANY             = 0x80      # pub/sub to ANY or ALL


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
    sfmt = '>BH{}H'
    if isinstance(address, str):
        address = address.split('.')
    address = tuple(int(a) for a in address)
    if len(address) == 4:
        atype = SOCKET_TYPES.TCP_IP4.value
    elif len(address) == 8:
        atype = SOCKET_TYPES.TCP_IP6.value
    else:
        raise ValueError(len(address))
    return struct.pack(sfmt.format(len(address)), atype, port,
                       *address)


def tmq_unpack_address_t(packed_addr):
    atype, port = struct.unpack('>BH', packed_addr[:3])
    if atype == SOCKET_TYPES.TCP_IP4.value:
        alen = 4
    elif atype == SOCKET_TYPES.TCP_IP6.value:
        alen = 8
    else: raise ValueError(atype)
    return ((struct.unpack('>{}H'.format(alen), packed_addr[3:3 + 2 * alen]),
             port), 3 + 2 * alen)


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

if __name__ == '__main__':
    original = 8, (8034342, 3, 4), b'hello'
    packed = tmq_pack(*original)
    unpacked = tmq_unpack(packed)
    print(unpacked)
    assert(original == unpacked)


