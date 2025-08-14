import types
from collections.abc import Mapping, Generator, Sequence
from dataclasses import Field, field, fields, make_dataclass, dataclass
from inspect import isclass
from io import BytesIO
from struct import calcsize, pack, unpack
from types import EllipsisType, GenericAlias, UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    ClassVar,
    Literal,
    Self,
    TypeAliasType,
    TypeVar,
    Union,  # pyright: ignore[reportDeprecated]
    cast,
    dataclass_transform,
    get_args,
    get_origin,
    get_type_hints,
    overload,
    override,
)

from cippy._logging import get_logger
from cippy.exceptions import BufferEmptyError, DataError
from cippy.util import DataclassMeta, PredefinedValues

if TYPE_CHECKING:
    from ._core_types import IntDataType

# pyright: reportPrivateUsage=false

type ElementaryPyType = int | float | bool | str | bytes
type BufferT = BytesIO | bytes | BYTES


def buff_repr(buffer: BufferT) -> str:
    if isinstance(buffer, BytesIO):
        return repr(buffer.getvalue())
    else:
        return repr(buffer)


def get_bytes(buffer: BufferT, length: int) -> bytes:
    if not isinstance(buffer, BytesIO):
        return buffer[:length]

    return buffer.read(length)


def as_stream(buffer: BufferT) -> BytesIO:
    if not isinstance(buffer, BytesIO):
        return BytesIO(buffer)
    return buffer


class _DataTypeMeta(type):
    @override
    def __repr__(cls):
        return cls.__name__


class DataType(metaclass=_DataTypeMeta):
    """
    Base class to represent a CIP data type.
    Instances of a type are only used when defining the
    members of a structure.

    Each type class provides ``encode`` / ``decode`` class methods.
    If overriding them, they must catch any unhandled exception
    and raise a :class:`DataError` from it. For ``decode``, ``BufferEmptyError``
    should be reraised immediately without modification.
    The buffer empty error is needed for decoding arrays of
    unknown length.  Typically, for custom types, overriding the
    private ``_encode``/``_decode`` methods are sufficient. The private
    methods do not need to do any exception handling if using the
    base public methods.  For ``_decode`` use the private ``_stream_read``
    method instead of ``stream.read``, so that ``BufferEmptyError`` exceptions are
    raised appropriately.
    """

    __encoded_value__: bytes = b""
    size: ClassVar[int] = 0
    __log = get_logger(__qualname__)

    def __new__(cls, *args: Any, **kwargs: Any):
        if super().__new__ is object.__new__:
            return super().__new__(cls)
        return super().__new__(cls, *args, **kwargs)

    def __bytes__(self) -> bytes:
        return self.__class__.encode(self)

    @classmethod
    def encode(cls: type[Self], value: Self, *args: Any, **kwargs: Any) -> bytes:
        """
        Serializes a Python object ``value`` to ``bytes``.

        .. note::
            Any subclass overriding this method must catch any exception and re-raise a :class:`DataError`
        """
        try:
            return cls._encode(value, *args, **kwargs)
        except Exception as err:
            raise DataError(f"Error packing {value!r} as {cls.__name__}") from err

    @classmethod
    def _encode(cls: type[Self], value: Self, *args: Any, **kwargs: Any) -> bytes:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError

    @classmethod
    def decode(cls, buffer: BufferT) -> Self:
        """
        Deserializes a Python object from the ``buffer`` of ``bytes``

        .. note::
            Any subclass overriding this method must catch any exception and re-raise as a :class:`DataError`.
            Except ``BufferEmptyErrors`` they must be re-raised as such, array decoding relies on this.
        """
        try:
            stream = as_stream(buffer)
            value = cls._decode(stream)
            if isinstance(buffer, bytes) and (leftover := stream.read()):
                cls.__log.debug(f"leftover data decoding {cls.__name__}: {leftover!r}")
            return value
        except (BufferEmptyError, DataError):
            raise
        except Exception as err:
            raise DataError(f"Error unpacking {buff_repr(buffer)} as {cls.__name__}") from err

    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError

    @classmethod
    def _stream_read(cls, stream: BytesIO, size: "int | IntDataType") -> bytes:
        """
        Reads `size` bytes from `stream`.
        Raises `BufferEmptyError` if stream returns no data.
        """
        if not (data := stream.read(size)):
            raise BufferEmptyError()
        return data

    @classmethod
    def _stream_peek(cls, stream: BytesIO, size: "int | IntDataType") -> bytes:
        return stream.getvalue()[stream.tell() : stream.tell() + size]

    def __rich__(self) -> str:
        return self.__repr__()


