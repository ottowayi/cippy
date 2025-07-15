from cippy.util import PredefinedValues
import pytest


def test_predefined_values():
    class Test(PredefinedValues):
        x = 1
        y = 2
        z = 3
        _skipped = None

    assert "x" in Test
    assert Test.x == 1 == Test["x"]
    assert Test[1] == "x"
    assert Test.to_dict() == {1: "x", 2: "y", 3: "z"}
    assert Test.to_dict(key="name") == {"x": 1, "y": 2, "z": 3}
    assert Test.get_name(1) == "x"
    assert Test.get_name(420) is None

    class Test2(Test):
        x = 69

    assert Test2.x == 69
    with pytest.raises(KeyError):
        Test2[1]

    assert Test2.to_dict() == {69: "x", 2: "y", 3: "z"}
    assert Test2.to_dict(key="name") == {"x": 69, "y": 2, "z": 3}
    assert Test2.get_name(1) is None
    assert Test2.get_name(69) == "x"

    assert {**Test2} == Test2.to_dict()
