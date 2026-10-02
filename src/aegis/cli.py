"""CLI: conversa com o assistente sem subir HTTP (mesmo pipeline, barramento em memória)."""

from __future__ import annotations

import asyncio
import dataclasses
import sys
import tempfile
from pathlib import Path

from .bootstrap import build_runtime
from .config import Settings


def render(r: dict) -> str:
    out = [r["answer"]]
    if r["sources"]:
        out.append("\nFontes: " + "; ".join(f"{s['id']} {s['titulo']}" for s in r["sources"]))
    if r["next_steps"]:
        out.append("\nPróximos passos:\n" + "\n".join(f"  {i}. {t}" for i, t in enumerate(r["next_steps"], 1)))
    for w in r["warnings"]:
        out.append(f"\n[aviso] {w}")
    out.append(f"\n(intenção={r['intent']} confiança={r['confidence']} provedor={r['provider']} {r['latency_ms']}ms)")
    return "\n".join(out)


async def _run(questions: list[str]) -> None:
    s = dataclasses.replace(Settings.from_env(), role="all", bus_backend="memory",
                            audit_dir=Path(tempfile.mkdtemp(prefix="aegis-cli-")))
    rt = build_runtime(s)
    await rt.bus.start()
    try:
        if questions:
            for q in questions:
                print(render(await rt.pipeline.ask(q, "cli", "aluno")))
        else:
            print("Aegis — digite sua pergunta (Ctrl+D para sair).")
            loop = asyncio.get_running_loop()
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                if line.strip():
                    print(render(await rt.pipeline.ask(line.strip(), "cli", "aluno")), "\n")
    finally:
        await rt.bus.stop()


def main() -> None:
    asyncio.run(_run(sys.argv[1:]))


if __name__ == "__main__":
    main()
