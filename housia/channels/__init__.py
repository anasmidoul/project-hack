"""Portal channels. Imports are lazy, so the web app and tests never import browser-use."""

from housia.channels.base import Channel


def get_channel(name: str) -> Channel:
    if name == "mock":
        from housia.channels.mock import MockChannel

        return MockChannel()
    if name == "idealista":
        from housia.channels.idealista import IdealistaChannel

        return IdealistaChannel()
    if name == "badi":
        from housia.channels.badi import BadiChannel

        return BadiChannel()
    raise ValueError(f"Unknown channel: {name!r}")
