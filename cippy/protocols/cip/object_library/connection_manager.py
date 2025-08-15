from dataclasses import InitVar, dataclass
from enum import IntEnum
from io import BytesIO
from typing import ClassVar, Self, Any, final
from typing_extensions import override
from collections.abc import Sequence

from cippy._logging import get_logger
from cippy.data_types import (
    BYTES,
    DWORD,
    PADDED_EPATH_LEN,
    PADDED_EPATH_PAD_LEN,
    UDINT,
    UINT,
    USINT,
    WORD,
    Array,
    DataType,
    Struct,
    as_stream,
    attr,
    array,
)
from cippy.util import StatusEnum

from ..cip_object import CIPAttribute, CIPObject, GeneralStatusCodes, StatusCodesType, service
from ..cip_route import CIPRoute
from ..msg_router_services import MessageRouterRequest, MsgRouterResponseParser, message_router_service
from .._base import CIPRequest, CIPResponse


class ForwardOpenRequest(Struct):
    priority_tick_time: USINT
    timeout_ticks: USINT
    o2t_connection_id: UDINT
    t2o_connection_id: UDINT
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    timeout_multiplier: USINT
    _reserved: BYTES[3] | bytes = attr(reserved=True, default=BYTES(b"\x00" * 3), init=False)
    o2t_rpi: UDINT
    o2t_connection_params: WORD
    t2o_rpi: UDINT
    t2o_connection_params: WORD
    transport_type: USINT
    connection_path: PADDED_EPATH_LEN


class LargeForwardOpenRequest(Struct):
    priority_tick_time: USINT
    timeout_ticks: USINT
    o2t_connection_id: UDINT
    t2o_connection_id: UDINT
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    timeout_multiplier: USINT
    _reserved: BYTES[3] | bytes = attr(reserved=True, default=BYTES(b"\x00" * 3), init=False)
    o2t_rpi: UDINT
    o2t_connection_params: DWORD
    t2o_rpi: UDINT
    t2o_connection_params: DWORD
    transport_type: USINT
    connection_path: PADDED_EPATH_LEN


class ForwardOpenResponse(Struct):
    o2t_connection_id: UDINT
    t2o_connection_id: UDINT
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    o2t_api: UDINT
    t2o_api: UDINT
    application_reply_size: USINT = attr(init=False)
    _reserved: USINT = attr(reserved=True, default=USINT(0))
    application_reply: BYTES = attr(len_ref="application_reply_size")


class ConnectionPriority(IntEnum):
    _MASK = 0b_0000_1100_0000_0000
    low = 0b_0000_0000_0000_0000
    high = 0b_0000_0100_0000_0000
    scheduled = 0b_0000_1000_0000_0000
    urgent = 0b_0000_1100_0000_0000


class ConnectionType(IntEnum):
    _MASK = 0b_0110_0000_0000_0000
    null = 0b_0000_0000_0000_0000
    multicast = 0b_0010_0000_0000_0000
    point_to_point = 0b_0100_0000_0000_0000


class ConnectionTimeoutMultiplier(IntEnum):
    x4 = 0
    x8 = 1
    x16 = 2
    x32 = 3
    x64 = 4
    x128 = 5
    x256 = 6
    x512 = 7


class ProductionTrigger(IntEnum):
    _MASK = 0b_0111_0000
    cyclic = 0b_0000_0000
    change_of_state = 0b_0001_0000
    application_object = 0b_0010_0000
    # 3-7 reserved by CIP


class ForwardOpenFailedResponse(Struct):
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    remaining_path_size: USINT
    _reserved: USINT = attr(reserved=True, default=USINT(0))


class ForwardCloseRequest(Struct):
    priority_tick_time: USINT
    timeout_ticks: USINT
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    connection_path: PADDED_EPATH_PAD_LEN


class ForwardCloseResponse(Struct):
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    application_reply_size: USINT = attr(init=False)
    _reserved: USINT = attr(reserved=True, default=USINT(0))
    application_reply: BYTES = attr(len_ref="application_reply_size")


class ForwardCloseFailedResponse(Struct):
    connection_serial: UINT
    originator_vendor_id: UINT
    originator_serial: UDINT
    remaining_path_size: USINT
    _reserved: USINT = attr(reserved=True, default=USINT(0))


