from dataclasses import fields
from typing import Any


def assert_lhs_fields_match(obj1: Any, obj2: Any) -> None:
    """
    Assert that each field of obj1 matches a field of the same name on obj2.

    But not vice versa, i.e. obj2 can have more fields (which is the whole
    point).

    Args:
      obj1: Dataclass instance that forms the left-hand side of the comparison
        (the one that can have fewer fields).
      obj2: Dataclass instance that forms the right-hand side of the comparison
        (the one that can have more fields).
    """
    for field in fields(obj1):
        assert (v1 := getattr(obj1, field.name)) == (
            v2 := getattr(obj2, field.name)
        ), f"field {field.name} doesn't match: {v1} != {v2}"