class _ElementaryDataTypeMeta(_DataTypeMeta):
    def __new__[T: ElementaryPyType](
        mcs, name: str, bases: "tuple[type[ElementaryDataType[T]], ...]", classdict: dict[str, Any]
    ):
        _klass = super().__new__(mcs, name, bases, classdict)
        klass = cast("type[ElementaryDataType[T]]", _klass)
        if cls_args := get_args(klass.__orig_bases__[0]):  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            klass._base_type = cls_args[0]  # pyright: ignore[reportGeneralTypeIssues]

        if klass._format and not klass.size:
            klass.size = calcsize(klass._format)

        if klass.code:
            klass._codes[klass.code] = klass  # pyright: ignore[reportArgumentType]

        return klass


class ElementaryDataType[T: ElementaryPyType](DataType, metaclass=_ElementaryDataTypeMeta):
    """
    Type that represents a single primitive value in CIP.
    """

    code: ClassVar[int] = 0x00  #: CIP data type identifier
    size: ClassVar[int] = 0  #: size of type in bytes
    _format: ClassVar[str] = ""
    _base_type: type[T]  # pyright: ignore[reportUninitializedInstanceVariable] - set by metaclass

    # keeps track of all subclasses using the cip type code
    _codes: ClassVar[dict[int, type[ElementaryPyType]]] = {}

    def __new__(cls: type[Self], value: T | Self, *args: Any, **kwargs: Any):
        try:
            obj = super().__new__(cls, value, *args, **kwargs)
        except Exception as err:
            raise DataError(f"invalid value for {cls}: {value!r}") from err

        # encode at the same time we create the object, removes the need for validation
        # since if it can be encoded, it's valid.
        obj.__encoded_value__ = cls.encode(obj, *args, **kwargs)
        return obj

    @override
    def __bytes__(self) -> bytes:
        return self.__encoded_value__

    @override
    @classmethod
    def encode(cls, value: Self | T, *args: Any, **kwargs: Any) -> bytes:
        return super().encode(cast(Self, value), *args, **kwargs)

    @override
    @classmethod
    def _encode(cls, value: Self, *args: Any, **kwargs: Any) -> bytes:
        return pack(cls._format, value)

    @override
    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        data = cls._stream_read(stream, cls.size)
        return cls(unpack(cls._format, data)[0])

    @override
    def __repr__(self):
        return f"{self.__class__.__name__}({self._base_type.__repr__(self)})"  # noqa # type: ignore

    @override
    def __str__(self):
        return self._base_type.__repr__(self)  # type: ignore


def _default_len_ref_encode(value: "Array[DataType, ArrayLenT]") -> int:
    return len(value)


def _default_len_ref_decode(value: int) -> int:
    return value


@dataclass
class LenRef:
    name: str
    encode_func: "Callable[[Array[DataType, ArrayLenT]], int]"
    decode_func: "Callable[[int], int]"


@dataclass
class SizeRef:
    name: str = field(init=False)
    encode_func: "Callable[[int], int]"
    decode_func: "Callable[[int], int]"


@dataclass
class ConditionalOn:
    name: str
    encode_func: "Callable[[DataType], bool]"
    decode_func: "Callable[[DataType], bool]"


def _process_typehint(typ: Any, _field: Field[type[DataType]]) -> type[DataType]:
    if isclass(typ) and issubclass(typ, DataType):
        return typ

    field_type = None
    origin = get_origin(typ)
    if origin is Annotated:
        _type, *extra = get_args(typ)
        _type_origin = get_origin(_type)
        if isclass(_type_origin) and issubclass(_type_origin, Array):
            element_type, ary_len = get_args(_type)
            if get_origin(element_type) is type:
                element_type, *_ = get_args(element_type)
            if not isclass(element_type) or not issubclass(element_type, DataType):
                raise DataError("Annotated array types must have a type[DataType] for the element type (1st) arg")  # fmt: skip
            if ary_len is int:
                _ary_len = next(iter(extra), None)
                if not isinstance(_ary_len, int):
                    raise DataError("Annotated arrays using Array[*, int] must provide an int for the next annotated arg")  # fmt: skip
                ary_len = _ary_len
            field_type = array(element_type, ary_len)
        else:
            if not isclass(_type) or not issubclass(_type, DataType):
                raise DataError(f"Annotated types must provide a DataType for the first arg: {_field.name}")
            field_type = _type

    elif isclass(origin) and issubclass(origin, Array):
        # handles 'x: ArrayType[y, z]' case
        field_type = array(*get_args(typ))

    return cast(type[DataType], field_type)


