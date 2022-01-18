"""Minecraft-specific client."""

import rcon

from mcipc.rcon.functions import str_until_none


__all__ = ['Client']


class Client(rcon.Client):
    """An RCON client for Minecraft."""

    def run(self, command: str, *arguments: str) -> str:
        """Runs the command with additional checks."""
        return super().run(*str_until_none(command, *arguments))
