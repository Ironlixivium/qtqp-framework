"""Type alias for user-supplied form values."""

from collections.abc import Mapping

type UserInputValues = Mapping[str, bool | str | list[str] | tuple[str, str, float] | None]