def _process_fields(cls: "type[Struct]") -> None:
    _fields = fields(cls)  # noqa
    _type_hints = get_type_hints(cls, include_extras=True)
    cls.__struct_dataclass_fields__ = {}
    cls.__struct_members__ = {}
    cls.__struct_attributes__ = {}
    cls.__struct_array_length_sources__ = {}
    cls.__struct_conditional_attributes__ = {}
    cls.__struct_size_ref__ = None

    for _field in _fields:
        cls.__struct_dataclass_fields__[_field.name] = _field
        typ = _type_hints.get(_field.name)
        metadata = _field.metadata or {}

        if isclass(typ) and issubclass(typ, DataType):
            field_type = typ
        elif isinstance(typ, TypeAliasType):
            field_type = _process_typehint(typ.__value__, _field)
        elif (origin := get_origin(typ)) is not None:
            if origin in (UnionType, Union):  # pyright: ignore[reportDeprecated]
                _type, *_ = get_args(typ)
            else:
                _type = typ
            field_type = _process_typehint(_type, _field)
        else:
            raise DataError(f"Unsupported annotation for struct field: {_field.name}")

        if field_type is None:  # pyright: ignore[reportUnnecessaryComparison]
            raise DataError(f"Failed to determine type (unsupported annotation) for field: {_field.name}")
        cls.__struct_members__[_field.name] = field_type
        if not metadata.get("reserved"):
            cls.__struct_attributes__[_field.name] = field_type
        if len_ref := metadata.get("len_ref"):
            if not issubclass(field_type, (Array, BYTES)):
                raise DataError(f"Fields with 'len_ref' must be Arrays: {_field.name}")
            if len_ref.name not in cls.__struct_members__:
                raise DataError(f"Invalid 'len_ref', {len_ref.name} is not a previous member of the struct")
            cls.__struct_array_length_sources__[_field.name] = len_ref
        if size_ref := metadata.get("size_ref"):
            if cls.__struct_size_ref__ is not None:
                raise DataError(f"'size_ref' already defined for struct field: {cls.__struct_size_ref__.name}")
            size_ref.name = _field.name
            cls.__struct_size_ref__ = size_ref
        if conditional_on := metadata.get("conditional_on"):
            if _field.default is not None:
                raise DataError("'conditional_on' fields must provide a default of None")
            cls.__struct_conditional_attributes__[_field.name] = conditional_on


def _default_ref_callable(value: DataType | int) -> int:
    return value  # type: ignore


def _default_conditional_callable(value: DataType | int) -> bool:
    """
    typically used for status codes, so 0 is True and anything else is False
    """
    return value == 0


@overload  # if a default is provided
def attr[T: DataType](
    *,
    default: T,
    init: Literal[True] = True,
    reserved: Literal[False] = False,
    len_ref: LenRef | str | None = None,
    size_ref: SizeRef | bool | str = False,
    conditional_on: ConditionalOn | str | None = None,
    fmt: str | None = None,
    **kwargs: Any,
) -> T: ...
@overload
def attr[T: DataType](
    *,
    default: DataType | None = None,
    reserved: Literal[True] = True,
    init: Literal[False] = False,
    len_ref: LenRef | str | None = None,
    size_ref: SizeRef | bool | str = False,
    conditional_on: ConditionalOn | str | None = None,
    fmt: str | None = None,
    **kwargs: Any,
) -> Any: ...
def attr[T: DataType](
    *,
    default: T | None = None,
    init: bool = True,
    reserved: bool = False,
    len_ref: LenRef | str | None = None,
    size_ref: SizeRef | bool | str = False,
    conditional_on: ConditionalOn | str | None = None,
    fmt: str | None = None,
    **kwargs: Any,
) -> Any | T:
    """
    Customize behavior of struct attributes (and their underlying dataclass fields)

    default: Default value for the attribute when creating the object, will be overwritten with decoded value when
             instance created using decode(). `None` is not a valid default value for fields, unlike in regular dataclasses.
             `None` means the attribute must be provided when creating the object.

    init: Whether the attribute can be provided when creating the struct. If False, then the attribute
          will not be set on the instance automatically and must be done manually in __post_init__.
          Value will be overwritten with decoded value after instance is created using decode()
    reserved: Whether the attribute is reserved. If True, the attribute will not be _user facing_ and implies `init=False`.
    len_ref: Used forArray attributes whose length is determined by another attribute and used when decoding the
             struct whole. The attribute should be type hinted as `Array[...]` as well. This parameter must be
             the name of the length attribute or a tuple of the name, a decode function, and an encoded function.
             These functions are 1-arg callables that, for the decode function, receive the value of the length attribute
             and return an int of the array length to decode; and for the encode function, receives array
             and return an int of what the length field should be encoded as.
             The length attribute must be defined before the array as well, since it needs to be decoded before the array can be.
    size_ref: Indicates the field contains the size (byte count) for all the fields following it. Only one field can
              be a `size_ref` and cannot be used with `len_ref`.  The field can either be `True` or a 1-arg callable
              that accepts the size as an int for the following fields and returns an int.
    """
    if (size_ref or len_ref) and reserved:
        raise DataError("Cannot specify both reserved=True and size_ref/len_ref")
    if size_ref and len_ref:
        raise DataError("Cannot specify both size_ref and len_ref")
    if size_ref:
        init = False
    if reserved:
        init = False
        if default is None:
            raise DataError("Cannot specify `reserved` without a `default`")
    field_kwargs: dict[str, Any] = dict(init=init, metadata={"reserved": reserved})
    if default is not None:
        field_kwargs["default"] = default
    if len_ref is not None and isinstance(len_ref, str):
        len_ref = LenRef(len_ref, _default_len_ref_encode, _default_len_ref_decode)
    field_kwargs["metadata"]["len_ref"] = len_ref
    if size_ref and isinstance(size_ref, bool):
        size_ref = SizeRef(_default_ref_callable, _default_ref_callable)
    field_kwargs["metadata"]["size_ref"] = size_ref
    if conditional_on is not None:
        field_kwargs["default"] = default
        if isinstance(conditional_on, str):
            conditional_on = ConditionalOn(conditional_on, _default_conditional_callable, _default_conditional_callable)
    field_kwargs["metadata"]["conditional_on"] = conditional_on
    if fmt is not None:
        field_kwargs["metadata"]["fmt"] = fmt

    return field(**field_kwargs, **kwargs)


