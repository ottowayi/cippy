from typing import Callable, Concatenate, Protocol
from functools import wraps


class Connection(Protocol):
    @property
    def connected(self) -> bool: ...


def is_connected[T: Connection, **P, R](func: Callable[Concatenate[T, P], R]) -> Callable[Concatenate[T, P], R]:
    @wraps(func)
    def wrapped(self: T, *args: P.args, **kwargs: P.kwargs) -> R:
        if not self.connected:
            raise ConnectionError("not connected")
        return func(self, *args, **kwargs)

    return wrapped
