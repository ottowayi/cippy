"""
Various utility functions.
"""

from dataclasses import dataclass, Field, field
from typing import Literal, dataclass_transform, Generator, Self
from enum import Enum, IntEnum
from typing_extensions import overload


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
    Just an IntEnum with a better repr
    """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class _PredefinedMeta[T](type):
    __value_lookup__: dict[T, str]
    __name_lookup__: dict[str, T]

    def __new__(mcs, name, bases, clsdict, **kwargs):
        cls = super().__new__(mcs, name, bases, clsdict)

        lookup: dict[str, T] = {}
        # first get all the name from the parent classes, child overwrites parent
        for base in reversed(cls.__mro__[:-1]):
            if (_lookup := getattr(base, "__name_lookup__", None)) is not None:
                lookup |= _lookup

        # update with names+values from this class
        lookup |= {k: v for k, v in vars(cls).items() if not k.startswith("_")}

        # make lookup table for reverse lookup {value: name}
        cls.__name_lookup__ = lookup
        cls.__value_lookup__ = {v: k for k, v in lookup.items()}
        return cls

    def get_name(cls, value) -> str | None:
        return cls.__value_lookup__.get(value, None)

    def __contains__(cls, value) -> bool:
        return value in (cls.__value_lookup__ | cls.__name_lookup__)

    def keys(cls):
        return cls.__value_lookup__.keys()

    @overload
    def __getitem__(cls, value: T) -> str: ...
    @overload
    def __getitem__(cls, value: str) -> T: ...
    def __getitem__(cls, value: T | str) -> str | T:
        try:
            return cls.__name_lookup__[value]  # type: ignore - not checking if string b/c values could be STRING types
        except KeyError:
            try:
                return cls.__value_lookup__[value]  # type: ignore
            except KeyError:
                raise KeyError(f"{value!r} is not a name or value in this class") from None

    @overload
    def to_dict(cls, key: Literal["name"]) -> dict[str, T]: ...
    @overload
    def to_dict(cls, key: Literal["value"] = "value") -> dict[T, str]: ...
    def to_dict(cls, key: Literal["name", "value"] = "value") -> dict[T, str] | dict[str, T]:
        if key == "value":
            return {k: v for k, v in cls.__value_lookup__.items()}
        else:
            return {k: v for k, v in cls.__name_lookup__.items()}


class PredefinedValues(metaclass=_PredefinedMeta):
    def __new__(cls, *args, **kwargs):
        raise TypeError("Cannot instantiate a PredefinedValues class")
