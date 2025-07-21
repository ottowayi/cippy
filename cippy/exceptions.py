class PycommError(Exception):
    """
    Base exception for all exceptions raised by cippy
    """


class DataError(PycommError):
    """
    For exceptions raised during binary encoding/decoding of data
    """


class BufferEmptyError(DataError):
    """
    Raised when trying to decode an empty buffer
    """


class ResponseError(PycommError):
    """
    For exceptions raised during handling for responses to requests
    """

    def __init__(self, msg: str, response=None, *args):
        super().__init__(msg, response, *args)
        self.response = response


class RequestError(PycommError):
    """
    For exceptions raised due to issues building requests or processing of user supplied data
    """


class DriverError(PycommError):
    """
    Generic error for driver related exceptions
    """
