"""Processo worker: consome o barramento e executa os estágios (sem porta HTTP exposta)."""

from __future__ import annotations

import asyncio
import logging

from .bootstrap import build_runtime
from .config import Settings


async def _main() -> None:
    s = Settings.from_env()
    rt = build_runtime(s)
    await rt.bus.start()
    logging.getLogger("aegis.worker").info("worker pronto (bus=%s)", s.bus_backend)
    try:
        await asyncio.Event().wait()
    finally:
        await rt.bus.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_main())
