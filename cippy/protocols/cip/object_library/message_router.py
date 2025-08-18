from typing import ClassVar, Self

from cippy.data_types import BYTES, EPATH, UINT, USINT, Array

from .._base import CIPRequest
from ..cip_object import CIPAttribute, CIPObject, GeneralStatusCodes, StatusCodesType, service
from ..msg_router_services import message_router_service


class MessageRouter(CIPObject):
    """
    The object handles routing service calls to objects within the device from client messages
    """

    class_code: int = 0x02

    #: List of supported objects (class codes)
    object_list: CIPAttribute[Array[UINT, UINT], Self] = CIPAttribute(
        id=1, data_type=Array[UINT, UINT], get_all_instance=True
    )
    #: Max number of supported connections
    num_available: CIPAttribute[UINT, Self] = CIPAttribute(id=2, data_type=UINT, get_all_instance=True)
    #: Number of currently active connections
    num_active: CIPAttribute[UINT, Self] = CIPAttribute(id=3, data_type=UINT, get_all_instance=True)
    #: List of connection ids for active connections
    active_connections: CIPAttribute[Array[UINT, None], Self] = CIPAttribute(
        id=4, data_type=Array[UINT, None], get_all_instance=True
    )

    @service(id=USINT(0x4B))
    def symbolic_translation(cls, symbol: EPATH) -> CIPRequest[EPATH | BYTES]:
        """
        Translates a single `SymbolicSegment` `EPATH` to the equivalent `LogicalSegment` `EPATH` if one exists
        """
        request = message_router_service(
            service=cls.symbolic_translation.id,
            class_code=cls.class_code,
            instance=None,
            request_data=symbol,
            response_type=EPATH,
            failed_response_type=BYTES,
        )
        return request

    STATUS_CODES: ClassVar[StatusCodesType] = {
        symbolic_translation.id: {
            GeneralStatusCodes.invalid_parameter: {
                0x00: "Symbolic Path unknown",
                0x01: "Symbolic Path destination not assigned",
                0x02: "Symbolic Path segment error",
            }
        }
    }
