"""Interfaz gráfica del evaluador semántico. Ejecutar:  python app.py"""
import tkinter as tk
from tkinter import ttk

from logic import (LogicError, parse_signature, check_language, build_interp,
                   parse_formula, free_vars, parse_env, evaluate, explain, to_str,
                   Pred, eval_term)
from game import Game, NAME
from graphview import GraphWindow

MONO = ("Courier New", 11)
UI = ("Segoe UI", 10)

EJEMPLOS = {
    "Orden ≤ en {0,1,2}: ∀x ∃y L(x,y)": dict(
        funcs="s/1, c/0", preds="L/2, P/1", dom="0, 1, 2",
        interp="c = 0\ns(0) = 1\ns(1) = 2\ns(2) = 0\nP(1)\nP(2)\n"
               + "\n".join(f"L({a},{b})" for a in "012" for b in "012" if a <= b),
        formula="∀x ∃y L(x,y)", env=""),
    "Fórmula abierta con entorno": dict(
        funcs="s/1, c/0", preds="L/2, P/1", dom="0, 1, 2",
        interp="c = 0\ns(0) = 1\ns(1) = 2\ns(2) = 0\nP(1)\nP(2)\n"
               + "\n".join(f"L({a},{b})" for a in "012" for b in "012" if a <= b),
        formula="P(x) → ∃y L(s(y), x)", env="x = 2"),
    "Universal falso (contraejemplo)": dict(
        funcs="", preds="E/2", dom="a, b, c",
        interp="E(a,b)\nE(b,c)\nE(c,a)",
        formula="∀x ∃y (E(x,y) ∧ E(y,x))", env=""),
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Evaluador semántico — MM3032 Lógica Matemática")
        self.geometry("1250x780")
        self.columnconfigure(0, weight=1, uniform="a")
        self.columnconfigure(1, weight=1, uniform="a")
        self.rowconfigure(0, weight=1)
        self._build_inputs()
        self._build_output()
        self.cargar(next(iter(EJEMPLOS)))

    # ------------------------------------------------------------ UI
    def _build_inputs(self):
        L = ttk.Frame(self, padding=8)
        L.grid(row=0, column=0, sticky="nsew")
        L.columnconfigure(0, weight=1)
        L.rowconfigure(3, weight=1)

        top = ttk.Frame(L)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Ejemplo:", font=UI).pack(side="left")
        self.cb = ttk.Combobox(top, values=list(EJEMPLOS), state="readonly", width=45)
        self.cb.pack(side="left", padx=6)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.cargar(self.cb.get()))

        # 1. Lenguaje
        g = ttk.LabelFrame(L, text=" 1. Lenguaje (nombre/aridad, separados por coma) ", padding=6)
        g.grid(row=1, column=0, sticky="ew", pady=4)
        g.columnconfigure(1, weight=1)
        ttk.Label(g, text="Funciones:").grid(row=0, column=0, sticky="w")
        self.e_funcs = ttk.Entry(g, font=MONO)
        self.e_funcs.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(g, text="Predicados:").grid(row=1, column=0, sticky="w")
        self.e_preds = ttk.Entry(g, font=MONO)
        self.e_preds.grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Label(g, text="(constantes = funciones de aridad 0, ej. c/0)",
                  foreground="#666").grid(row=2, column=1, sticky="w")

        # 2. Interpretación
        g = ttk.LabelFrame(L, text=" 2. Interpretación ", padding=6)
        g.grid(row=2, column=0, rowspan=2, sticky="nsew", pady=4)
        g.columnconfigure(0, weight=1)
        g.rowconfigure(2, weight=1)
        ttk.Label(g, text="Dominio (elementos separados por coma):").grid(row=0, column=0, sticky="w")
        self.e_dom = ttk.Entry(g, font=MONO)
        self.e_dom.grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Label(g, text="Funciones:  f(a,b) = c   (constantes: c = a)      Relaciones:  R(a,b)   (aridad 0: S)      # comentario",
                  foreground="#666").grid(row=2, column=0, sticky="nw")
        self.t_interp = tk.Text(g, font=MONO, height=10, undo=True)
        self.t_interp.grid(row=3, column=0, sticky="nsew")
        g.rowconfigure(3, weight=1)
        g.rowconfigure(2, weight=0)

        # 3. Fórmula
        g = ttk.LabelFrame(L, text=" 3. Fórmula ", padding=6)
        g.grid(row=4, column=0, sticky="ew", pady=4)
        g.columnconfigure(0, weight=1)
        self.e_form = ttk.Entry(g, font=("Courier New", 14))
        self.e_form.grid(row=0, column=0, sticky="ew", pady=2)
        self.e_form.bind("<KeyRelease>", lambda e: self.actualizar_libres())
        self.e_form.bind("<Return>", lambda e: self.evaluar())
        bar = ttk.Frame(g)
        bar.grid(row=1, column=0, sticky="w", pady=2)
        for s in ["¬", "∧", "∨", "→", "↔", "∀", "∃", "(", ")", ","]:
            ttk.Button(bar, text=s, width=3, takefocus=False,
                       command=lambda s=s: self.insertar(s)).pack(side="left", padx=1)
        ttk.Button(bar, text="⌫", width=3, takefocus=False, command=self.borrar).pack(side="left", padx=(8, 1))
        ttk.Button(bar, text="Limpiar", takefocus=False,
                   command=lambda: (self.e_form.delete(0, "end"), self.actualizar_libres())).pack(side="left", padx=1)
        ttk.Label(g, text="Teclado también: ! & | -> <-> forall exists", foreground="#666").grid(row=2, column=0, sticky="w")

        # 4. Entorno
        g = ttk.LabelFrame(L, text=" 4. Entorno (valores de las variables libres) ", padding=6)
        g.grid(row=5, column=0, sticky="ew", pady=4)
        g.columnconfigure(0, weight=1)
        self.lbl_libres = ttk.Label(g, text="Variables libres: —", font=UI)
        self.lbl_libres.grid(row=0, column=0, sticky="w")
        self.e_env = ttk.Entry(g, font=MONO)
        self.e_env.grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Label(g, text="formato:  x = a, y = b", foreground="#666").grid(row=2, column=0, sticky="w")

        bt = ttk.Frame(L)
        bt.grid(row=6, column=0, sticky="ew", pady=6)
        bt.columnconfigure(0, weight=1)
        bt.columnconfigure(1, weight=1)
        bt.columnconfigure(2, weight=1)
        ttk.Button(bt, text="▶  Evaluar", command=self.evaluar).grid(row=0, column=0, sticky="ew", padx=(0, 3), ipady=6)
        ttk.Button(bt, text="🎲  Jugar (Hintikka)", command=self.jugar).grid(row=0, column=1, sticky="ew", padx=3, ipady=6)
        ttk.Button(bt, text="🕸  Ver grafos", command=self.grafos).grid(row=0, column=2, sticky="ew", padx=(3, 0), ipady=6)

    def _build_output(self):
        R = ttk.Frame(self, padding=8)
        R.grid(row=0, column=1, sticky="nsew")
        R.columnconfigure(0, weight=1)
        R.rowconfigure(2, weight=1)
        R.rowconfigure(4, weight=2)
        self.lbl_res = tk.Label(R, text="Resultado", font=("Segoe UI", 22, "bold"),
                                bg="#eeeeee", fg="#555", pady=10)
        self.lbl_res.grid(row=0, column=0, sticky="ew")
        ttk.Label(R, text="Razones decisivas", font=UI).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.t_out = tk.Text(R, font=MONO, wrap="word", state="disabled")
        self.t_out.grid(row=2, column=0, sticky="nsew")
        self.t_out.tag_config("err", foreground="#b00020")
        self.t_out.tag_config("warn", foreground="#8a6d00")
        self.t_out.tag_config("ok", foreground="#1b7f3b")
        self.t_out.tag_config("ko", foreground="#b00020")
        ttk.Label(R, text="Árbol de evaluación completo (doble clic para expandir)", font=UI).grid(row=3, column=0, sticky="w", pady=(8, 0))
        fr = ttk.Frame(R)
        fr.grid(row=4, column=0, sticky="nsew")
        fr.columnconfigure(0, weight=1)
        fr.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(fr, show="tree")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(fr, command=self.tree.yview)
        sy.grid(row=0, column=1, sticky="ns")
        sx = ttk.Scrollbar(fr, orient="horizontal", command=self.tree.xview)
        sx.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.column("#0", width=900, stretch=False)
        self.tree.tag_configure("ok", foreground="#1b7f3b")
        self.tree.tag_configure("ko", foreground="#b00020")

    # ------------------------------------------------------ acciones
    def insertar(self, s):
        self.e_form.insert(self.e_form.index(tk.INSERT), s)
        self.e_form.focus_set()
        self.actualizar_libres()

    def borrar(self):
        i = self.e_form.index(tk.INSERT)
        if i > 0:
            self.e_form.delete(i - 1)
        self.e_form.focus_set()
        self.actualizar_libres()

    def cargar(self, nombre):
        ex = EJEMPLOS[nombre]
        self.cb.set(nombre)
        for w, k in ((self.e_funcs, "funcs"), (self.e_preds, "preds"), (self.e_dom, "dom"),
                     (self.e_form, "formula"), (self.e_env, "env")):
            w.delete(0, "end")
            w.insert(0, ex[k])
        self.t_interp.delete("1.0", "end")
        self.t_interp.insert("1.0", ex["interp"])
        self.actualizar_libres()

    def lenguaje(self):
        funcs = parse_signature(self.e_funcs.get(), "Funciones")
        preds = parse_signature(self.e_preds.get(), "Predicados")
        check_language(funcs, preds)
        return funcs, preds

    def actualizar_libres(self):
        try:
            funcs, preds = self.lenguaje()
            f = parse_formula(self.e_form.get(), funcs, preds)
            fv = sorted(free_vars(f))
            self.lbl_libres.config(
                text="Variables libres: " + (", ".join(fv) if fv else "ninguna (fórmula cerrada)"),
                foreground="#000")
        except LogicError:
            self.lbl_libres.config(text="Variables libres: (la fórmula aún no es válida)", foreground="#888")

    def escribir(self, txt, tag=None):
        self.t_out.config(state="normal")
        self.t_out.insert("end", txt + "\n", tag)
        self.t_out.config(state="disabled")

    def invalido(self, titulo, errores, formula=None, err=None):
        self.lbl_res.config(text="ENTRADA INVÁLIDA — sin valor de verdad", bg="#ffe0b2", fg="#8a4b00",
                            font=("Segoe UI", 16, "bold"))
        self.escribir(titulo, "err")
        for e in errores:
            self.escribir("  • " + e, "err")
        if formula is not None and err is not None and err.pos is not None:
            self.escribir("")
            self.escribir("  " + formula, None)
            self.escribir("  " + " " * err.pos + "^" * max(1, err.length), "err")

    def _leer(self):
        """Valida todas las entradas. Devuelve (f, I, env, avisos) o None si hay errores."""
        self.t_out.config(state="normal")
        self.t_out.delete("1.0", "end")
        self.t_out.config(state="disabled")
        self.tree.delete(*self.tree.get_children())
        try:
            funcs, preds = self.lenguaje()
        except LogicError as e:
            return self.invalido("Error en el lenguaje:", [e.msg])
        I, errs = build_interp(funcs, preds, self.e_dom.get(), self.t_interp.get("1.0", "end"))
        if errs:
            return self.invalido("Error en la interpretación:", errs)
        ftxt = self.e_form.get()
        try:
            f = parse_formula(ftxt, funcs, preds)
        except LogicError as e:
            col = f" (columna {e.pos + 1})" if e.pos is not None else ""
            return self.invalido("Error de sintaxis en la fórmula:", [e.msg + col], ftxt, e)
        env, errs, avisos = parse_env(self.e_env.get(), free_vars(f), I)
        if errs:
            return self.invalido("Error en el entorno:", errs)
        return f, I, env, avisos

    def jugar(self):
        datos = self._leer()
        if datos is not None:
            f, I, env, _ = datos
            GameWindow(self, f, I, env)

    def grafos(self):
        """Evalúa y abre la visualización de la interpretación con la evidencia resaltada."""
        self.evaluar()
        if self.ultimo is not None:
            I, nodo = self.ultimo
            try:
                GraphWindow(self, I, nodo)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.escribir(f"No se pudo abrir el grafo: {type(e).__name__}: {e}", "err")

    def evaluar(self):
        self.ultimo = None
        datos = self._leer()
        if datos is None:
            return
        f, I, env, avisos = datos
        nodo = evaluate(f, I, env)
        self.ultimo = (I, nodo)
        if nodo.value:
            self.lbl_res.config(text="VERDADERO", bg="#c8e6c9", fg="#1b5e20", font=("Segoe UI", 22, "bold"))
        else:
            self.lbl_res.config(text="FALSO", bg="#ffcdd2", fg="#b71c1c", font=("Segoe UI", 22, "bold"))
        for a in avisos:
            self.escribir("Aviso: " + a, "warn")
        if env:
            self.escribir("Entorno: " + ", ".join(f"{k} = {v}" for k, v in sorted(env.items())))
        for ln in explain(nodo):
            self.escribir(ln, "ok" if ln.lstrip().startswith("✔") else "ko")
        self.poblar(nodo, "", 0)

    def poblar(self, n, parent, depth):
        txt = f"{'✔' if n.value else '✘'} {n.label}    —  {n.why}"
        iid = self.tree.insert(parent, "end", text=txt, open=depth < 2, tags=("ok" if n.value else "ko",))
        for c in n.children:
            self.poblar(c, iid, depth + 1)


