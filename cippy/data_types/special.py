from ipaddress import IPv4Address
from typing import Any, Self, override

from ._base import Struct
from .numeric import UDINT, UDINT_BE, USINT

__all__ = ("IPAddress", "IPAddress_BE", "Revision")


class IPAddress(UDINT):
    ip: IPv4Address | None = None

    def __new__(cls, value: int, *args: Any, **kwargs: Any) -> Self:
        obj = super().__new__(cls, value, *args, **kwargs)
        try:
            obj.ip = IPv4Address(value)
        except ValueError:
            obj.ip = None

        return obj

    @override
    def __repr__(self) -> str:
        if self.ip is not None:
            return f"{self.__class__.__name__}('{self.ip}')"
        return f"{self.__class__.__name__}({int.__str__(self)}: 'INVALID')"


class IPAddress_BE(UDINT_BE):
    ip: IPv4Address | None = None

    def __new__(cls, value: int, *args: Any, **kwargs: Any) -> Self:
        obj = super().__new__(cls, value, *args, **kwargs)
        try:
            obj.ip = IPv4Address(value)
        except ValueError:
            obj.ip = None
        return obj

    @override
    def __repr__(self) -> str:
        if self.ip is not None:
            return f"{self.__class__.__name__}('{self.ip}')"
        return f"{self.__class__.__name__}({int.__str__(self)}: 'INVALID')"


class Revision(Struct):
    major: USINT
    minor: USINT

    @override
    def __format__(self, format_spec: str) -> str:
        if format_spec == "@":
            return f"{self.major:d}.{self.minor:03}"
        return super().__format__(format_spec)