class TickTime(IntEnum):
    """
    Time per tick (in milliseconds)
    """

    ms_1 = 0b_0000
    ms_2 = 0b_0001
    ms_4 = 0b_0010
    ms_8 = 0b_0011
    ms_16 = 0b_0100
    ms_32 = 0b_0101
    ms_64 = 0b_0110
    ms_128 = 0b_0111
    ms_256 = 0b_1000
    ms_512 = 0b_1001
    ms_1024 = 0b_1010
    ms_2048 = 0b_1011
    ms_4096 = 0b_1100
    ms_8192 = 0b_1101
    ms_16384 = 0b_1110
    ms_32768 = 0b_1111


class UnconnectedSendRequest(Struct):
    """

    Request timeout = tick_time * num_ticks
    Default timeout is 1024ms

    TODO: size may be off by 1 due to padding if `message_request_size` is odd or not
    """

    priority_tick_time: USINT = attr(init=False)
    timeout_ticks: USINT = attr(init=False)
    message_request_size: UINT = attr(init=False)
    message_request: MessageRouterRequest
    route_path: PADDED_EPATH_PAD_LEN

    tick_time: InitVar[TickTime]
    num_ticks: InitVar[int]
    priority: InitVar[bool] = False
    PRIORITY: ClassVar[USINT] = USINT(0b_000_1_0000)

    def __post_init__(
        self,
        tick_time: TickTime = TickTime.ms_1024,
        num_ticks: int = 1,
        priority: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        _priority = self.PRIORITY if priority else USINT(0)
        self.priority_tick_time = USINT(_priority | tick_time)
        self.timeout_ticks = USINT(num_ticks)
        self.message_request_size = UINT(len(bytes(self.message_request)))

    @override
    @classmethod
    def _decode(cls, stream: BytesIO) -> Self:
        ptt = USINT.decode(stream)
        tick_time = TickTime(ptt | 0b_0000_1111)
        priority = bool(ptt & cls.PRIORITY)
        ticks = USINT.decode(stream)
        request_size = UINT.decode(stream)
        request_data = cls._stream_read(stream, request_size)
        request = MessageRouterRequest.decode(request_data)
        if request_size % 2:
            _ = cls._stream_read(stream, 1)
        route_path = PADDED_EPATH_PAD_LEN.decode(stream)

        return cls(
            message_request=request,
            route_path=route_path,
            tick_time=tick_time,
            num_ticks=ticks,
            priority=priority,
        )

    @override
    @classmethod
    def _encode(cls, value: Self, *args: Any, **kwargs: Any) -> bytes:
        return b"".join(
            bytes(x)
            for x in (
                value.priority_tick_time,
                value.timeout_ticks,
                value.message_request_size,
                value.message_request,
                b"\x00" if value.message_request_size % 2 else b"",
                value.route_path,
            )
        )


class UnconnectedSendResponseHeader(Struct):
    reply_service: USINT
    _reserved: USINT = attr(reserved=True, default=USINT(0))
    general_status: USINT

    __field_descriptions__ = {"general_status": GeneralStatusCodes.dict()}  # type: ignore


class UnconnectedSendSuccessResponse(Struct):
    _reserved2: USINT = attr(reserved=True, default=USINT(0), init=False)
    service_response_data: BYTES


class UnconnectedSendFailedResponse(Struct):
    additional_status: Array[UINT, USINT]
    remaining_path_size: USINT


@dataclass
class UnconnectedSendResponseParser[T: DataType](MsgRouterResponseParser[T, UnconnectedSendFailedResponse]):
    __log = get_logger(__qualname__)
    response_type: type[T]
    failed_response_type: type[UnconnectedSendFailedResponse] = UnconnectedSendFailedResponse

    @override
    def parse(
        self, data: BYTES, request: CIPRequest[T | UnconnectedSendFailedResponse]
    ) -> CIPResponse[T | UnconnectedSendFailedResponse]:
        buff = as_stream(data)
        header = UnconnectedSendResponseHeader.decode(buff)
        self.__log.debug("decoded unconnected send response header: %r", header)
        if header.general_status in self.success_statuses:
            resp_data = UnconnectedSendSuccessResponse.decode(buff)
            self.__log.debug("decoded unconnected send response data: %r", resp_data)
            msg_data = self.response_type.decode(resp_data.service_response_data)
            msg = "Success"
        else:
            addl_status = Array[UINT, USINT].decode(buff)
            match header.general_status, addl_status:
                case (  # pyright: ignore[reportUnnecessaryComparison]
                    GeneralStatusCodes.connection_failure,
                    [
                        ConnMgrExtStatusCodesConnFailure.unconnected_send_timeout
                        | ConnMgrExtStatusCodesConnFailure.port_unavailable
                        | ConnMgrExtStatusCodesConnFailure.invalid_link_address
                        | ConnMgrExtStatusCodesConnFailure.invalid_segment,
                        *_,
                    ],
                ) | (GeneralStatusCodes.resource_unavailable | GeneralStatusCodes.path_error, _):
                    remaining_path_size = USINT.decode(buff)
                    msg_data = UnconnectedSendFailedResponse(addl_status, remaining_path_size)
                case _:
                    msg_data = UnconnectedSendFailedResponse(addl_status, USINT(0))
                    remaining_path_size = None

            general_msg, ext_msg = ConnectionManager.get_status_messages(
                service=request.message.service,
                status=header.general_status,
                ext_status=[int(x) for x in addl_status],
                extra_data=remaining_path_size,
            )

            msg = f"({header.general_status:#04x}) {general_msg}: {ext_msg}" if ext_msg else general_msg
            self.__log.debug("decoded unconnected send response data: %r", msg_data)

        return CIPResponse(
            request=request, message=header, data=msg_data, status_message=msg, success_statuses=self.success_statuses
        )


# TODO: when len_ref passes the array and not just the len of it
# class ConnectionEntryList(Struct):
#     num_entries: UINT
#     conn_open_bits: USINT[...] = attr(
#         len_ref=(
#             "num_entries",
#             lambda x: len(x) // 8 + (1 if len(x) % 8 else 0),
#             lambda x: len(x) * 8,
#         )
#     )


class ConnMgrExtStatusCodesConnFailure(StatusEnum):
    """
    Connection Manager Extended Status codes for General Status Code 0x01 - Connection failure
    """

    connection_in_use = 0x0100, "Connection in use or duplicate forward_open"
    transport_class_trigger_unsupported = 0x0103, "Transport class and trigger combination not supported"
    ownership_conflict = 0x0106, "Connection cannot be established due to another having exclusive ownership of a required resource"  # fmt: skip
    connection_missing = 0x0107, "Target connection not found"
    invalid_network_parameter = 0x0108, "A network connection parameter not supported by target/router"
    invalid_connection_size = 0x0109, "Requested connection size not supported by target/router"
    connection_not_configured = 0x0110, "Requested connection has not configured"
    unsupported_rpi = 0x0111, "Requested rpi or timeout value not supported by device"
    out_of_connections = 0x0113, "Connection Manager out of connections"
    code_mismatch = 0x0114, "Electronic key mismatch for vendor ID or product code"
    product_type_mismatch = 0x0115, "Electronic key mismatch for product type"
    revision_mismatch = 0x0116, "Electronic key mismatch for revision"
    invalid_application_path = 0x0117, "Invalid produced or consumed application path"
    invalid_configuration_path = 0x0118, "Invalid or inconsistent configuration application path"
    nonlisten_onlu_connection_closed = 0x0119, "Non-listen only connection not opened"
    target_out_of_connections = 0x011A, "Instance of target object is out of connections"
    rpi_inhibit_time_conflict = (
        0x011B,
        "Target to originator RPI is smaller than the target to originator production inhibit time",
    )
    connection_timeout = 0x0203, "Target attempted to send message on a connection that has timed out"
    unconnected_send_timeout = 0x0204, "Unconnected request timed out, UCMM did not receive a reply within timeout"
    unconnected_send_parameter_error = 0x0205, "Unconnected send request parameter invalid"
    unconnected_message_too_large = 0x0206, "Message too large for unconnected_send service"
    unconnected_ack_only = 0x0207, "Unconnected message received only acknowledgement, but no data response"
    memory_buffer_exceeded = 0x0301, "Target or router connection buffer out of memory"
    insufficient_network_bandwidth = (
        0x0302,
        "Producer node cannot allocate sufficient bandwidth for scheduled connection",
    )
    no_consumed_id_filter = 0x0303, "Link consumer has no connection ID filter available"
    schedule_priority_error = 0x0304, "Scheduled priority in connection request cannot be met by network"
    schedule_signature_mismatch = 0x0305, "Connection schedule signature from originator inconsistent with target"
    schedule_signature_validation_error = (
        0x0306,
        "Connection schedule signature from originator cannot be validated by target",
    )
    port_unavailable = 0x0311, "Port segment contains port that is unavailable or does not exist"
    invalid_link_address = 0x0312, "Port segment contains an invalid link address for target network"
    invalid_segment = 0x0315, "Connection path contains an invalid segment type or value"
    forward_close_mismatch = 0x0316, "Forward close request path does not match connection that was closed"
    schedule_not_specified = 0x0317, "Schedule network segment missing or value is invalid"
    link_to_self_unsupported = 0x0318, "Port segment contains a loopback link address which is unsupported by device"
    secondary_resources_unavailable = (
        0x0319,
        "Secondary in redundant chassis system is unable to duplicate connection request in primary",
    )
    rack_connection_already_established = 0x031A, "Request for rack connection refused, one is already established"
    misc = 0x031C, "Miscellaneous, like for whatever I guess 🤷"
    redundant_connection_mismatch = 0x031D, "Redundant connection request parameters mismatch"
    consumer_resources_error = (
        0x031E,
        "No more user configurable link consumer resources available in the producing module",
    )
    no_consumers = 0x031F, "Target has no consumers configured for producing application"
    network_link_offline = 0x0800, "Network link in path to module is offline"
    no_target_application_data = 0x0810, "Target application has no valid data to produce for requested connection"
    no_originator_application_data = (
        0x0811,
        "Originator application has no valid data to produce for requested connection",
    )
    node_address_changed = 0x0812, "Node address has changed since the network was scheduled"
    offsubnet_multicast_error = 0x0813, "Producer for connection request is not configured for off-subset multicast"


class ConnectionManager(CIPObject):
    """
    Manages internal resources for both I/O and Explicit Messaging connections.
    """

    class_code: int = 0x06

    #: Number of received Forward Open requests
    open_requests: CIPAttribute[UINT, Self] = CIPAttribute(id=1, data_type=UINT, get_all_instance=True)
    #: Number of Forward Open requests rejected because of bad formatting
    open_format_rejects: CIPAttribute[UINT, Self] = CIPAttribute(id=2, data_type=UINT, get_all_instance=True)
    #: Number of Forward Open requests rejected for lack of resources
    open_resource_rejects: CIPAttribute[UINT, Self] = CIPAttribute(id=3, data_type=UINT, get_all_instance=True)
    #: Number of Forward Open requests reject for reasons other than bad formatting or lack of resources
    open_other_rejects: CIPAttribute[UINT, Self] = CIPAttribute(id=4, data_type=UINT, get_all_instance=True)
    #: Number of received Forward Close requests
    close_requests: CIPAttribute[UINT, Self] = CIPAttribute(id=5, data_type=UINT, get_all_instance=True)
    #: Number of Forward Close requests rejected because of bad formatting
    close_format_rejects: CIPAttribute[UINT, Self] = CIPAttribute(id=6, data_type=UINT, get_all_instance=True)
    #: Number of Forward Close requests reject for reasons other than bad formatting
    close_other_rejects: CIPAttribute[UINT, Self] = CIPAttribute(id=7, data_type=UINT, get_all_instance=True)
    #: Number of connection timeouts in connections managed by this instance
    connection_timeouts: CIPAttribute[UINT, Self] = CIPAttribute(id=8, data_type=UINT, get_all_instance=True)
    #: List of connections, each positive bit corresponds to a connection instance
    # TODO connection_entry_list = CIPAttribute(id=9, data_type=...)
    #      and also get_all_instance=True for following attrs
    # attribute 10 is reserved or obsolete
    #: CPU utilization as tenths of a percent, 0-100% scaled to 0-1000
    cpu_utilization: CIPAttribute[UINT, Self] = CIPAttribute(id=11, data_type=UINT)
    #: Total size (in bytes) of the buffer
    max_buffer_size: CIPAttribute[UDINT, Self] = CIPAttribute(id=12, data_type=UDINT)
    #: Currently available size (in bytes) of the buffer
    buffer_size_remaining: CIPAttribute[UDINT, Self] = CIPAttribute(id=13, data_type=UDINT)

    @classmethod
    def __customize_object__(cls) -> None:
        cls.num_instances.get_all_class = False
        cls.max_class_attr.get_all_class = True
        cls.max_instance_attr.get_all_class = True

    @service(id=USINT(0x4E))
    def forward_close(
        cls, params: ForwardCloseRequest
    ) -> CIPRequest[ForwardCloseResponse | ForwardCloseFailedResponse]:
        """
        Closes a connection
        """
        return message_router_service(
            service=cls.forward_close.id,
            class_code=cls.class_code,
            instance=ConnectionManager.Instance.open_request,
            request_data=params,
            response_type=ForwardCloseResponse,
            failed_response_type=ForwardCloseFailedResponse,
        )

    @service(id=0x54)
    def forward_open(cls, params: ForwardOpenRequest) -> CIPRequest[ForwardOpenResponse | ForwardOpenFailedResponse]:
        """
        Opens a connection with a maximum data size of 511 bytes
        """

        return message_router_service(
            service=cls.forward_open.id,
            class_code=cls.class_code,
            instance=ConnectionManager.Instance.open_request,
            request_data=params,
            response_type=ForwardOpenResponse,
            failed_response_type=ForwardOpenFailedResponse,
        )

    @service(id=USINT(0x5B))
    def large_forward_open(
        cls, params: LargeForwardOpenRequest
    ) -> CIPRequest[ForwardOpenResponse | ForwardOpenFailedResponse]:
        """
        Opens a connection with a maximum data size of 65535 bytes
        """
        return message_router_service(
            service=cls.large_forward_open.id,
            class_code=cls.class_code,
            instance=cls.Instance.open_request,
            request_data=params,
            response_type=ForwardOpenResponse,
            failed_response_type=ForwardOpenFailedResponse,
        )

    @service(id=USINT(0x52))
    def unconnected_send[T: DataType](
        cls,
        msg: CIPRequest[T],
        route_path: CIPRoute,
        tick_time: TickTime,
        num_ticks: int,
    ) -> CIPRequest[T | UnconnectedSendFailedResponse]:
        return CIPRequest(
            message=MessageRouterRequest.build(
                service=cls.unconnected_send.id,
                class_code=cls.class_code,
                instance=1,
                data=UnconnectedSendRequest(
                    message_request=msg.message,
                    route_path=route_path.epath(padded=True, length=True, padded_len=True),
                    tick_time=tick_time,
                    num_ticks=num_ticks,
                ),
            ),
            response_parser=UnconnectedSendResponseParser(
                response_type=msg.response_parser.response_type,
                success_statuses=msg.response_parser.success_statuses,  # type: ignore
            ),
        )

    @final
    class Instance(CIPObject.Instance):
        open_request = 0x01
        open_format_rejected = 0x02
        open_resource_rejected = 0x03
        open_other_rejected = 0x04
        close_request = 0x05
        close_format_request = 0x06
        close_other_request = 0x07
        connection_timeout = 0x08

    STATUS_CODES: ClassVar[StatusCodesType] = {
        "*": {
            GeneralStatusCodes.connection_failure: ConnMgrExtStatusCodesConnFailure,
            GeneralStatusCodes.invalid_attribute: {
                "*": "Error in data segment for forward open request",  # ext. status is the index of the error in the segment
            },
        },
    }

    @override
    @classmethod
    def _customize_extended_status(
        cls, general_status: int, ext_status: int, ext_status_extra: Sequence[int], extra_data: DataType | None
    ) -> str | None:
        if ext_status == ConnMgrExtStatusCodesConnFailure.invalid_connection_size:  # pyright: ignore[reportUnnecessaryComparison]
            if ext_status_extra:
                max_supported_size = ext_status_extra[0]
                return f"{max_supported_size=:d}"
        if general_status == GeneralStatusCodes.invalid_attribute:  # pyright: ignore[reportUnnecessaryComparison]
            return f"DataSegment error at index {ext_status}"
        if general_status == GeneralStatusCodes.object_state_conflict:  # pyright: ignore[reportUnnecessaryComparison]
            return f"state={ext_status:#06x}"

        return None
