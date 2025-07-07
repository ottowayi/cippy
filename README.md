# cippy

A pure Python EtheNet/IP library.

## tl;dr

This library started out as a refactor for a v2 of [pycomm3](https://github.com/ottowayi/pycomm3), which turned
into a full rewrite and redesign of the entire codebase and deserved a new name.

- new, improved data type system
- new protocol implementations for CIP and EtherNet/IP
    - _generic_ protocol implementations
    - decoupled CIP from EtherNet/IP
- separated _connections_ (protocol implementation) from _drivers_ (features built on top of connections)

## TODO

A lot. 