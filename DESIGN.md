
# Ideas
Broker
- standard place to exist is on port 32 or 3232 every 32nd address point (i.e. `192.10.7.32`, `*.64`, etc at port 3232)
    - all clients / brokers can be given the address of one of the brokers, or can scan it themselves (on their local network)
    - brokers always scan for other brokers and keep track of where they are and who the “active” brokers are
    - if an active broker goes down it is removed from the list and a new active broker is added
    - the first active brokers chosen are always the ones with the lowest addresses
    - there is one “master” active broker that will respond to a broadcast to all addresses

- at any point there are up to 3 “active” brokers. These maintain the state of pub/sub
    - clients can talk to any of the 3 brokers
    - clients keep addresses of all active brokers, so if one fails they switch
    - generally brokers tell clients which broker they should use (for load balancing)
        - but clients can ignore this and it doesn’t matter

- when a client issues a pub or sub request, this is handled like a database transaction
    - notes:
        - the state of all data has an incrementing “id” tied to it
        - “database” communication is handled over underlying socket that is used in tmq
            with list of master brokers discovered
    - request path
        - client issues the request to one of the active brokers (using the current id it has stored)
        - the request goes out to all 3 active brokers
        - if all brokers acknowledge the process, it gets stored with an incremented id
        - when the client acknowledges that it received the data, the id is stored next to it in the broker
        - this way all the brokers know how up to date the clients are with the state of pub/sub
            - in the background, all concerning clients are updated as to the new state and their
                id is updated
