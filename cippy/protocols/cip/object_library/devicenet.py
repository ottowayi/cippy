from typing import ClassVar

from ..cip_object import CIPObject


class DeviceNet(CIPObject):
    class_code: int = 0x03
