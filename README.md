# TMQ -- Token Message Queue

The Token Message Queue is a messaging protocol written in the spirit of ZMQ, but
using tokens instead of string matching.

## Goals
- ultra lightweight
    - very low memory usage
    - almost no cpu overhead
    - embeddable (with dynamic memory manager like tinymem)
- ultra fast
    - lookup is done only in hash tables
- simple
    - reference implementation is built in pure python
    - can be used for any protocol
        - only requirement is a socket with standard calls
        - target support is: TCP, uIP, ZigBee, UART and CAN
    - has limited feature set
- publish / subscribe pattern:
    - publishers send data only to subscribers
    - subscribers receive only what they are subscribed to
- Mesh self-healing bridging node network
    - Clients are the “normal” -- everything acts as a client
    - Brokers keep track of client locations and publishers. Brokers can go down
        and other brokers can take their place
    - Bridges act as a “bridge” between two communication protocols, for instance
        TCP/IP and ZigBee

## Features / Limitations
- tokens are 32 bit integers, so over 4 billion unique ID’s
- publish / subcribe to up to 256 tokens per message or subscriber
    - for example, pub/sub to (tmq_hash(“kitchen”), tmq_hash(“temperature”))
        is 2 tokens.
    - can choose ANY or ALL pattern
- send up to 2048 bytes / message
    - limitation created for embedibility


## Operations

### TMQ packets
tmq packets are lightweight, containing only:
- the packet type (1 byte)
- the number of tokens (1 byte)
- the length of the data (2 bytes)
- the tokens (4 * number_of_tokens)
- the data

