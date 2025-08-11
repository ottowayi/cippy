from ast import Str
from dataclasses import Field, dataclass, field, replace
from inspect import isclass
from re import L
from typing import Callable, ClassVar, Final, Literal, Protocol, Sequence, cast, Self, overload, Any

from cippy.data_types import BYTES, UINT, USINT, DataType, Struct, attr
from cippy.exceptions import DataError
from cippy.util import PredefinedValues, StatusEnum

from ._base import SUCCESS, CIPRequest, CIPResponseParser
from .msg_router_services import MessageRouterRequest, MsgRouterResponseParser


@dataclass
class CIPAttribute[T: DataType, TObj: "CIPObject"]:
    #: Attribute ID number
    id: int
    #: Data type of the attribute
    data_type: type[T]
    #: Flag to indicate the attribute is a class attribute if True, False if it is an instance attribute
    class_attr: bool = False

    #: Flag to indicate if this attribute is included in the class get_attributes_all response
    get_all_class: bool = False

    #: Flag to indicate if this attribute is included in the instance get_attributes_all response
    get_all_instance: bool = False

    # set by metaclass
    object: "type[TObj]" = field(init=False)  # object containing the attribute
    name: str = field(init=False)  # attribute name (variable name of CIPObject class var)

    def __post_init__(self):
        if self.class_attr and self.get_all_instance:
            raise ValueError("cannot be class attribute and get_all_instance=True")
        if not self.class_attr and self.get_all_class:
            raise ValueError("cannot be instance attribute and get_all_class=True")

    def __str__(self):
        return f"{self.object.__name__}.{self.name}"

    @overload
    def __get__(self, instance: None, owner: "type[TObj]") -> Self: ...
    @overload
    def __get__(self, instance: TObj, owner: "type[TObj] | None" = None) -> T: ...
    def __get__(self, instance: TObj | None, owner: "type[TObj] | None" = None) -> Self | T:
        if instance is None:
            return self
        else:
            try:
                return instance.__dict__[self.name]
            except KeyError:
                raise AttributeError(self.name) from None

    def __set_name__(self, owner: type[TObj], name: str) -> None:
        self.name = name
        self.object = owner

    def __set__(self, instance: TObj, value):
        if instance.instance and self.class_attr:
            raise DataError(
                f"cannot set class attribute {self.name} on non-class instance of {instance.__class__.__name__}"
            )
        if not instance.instance and not self.class_attr:
            raise DataError(
                f"cannot set instance attribute {self.name} on class instance of {instance.__class__.__name__}"
            )
        if not isinstance(value, self.data_type):
            try:
                if issubclass(self.data_type, Struct):
                    value = self.data_type(**value)
                else:
                    value = self.data_type(value)
            except Exception as err:
                raise DataError("failed converting attribute {self.name} to {self.data_type} from {value!r}") from err
        instance.__dict__[self.name] = value


@dataclass
class _CIPService:
    id: USINT
    name: str
    func: Callable


class _MetaCIPObject(type):
    # keeps track of object classes by class code
    __cip_objects__: ClassVar[dict[int, "type[CIPObject]"]] = {}
    __cip_services__: dict[USINT, _CIPService]
    __cip_attributes__: dict[int, CIPAttribute]
    __cip_instance_attributes__: dict[str, CIPAttribute]
    __cip_class_attributes__: dict[str, CIPAttribute]
    __instance_struct__: type[Struct]
    __class_struct__: type[Struct]
    class_code: int = 0

    def __new__(cls, name, bases, classdict):
        klass = super().__new__(cls, name, bases, classdict)
        # start with new attrs added to this class
        cip_attrs: dict[str, CIPAttribute] = {
            attr_name: attr for attr_name, attr in vars(klass).items() if isinstance(attr, CIPAttribute)
        }
        # then add copies of all parent attrs, excluding overridden ones on this class
        for _class in bases:
            for attr_name, attr in vars(_class).items():
                if isinstance(attr, CIPAttribute) and attr_name not in cip_attrs:
                    new_attr = replace(attr)
                    cip_attrs[attr_name] = new_attr
                    new_attr.__set_name__(klass, attr_name)

        klass.__cip_attributes__ = {}
        klass.__cip_class_attributes__ = {}
        klass.__cip_instance_attributes__ = {}
        for attr_name, attr in cip_attrs.items():
            setattr(klass, attr_name, attr)
            klass.__cip_attributes__[attr.id] = attr
            if attr.class_attr:
                klass.__cip_class_attributes__[attr_name] = attr
            else:
                klass.__cip_instance_attributes__[attr_name] = attr

        klass.__customize_object__()

        klass.__instance_struct__ = Struct.create(
            f"{name}Instance",
            [
                (attr.name, attr.data_type)
                for attr in klass.__cip_instance_attributes__.values()
                if attr.get_all_instance
            ],
        )
        klass.__class_struct__ = Struct.create(
            f"{name}Class",
            [(attr.name, attr.data_type) for attr in klass.__cip_class_attributes__.values() if attr.get_all_class],
        )

        services = {
            _id: _CIPService(_id, name, func.__func__)
            for name, func in vars(klass).items()
            if isinstance(func, classmethod) and (_id := getattr(func.__func__, "__cip_service_id__", None)) is not None
        }

        klass.__cip_services__ = services

        return klass

    def __customize_object__(cls) -> None: ...

    def __repr__(cls):
        return cls.__name__

    def __str__(cls):
        return f"{cls.__name__} ({cls.class_code:#04x})"


