from typing import Sequence, TypeVar

T = TypeVar("T")


def one_or_none(seq: Sequence[T]) -> T | None:
    if len(seq) > 1:
        raise ValueError(
            "more than one element where at most one was expected"
        )
    elif len(seq) == 1:
        return seq[0]
    return None


def exactly_one(seq: Sequence[T]) -> T:
    if len(seq) > 1:
        raise ValueError(
            "more than one element where exactly one was expected"
        )
    elif len(seq) < 1:
        raise ValueError("no elements where exactly one was expected")
    return seq[0]
