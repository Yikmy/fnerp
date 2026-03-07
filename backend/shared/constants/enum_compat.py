"""Enum compatibility helpers."""

from enum import Enum

try:
    from enum import StrEnum as _StrEnum
except ImportError:  # Python < 3.11
    class _StrEnum(str, Enum):
        """Backport of :class:`enum.StrEnum` for older Python versions."""

        def __str__(self) -> str:
            return str(self.value)


StrEnum = _StrEnum

__all__ = ["StrEnum"]