def service(id: USINT):
    def _service[T: _MetaCIPObject, **P, R](method: Callable[P, R]) -> Callable[P, R]:
        class Service:
            def __init__(self, method: Callable[P, R]) -> None:
                self.method = cast(Callable[P, R], method)

            def __set_name__(self, owner: T, name: str) -> None:
                if not isinstance(owner, _MetaCIPObject):
                    raise TypeError("services must be subclasses of CIPObject")
                if not isinstance(self.method, classmethod):
                    raise TypeError("services must be classmethods")

                self.method.__func__.__cip_service_id__ = id  # type: ignore

                setattr(owner, name, self.method)

            def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
                return self.method(*args, **kwargs)

        return Service(method)

    return _service


class AttrListItem[T: DataType](Protocol):
    id: UINT
    status: UINT
    data: T | None


class CIPObject(metaclass=_MetaCIPObject):
    """
    Base class for all CIP objects.  Defines services, attributes, and other properties common to all CIP objects.
    """

    class_code: ClassVar[int] = 0

    class Instance(PredefinedValues):
        CLASS = 0  #: The class itself and not an instance
        DEFAULT = 1  #: The first instance of a class, used as the default if not specified

    #: A map of service code, to general and extended status codes and messages
    #: `*` = Applies to any code, used as a fallback if code is not found
    #: `{ service | * : { general_status | * : {ext_status | * : message} } }`
    STATUS_CODES: ClassVar[
        dict[
            Literal["*"] | int,  # service messages apply to or '*' = any service
            dict[
                StatusEnum | int | Literal["*"],  # general status codes or '*' = any status
                dict[  # map of ext status code (or any if '*') to message
                    int | StatusEnum | Literal["*"], str
                ]
                | type[StatusEnum],  # or an enum of all ext statuses
            ],
        ]
    ] = {}

    # --- Reserved class attributes, common to all object classes ---

    #: CIP object specification revision
    object_revision = CIPAttribute(id=1, data_type=UINT, class_attr=True, get_all_class=True)
    #: Maximum instance id for instances of the object
    max_instance = CIPAttribute(id=2, data_type=UINT, class_attr=True, get_all_class=True)
    #: Number of instances of the object
    num_instances = CIPAttribute(id=3, data_type=UINT, class_attr=True, get_all_class=True)
    #: List of attribute ids for optional attributes supported by device
    optional_attrs_list = CIPAttribute(id=4, data_type=UINT[UINT], class_attr=True, get_all_class=True)
    #: List of service codes for optional services supported by device
    optional_service_list = CIPAttribute(id=5, data_type=UINT[UINT], class_attr=True, get_all_class=True)
    #: The attribute id of the last (max) attribute supported by device
    max_class_attr = CIPAttribute(id=6, data_type=UINT, class_attr=True, get_all_class=True)
    #: The instance id of the last (max) instance of the object in the device
    max_instance_attr = CIPAttribute(id=7, data_type=UINT, class_attr=True, get_all_class=True)

    def __init__(self, instance: int | None, **kwargs: dict) -> None:
        self.instance = instance

        for attr_name, attr_value in kwargs.items():
            setattr(self, attr_name, attr_value)

        self.__attributes__ = self.__cip_instance_attributes__ if self.instance else self.__cip_class_attributes__

    def __init_subclass__(cls) -> None:
        cls.__cip_objects__[cls.class_code] = cls

    def dict(self) -> dict[str, DataType]:
        return {a: val for a in self.__attributes__ if (val := getattr(self, a, None)) is not None}

    @service(id=USINT(0x01))
    @classmethod
    def get_attributes_all(cls, instance: int | None = 1) -> CIPRequest[Struct | BYTES]:
        if not instance:
            resp_type = cls.__class_struct__
            instance = 0
        else:
            resp_type = cls.__instance_struct__
        parser: CIPResponseParser[Struct | BYTES] = MsgRouterResponseParser(
            response_type=resp_type, failed_response_type=BYTES
        )
        return CIPRequest(
            message=MessageRouterRequest.build(
                service=cls.get_attributes_all.__cip_service_id__,  # type: ignore
                class_code=cls.class_code,
                instance=instance,
            ),
            response_parser=parser,
        )

    @service(id=USINT(0x0E))
    @classmethod
    def get_attribute_single[T: DataType](
        cls, attribute: CIPAttribute, instance: int | None = 1
    ) -> CIPRequest[T | BYTES]:
        parser: CIPResponseParser[T | BYTES] = MsgRouterResponseParser(
            response_type=attribute.data_type, failed_response_type=BYTES
        )
        return CIPRequest(
            message=MessageRouterRequest.build(
                service=cls.get_attribute_single.__cip_service_id__,  # type: ignore
                class_code=attribute.object.class_code,
                instance=instance or 0,
                attribute=attribute.id,
            ),
            response_parser=parser,
        )

    @service(id=USINT(0x03))
    @classmethod
    def get_attribute_list[T: DataType](
        cls, attributes: Sequence[CIPAttribute], instance: int | None = 1
    ) -> CIPRequest[Struct | BYTES]:
        members: list[
            tuple[str, type[DataType | AttrListItem[T]]] | tuple[str, type[DataType] | AttrListItem[T], Field]
        ] = [("count", UINT, field())]
        for _attr in attributes:
            _GetAttrsListItem = cast(
                type[AttrListItem[T]],
                type(
                    f"{_attr.name}_GetAttrListItem",
                    (Struct,),
                    {
                        "data": attr(conditional_on="status"),
                        "__annotations__": {"id": UINT, "status": UINT, "data": _attr.data_type | None},
                        "__bool__": (lambda self: self.status == SUCCESS),
                    },
                ),
            )

            members.append((_attr.name, _GetAttrsListItem))

        GetAttrListResp = cast(type[Struct], Struct.create(name="GetAttrListResp", members=members))  # pyright: ignore [reportArgumentType]

        parser: CIPResponseParser[Struct | BYTES] = MsgRouterResponseParser(
            response_type=GetAttrListResp, failed_response_type=BYTES
        )
        return CIPRequest(
            message=MessageRouterRequest.build(
                service=cls.get_attribute_list.__cip_service_id__,  # type: ignore
                class_code=cls.class_code,
                instance=instance or 0,
                data=UINT[UINT](a.id for a in attributes),
            ),
            response_parser=parser,
        )

    @classmethod
    def get_status_messages(
        cls,
        service: int,
        status: int,
        ext_status: Sequence[int],
        extra_data: DataType | None = None,
    ) -> tuple[str, str | None]:
        if service in cls.STATUS_CODES:
            obj_svc_statues = cls.STATUS_CODES[service]
        else:
            obj_svc_statues = cls.STATUS_CODES.get("*", {})

        general_status_msg = GENERAL_STATUS_CODES.get(status, "UNKNOWN")
        if status in obj_svc_statues:
            ext_statuses = obj_svc_statues[status]
        else:
            ext_statuses = obj_svc_statues.get("*", {})
        if not ext_status:
            ext_status_msg = None
        else:
            ext_code, *ext_extra = ext_status

            if isinstance(ext_statuses, dict):
                ext_msg = ext_statuses.get(ext_code, ext_statuses.get("*"))
            elif isclass(ext_statuses) and issubclass(ext_statuses, StatusEnum):
                _ext_status: StatusEnum | None = ext_statuses._value2member_map_.get(ext_code)  # type: ignore
                ext_msg = _ext_status.description if _ext_status is not None else None

            else:
                ext_msg = None
            hex_ext_code = f"{ext_code.value:#06x}" if isinstance(ext_code, StatusEnum) else f"{ext_code:#06x}"
            base_ext_msg = f"({hex_ext_code}){f' {ext_msg}' if ext_msg else ''}"

            ext_status_msg_extra = cls._customize_extended_status(status, ext_code, ext_extra, extra_data)
            if ext_status_msg_extra:
                ext_status_msg = f"{base_ext_msg}: {ext_status_msg_extra}"
            elif ext_extra or extra_data:
                ext_status_msg = f"{base_ext_msg}: ext_status_words={ext_extra!r}, extra_data={extra_data!r}"
            else:
                ext_status_msg = base_ext_msg

        return general_status_msg, ext_status_msg

    @classmethod
    def _customize_extended_status(
        cls,
        general_status: int,
        ext_status: int,
        ext_status_extra: Sequence[int],
        extra_data: DataType | None,
    ) -> str | None:
        return None

    def __repr__(self) -> str:
        attrs = [
            (name, val)
            for name in (self.__cip_instance_attributes__ if self.instance else self.__cip_class_attributes__)
            if (val := getattr(self, name, None)) is not None
        ]
        return f"{self.__class__.__name__}({', '.join(f'{n}={v!r}' for n, v in attrs)})"


