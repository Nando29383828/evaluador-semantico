import math
import unittest

from logic import *
from vizcore import circle_layout, curve, loop_arc, vistas, describe, decisive, paint

LEQ = "\n".join(f"L({a},{b})" for a in "012" for b in "012" if a <= b)
SUCC = "c = 0\ns(0)=1\ns(1)=2\ns(2)=0\nP(1)\nP(2)\n" + LEQ
FUNCS, PREDS = {"s": 1, "c": 0}, {"L": 2, "P": 1}
I, errs = build_interp(FUNCS, PREDS, "0,1,2", SUCC)
assert not errs


class FakeCanvas:
    def __init__(self):
        self.items = []

    def delete(self, *a):
        self.items = []

    def __getattr__(self, name):
        if name.startswith("create_"):
            def f(*a, **k):
                self.items.append((name[7:], a, k))
                return len(self.items)
            return f
        raise AttributeError(name)

    def count(self, kind, **match):
        return sum(1 for k, a, kw in self.items
                   if k == kind and all(kw.get(x) == y for x, y in match.items()))


def evalua(formula, env=""):
    f = parse_formula(formula, FUNCS, PREDS)
    e, errs, _ = parse_env(env, free_vars(f), I)
    assert not errs
    return evaluate(f, I, e)


class Geometria(unittest.TestCase):
    def test_layout_en_circulo(self):
        pts = circle_layout(5, 100, 100, 50)
        for x, y in pts:
            self.assertAlmostEqual(math.hypot(x - 100, y - 100), 50)
        self.assertEqual(circle_layout(1, 10, 20, 50), [(10, 20)])

    def test_curva_recortada_y_lados_opuestos(self):
        p, q = (0, 0), (100, 0)
        s, m, e = curve(p, q, 20)
        self.assertAlmostEqual(math.hypot(s[0] - p[0], s[1] - p[1]), 20)
        self.assertAlmostEqual(math.hypot(e[0] - q[0], e[1] - q[1]), 20)
        _, m2, _ = curve(q, p, 20)
        self.assertGreater(m[1] * m2[1] * -1, 0)   # a->b y b->a se curvan en lados opuestos

    def test_bucle_hacia_afuera(self):
        bbox, start, ext = loop_arc((100, 20), (100, 100), 20)  # nodo arriba del centro
        self.assertLess((bbox[1] + bbox[3]) / 2, 20)            # el bucle queda más arriba
        self.assertEqual(ext, 290)


class Datos(unittest.TestCase):
    def test_vistas(self):
        self.assertEqual(vistas(I), {"L (relación binaria)": ("rel", "L"), "s (función unaria)": ("fun", "s")})

    def test_describe(self):
        d = describe(I)
        self.assertIn("Dominio: {0, 1, 2}", d)
        self.assertIn("Constantes: c = 0", d)
        self.assertIn("Función s: 0→1, 1→2, 2→0", d)
        self.assertIn("Predicado P = {1, 2}", d)
        self.assertIn("(0, 1)", d)

    def test_decisive_testigo_y_contraejemplo(self):
        atoms, picks = decisive(evalua("∃x P(x)"))
        self.assertIn((("P", ("1",)), True), atoms)
        self.assertEqual(picks, {"1"})
        atoms, picks = decisive(evalua("∀x P(x)"))
        self.assertEqual(atoms, [(("P", ("0",)), False)])    # contraejemplo x=0
        self.assertEqual(picks, {"0"})


class Dibujo(unittest.TestCase):
    def test_relacion_basica(self):
        c = FakeCanvas()
        paint(c, 700, 560, I, ("rel", "L"))
        self.assertEqual(c.count("arc"), 3)        # bucles (0,0), (1,1), (2,2)
        self.assertEqual(c.count("line"), 3)       # (0,1), (0,2), (1,2)
        self.assertGreaterEqual(c.count("oval"), 3)
        self.assertGreaterEqual(c.count("text"), 3 + 2)  # nombres + etiquetas (P, c)

    def test_funcion(self):
        c = FakeCanvas()
        paint(c, 700, 560, I, ("fun", "s"))
        self.assertEqual(c.count("line"), 3)       # 0->1, 1->2, 2->0
        self.assertEqual(c.count("arc"), 0)

    def test_evidencia_en_aristas(self):
        # ∃x ∀y L(x,y): testigo x=0; aristas (0,0),(0,1),(0,2) verdes
        atoms, picks = decisive(evalua("∃x ∀y L(x,y)"))
        c = FakeCanvas()
        paint(c, 700, 560, I, ("rel", "L"), atoms, picks)
        verdes = c.count("line", fill="#66bb6a") + c.count("arc", outline="#66bb6a")
        self.assertEqual(verdes, 3)
        self.assertEqual(c.count("oval", outline="#ffa726"), 1)   # solo el testigo

    def test_evidencia_de_tupla_ausente(self):
        # ∀x ∀y L(x,y): contraejemplo (1,0) no está en L -> flecha roja discontinua
        atoms, picks = decisive(evalua("∀x ∀y L(x,y)"))
        c = FakeCanvas()
        paint(c, 700, 560, I, ("rel", "L"), atoms, picks)
        self.assertEqual(c.count("line", fill="#ef5350"), 1)
        self.assertEqual(c.count("oval", outline="#ffa726"), 2)   # x=1 y y=0

    def test_sin_resaltar_y_sin_vista(self):
        atoms, picks = decisive(evalua("∃x P(x)"))
        c = FakeCanvas()
        paint(c, 700, 560, I, ("rel", "L"), atoms, picks, resaltar=False)
        self.assertEqual(c.count("oval", outline="#ffa726"), 0)
        paint(c, 700, 560, I, None, atoms, picks)                 # sin vista: solo nodos
        self.assertEqual(c.count("line") + c.count("arc"), 0)
        self.assertEqual(c.count("oval", outline="#ffa726"), 1)

    def test_dominio_de_un_elemento_y_grande(self):
        I1, e = build_interp({}, {"R": 2}, "a", "R(a,a)")
        c = FakeCanvas()
        paint(c, 700, 560, I1, ("rel", "R"))
        self.assertEqual(c.count("arc"), 1)
        dom = ",".join(f"e{i}" for i in range(30))
        tuplas = "\n".join(f"R(e{i},e{(i + 1) % 30})" for i in range(30))
        I2, e = build_interp({}, {"R": 2}, dom, tuplas)
        paint(c, 700, 560, I2, ("rel", "R"))
        self.assertEqual(c.count("line"), 30)


if __name__ == "__main__":
    unittest.main()
