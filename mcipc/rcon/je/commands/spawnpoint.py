"""Implementation of the spawnpoint command."""

from mcipc.rcon.proto import Client
from mcipc.rcon.types import Vec3


__all__ = ['spawnpoint']


def spawnpoint(self: Client, targets: str = None, position: Vec3 = None,
               angle: float = None) -> str:
    """Sets the spawn point for a player."""

    return self.run('spawnpoint', targets, position, angle)
