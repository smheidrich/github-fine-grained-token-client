from typing import Any, Sequence


def one_or_none(seq: Sequence[Any]):
    if len(seq) > 1:
        raise ValueError("more than one element found")
    elif len(seq) == 1:
        return seq[0]
    return None
