"""
Various utility functions.
"""

from dataclasses import dataclass, Field, field
from typing import dataclass_transform, Generator, Self
from enum import Enum, IntEnum


def cycle(stop, start=0) -> Generator[int, None, None]:
    while True:
        yield from range(start, stop)


@dataclass_transform(field_specifiers=(Field, field))
class DataclassMeta(type):
    """
    Metaclass that automatically turns classes into dataclasses, so that any subclasses do not
    also require the dataclass decorator.
    """

    def __new__(mcs, name: str, bases: tuple, cls_dict: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, cls_dict)
        return dataclass(cls, **kwargs)  # type: ignore


class StatusEnum(int, Enum):
    description: str

    def __new__(cls, value: int, description: str = "UNKNOWN") -> Self:
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj

    def __repr__(self):
        return f"{self.value:#04x}: {self.description!r}"


class IntEnumX(IntEnum):
    """
    Just an IntEnum the prints a better repr, and X just is so cool, might rename this whole library to X
    """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"
