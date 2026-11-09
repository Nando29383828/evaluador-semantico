import random
import unittest

from logic import *
from game import Game

LEQ = "\n".join(f"L({a},{b})" for a in "012" for b in "012" if a <= b)
SUCC = "c = 0\ns(0)=1\ns(1)=2\ns(2)=0\nP(1)\nP(2)\n" + LEQ
FUNCS, PREDS = {"s": 1, "c": 0}, {"L": 2, "P": 1}
I, errs = build_interp(FUNCS, PREDS, "0,1,2", SUCC)
assert not errs

FORMULAS = [
    ("∀x ∃y L(x,y)", ""), ("∃x ∀y L(x,y)", ""), ("∀x P(x)", ""), ("∃x P(x)", ""),
    ("∀x (P(x) → ∃y L(y,x))", ""), ("∃x ¬L(x,x)", ""), ("∀x ∀y (L(x,y) ↔ L(y,x))", ""),
    ("∀x (L(x,s(x)) ∨ P(x))", ""), ("¬∀x ∃y (L(y,x) ∧ ¬L(x,y))", ""),
    ("P(x) → ∃y L(s(y), x)", "x=2"), ("P(x) ↔ L(x, c)", "x=0"),
    ("∃x (P(x) ∧ ∀y (L(x,y) → P(y)))", ""), ("¬¬P(s(c))", ""),
    ("∀x ¬(P(x) ∧ ¬P(x))", ""), ("∃x ∃y (¬L(x,y) ∧ ¬L(y,x))", ""),
]


def jugar(formula, envtxt, user_verifier, rng, optimo):
    f = parse_formula(formula, FUNCS, PREDS)
    env, e, _ = parse_env(envtxt, free_vars(f), I)
    assert not e
    g = Game(f, I, env, user_verifier)
    pasos = 0
    while g.winner is None:
        if optimo:
            i = g.hint()[0]          # debe existir si estamos del lado ganador
        else:
            i = rng.randrange(len(g.options))
        g.choose(i)
        pasos += 1
        assert pasos < 500
    return g


class Hintikka(unittest.TestCase):
    def test_teorema(self):
        rng = random.Random(7)
        for formula, env in FORMULAS:
            for uv in (True, False):
                g0 = jugar(formula, env, uv, rng, optimo=False)
                gana_lado = g0.user_side_wins()
                if gana_lado:
                    g = jugar(formula, env, uv, rng, optimo=True)
                    self.assertEqual(g.winner, "U", (formula, uv))
                else:
                    for _ in range(25):   # jueguen como jueguen, pierden
                        g = jugar(formula, env, uv, rng, optimo=False)
                        self.assertEqual(g.winner, "C", (formula, uv))

    def test_veredicto_coincide_con_tarski(self):
        for formula, env in FORMULAS:
            f = parse_formula(formula, FUNCS, PREDS)
            e, _, _ = parse_env(env, free_vars(f), I)
            self.assertEqual(Game(f, I, e, True).truth, evaluate(f, I, e).value)

    def test_computadora_empieza_si_le_toca(self):
        f = parse_formula("∃x P(x)", FUNCS, PREDS)
        g = Game(f, I, {}, user_is_verifier=False)   # el usuario falsifica; elige ∃ la CPU
        self.assertIsNotNone(g.winner or True)
        self.assertEqual(g.winner, "C")              # ∃x P(x) es verdadera: gana el Verificador (CPU)


if __name__ == "__main__":
    unittest.main()
