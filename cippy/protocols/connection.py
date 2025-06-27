from typing import Protocol
from functools import wraps


class Connection(Protocol):
    @property
    def connected(self) -> bool: ...


def is_connected(func):
    @wraps(func)
    def wrapped(self: Connection, *args, **kwargs):
        if not self.connected:
            raise ConnectionError("not connected")
        return func(self, *args, **kwargs)

    return wrapped
