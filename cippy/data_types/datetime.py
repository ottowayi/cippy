from typing import ClassVar

from ._base import Struct
from .numeric import DINT, INT, LINT, UDINT, UINT

__all__ = (
    "STIME",
    "DATE",
    "TIME_OF_DAY",
    "DATE_AND_TIME",
    "FTIME",
    "LTIME",
    "ITIME",
    "TIME",
)


class STIME(DINT):
    """
    Synchronous time information
    """

    code: ClassVar[int] = 0xCC  #: 0xCC


class DATE(UINT):
    """
    Date information
    """

    code: ClassVar[int] = 0xCD  #: 0xCD


class TIME_OF_DAY(UDINT):
    """
    Time of day
    """

    code: ClassVar[int] = 0xCE  #: 0xCE


class DATE_AND_TIME(Struct):
    """
    Date and time of day
    """

    code: ClassVar[int] = 0xCF  #: 0xCF

    time: UDINT
    date: UINT


class FTIME(DINT):
    """
    duration - high resolution
    """

    code: ClassVar[int] = 0xD6  #: 0xD6


class LTIME(LINT):
    """
    duration - long
    """

    code: ClassVar[int] = 0xD7  #: 0xD7


class ITIME(INT):
    """
    duration - short
    """

    code: ClassVar[int] = 0xD8  #: 0xD8


class TIME(DINT):
    """
    duration - milliseconds
    """

    code: ClassVar[int] = 0xDB  #: 0xDB
