from cippy.protocols.cip.cip_object import CIPAttribute, CIPObject, GeneralStatusCodes
from cippy.protocols.cip.object_library.connection_manager import ConnectionManager, ConnMgrExtStatusCodesConnFailure
from cippy.data_types import (
    BYTES,
    UINT,
    UDINT,
    CIPSegment,
    SegmentType,
    PADDED_EPATH,
    LogicalSegment,
    LogicalSegmentType,
    USINT,
    SHORT_STRING,
    PortSegment,
    PADDED_EPATH_PAD_LEN,
)
import pytest
from dataclasses import dataclass, field
from typing import Sequence

from cippy.protocols.cip.object_library.identity import Identity
from cippy.protocols.cip.object_library.port import Port


@dataclass
class StatusMsgTest:
    cip_object: type[CIPObject] = CIPObject
    service: int = 0x00
    status: int = 0x00
    ext_status: Sequence[int] = field(default_factory=lambda: [0x00])
    extra_data: BYTES = BYTES(b"")


status_msg_tests = [
    # any object, any service, success
    (StatusMsgTest(), (GeneralStatusCodes.success.description, "(0x0000)")),
    # specific object, any service, success
    (StatusMsgTest(ConnectionManager), (GeneralStatusCodes.success.description, "(0x0000)")),
    (  # specific object, any service, ext msg, no extras
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.connection_failure,
            ext_status=[ConnMgrExtStatusCodesConnFailure.connection_missing],
        ),
        (
            GeneralStatusCodes.connection_failure.description,
            "(0x0107) Target connection not found",
        ),
    ),
    (  # specific object, any service, ext msg, unused extras
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.connection_failure,
            ext_status=[ConnMgrExtStatusCodesConnFailure.connection_missing, UINT(69)],
            extra_data=BYTES(b"nice."),
        ),
        (
            GeneralStatusCodes.connection_failure.description,
            "(0x0107) Target connection not found: ext_status_words=[UINT(69)], extra_data=BYTES[...](b'nice.')",
        ),
    ),
    (  # specific object, any service, no ext msg, with extras
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.connection_failure,
            ext_status=[UINT(69), UINT(69)],
            extra_data=BYTES(b"nice."),
        ),
        (
            GeneralStatusCodes.connection_failure.description,
            "(0x0045): ext_status_words=[UINT(69)], extra_data=BYTES[...](b'nice.')",
        ),
    ),
    (  # specific object, any service, known ext, with ext addl
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.connection_failure,
            ext_status=[ConnMgrExtStatusCodesConnFailure.invalid_connection_size, UINT(500)],
        ),
        (
            GeneralStatusCodes.connection_failure.description,
            "(0x0109) Requested connection size not supported by target/router: max_supported_size=500",
        ),
    ),
    (  # specific object, any service, no ext, with ext addl
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.connection_failure,
            ext_status=[],
            extra_data=BYTES(b"blah blah blah blahhhhhhhhhhhhh"),
        ),
        (GeneralStatusCodes.connection_failure.description, None),
    ),
    # a few custom message handlers
    (
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.object_state_conflict,
            ext_status=[1],
        ),
        (
            GeneralStatusCodes.object_state_conflict.description,
            "(0x0001): state=0x0001",
        ),
    ),
    (
        StatusMsgTest(
            cip_object=ConnectionManager,
            status=GeneralStatusCodes.object_state_conflict,
            ext_status=[UDINT(0x42069)],  # udint not in spec, but testing formatting of it
        ),
        (
            GeneralStatusCodes.object_state_conflict.description,
            "(0x42069): state=0x42069",
        ),
    ),
    # TODO: you missed using `service` in any tests dumbass
]


@pytest.mark.parametrize("inputs, expected", status_msg_tests)
def test_get_status_messages(inputs, expected):
    msgs = inputs.cip_object.get_status_messages(inputs.service, inputs.status, inputs.ext_status, inputs.extra_data)
    assert msgs == expected


def test_cip_object_instance():
    class TestObject(CIPObject):
        attr1 = CIPAttribute(id=1, data_type=UINT)
        attr2 = CIPAttribute(id=2, data_type=UDINT)

    x = TestObject(instance=1)
    assert x.instance == 1
    assert x.__attributes__ == {"attr1": TestObject.attr1, "attr2": TestObject.attr2}
    with pytest.raises(AttributeError):
        x.attr1  # not set on instance yet

    x.attr1 = 2
    assert isinstance(x.attr1, UINT)
    with pytest.raises(AttributeError):
        x.max_instance  # class attr on instance

    assert x.dict() == {"attr1": 2}

    # TODO: more, duh


def test_cip_object_decodes():
    port = Port(
        instance=1,
        port_type=UINT(100),
        port_number=UINT(10),
        link_object=PADDED_EPATH_PAD_LEN(
            segments=[
                LogicalSegment(type=LogicalSegmentType.type_class_id, value=UINT(768)),
                LogicalSegment(type=LogicalSegmentType.type_instance_id, value=USINT(1)),
            ]
        ),
        port_name=SHORT_STRING("Backplane"),
        node_address=PADDED_EPATH(segments=[PortSegment(port=1, link_address=USINT(1))]),
    )

    enc_port = b"d\x00\x01\x00\x03\x00!\x00\x00\x03$\x01\tBackplane\x01\x01"

    assert port == Port(instance=1, **Port.__instance_struct__.decode(enc_port))

    cls_iden = Identity(
        instance=None, object_revision=UINT(1), max_instance=UINT(1), max_class_attr=UINT(7), max_instance_attr=UINT(7)
    )
    enc_cls_iden = b"\x01\x00\x01\x00\x07\x00\x07\x00"
    assert cls_iden == Identity(instance=0, **Identity.__class_struct__.decode(enc_cls_iden))
