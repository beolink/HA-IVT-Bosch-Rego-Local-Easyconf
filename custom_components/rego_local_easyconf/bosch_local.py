"""A Bosch internet gateway answering on the LAN: not in this version.

The order of sources keeps a place for it (const.SOURCE_PRIORITY), between
Husdata and the cloud. The gateways IVT sells today - the K30 RF and K40 behind
IVT Anywhere II - answer nothing locally: they are outbound clients of Bosch's
cloud (the K30 on the IVT Geo 608C this was built against has no open port),
so for them the cloud is the way in. Buderus's KM50/KM100/KM200 and MB LAN 2
do answer on the LAN, with AES-encrypted JSON; supporting them needs a unit to
measure against, and none is at hand. The probe finds nothing until then.
"""

from __future__ import annotations

from typing import Any


async def probe(session: Any, host: str) -> None:
    return None
