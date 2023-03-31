"""
Things only relevant for developing this library.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .permissions import PermissionValue


@dataclass
class PossiblePermission:
    identifier: str
    name: str
    description: str
    allowed_values: tuple[PermissionValue, ...]


@dataclass
class PossiblePermissions:
    repository: Sequence[PossiblePermission]
    account: Sequence[PossiblePermission]
