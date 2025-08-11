from cippy.drivers import CIPDriver
import pytest

from cippy.protocols.cip.object_library import Identity
from cippy.data_types import UINT, SHORT_STRING, WORD, UDINT, USINT, Revision


def test_cip_driver_basics():
    driver = CIPDriver("192.168.1.236")
    driver.open()
    assert driver.connection.connected is True
    assert driver.connection.cip_connected is False

    driver.close()
    assert driver.connection.connected is False
    assert driver.connection.cip_connected is False

    driver.open(cip_connected=True)
    assert driver.connection.connected is True
    assert driver.connection.cip_connected is True
    assert driver.connection.config.connected_config.o2t_connection_id != 0
    identity = driver.identity
    assert isinstance(identity, Identity)
    assert identity.vendor_id == 1
    assert identity.dict() == {
        "device_type": UINT(12),
        "product_code": UINT(191),
        "product_name": SHORT_STRING("1769-L23E-QBFC1 Ethernet Port"),
        "revision": Revision(major=USINT(20), minor=USINT(19)),
        "serial_number": UDINT(3223240336),
        "status": WORD((0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
        "vendor_id": UINT(1),
    }

    cls_identity = driver.read_object(Identity, instance=None)
    assert isinstance(cls_identity, Identity)
    with pytest.raises(AttributeError):
        cls_identity.revision
    assert cls_identity.object_revision == 1
    assert cls_identity.dict() == {
        "max_class_attr": UINT(7),
        "max_instance": UINT(1),
        "max_instance_attr": UINT(7),
        "object_revision": UINT(1),
    }
