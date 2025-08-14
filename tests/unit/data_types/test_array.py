# pyright: reportMissingParameterType = false

import pytest

from cippy.data_types import DINT, INT, SINT, STRING, Array, Struct, array
from cippy.exceptions import DataError


def test_array_classes():
    assert issubclass(array(DINT, 4), Array)
    d: type[Array[DINT, int]] = array(DINT, 4)

    assert d.element_type is DINT
    assert d.length == 4
    assert d is Array[DINT, 4] is array(DINT, 4)
    assert array(DINT, SINT).length is SINT
    assert array(DINT, ...).length is Ellipsis

    assert array(DINT, 4).size == DINT.size * 4

    with pytest.raises(DataError):
        x = array(DINT, ...).size

    with pytest.raises(DataError):
        x = array(DINT, INT).size

    assert array(DINT, 1) == array(DINT, 1)
    assert array(DINT, 1) != array(DINT, 2)
    assert array(DINT, None) == array(DINT, ...)
    assert array(DINT, 10) != array(INT, 100)
    assert array(DINT, ...) != array(INT, ...)

    assert (
        array(DINT, ...)
        is Array[DINT, ...]  # type: ignore
        is array(DINT, None)
        is Array[DINT, None]
    )


elementary_tests = [
    (DINT, 1, [1], bytes(DINT(1))),
    (STRING, 1, ["hello there"], bytes(STRING("hello there"))),
    (DINT, 3, [1, 2, 3], bytes(DINT(1)) + bytes(DINT(2)) + bytes(DINT(3))),
]


@pytest.mark.parametrize("typ, length, values, encoded", elementary_tests)
def test_array_elementary(typ, length, values, encoded):
    ary_type = array(typ, length)
    ary = ary_type(values)

    assert bytes(ary) == encoded
    assert ary_type.decode(encoded) == ary


def test_array_slicing():
    ary = array(DINT, 10)(range(10))
    assert ary[:4] == Array[DINT, 4](range(4))
    assert bytes(ary[:4]) == bytes(array(DINT, 4)(range(4)))

    ary[5:] = [0, 0, 0, 0, 0]
    assert ary == array(DINT, 10)([0, 1, 2, 3, 4, 0, 0, 0, 0, 0])
    assert bytes(ary[5:]) == bytes(DINT(0)) * 5
    assert ary[:2].size == DINT.size * 2


def test_array_struct():
    class S1(Struct):
        x: DINT | int = 0
        y: STRING | str = "xyz"
        z: Array[DINT, ...] = Array[DINT, 3]([1, 2, 3])

    ary = Array[S1, 3]([S1(), S1(), S1()])

    assert ary[0].x == 0
    assert bytes(ary) == bytes(S1()) * 3
    ary[1].z[0] = -1
    assert ary[1] == S1(z=[-1, 2, 3])
    assert bytes(ary) != (bytes(S1()) * 3)
    assert bytes(ary) == bytes(S1()) + bytes(S1(z=[-1, 2, 3])) + bytes(S1())
