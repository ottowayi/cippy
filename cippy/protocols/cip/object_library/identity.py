from enum import IntEnum
from typing import ClassVar

from cippy.const import VENDORS, DeviceTypes
from cippy.data_types import UINT, WORD, UDINT, SHORT_STRING, USINT, Revision, Struct
from ..cip_object import CIPObject, CIPAttribute, StandardClassAttrs


class Status(WORD):
    owned: bool
    configured: bool
    extended_status: tuple[bool, bool, bool, bool]
    minor_recoverable_fault: bool
    minor_unrecoverable_fault: bool
    major_recoverable_fault: bool
    major_unrecoverable_fault: bool

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bits = [bool(b) for b in self.bits]
        self.owned = bits[0]
        self.configured = bits[2]
        self.extended_status = (bits[4], bits[5], bits[6], bits[7])
        self.minor_recoverable_fault = bits[8]
        self.minor_unrecoverable_fault = bits[9]
        self.major_recoverable_fault = bits[10]
        self.major_unrecoverable_fault = bits[11]


class IdentityInstanceAttrs(Struct):
    vendor_id: UINT
    device_type: UINT
    product_code: UINT
    revision: Revision
    status: Status
    serial_number: UDINT
    product_name: SHORT_STRING

    _vendors: ClassVar[dict[int, str]] = VENDORS

    @property
    def vendor_name(self) -> str | None:
        """
        The vendor name if `vendor_id` is a known vendor, else None.
        """
        return self._vendors.get(self.vendor_id, None)

    @property
    def serial(self) -> str | None:
        """
        String version of the serial number formatted as 8 uppercase hex digits.
        """
        return f"{self.serial_number:@X}" if self.serial_number is not None else None

    @property
    def rev(self) -> str | None:
        """
        String version of the revision number
        """
        return f"{self.revision:@}" if self.revision is not None else None

    @property
    def device_type_name(self) -> str | None:
        return DeviceTypes.get_name(self.device_type)


class Identity(CIPObject[IdentityInstanceAttrs, StandardClassAttrs]):
    """
    This object provides general identity and status information about a device.
    It is required by all CIP objects and if a device contains multiple discrete
    components, multiple instances of this object may be created.
    """

    class_code = 0x01

    # --- Required attributes ---
    #: Identification code assigned to the vendor
    vendor_id = CIPAttribute(id=1, data_type=UINT)
    #: Indication of general type of product
    device_type = CIPAttribute(id=2, data_type=UINT)
    #: Identification code of a particular product for an individual vendor
    product_code = CIPAttribute(id=3, data_type=UINT)
    #: Revision of the item the Identity Object represents
    revision = CIPAttribute(id=4, data_type=Revision)
    #: Summary status of the device
    status = CIPAttribute(id=5, data_type=WORD)
    #: Serial number of the device
    serial_number = CIPAttribute(id=6, data_type=UDINT)
    #: Human readable identification of the device
    product_name = CIPAttribute(id=7, data_type=SHORT_STRING)

    # TODO: add custom type for status that shows what the bits mean

    # --- Optional attributes ---
    #: Present state of the device, see :class:`~IdentityObject.States`
    state = CIPAttribute(id=8, data_type=USINT)

    _svc_get_attrs_all_instance_type: type[IdentityInstanceAttrs] = IdentityInstanceAttrs

    class States(IntEnum):
        """
        Enum of the possible state attribute values,
        any not listed are 'reserved'
        """

        #: The device is powered off
        Nonexistent = 0
        #: The device is currently running self tests
        DeviceSelfTesting = 1
        #: The device requires commissioning, configuration is invalid or incomplete
        Standby = 2
        #: The device is functioning normally
        Operational = 3
        #: The device experienced a fault that it can recover from
        MajorRecoverableFault = 4
        #: The device experienced a fault that it cannot recover from
        MajorUnrecoverableFault = 5
        #: Default value for a ``get_attributes_all`` service response if attribute is not supported
        DefaultGetAttributesAll = 255
