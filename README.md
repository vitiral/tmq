# TMQ: Token Message Queue

![Basic Idea](http://i.imgur.com/HUHrNlv.png?1)

The token message queue implements a pub/sub message protocol on top of other
socket types, such as TCP. It is similar to protocols such as ZMQ, except that
it is specifically written to be embeddable. This adds a few limitations, but
still allows for a lot of growth

This is the python implementation of TMQ specifically designed to be run on
[micropython](http://micropython.org/) or any other python distribution. So when
the example above says “embedded” it isn’t kidding! This library can be embedded
in a microcontroller.

> Development to write this library in ANSI C that can be run on microcontrollers is in
> progress, stay tuned


# Example Use
Say you want to do the above example, where you have an embedded device in a
fridge, a web server that listens for fridge data, and another embedded device
that turns on a speaker if there is an alarm state. You might do it something
like this.

**Fridge**
```python
import time
from pickle import dumps
from sensors import read_temp, read_light
from tmq import *

# setup addresses
broker_addr = ‘42.42.0.42’, 9942
myaddr = ‘42.42.0.43’, 9943

# create the socket
context = tmq_init()
socket = tmq_socket(context)
tmq_bind(socket, myaddr)
tmq_broker(socket, broker_addr)

# tell the broker what we will be publishing
tmq_publish(socket, (‘fridge’, ‘temp’))
tmq_publish(socket, (‘fridge’, ‘light’))

# Publish data periodically
while True:
    tmq_send(socket, (‘fridge’, ‘temp’), dumps(read_temp()))
    tmq_send(socket, (‘fridge’, ‘light’), dumps(read_light()))
    sleep(1)
```

Notice how only the broker address had to be known, not the address of the webserver
or anything else.


**Webserver**
```python
import time
from pickle import loads, dumps
from server import update_data  # however you update the webserver
from tmq import *

# setup addresses
broker_addr = ‘42.42.0.42’, 9942
myaddr = ‘42.42.0.44’, 9943

# create the socket
context = tmq_init()
socket = tmq_socket(context)
tmq_bind(socket, myaddr)
tmq_broker(socket, broker_addr)

# tell the broker what we will want to subscribe to
tmq_subscribe(socket, (‘fridge’, ‘temp’))
tmq_subscribe(socket, (‘fridge’, ‘light’))

# tell the broker what we want to publish to
tmq_publish(socket, (‘fridge’, ‘alert’))

# Check to see if we have new data, if we do update the web server and
# do some logic
temp, light = 3, False  # set some initial values
while True:
    new_temp = tmq_recv(socket, (‘fridge’, ‘temp’))
    new_light = tmq_recv(socket, (‘fridge’, ‘light’))
    if new_temp is not None:
        new_temp = loads(new_temp)          # data is in binary form
        update_data({‘temp’: new_temp})     # update the web server
    if new_light is not None:
        new_light = loads(new_light)
        update_data({‘temp’: new_light})

    temp, light = new_temp, new_light

    # if the light is on and the temperature is high, fridge is open
    new_alert = light and temp > 10
    if new_alert != alert:
        update_data({‘alert’: new_alert})
    alert = new_alert

    tmq_send(socket, (‘fridge’, ‘alert’), dumps(alert))  # let everybody know the alert status

    sleep(1)
```

**Speaker Alarm**

You can probably figure out the speaker code for yourself :)


# Internals

Although the above looks a lot like ZeroMQ, the internals are very different.

## Tokens
As you may have guessed, Token Message Queue uses **tokens** for it’s
internals, not strings. That means that the patterns used in the example are
actually being put through the function `tmq_hash` before they are used as
tokens.

> Hashes have the possibility of overlap. Each token is a 32bit integer, so the
> possibility of overlap is very small, especially on embedded applications where
> the intended purpose of the library is for there to be less than a thousand
> tokens (any more than that and embedded devices probably cannot be a **broker**),
> the chance of a collision is low.
>
> Therefore, for large projects that use several thousand tokens, it is
> recommended to run a check on your list of tokens to make sure there are no
> overlaps. This can be done with `tmq.check_tokens` or by using only integers
> for tokens
>
> To give you an idea how unlikely an overlap is, if you have 1,000 tokens the
> probability of overlap is 0.01%. If you have 10,000 tokens, it is 1.16%.
> This is certainly not 0, which is why for large projects you should use
> `check_tokens`

Because TMQ uses tokens instead of string matching, all matching is done via
hash tables and is *extrmely* fast and lightweight. There is no need to store
large bit fields or do any special processing per message.

## Matching

The matching algorithm used by TMQ is similar to ZMQ. Matching is done via
a collection of tokens called a **pattern**. If `A` is a token, then 
`(A, B, C)` is a pattern. Patterns can also have repeating tokens like 
`(A, B, A)`. *Order is important*

When *subscribing* to a pattern, you will receive all patterns whose first
values match your pattern. So if you subscribe to `(A, B)` you will receive
`(A, B)` and also `(A, B, C, D)`

So when *publishing* to a pattern, the data will be sent to all points that
match any part of the pattern from left to right. So if you are publishing to
`(A, B, C, D)` then (for example) subscribers `(A, B, C, D)` and `(A, B)` 
will receive it.

Pattern matching is from left to right only, so subscriber `(B, C)` will not
receive `(A, B, C)`

Subscribing to an empty pattern `()` will result in receiving all TMQ 
communication on the network.

It is illegal to publish to an empty pattern and will throw an exception.

# Goals
TMQ has the following design goals

- ultra lightweight
    - very low memory usage
    - almost no cpu overhead
    - embeddable (with dynamic memory manager like tinymem)
- ultra fast
    - lookup is done only in hash tables
- simple
    - reference implementation is built in pure python in very few lines of code
    - can be used for any protocol
        - only requirement is a socket with standard calls
        - target support is: TCP, uIP, ZigBee, UART, I2C and CAN
    - has limited feature set
- publish / subscribe pattern:
    - publishers send data only to subscribers
    - subscribers receive only what they are subscribed to
- Made of three simple components:
    - Clients publish and subscribe data
    - Brokers direct traffic flow based on token pub/sub
    - Bridges transparently transfer data between different socket types
- Mesh self-healing bridging node network
    - Clients communicate failures to their Broker
    - Brokers keep track of when clients go down and notify other clients to remove them
    - Clients can keep a list of multiple brokers. When one goes down, they go to
        another one (self healing mesh)
    - Bridges also can fail and be taken over by another bridge. Bridges use patterns
        to determine their purpose. The broker determines which bridge to use and
        brings up another with an identical pattern should that bridge go down

## Features / Limitations
- tokens are 32 bit integers, so over 4 billion unique ID’s
- publish / subcribe to up to 256 tokens per packet
- send up to 2048 bytes / message

There are
- no limitations on number of clients or brokers
- no limitation on number of tokens (although too many might break embedded brokers,
    see below)
- no limitation on what you can do with this library. It is the internet of things
    on steroids

## Operations

### Client Nodes
> Created with `tmq_socket(context, TMQ_CLIENT)`
>
> Clients must also bind a listener address with `tmq_bind` and select a broker with
> `tmq_broker`

clients are able to send (publish) data, and also receive (subscribe). In addition,
all clients must be bound to an address as a “listener” to receive instructions
from the broker -- even if they are only publishing data.

Clients mark that they publish/subscribe through `tmq_publish` and `tmq_subscribe`
routines. These communicate to the broker and handles all requirements transparently.

Subscribed data can be gotten from `tmq_recv(socket, pattern)`. This call is non
blocking (returns None if data is not available for pattern). Otherwise it
returns binary data.

Data can be published with `tmq_send(socket, pattern, data)`. It is a good idea
to call `tmq_publish` before hand, as this will allow the publisher to get
subscribers before trying to send data.

### Broker Nodes
> Created with `tmq_socket(context, TMQ_BROKER)`
>
> Must also `tmq_bind` to listen to incomming signals

The broker is what organizes all clients, letting them pub/sub using only tokens.
Basically, it’s what lets you publish to a pattern instead of a list of ip addresses
and ports.

All clients must select the broker to use with the call
`tmq_broker(client_socket, broker_address)`.

### TMQ packets
tmq packets are lightweight, containing only:
- the packet type (1 byte)
- the number of tokens (1 byte)
- the length of the data (2 bytes)
- the tokens (4 * number_of_tokens)
- the data (maximum of 2048 bytes)

### Packing / Unpacking Data
All data is in raw binary format (python **bytes** object). It is up to the
programmer to convert it. Several good libraries exist for this purpose, please
check out:

#### [pickle module](https://docs.python.org/3.4/library/pickle.html)

PROS:
- python standard library
- easy to use
- pretty fast

CONS:
- uses more space/memory/processing power than it probably needs to
- not suitable for cross language communication (i.e. python to C)

#### [struct module](https://docs.python.org/3.4/library/struct.html)

PROS:
- python standard library
- very fast
- very compact data (as compact as possible without compression)
- best option for communication with C -- literally maps to a
    [packed][packing C structs] C struct. 
- Probably good for other languages as well

CONS:
- more difficult to use (but not THAT difficult)
- can handle any data type, but requires a lot of work to handle
    anything but integers, floats, strings, etc.

#### [Message Pack (msgpack)](http://msgpack.org/)

PROS:
- easy to use (pretty much maps to standard python dictionaries)
- very fast
- GREAT for cross language communication (libraries in pretty
    much everything, even embedded C)

CONS:
- Can only handle standard data types (int, float, str/bytes, etc)

#### [JSON](https://docs.python.org/3.4/library/json.html)

PROS:
- easy to use (pretty much maps to standard python dictionaries)
- human readable (plain text ASCII)
- GREAT for cross language communication (libraries in pretty
    much everything, even embedded C)

CONS:
- Not even remotely compact (plain text)
- Kind of slow (?)
- Have to call `encode()` on it, as it creates a string. This
    requires two processing steps and at least twice the memory


[packing C structs]: https://gcc.gnu.org/onlinedocs/gcc/Type-Attributes.html
