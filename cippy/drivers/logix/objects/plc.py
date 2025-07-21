from cippy.protocols.cip import CIPObject, CIPAttribute
from cippy.data_types import Struct, STRING, BYTES


class PLCInstanceAttrs(Struct):
    program_name: STRING
    unknown: BYTES


class PLC(CIPObject):
    """
    Object that represents something about the PLC?, this class code is referenced in KB23341
    Only known attribute is the program name.
    """

    class_code = 0x64

    program_name = CIPAttribute(id=1, data_type=STRING)
