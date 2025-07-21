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

    def __init__(self, msg: str, response=None, *args):
        super().__init__(msg, response, *args)
        self.response = response


class RequestError(CippyError):
    """
    For exceptions raised due to issues building requests or processing of user supplied data
    """


class DriverError(CippyError):
    """
    Generic error type for issues with the driver
    """