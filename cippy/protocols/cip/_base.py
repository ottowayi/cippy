from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol
from cippy.data_types import (
    BYTES,
    USINT,
    DataType,
)

if TYPE_CHECKING:
    from .cip_object import CIPObject
    from .msg_router_services import MessageRouterRequest


@dataclass
class CIPRequest[T: DataType]:
    message: "MessageRouterRequest"
    response_parser: "CIPResponseParser[T]" = field(repr=False)


class CIPResponseMessage(Protocol):
    general_status: USINT


SUCCESS = USINT(0)


@dataclass
class CIPResponse[T: DataType]:
    request: CIPRequest[T]
    message: CIPResponseMessage
    data: T | BYTES | None = None
    status_message: str | None = None
    success_statuses: set[USINT | int] = field(default_factory=lambda: {SUCCESS}, repr=False)

    def __bool__(self) -> bool:
        return self.message.general_status in self.success_statuses


class CIPResponseParser[T: DataType](Protocol):
    response_type: type[T]

    def parse(self, data: BYTES, request: CIPRequest[T]) -> CIPResponse[T]:
        raise NotImplementedError
