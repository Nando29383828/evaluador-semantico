import unittest
from logic import *

LEQ = "\n".join(f"L({a},{b})" for a in "012" for b in "012" if a <= b)
SUCC = "c = 0\ns(0)=1\ns(1)=2\ns(2)=0\nP(1)\nP(2)\n" + LEQ
FUNCS, PREDS = {"s": 1, "c": 0}, {"L": 2, "P": 1}


def run(formula, env=""):
    I, errs = build_interp(FUNCS, PREDS, "0,1,2", SUCC)
    assert not errs, errs
    f = parse_formula(formula, FUNCS, PREDS)
    e, errs, _ = parse_env(env, free_vars(f), I)
    assert not errs, errs
    return evaluate(f, I, e)


class Semantica(unittest.TestCase):
    def test_cuantificadores(self):
        self.assertTrue(run("∀x ∃y L(x,y)").value)
        self.assertTrue(run("∃x ∀y L(x,y)").value)          # x=0
        self.assertFalse(run("∀x ∃y (L(y,x) ∧ ¬L(x,y))").value)  # x=0 falla
        self.assertFalse(run("∃x ¬L(x,x)").value)

    def test_testigo_y_contraejemplo(self):
        self.assertIn("testigo: x = 1", run("∃x P(x)").why)
        self.assertIn("contraejemplo: x = 0", run("∀x P(x)").why)
        self.assertIn("3 elementos", run("∀x L(x,x)").why)
        self.assertIn("ninguno", run("∃x ¬L(x,x)").why)

    def test_funciones_y_constantes(self):
        self.assertTrue(run("L(c, s(c))").value)             # 0 <= 1
        self.assertTrue(run("L(s(s(s(c))), s(c))").value)    # s^3(0)=0 <= 1
        # s(s(c)) = 2, c = 0  ->  L(2,0) falso
        self.assertFalse(run("L(s(s(c)), c)").value)

    def test_formula_abierta(self):
        self.assertTrue(run("P(x) → L(x, s(y))", "x=1, y=2").value is False)
        self.assertTrue(run("P(x)", "x=2").value)

    def test_variable_ligada_y_libre(self):
        f = parse_formula("P(x) ∧ ∀x L(x,x)", FUNCS, PREDS)
        self.assertEqual(free_vars(f), {"x"})
        self.assertEqual(free_vars(parse_formula("∀x ∃x P(x)", FUNCS, PREDS)), set())
        self.assertTrue(run("∀z P(c) ∨ ¬P(c)").value)         # var. no usada

    def test_conectivos_y_alias(self):
        self.assertTrue(run("P(s(c)) <-> !P(c)").value)
        self.assertTrue(run("forall x (L(x,x) & (P(x) | !P(x)))").value)
        self.assertTrue(run("P(c) -> P(c)").value)  # F->F

    def test_precedencia(self):
        f = parse_formula("P(c) → P(c) → P(c)", FUNCS, PREDS)   # asoc. derecha
        self.assertEqual(f.r.op, "→")
        f = parse_formula("¬P(c) ∧ P(c) ∨ P(c)", FUNCS, PREDS)
        self.assertEqual(f.op, "∨")


class Validacion(unittest.TestCase):
    def err(self, text):
        with self.assertRaises(LogicError) as cm:
            parse_formula(text, FUNCS, PREDS)
        return cm.exception.msg

    def test_sintaxis(self):
        self.assertIn("paréntesis", self.err("∀x (P(x)"))
        self.assertIn("no declarado", self.err("Q(x)"))
        self.assertIn("aridad 2", self.err("L(x)"))
        self.assertIn("aridad 1", self.err("P(x,y)"))
        self.assertIn("predicado", self.err("P(P(x))"))
        self.assertIn("término", self.err("s(x)"))
        self.assertIn("vacía", self.err("   "))
        self.assertIn("inesperado", self.err("P(x) P(y)"))
        self.assertIn("variable", self.err("∀ P(x)"))
        self.assertIn("carácter", self.err("P(x) $ P(y)"))

    def test_interpretacion(self):
        def bad(dom, txt):
            I, errs = build_interp(FUNCS, PREDS, dom, txt)
            self.assertIsNone(I)
            return " | ".join(errs)
        self.assertIn("vacío", bad("", SUCC))
        self.assertIn("repetidos", bad("0,1,1", SUCC))
        self.assertIn("total", bad("0,1,2", SUCC.replace("s(2)=0\n", "")))
        self.assertIn("vacía", bad("0,1,2", SUCC.replace("P(1)\nP(2)\n", "")))
        self.assertIn("no pertenece", bad("0,1,2", SUCC + "\nP(9)"))
        self.assertIn("contradicción", bad("0,1,2", SUCC + "\ns(0)=2"))
        self.assertIn("aridad", bad("0,1,2", SUCC + "\nL(0)"))
        self.assertIn("no declarado", bad("0,1,2", SUCC + "\nZ(0)"))

    def test_entorno(self):
        I, _ = build_interp(FUNCS, PREDS, "0,1,2", SUCC)
        _, errs, _ = parse_env("", {"x"}, I)
        self.assertTrue(any("falta" in e for e in errs))
        _, errs, _ = parse_env("x=7", {"x"}, I)
        self.assertTrue(any("dominio" in e for e in errs))

    def test_predicado_0ario(self):
        I, errs = build_interp({}, {"S": 0}, "a", "S")
        self.assertFalse(errs)
        f = parse_formula("S ∧ S()", {}, {"S": 0})
        self.assertTrue(evaluate(f, I, {}).value)


if __name__ == "__main__":
    unittest.main()
