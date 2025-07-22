from cippy.data_types import BYTES, STRING, Struct, attr
from cippy.protocols.cip import CIPAttribute, CIPObject


class PLCInstanceAttrs(Struct):
    program_name: STRING
    unknown: BYTES = attr(reserved=True, default=BYTES(b""))


class PLC(CIPObject):
    """
    Object that represents something about the PLC?, this class code is referenced in KB23341
    Only known attribute is the program name.
    """

    class_code = 0x64

    program_name = CIPAttribute(id=1, data_type=STRING)

    _svc_get_attrs_all_instance_type = PLCInstanceAttrs
