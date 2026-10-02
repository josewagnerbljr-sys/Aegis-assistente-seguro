"""Simulado de segurança no terminal usando data/treinamento/banco_quiz.json."""

import json
import random
from pathlib import Path

bank = json.loads((Path(__file__).resolve().parents[1] / "data/treinamento/banco_quiz.json").read_text(encoding="utf-8"))
random.shuffle(bank)
score = 0
for i, q in enumerate(bank, 1):
    print(f"\n[{i}/{len(bank)}] ({q['categoria']}/{q['nivel']}) {q['pergunta']}")
    for k, opt in zip("ABCD", q["opcoes"], strict=False):
        print(f"  {k}) {opt}")
    ans = input("Resposta: ").strip().upper()[:1]
    ok = "ABCD".find(ans) == q["correta"]
    score += ok
    print(("✔ Correto. " if ok else f"✘ Era {'ABCD'[q['correta']]}. ") + q["explicacao"])
print(f"\nResultado: {score}/{len(bank)} ({100 * score // len(bank)}%)")
