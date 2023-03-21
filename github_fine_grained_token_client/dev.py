"""
Things only relevant for developing this library.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class PossiblePermission:
    identifier: str
    name: str
    description: str


@dataclass
class PosiblePermissions:
    repository: Sequence[PossiblePermission]
    account: Sequence[PossiblePermission]