type StructValuesType = dict[str, DataType] | Sequence[DataType]

# Types that the Array length may be
type ArrayLenT = None | type[ElementaryDataType[int]] | int | EllipsisType


@dataclass_transform(field_specifiers=(attr,))
class _StructMeta(DataclassMeta, _DataTypeMeta):  # pyright: ignore[reportUnsafeMultipleInheritance]
    __struct_members__: dict[str, type[DataType]]
    __struct_attributes__: dict[str, type[DataType]]
    __struct_dataclass_fields__: dict[str, Field[DataType]]
    __struct_array_length_sources__: dict[str, LenRef]
    __struct_conditional_attributes__: dict[str, ConditionalOn]
    __struct_size_ref__: SizeRef | None

    __parent_struct__: "tuple[Struct, str] | None"
    __parent_array__: "tuple[Array[DataType, ArrayLenT], int] | None"
    __encoded_fields__: dict[str, bytes]
    __initialized__: bool

    def __new__(mcs, name: str, bases: tuple["type[Struct]", ...], cls_dict: dict[str, Any]):
        _repr = True
        if any(getattr(b, "__field_descriptions__", None) for b in bases) or cls_dict.get("__field_descriptions__"):
            _repr = False
        cls = cast("type[Struct]", super().__new__(mcs, name, bases, cls_dict, repr=_repr))
        _process_fields(cls)
        return cls

    @property
    def size(cls) -> int:
        return sum(sz for typ in cls.__struct_members__.values() if (sz := typ.size) != -1)


