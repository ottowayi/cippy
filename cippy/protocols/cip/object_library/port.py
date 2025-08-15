from typing import Annotated, Self

from cippy.data_types import (
    SHORT_STRING,
    Struct,
    PADDED_EPATH,
    PACKED_EPATH,
    PADDED_EPATH_PAD_LEN,
    UINT,
    Array,
    array,
)
from cippy.util import IntEnumX
from ..cip_object import CIPObject, CIPAttribute


class InstanceInfo(Struct):
    port_type: UINT
    port_number: UINT


class LinkObject(Struct):
    word_length: UINT
    link_path: Annotated[Array[PADDED_EPATH, int], 2]


class Port(CIPObject):
    """
    Represents the CIP ports on the device, one instance per port.
    """

    class_code: int = 0xF4

    # --- Class Attributes ---
    #: Gets the instance ID of the Port Object that the request entered through
    entry_port: CIPAttribute[UINT, Self] = CIPAttribute(id=8, data_type=UINT, class_attr=True, get_all_class=True)
    #: Array of port type and number for each instance (instance attributes 1 & 2)
    port_instance_info: CIPAttribute[Array[InstanceInfo, None], Self] = CIPAttribute(
        id=9, data_type=Array[InstanceInfo, None], class_attr=True, get_all_class=True, len_ref="max_instance"
    )

    # --- Instance Attributes ---
    #: Indicates the type of port, see :class:`PortTypes`
    port_type: CIPAttribute[UINT, Self] = CIPAttribute(id=1, data_type=UINT, get_all_instance=True)
    #: CIP port number of the port
    port_number: CIPAttribute[UINT, Self] = CIPAttribute(id=2, data_type=UINT, get_all_instance=True)
    #: Logical path that identifies the object for this port
    link_object: CIPAttribute[PADDED_EPATH_PAD_LEN, Self] = CIPAttribute(
        id=3, data_type=PADDED_EPATH_PAD_LEN, get_all_instance=True
    )
    #: String name that identifies the physical port on the device.
    port_name: CIPAttribute[SHORT_STRING, Self] = CIPAttribute(id=4, data_type=SHORT_STRING, get_all_instance=True)
    #: String name of the port type
    port_type_name: CIPAttribute[SHORT_STRING, Self] = CIPAttribute(id=5, data_type=SHORT_STRING)
    #: String description of the port
    port_description: CIPAttribute[SHORT_STRING, Self] = CIPAttribute(id=6, data_type=SHORT_STRING)
    #: Node number of the device on the port
    node_address: CIPAttribute[PADDED_EPATH, Self] = CIPAttribute(id=7, data_type=PADDED_EPATH, get_all_instance=True)
    #: Range of node numbers on the port, not used with EtherNet/IP
    port_node_range: CIPAttribute[Array[UINT, int], Self] = CIPAttribute(id=8, data_type=array(UINT, 2))
    #: Electronic key of network or chassis the port is attached to
    port_key: CIPAttribute[PACKED_EPATH, Self] = CIPAttribute(id=9, data_type=PACKED_EPATH)

    class PortTypes(IntEnumX):
        """
        Enum of the different ``port_type`` attribute values.

        Not listed:
          - 6-99 = Reserved for compatability with existing protocols
          - 100-199 = Vendor specific
          - 203 - 65534 = Reserved for future use

        """

        #: Connection terminates in this device
        Endpoint = 0
        #: Backplane
        Backplane = 1
        #: ControlNet
        ControlNet = 2
        #: ControlNet Redundant
        ControlNetRedundant = 3
        #: EtherNet/IP
        EtherNetIP = 4
        #: DeviceNet
        DeviceNet = 5
        #: Remote I/O Scanner
        RIOScanner = 6
        # Remote I/O Adapter
        RIOAdapter = 7
        #: Virtual backplane / CompactLogix
        VirtualBackplane = 100
        #: DataHighway
        DataHighway = 101
        #: DataHighway RS485
        DHRS485 = 102
        #: USB
        USB = 107
        #: CompoNet
        CompoNet = 200
        #: Modbus/TCP
        ModbusTCP = 201
        #: Modbus/SL
        ModbusSL = 202
        #: Port is not configured
        UnconfiguredPort = 65535
