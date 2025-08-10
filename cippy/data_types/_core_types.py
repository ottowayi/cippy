from io import BytesIO
from typing import Any, Literal, Self, Sequence

from ..exceptions import DataError
from ._base import ArrayLenT, Array, ElementaryDataType, _ElementaryDataTypeMeta, array

# TODO: eventually, come back to see if the __class_getitem__ can be moved to a base/meta class
#       couldn't get the type hinting to work with the ElementaryDataType generic


class IntDataType(ElementaryDataType[int], int, metaclass=_ElementaryDataTypeMeta):
    def __class_getitem__(cls, item: ArrayLenT) -> type[Array[Self, ArrayLenT]]:
        return array(cls, item)

    def __format__(self, format_spec):
        if format_spec == "@":
            char_count = 2 + 2 * self.size  # 2 per byte + '0x'
            format_spec = f"#0{char_count}x"
        if format_spec in ("@x", "@X"):
            char_count = self.size * 2
            format_spec = f"0{char_count}{format_spec[1]}"
        if format_spec == "@b":
            bit_count = 8 * self.size
            char_count = 2 + bit_count + (bit_count // 4) - 1
            format_spec = f"#0{char_count}_b"
        return super().__format__(format_spec)


class BoolDataType(ElementaryDataType[bool], int, metaclass=_ElementaryDataTypeMeta):
    def __new__(cls, value: int, *args, **kwargs):
        return super().__new__(cls, True if value else False, *args, **kwargs)

    def __class_getitem__(cls, item: ArrayLenT) -> type[Array[Self, ArrayLenT]]:
        return array(cls, item)

    @classmethod
    def _encode(cls, value: bool, *args, **kwargs) -> Literal[b"\x00", b"\xff"]:
        return b"\xff" if value else b"\x00"

    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        data = cls._stream_read(stream, cls.size)
        return cls(data[0])

    def __repr__(self):
        return f"{self.__class__.__name__}({bool(self)})"


class FloatDataType(ElementaryDataType[float], float, metaclass=_ElementaryDataTypeMeta):
    def __class_getitem__(cls, item: ArrayLenT) -> type[Array[Self, ArrayLenT]]:
        return array(cls, item)


class StringDataType(ElementaryDataType[str], str, metaclass=_ElementaryDataTypeMeta):  # type: ignore
    """
    Base class for any string type
    """

    len_type: type[IntDataType]  #: data type of the string length
    encoding: str = "iso-8859-1"

    def __class_getitem__(cls, item: ArrayLenT) -> type[Array[Self, ArrayLenT]]:
        return array(cls, item)

    @classmethod
    def _encode(cls, value: str, *args, **kwargs) -> bytes:
        return cls.len_type.encode(len(value)) + value.encode(cls.encoding)

    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        str_len: IntDataType = cls.len_type.decode(stream)
        if str_len == 0:
            return cls("")
        str_data = cls._stream_read(stream, str_len)

        return cls(str_data.decode(cls.encoding))

    def __str__(self):
        return str.__str__(self)


class BitArrayType(IntDataType):
    bits: tuple[int, ...]

    def __new__(cls, value: int | Sequence[int], *args, **kwargs):
        try:
            if not isinstance(value, int):
                value = cls._from_bits(value)
        except Exception:
            raise DataError(f"invalid value for {cls}: {value!r}")
        obj = super().__new__(cls, value)  # type: ignore
        return obj

    def __init__(self, *args, **kwargs) -> None:
        self.bits = self._to_bits(self)

    @classmethod
    def _encode(cls, value: int | Sequence[Any], *args, **kwargs) -> bytes:
        if not isinstance(value, int):
            value = cls._from_bits(value)
        return super()._encode(value)

    @classmethod
    def _to_bits(cls, value: int) -> tuple[int, ...]:
        return tuple((value >> idx) & 1 for idx in range(cls.size * 8))

    @classmethod
    def _from_bits(cls, value: Sequence[int]) -> int:
        if len(value) != (8 * cls.size):
            raise DataError(f"{cls.__name__} requires exactly {cls.size * 8} elements, got: {len(value)}")
        _value = 0
        for i, val in enumerate(value):
            if val:
                _value |= 1 << i

        return _value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.bits!r})"