@dataclass_transform(field_specifiers=(attr,))
class Struct(DataType, metaclass=_StructMeta):
    """
    Base type for a structure
    """

    # -- Set by metaclass, for doing cool shit automatically --
    #: map of all members inside the struct and their types
    __struct_members__: ClassVar[dict[str, type[DataType]]]
    #: mapping of _user_ members of the struct to their type,
    #: excluding reserved or private members not meant for users to interact with
    __struct_attributes__: ClassVar[dict[str, type[DataType]]]
    #: map of field names to dataclass Field objects, to avoid having to call fields() all the time
    __struct_dataclass_fields__: ClassVar[dict[str, Field[DataType]]]
    #: map of array field names to the field name that is the source of the length of the array
    __struct_array_length_sources__: ClassVar[dict[str, LenRef]]
    __struct_size_ref__: ClassVar[SizeRef | None]
    __struct_conditional_attributes__: ClassVar[dict[str, ConditionalOn]]
    #: map of field names to field values and associated descriptions, these
    __field_descriptions__: ClassVar[dict[str, dict[DataType | int | None, str] | type[PredefinedValues]]] = {}

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        _len_ref_fields = {v.name: k for k, v in self.__struct_array_length_sources__.items()}
        for member, typ in self.__struct_members__.items():
            if issubclass(typ, (Struct, Array)):
                getattr(self, member).__parent_struct__ = (self, member)
            if self.__struct_size_ref__ and member == self.__struct_size_ref__.name:
                continue
            value = getattr(self, member, None)
            if value is None:
                if member in self.__struct_conditional_attributes__:
                    continue
                if member in _len_ref_fields:
                    _array_name = _len_ref_fields[member]
                    _len_ref = self.__struct_array_length_sources__[_array_name]
                    _array_val = getattr(self, _array_name)
                    value = _len_ref.encode_func(_array_val)
                else:
                    raise DataError(f"{member!r} is not conditional or a array length reference but is None")
            if not isinstance(value, typ):
                try:
                    if issubclass(typ, Struct):
                        value = typ(**cast(Mapping[str, Any], value))
                    else:
                        value = typ(value)  # pyright: ignore[reportArgumentType, reportUnknownVariableType]
                except Exception as err:
                    raise DataError(f"Type conversion error for attribute {member!r}") from err
                else:
                    setattr(self, member, value)
            value = cast(DataType, value)
            if member not in self.__encoded_fields__:
                try:
                    if conditional_on := self.__struct_conditional_attributes__.get(member):
                        val = bytes(value) if conditional_on.encode_func(getattr(self, conditional_on.name)) else b""
                    else:
                        val = bytes(value)

                    self.__encoded_fields__[member] = bytes(val)
                except Exception as err:
                    raise DataError(f"Error encoding attribute {member!r}") from err

        self.__initialized__: bool = True
        self._update_size_ref()

    def __new__(cls, *args: Any, **kwargs: Any):
        self = super().__new__(cls)
        self.__parent_struct__ = None
        self.__parent_array__ = None
        self.__encoded_fields__ = {}
        self.__initialized__ = False
        return self

    @override
    def __setattr__(self, key: str, value: Any):
        if key.startswith("__") and key.endswith("__"):
            return super().__setattr__(key, value)

        if key not in self.__class__.__struct_members__:
            raise AttributeError(f"{key!r} is not an attribute of struct {self.__class__.__name__}")
        typ = self.__class__.__struct_members__[key]
        if conditional_on := self.__struct_conditional_attributes__.get(key):
            con_on = getattr(self, conditional_on.name)
            if value is not None and not conditional_on.encode_func(con_on):
                raise DataError(
                    f"Cannot set conditional attribute {key!r} because {conditional_on.name!r} indicates attribute is not present"
                )
        if value is not None and not isinstance(value, typ):
            try:
                if issubclass(typ, Struct):
                    value = typ(**cast(Mapping[str, Any], value))
                else:
                    value = typ(value)
            except Exception as err:
                raise DataError(f"Type conversion error for attribute {key!r}") from err
        value = cast(DataType, value)
        try:
            if len_ref := self.__struct_array_length_sources__.get(key):
                value = cast(Array[DataType, ArrayLenT], value)
                setattr(self, len_ref.name, len_ref.encode_func(value))
        except Exception as err:
            raise DataError(f"Error updating length attribute for array attribute {key!r}") from err

        try:
            # if conditional and None, encode as empty string
            self.__encoded_fields__[key] = bytes(value) if value is not None else b""
        except Exception as err:
            raise DataError(f"Error encoding attribute {key!r}") from err
        super().__setattr__(key, value)

        if issubclass(typ, (Struct, Array)):
            value.__parent_struct__ = (self, key)

        if self.__parent_struct__ is not None:
            parent, my_name = self.__parent_struct__
            parent.__setattr__(my_name, self)

        if self.__parent_array__ is not None:
            parent, my_index = self.__parent_array__
            parent._encoded_array[my_index] = bytes(self)  # noqa

        if self.__struct_size_ref__ is not None and key != self.__struct_size_ref__.name:
            self._update_size_ref()

    def _update_size_ref(self) -> None:
        if self.__struct_size_ref__ is None or not self.__initialized__:
            return
        ref = self.__struct_size_ref__
        member_list = list(self.__struct_members__)
        following_members = member_list[member_list.index(ref.name) + 1 :]
        new_size = ref.encode_func(sum(len(self.__encoded_fields__[m]) for m in following_members))
        self.__setattr__(ref.name, new_size)

    def __iter__(self) -> Generator[tuple[str, DataType], None, None]:
        yield from ((m, self[m]) for m in self.__struct_members__)

    def __getitem__(self, item: str) -> Self:
        if item not in self.__class__.__struct_members__:
            raise DataError(f"Invalid member name: {item}")

        return getattr(self, item)

    def __setitem__(self, item: str, value: Any) -> None:
        if item not in self.__class__.__struct_members__:
            raise DataError(f"Invalid member name: {item}")

        setattr(self, item, value)

    def keys(self):
        return self.__class__.__struct_members__.keys()

    @override
    def __bytes__(self: Self) -> bytes:
        return self.__class__.encode(self)

    @override
    @classmethod
    def _encode(cls: type[Self], value: Self, *args: Any, **kwargs: Any) -> bytes:
        for member in cls.__struct_members__:
            if conditional_on := cls.__struct_conditional_attributes__.get(member):
                ref_value = getattr(value, conditional_on.name)
                member_value = value.__encoded_fields__[member]
                if conditional_on.encode_func(ref_value) and not member_value:
                    raise DataError(f"conditional attribute {member!r} missing based on {conditional_on.name!r} value of {member_value}")  # fmt: skip
        return b"".join(value.__encoded_fields__[attr_name] for attr_name in cls.__struct_members__)

    @override
    @classmethod
    def _decode(cls: type[Self], stream: BytesIO) -> Self:
        values: dict[str, DataType] = {}
        for name, typ in cls.__struct_members__.items():
            try:
                if len_ref := cls.__struct_array_length_sources__.get(name):
                    typ = cast(type[Array[DataType, int]], typ)
                    val = cast("IntDataType", values[len_ref.name])
                    length = len_ref.decode_func(val)
                    if typ is BYTES:
                        _array = BYTES[length]
                    else:
                        _array = array(typ.element_type, length)
                    values[name] = _array.decode(stream)
                elif conditional_on := cls.__struct_conditional_attributes__.get(name):
                    if conditional_on.decode_func(values[conditional_on.name]):
                        values[name] = typ.decode(stream)
                    else:
                        values[name] = cast(DataType, cls.__struct_dataclass_fields__[name].default)
                else:
                    values[name] = typ.decode(stream)
            except BufferEmptyError:
                raise
            except Exception as err:
                raise DataError(f"Error decoding attribute {name!r}, decoded so far: {values}") from err

        post_init_vars = {name: val for name, val in values.items() if not cls.__struct_dataclass_fields__[name].init}
        init_vars = {k: v for k, v in values.items() if k not in post_init_vars}
        instance = cls(**init_vars)
        for name, val in post_init_vars.items():
            setattr(instance, name, val)
        return instance

    @classmethod
    def create[T: DataType](
        cls,
        name: str,
        members: Sequence[tuple[str, type[T]]] | Sequence[tuple[str, type[T], Field[T]]],
    ) -> type["Struct"]:
        _fields: list[tuple[str, type[T], Field[T] | None]] = []
        member: tuple[str, type[T]] | tuple[str, type[T], Field[T]]
        for i, member in enumerate(members):
            if len(member) == 2:
                _name, typ = member
                _field = None
            else:
                _name, typ, _field = member

            if not _name:
                _name = f"_reserved_attr{i}_"
                if _field is None:
                    _field = attr(reserved=True)
                else:
                    _field.metadata = types.MappingProxyType({**(_field.metadata or {}), "reserved": True})

            _fields.append((_name, typ, _field))

        struct_class = cast(type[Struct], make_dataclass(cls_name=name, fields=_fields, bases=(cls,)))

        return struct_class

    def __get_description__(self, field_name: str) -> str | None:
        if field_name not in self.__field_descriptions__:
            return None
        return self.__field_descriptions__[field_name].get(getattr(self, field_name))  # pyright: ignore[reportUnknownMemberType]

    def __field_reprs__(self):
        for name in self.__struct_members__:
            value = getattr(self, name)
            desc = self.__get_description__(name)
            if (fmt := self.__dataclass_fields__[name].metadata.get("fmt")) is not None:
                str_value = format(value, fmt)
            else:
                str_value = repr(value)
            if desc:
                yield f"{name}: {desc!r} = {str_value}"
            else:
                yield f"{name}={str_value}"

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(self.__field_reprs__())})"

    def __rich_console__(self, console, options):  # type: ignore
        yield self.__class__.__name__
        yield from self.__field_reprs__()


