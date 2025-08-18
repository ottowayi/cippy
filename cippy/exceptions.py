from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cippy.data_types import DataType
    from cippy.protocols.cip import CIPResponse
    from cippy.protocols.ethernetip import EIPResponse


class CippyError(Exception):
    """
    Base exception for all exceptions raised by cippy
    """


class DataError(CippyError):
    """
    For exceptions raised during binary encoding/decoding of data
    """


class BufferEmptyError(DataError):
    """
    Raised when trying to decode an empty buffer
    """


class ResponseError(CippyError):
    """
    For exceptions raised during handling for responses to requests
    """


class RequestError(CippyError):
    """
    For exceptions raised due to issues building requests or processing of user supplied data
    """


class DriverError(CippyError):
    """
    Generic error type for issues with the driver
    """
