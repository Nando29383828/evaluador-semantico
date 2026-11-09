"""Prueba aislada de la visualización: abre SOLO la ventana del grafo.
Ejecutar:  python3 probar_grafo.py
Si aquí se ve el grafo, la visualización funciona y el problema está en cómo
se llama desde app.py. Si aquí NO se ve, copie el mensaje de la Terminal."""
import tkinter as tk

from logic import parse_formula, free_vars, parse_env, build_interp, evaluate
from graphview import GraphWindow

FUNCS, PREDS = {"s": 1, "c": 0}, {"L": 2, "P": 1}
LEQ = "\n".join(f"L({a},{b})" for a in "012" for b in "012" if a <= b)
I, errs = build_interp(FUNCS, PREDS, "0,1,2", "c = 0\ns(0)=1\ns(1)=2\ns(2)=0\nP(1)\nP(2)\n" + LEQ)
assert not errs, errs
f = parse_formula("∃x ∀y L(x,y)", FUNCS, PREDS)
nodo = evaluate(f, I, {})

root = tk.Tk()
root.title("Prueba")
tk.Label(root, text="Ventana principal de prueba.\nDebe abrirse otra con el grafo.\nCierre esta para terminar.",
         padx=30, pady=30).pack()
GraphWindow(root, I, nodo)
root.mainloop()
