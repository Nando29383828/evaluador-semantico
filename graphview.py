"""Ventana de visualización de la interpretación (usa vizcore para dibujar)."""
import traceback
import tkinter as tk
from tkinter import ttk

from vizcore import vistas, describe, decisive, paint

LEYENDA = ("Azul: tupla de la relación · Morado: f(a) de una función · "
           "Verde grueso: tupla que SÍ está y es evidencia · Rojo discontinuo: tupla que NO está y es evidencia · "
           "Aro naranja: elemento elegido (testigo / contraejemplo / jugada)")


class GraphWindow(tk.Toplevel):
    def __init__(self, master, I, nodo=None):
        super().__init__(master)
        self.title("Visualización de la interpretación")
        alto = max(560, min(860, self.winfo_screenheight() - 140))
        self.geometry(f"780x{alto}")
        self.I = I
        self.atoms, self.picks = decisive(nodo) if nodo is not None else ([], set())
        self.vistas = vistas(I)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ttk.Label(top, text="Mostrar:").pack(side="left")
        self.cb = ttk.Combobox(top, values=list(self.vistas), state="readonly", width=28)
        self.cb.pack(side="left", padx=6)
        if self.vistas:
            self.cb.current(0)
        else:
            ttk.Label(top, text="(no hay relaciones binarias ni funciones unarias que dibujar)").pack(side="left")
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.dibujar())
        self.hl = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Resaltar evidencia", variable=self.hl, command=self.dibujar).pack(side="right")
        ttk.Button(top, text="↻ Redibujar", command=self.dibujar).pack(side="right", padx=6)

        self.canvas = tk.Canvas(self, bg="#1e1e1e", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10)
        self.canvas.bind("<Configure>", lambda e: self.dibujar())

        ttk.Label(self, text=LEYENDA, wraplength=740, foreground="#888").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        txt = tk.Text(self, height=9, font=("Courier New", 11), wrap="word")
        txt.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        txt.insert("1.0", describe(I))
        txt.config(state="disabled")

        # En macOS la ventana nueva a veces queda detrás y sin tamaño al dibujar:
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.after(80, self.dibujar)
        self.after(400, self.dibujar)

    def vista(self):
        return self.vistas.get(self.cb.get())

    def dibujar(self):
        W, H = self.canvas.winfo_width(), self.canvas.winfo_height()
        if W < 100 or H < 100:      # aún sin tamaño real: usar uno por defecto
            W, H = 740, 520
        try:
            paint(self.canvas, W, H, self.I, self.vista(), self.atoms, self.picks, self.hl.get())
        except Exception as e:      # mostrar el error en la propia ventana
            traceback.print_exc()
            self.canvas.delete("all")
            self.canvas.create_text(W / 2, H / 2, fill="#ef5350", width=W - 40,
                                    text=f"Error al dibujar:\n{type(e).__name__}: {e}")

    def resaltar(self, elementos, atomos):
        """Actualiza la evidencia mostrada (la usa el juego en cada jugada)."""
        self.atoms, self.picks = list(atomos), set(elementos)
        self.hl.set(True)
        self.dibujar()
