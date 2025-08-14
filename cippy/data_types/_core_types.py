from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal, Self, override, cast
from collections.abc import Sequence

from ..exceptions import DataError
from ._base import ElementaryDataType, _ElementaryDataTypeMeta  # pyright: ignore[reportPrivateUsage]

if TYPE_CHECKING:
    from .numeric import UDINT, UINT, USINT


class IntDataType(ElementaryDataType[int], int, metaclass=_ElementaryDataTypeMeta):
    @override
    def __format__(self, format_spec: str):
        if format_spec == "@":
            char_count = 2 + 2 * self.size  # 2 per byte + '0x'
            format_spec = f"#0{char_count}x"
        if format_spec in ("@x", "@X"):
            char_count = self.size * 2
            format_spec = f"0{char_count}{format_spec[1]}"
        if format_spec in ("@b", "@B"):
            bit_count = 8 * self.size
            char_count = bit_count + (bit_count // 4) - 1
            alt = "#" if format_spec == "@b" else ""
            if alt:
                char_count += 2
            format_spec = f"{alt}0{char_count}_b"
        return super().__format__(format_spec)


class BoolDataType(ElementaryDataType[bool], int, metaclass=_ElementaryDataTypeMeta):
    def __new__(cls, value: int, *args: Any, **kwargs: Any):
        return super().__new__(cls, True if value else False, *args, **kwargs)

    @override
    @classmethod
    def _encode(cls, value: bool, *args: Any, **kwargs: Any) -> Literal[b"\x00", b"\xff"]:
        return b"\xff" if value else b"\x00"

    @override
    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        data = cls._stream_read(stream, cls.size)
        return cls(data[0])

    @override
    def __repr__(self):
        return f"{self.__class__.__name__}({bool(self)})"


class FloatDataType(ElementaryDataType[float], float, metaclass=_ElementaryDataTypeMeta): ...


type StrLenT = "UDINT | UINT | USINT"


class _StringTypeMeta(_ElementaryDataTypeMeta):
    len_type: type[StrLenT]  # pyright: ignore[reportUninitializedInstanceVariable]

    @property
    def size(cls) -> int:
        raise DataError("string types do not have a static size")


class StringDataType(ElementaryDataType[str], str, metaclass=_StringTypeMeta):
    """
    Base class for any string type
    """

    len_type: type[StrLenT]  #: data type of the string length
    encoding: str = "iso-8859-1"

    @override
    @classmethod
    def _encode(cls, value: str, *args: Any, **kwargs: Any) -> bytes:
        return cls.len_type.encode(len(value)) + value.encode(cls.encoding)

    @override
    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        str_len: StrLenT = cls.len_type.decode(stream)
        if str_len == 0:
            return cls("")
        str_data = cls._stream_read(stream, str_len)

        return cls(str_data.decode(cls.encoding))

    @override
    def __str__(self):
        return str.__str__(self)


class BitArrayType(IntDataType):
    bits: tuple[int, ...]

    def __new__(cls, value: int | Sequence[int], *args: Any, **kwargs: Any):
        try:
            if not isinstance(value, int):
                value = cls._from_bits(value)
        except Exception:
            raise DataError(f"invalid value for {cls}: {value!r}")
        obj = super().__new__(cls, value)
        return obj

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.bits = self._to_bits(self)

    @override
    @classmethod
    def _encode(cls, value: int | Sequence[Any], *args: Any, **kwargs: Any) -> bytes:
        if not isinstance(value, int):
            value = cls._from_bits(value)
        return super()._encode(cast(Self, value))

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

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.bits!r})"