class _ArrayMeta(_DataTypeMeta):
    element_type: type[DataType]  # pyright: ignore[reportUninitializedInstanceVariable]
    length: ArrayLenT  # pyright: ignore[reportUninitializedInstanceVariable]

    def __new__(mcs, name: str, bases: "tuple[type[Array[DataType, ArrayLenT]], ...]", classdict: dict[str, Any]):
        cls = cast("type[Array[DataType, ArrayLenT]]", super().__new__(mcs, name, bases, classdict))
        return cls

    @override
    def __repr__(cls) -> str:
        if cls is Array:
            return Array.__name__
        if cls.length in (Ellipsis, None):
            return f"{cls.element_type}[...]"

        return f"{cls.element_type}[{cls.length!r}]"

    @override
    def __hash__(cls):
        return hash(type(cls))

    @property
    def size(cls) -> int:
        if (
            cls.length in {None, Ellipsis}  # fmt: skip
            or (isclass(cls.length) and issubclass(cls.length, DataType))  # pyright: ignore[reportUnnecessaryIsInstance]
        ):
            raise DataError("cannot determine dynamic array sizes before instantiation")
        else:
            return cast(int, cls.length) * cls.element_type.size

    @override
    def __eq__(self, other: Any) -> bool:
        try:
            return self.element_type == other.element_type and self.length == other.length
        except Exception:
            return False


# keep a cache of all array types created so each type is only created once
__ARRAY_TYPE_CACHE__: dict[tuple[type[DataType], ArrayLenT], type["Array[DataType, ArrayLenT]"]] = {}