class GameWindow(tk.Toplevel):
    """Juego de evaluación de Hintikka contra la computadora."""

    def __init__(self, master, f, I, env):
        super().__init__(master)
        self.title("Juego de Hintikka")
        self.geometry("820x700")
        self.f, self.I, self.env = f, I, env
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        ttk.Label(self, text="Fórmula: " + to_str(f) + ("    [" + ", ".join(f"{k}={v}" for k, v in sorted(env.items())) + "]" if env else ""),
                  font=("Courier New", 13, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))

        top = ttk.Frame(self)
        top.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self.rol = tk.StringVar(value="V")
        ttk.Radiobutton(top, text="Soy el VERIFICADOR (la fórmula es verdadera)", variable=self.rol, value="V").pack(side="left")
        ttk.Radiobutton(top, text="Soy el FALSIFICADOR (la fórmula es falsa)", variable=self.rol, value="F").pack(side="left", padx=10)
        ttk.Button(top, text="↻ Nueva partida", command=self.nueva).pack(side="right")
        ttk.Button(top, text="🕸 Grafo", command=self.abrir_grafo).pack(side="right", padx=6)
        self.graph = None

        self.lbl_pos = tk.Label(self, text="", font=("Courier New", 13), anchor="w", justify="left",
                                bg="#37474f", fg="#ffffff", padx=10, pady=8, wraplength=780)
        self.lbl_pos.grid(row=2, column=0, sticky="ew", padx=10, pady=4)

        self.fr = ttk.LabelFrame(self, text=" Tu jugada ", padding=8)
        self.fr.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        self.lbl_prompt = ttk.Label(self.fr, text="", wraplength=760)
        self.lbl_prompt.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        self.fr_btn = ttk.Frame(self.fr)
        self.fr_btn.grid(row=1, column=0, columnspan=4, sticky="ew")
        self.lbl_hint = ttk.Label(self.fr, text="", foreground="#8a6d00", wraplength=760)
        self.lbl_hint.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.btn_hint = ttk.Button(self.fr, text="💡 Pista", command=self.pista)
        self.btn_hint.grid(row=2, column=0, sticky="w", pady=(6, 0))

        self.lbl_fin = tk.Label(self, text="", font=("Segoe UI", 16, "bold"), pady=6)
        self.lbl_fin.grid(row=4, column=0, sticky="ew", padx=10)

        fr = ttk.Frame(self)
        fr.grid(row=5, column=0, sticky="nsew", padx=10, pady=(4, 10))
        fr.columnconfigure(0, weight=1)
        fr.rowconfigure(0, weight=1)
        self.t_log = tk.Text(fr, font=("Courier New", 11), wrap="word", state="disabled")
        self.t_log.grid(row=0, column=0, sticky="nsew")
        sc = ttk.Scrollbar(fr, command=self.t_log.yview)
        sc.grid(row=0, column=1, sticky="ns")
        self.t_log.configure(yscrollcommand=sc.set)
        self.t_log.tag_config("u", foreground="#4fc3f7")
        self.t_log.tag_config("c", foreground="#ffb74d")
        self.t_log.tag_config("fin", foreground="#81c784", font=("Courier New", 11, "bold"))
        self.t_log.tag_config("sys", foreground="#bbbbbb")
        self.nueva()

    def nueva(self):
        self.game = Game(self.f, self.I, self.env, self.rol.get() == "V")
        self.leidas = 0
        self.t_log.config(state="normal")
        self.t_log.delete("1.0", "end")
        self.t_log.config(state="disabled")
        self.refrescar()

    def refrescar(self):
        g = self.game
        self.t_log.config(state="normal")
        for txt, tag in g.lines[self.leidas:]:
            self.t_log.insert("end", txt + "\n", tag)
        self.leidas = len(g.lines)
        self.t_log.see("end")
        self.t_log.config(state="disabled")
        for w in self.fr_btn.winfo_children():
            w.destroy()
        self.lbl_hint.config(text="")
        fs, es, ver = g.current()
        self.lbl_pos.config(text=f"Posición: {fs}" + (f"   [{es}]" if es else "") + f"\nVerificador: {NAME[ver]}")
        if g.winner is not None:
            gano = g.winner == "U"
            self.lbl_fin.config(text="¡GANASTE!" if gano else "PERDISTE",
                                bg="#c8e6c9" if gano else "#ffcdd2", fg="#1b5e20" if gano else "#b71c1c")
            self.lbl_prompt.config(text=g.conclusion())
            self.btn_hint.state(["disabled"])
            self.actualizar_grafo()
            return
        self.lbl_fin.config(text="", bg=self.cget("bg"))
        self.btn_hint.state(["!disabled"])
        self.lbl_prompt.config(text=g.prompt)
        for i, o in enumerate(g.options):
            ttk.Button(self.fr_btn, text=o.label, command=lambda i=i: self.jugar(i)).grid(
                row=i // 4, column=i % 4, padx=3, pady=3, sticky="ew")
        self.actualizar_grafo()

    def jugar(self, i):
        self.game.choose(i)
        self.refrescar()

    def abrir_grafo(self):
        if self.graph is None or not self.graph.winfo_exists():
            self.graph = GraphWindow(self, self.I)
        self.actualizar_grafo()

    def actualizar_grafo(self):
        """Resalta en el grafo los elementos elegidos hasta ahora y, al terminar, el átomo decisivo."""
        gw = self.graph
        if gw is None or not gw.winfo_exists():
            return
        f, env, _ = self.game.state
        atomos = []
        if self.game.winner is not None and isinstance(f, Pred):
            vals = tuple(eval_term(a, self.I, env) for a in f.args)
            atomos = [((f.name, vals), vals in self.I.rels[f.name])]
        gw.resaltar(set(env.values()), atomos)

    def pista(self):
        g = self.game
        win = g.hint()
        if win:
            self.lbl_hint.config(text="Una jugada ganadora: «" + g.options[win[0]].label + "»")
        else:
            self.lbl_hint.config(text="Ninguna jugada gana: con juego óptimo de la computadora ya no puedes ganar "
                                      "(esa es la lectura de que la fórmula juega a favor del otro bando).")


if __name__ == "__main__":
    App().mainloop()
