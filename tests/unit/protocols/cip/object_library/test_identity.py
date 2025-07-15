from cippy.data_types import Revision
from cippy.const import VENDOR_ID_ROCKWELL, VENDOR_NAME_ROCKWELL
from cippy.protocols.cip.object_library import IdentityInstanceAttrs


def test_device_identity():
    identity = IdentityInstanceAttrs(
        vendor_id=VENDOR_ID_ROCKWELL,
        device_type=0x0C,
        product_code=0x69,
        revision=Revision(0, 10),
        status=0b0011_0011_0101_0000,
        serial_number=0x11223344,
        product_name="Something Overpriced",
    )

    assert identity.vendor_id == VENDOR_ID_ROCKWELL
    assert identity.vendor_name == VENDOR_NAME_ROCKWELL
    assert f"{identity.status:@b}" == "0b0011_0011_0101_0000"
    assert identity.status.bits == (0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0)
    assert identity.serial == "11223344"
    assert identity.rev == "0.010"
    assert identity.status.owned is False
    assert identity.status.minor_unrecoverable_fault is True
    assert identity.status.major_recoverable_fault is False
    assert identity.status.extended_status == (True, False, True, False)
    assert identity.device_type_name == "communications_adapter"