def array[TElem: DataType, TLen: ArrayLenT](element_type: type[TElem], length: TLen) -> type["Array[TElem, TLen]"]:
    """
    Creates an array type of `length` elements of `element_type`, not for use with `BYTES` type
    """
    _type: type[TElem] = element_type
    _len: TLen = length
    if _len is None:
        _len = ...  # type: ignore

    _key = (_type, _len)
    if _key not in __ARRAY_TYPE_CACHE__:
        klass = cast(
            type[Array[TElem, TLen]], type(f"{_type.__name__}Array", (Array,), dict(element_type=_type, length=_len))
        )
        __ARRAY_TYPE_CACHE__[(_type, _len)] = klass  # type: ignore

    return cast(type[Array[TElem, TLen]], __ARRAY_TYPE_CACHE__[_key])

    # return Array


class Array[TElem: DataType, TLen: ArrayLenT](DataType, metaclass=_ArrayMeta):
    """
    Base type for an array
    """

    element_type: type[TElem]
    length: TLen

    def __init__(self: Self, value: Sequence[Any]) -> None:
        self.__parent_struct__: tuple[Struct, str] | None = None
        if isinstance(self.length, int):
            try:
                val_len = len(value)
            except Exception as err:
                raise DataError("invalid value for array, must support len()") from err
            else:
                if val_len != self.length:
                    raise DataError(f"Array length error: expected {self.length} items, received {len(value)}")

        self._array: list[TElem] = [self._convert_element(v) for v in value]
        if issubclass(self.element_type, Struct):
            for i, obj in enumerate(self._array):
                obj.__parent_array__ = (self, i)  # type: ignore

        self._encoded_array = [bytes(x) for x in self._array]  # type: ignore

    @property
    def size(self) -> int:  # pyright: ignore[reportIncompatibleVariableOverride, reportImplicitOverride]
        if isclass(self.length) and issubclass(self.length, DataType):  # pyright: ignore[reportUnnecessaryIsInstance]
            return self.length.size + len(self._array) * self.element_type.size
        else:
            return len(self._array) * self.element_type.size

    def _convert_element(self, value: Any) -> TElem:
        if not isinstance(value, self.element_type):
            try:
                val: TElem = self.element_type(value)  # type: ignore
            except Exception as err:
                raise DataError("Error converting element:") from err
        else:
            val = cast(TElem, value)
        return val

    def __iter__(self) -> Generator[TElem, None, None]:
        yield from self._array

    def __reversed__(self) -> Generator[TElem, None, None]:
        yield from reversed(self._array)

    @override
    def __hash__(self):
        return hash((self.length, self.element_type, self._array))

    def __contains__(self, item: Any) -> bool:
        return item in self._array

    def __len__(self) -> int:
        return len(self._array)

    @overload
    def __getitem__(self, item: int) -> TElem: ...

    @overload
    def __getitem__(self, item: slice) -> "Array[TElem, int]": ...

    def __getitem__(self, item: slice | int) -> "Array[TElem, int] | TElem":
        if isinstance(item, slice):
            items = self._array[item]
            return cast(Array[TElem, int], array(self.element_type, len(items))(items))
        return self._array[item]

    def __setitem__(self, item: int | slice, value: Any) -> None:
        try:
            if isinstance(item, slice):
                self._array[item] = (self._convert_element(v) for v in value)
                self._encoded_array[item] = (bytes(x) for x in self._array[item])
            else:
                self._array[item] = self._convert_element(value)
                self._encoded_array[item] = bytes(self._array[item])

            if self.__parent_struct__ is not None:
                parent, my_name = self.__parent_struct__
                parent.__setattr__(my_name, self)
        except Exception as err:
            raise DataError("Failed to set item") from err

    @override
    def __bytes__(self) -> bytes:
        return self.__class__.encode(self)

    @override
    def __eq__(self, other: Any) -> bool:
        try:
            return self._array == other._array
        except Exception:
            return False

    @override
    @classmethod
    def _encode(cls, value: Self, *args: Any, **kwargs: Any) -> bytes:
        encoded_elements = b"".join(value._encoded_array)
        if isclass(value.length) and issubclass(value.length, DataType):  # pyright: ignore[reportUnnecessaryIsInstance]
            return bytes(value.length(len(value))) + encoded_elements

        return encoded_elements

    @classmethod
    def _decode_all(cls, stream: BytesIO, *args: Any, **kwargs: Any) -> list[TElem]:
        _array: list[TElem] = []
        while True:
            try:
                typ: type[TElem] = cast(type[TElem], cls.element_type)
                value: TElem = typ.decode(stream, *args, **kwargs)
                _array.append(value)
            except BufferEmptyError:
                break
        return _array

    @override
    @classmethod
    def decode(cls, buffer: BufferT, *args: Any, **kwargs: Any) -> Self:
        try:
            stream = as_stream(buffer)
            if cls.length in {None, Ellipsis}:
                return cls(cls._decode_all(stream, *args, **kwargs))

            if isclass(cls.length) and issubclass(cls.length, ElementaryDataType):  # pyright: ignore[reportUnnecessaryIsInstance]
                _len = cls.length.decode(stream)
            else:
                _len = cls.length
            typ = cast(type[TElem], cls.element_type)
            _val = [typ.decode(stream, *args, **kwargs) for _ in range(cast(int, _len))]

            return cls(_val)
        except Exception as err:
            if isinstance(err, BufferEmptyError):
                raise
            else:
                raise DataError(
                    f"Error unpacking into {cls.element_type}[{cls.length}] from {buff_repr(buffer)}"
                ) from err

    @override
    def __repr__(self):
        return f"{self.__class__!r}({self._array!r})"

    # fmt: off
    @overload
    def __class_getitem__[TE: DataType, TL: ArrayLenT](cls, item: tuple[type[TE], TL]) -> "type[Array[TE, TL]]":  ...
    @overload
    def __class_getitem__(cls, item: tuple[TypeVar, Any]) ->  GenericAlias: ...
    def __class_getitem__[TE: DataType, TL: ArrayLenT](cls, item: tuple[type[TE], TL] | tuple[TypeVar, Any]) -> "type[Array[TE, TL]] | GenericAlias":
    #fmt: on
        element_type, len_type = item
        if (
            isclass(element_type)
            and issubclass(element_type, DataType)  # pyright: ignore[reportUnnecessaryIsInstance]
            and (
                len_type in (None, ...)
                or isinstance(len_type, int)
                or (isclass(len_type) and issubclass(len_type, DataType) and issubclass(len_type, int))
            )
        ):
            _element_type = cast(type[TE], element_type)
            _len_type = cast(TL, len_type)
            return array(_element_type, _len_type)
        return GenericAlias(Array, (element_type, len_type))


