from .sequences import exactly_one


def expect_single_str(value: str | list[str]) -> str:
    if isinstance(value, str):
        return value
    elif isinstance(value, list):
        return exactly_one(value)
    raise TypeError(
        f"expect string or list, got value {value!r} of type {type(value)}"
    )


def expect_single_str_or_none(value: str | list[str] | None) -> str | None:
    if isinstance(value, str):
        return value
    elif isinstance(value, list):
        return exactly_one(value)
    elif value is None:
        return None
    raise TypeError(
        "expect string, list, or None, got value "
        f"{value!r} of type {type(value)}"
    )
