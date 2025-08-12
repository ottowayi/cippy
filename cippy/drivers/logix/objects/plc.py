from cippy.data_types import STRING
from cippy.protocols.cip import CIPAttribute, CIPObject


class PLC(CIPObject):
    """
    Object that represents something about the PLC?, this class code is referenced in KB23341
    Only known attribute is the program name.
    """

    class_code = 0x64

    program_name = CIPAttribute(id=1, data_type=STRING)