__BYTES_TYPE_CACHE__: "dict[tuple[int, type[IntDataType] | None], type[BYTES]]" = {}


class BYTES(ElementaryDataType[bytes], bytes, metaclass=_ElementaryDataTypeMeta):  # type: ignore
    """
    Base type for placeholder bytes, sized to `size`. if `size` is -1, then unlimited

    ignore comment b/c decode() method incompatible w/ bytes.decode(), but it's supposed to be
    b/c we're overriding the bytes behavior to return BYTES not str
    """

    size: ClassVar[int] = -1
    _int_type: "type[IntDataType] | None" = None

    # so this type can pretend to be an array sometimes
    element_type: type["BYTES"]  # set below
    length: None = None

    def __new__(cls, value: bytes | int, *args: Any, **kwargs: Any):
        if isinstance(value, int):
            value = bytes([value])
        if cls.size != -1 and len(value) != cls.size:
            raise DataError(f"expected {cls.size} bytes, got {len(value)}")

        return super().__new__(cls, value, *args, **kwargs)

    def __class_getitem__(cls, item: "int | EllipsisType | type[IntDataType]") -> type["BYTES"]:
        size = item if isinstance(item, int) else -1
        _int_type = item if not isinstance(item, (int, EllipsisType)) else None
        if (_key := (size, _int_type)) not in __BYTES_TYPE_CACHE__:
            klass = type("BYTES", (cls,), {"size": size, "_int_type": _int_type})
            __BYTES_TYPE_CACHE__[_key] = klass
        return __BYTES_TYPE_CACHE__[_key]

    @override
    @classmethod
    def _encode(cls, value: bytes, *args: Any, **kwargs: Any) -> bytes:
        val = value[: cls.size] if cls.size != -1 else value
        if cls._int_type is not None:
            val = bytes(cls._int_type(len(value))) + value
        return val

    @override
    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        if cls._int_type is not None:
            size = cls._int_type.decode(stream)
        else:
            size = cls.size
        if size:
            try:
                data = cls._stream_read(stream, size)
            except BufferEmptyError:
                data = b""
        else:
            data = b""
        return cls(data)

    @override
    def __getitem__(self, item: "int | IntDataType | slice") -> bytes:  # pyright: ignore[reportIncompatibleMethodOverride]
        if isinstance(item, int):
            return super().__getitem__(slice(item, item + 1))

        return super().__getitem__(item)

    @override
    def __repr__(self) -> str:
        if self._int_type is not None:
            size = self._int_type.__name__
        else:
            size = "..." if self.size == -1 else self.size
        return f"{self.__class__.__name__}[{size}]({self})"


BYTES.element_type = BYTES