class GeneralStatusCodes(StatusEnum):
    success = 0x00, "Success"
    connection_failure = 0x01, "Connection failure"
    resource_unavailable = 0x02, "Insufficient resources for object to perform request"
    invalid_parameter_value = 0x03, "Invalid value for request parameter"
    path_error = 0x04, "A syntax error was detected decoding the Request Path"
    destination_unknown = 0x05, "Destination unknown, class unsupported, instance undefined or structure element undefined"  # fmt: skip
    partial_transfer = 0x06, "Only a partial amount of the expected data was transferred"
    connection_lost = 0x07, "Connection lost"
    service_not_supported = 0x08, "Service not supported"
    invalid_attribute = 0x09, "Invalid attribute value"
    attribute_list_error = 0x0A, "An attribute in get/set_attribute_list response has an error status"
    already_in_state = 0x0B, "Object is already in the state/mode being requested"
    object_state_conflict = 0x0C, "Object cannot perform request in its current state/mode"
    object_already_exists = 0x0D, "Instance requesting to be created already exists"
    attribute_not_settable = 0x0E, "Request was to modify an attribute that is not writable"
    privilege_violation = 0x0F, "Permission/privilege check failed"
    device_state_conflict = 0x10, "Device prohibited from executing request due to current state/mode"
    reply_too_large = 0x11, "Reply data too large to send"
    fragmentation_of_primitive = 0x12, "Request would result in fragmentation of a primitive value"
    not_enough_data = 0x13, "Request contained insufficient command data"
    attribute_not_supported = 0x14, "Attribute in request is not supported"
    too_much_data = 0x15, "Request contained more data than expected"
    object_not_exist = 0x16, "Object requested does not exist"
    fragmentation_inactive = 0x17, "Fragmentation sequence for request is not currently active"
    no_stored_attribute_data = 0x18, "Attribute data of the request object was not save prior to this request"
    attribute_store_failed = 0x19, "Attribute data failed to save due to an error"
    request_too_large = 0x1A, "Request was too large to send to destination"
    response_too_large = 0x1B, "Response was too large to send from destination"
    missing_attribute_list = 0x1C, "Request was missing an attribute required by the service"
    invalid_attribute_list = 0x1D, "Request contained an invalid attribute in list of attributes"
    embed_service_error = 0x1E, "Embedded service errored"
    vendor_specific_error = 0x1F, "Vendor specific error"
    invalid_parameter = 0x20, "A parameter in request was invalid"
    media_write_error = 0x21, "Attempted to write or modify data already written in a write-once medium"
    invalid_reply_service = 0x22, "Invalid reply received, reply service code does not match request"
    buffer_overflow = 0x23, "Message received was too large for buffer and was discarded"
    format_error = 0x24, "Format of message is not supported"
    path_key_failure = 0x25, "Key segment in request path does not match destination"
    path_size_invalid = 0x26, "Request path size too large or too small"
    unexpected_attribute = 0x27, "Unexpected attribute in request attribute list"
    invalid_member_id = 0x28, "Member ID in request does not exist for class/instance/attribute"
    member_not_settable = 0x29, "Request was to modify a non-modifiable member"
    dnet_grp2_server_failure = 0x2A, "DeviceNet Group 2 only server general failure"
    unknown_modbus_error = 0x2B, "A Modbus to CIP translator received an unknown Modbus error"

    @classmethod
    def dict(cls) -> dict[int | None, str]:
        d = {x._value_: x.description for x in cls}
        d[None] = "UNKNOWN"
        return d


GENERAL_STATUS_CODES: Final[dict[int, str]] = {s._value_: s.description for s in GeneralStatusCodes}
