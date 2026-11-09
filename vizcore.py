"""Visualización de una interpretación finita como grafo.

Este módulo no importa Tkinter: `paint` solo llama métodos de un objeto con
la interfaz de tk.Canvas (create_oval, create_line, create_arc, create_text),
de modo que se puede probar con un canvas falso.

Qué se dibuja:
  * elementos del dominio como nodos en círculo;
  * una relación binaria R como flechas a -> b para cada (a, b) ∈ Rᴵ;
  * una función unaria f como flechas a -> f(a) (en otro color);
  * junto a cada nodo, los predicados unarios que cumple y las constantes que nombra;
  * la evidencia de una evaluación: tuplas decisivas (verde si están, rojo
    discontinuo si NO están) y los elementos elegidos por los cuantificadores
    (testigo / contraejemplo) con aro naranja.
"""
import math


# ------------------------------------------------------------ geometría
def circle_layout(n, cx, cy, r):
    if n == 1:
        return [(cx, cy)]
    return [(cx + r * math.cos(-math.pi / 2 + 2 * math.pi * i / n),
             cy + r * math.sin(-math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)]


def curve(p, q, node_r, bend=0.18):
    """(inicio, control, fin) de una flecha curva p -> q recortada por el radio
    de los nodos. Las flechas a->b y b->a se curvan hacia lados opuestos."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / d, dx / d
    ctrl = ((p[0] + q[0]) / 2 + nx * bend * d, (p[1] + q[1]) / 2 + ny * bend * d)

    def trim(a, toward):
        vx, vy = toward[0] - a[0], toward[1] - a[1]
        l = math.hypot(vx, vy) or 1.0
        return (a[0] + vx / l * node_r, a[1] + vy / l * node_r)

    return trim(p, ctrl), ctrl, trim(q, ctrl)


def loop_arc(c, center, node_r, loop_r=14):
    """(bbox, inicio, extensión) de un arco-bucle sobre el nodo c, hacia afuera."""
    dx, dy = c[0] - center[0], c[1] - center[1]
    d = math.hypot(dx, dy)
    ux, uy = (dx / d, dy / d) if d > 1e-9 else (0.0, -1.0)
    lc = (c[0] + ux * (node_r + 0.6 * loop_r), c[1] + uy * (node_r + 0.6 * loop_r))
    to_node = math.degrees(math.atan2(-(c[1] - lc[1]), c[0] - lc[0]))  # y de pantalla hacia abajo
    return (lc[0] - loop_r, lc[1] - loop_r, lc[0] + loop_r, lc[1] + loop_r), to_node + 35, 290


# ------------------------------------------------------------ datos
def vistas(I):
    """Vistas dibujables: {'R (relación binaria)': ('rel','R'), ...}"""
    out = {}
    for n, ts in I.rels.items():
        if ts and len(next(iter(ts))) == 2:
            out[f"{n} (relación binaria)"] = ("rel", n)
    for n, tab in I.funcs.items():
        if tab and len(next(iter(tab))) == 1:
            out[f"{n} (función unaria)"] = ("fun", n)
    return out


def describe(I):
    """Texto con la interpretación completa (tablas de funciones y relaciones)."""
    L = ["Dominio: {" + ", ".join(I.domain) + "}"]
    ctes = [f"{n} = {tab[()]}" for n, tab in I.funcs.items() if () in tab]
    if ctes:
        L.append("Constantes: " + ", ".join(ctes))
    for n, tab in I.funcs.items():
        if () in tab:
            continue
        ar = len(next(iter(tab)))
        if ar == 1:
            body = ", ".join(f"{a[0]}→{v}" for a, v in tab.items())
        else:
            body = ", ".join(f"{n}({', '.join(a)})={v}" for a, v in tab.items())
        L.append(f"Función {n}: {body}")
    for n, ts in I.rels.items():
        ar = len(next(iter(ts)))
        if ar == 0:
            L.append(f"Predicado {n}: verdadero (aridad 0)")
        elif ar == 1:
            L.append(f"Predicado {n} = {{" + ", ".join(sorted(t[0] for t in ts)) + "}")
        else:
            L.append(f"Relación {n} = {{" + ", ".join("(" + ", ".join(t) + ")" for t in sorted(ts)) + "}")
    return "\n".join(L)


def decisive(node):
    """(átomos decisivos [((pred, tupla), valor)], elementos elegidos).

    Un elemento cuenta como "elegido" solo si es EL testigo o EL contraejemplo
    (el cuantificador tiene un único hijo decisivo). Cuando la evidencia es la
    comprobación completa del dominio, no se marca ningún elemento en particular.
    """
    atoms, picks = [], []

    def go(n):
        if n.atom:
            atoms.append((n.atom, n.value))
        unico = len(n.key) == 1
        for k in n.key:
            if k.pick and unico:
                picks.append(k.pick[1])
            go(k)

    go(node)
    return atoms, set(picks)


# ------------------------------------------------------------ dibujo
def paint(c, W, H, I, vista, atoms=(), picks=(), resaltar=True):
    c.delete("all")
    dom = I.domain
    n = len(dom)
    cx, cy = W / 2, H / 2
    R = max(40, min(W, H) / 2 - 75)
    pos = dict(zip(dom, circle_layout(n, cx, cy, R)))
    node_r = 24 if n == 1 else max(11, min(24, R * math.sin(math.pi / n) * 0.85))
    center = (cx, cy)

    def arrow(a, b, color, width, dash=None):
        if a == b:
            bbox, st, ext = loop_arc(pos[a], center, node_r)
            c.create_arc(*bbox, start=st, extent=ext, style="arc", outline=color,
                         width=width, dash=dash, arrow="last")
        else:
            p, m, q = curve(pos[a], pos[b], node_r)
            c.create_line(*p, *m, *q, smooth=True, arrow="last", fill=color,
                          width=width, dash=dash)

    hl, ring = {}, {}
    if resaltar:
        for (name, tup), val in atoms:
            if vista and vista[0] == "rel" and name == vista[1] and len(tup) == 2:
                hl[tup] = val
            if len(tup) == 1 and tup[0] in pos:
                ring[tup[0]] = val
    picks = set(picks) if resaltar else set()

    if vista:
        kind, name = vista
        if kind == "rel":
            edges, base = set(I.rels[name]), "#64b5f6"
        else:
            edges, base = {(a[0], v) for a, v in I.funcs[name].items()}, "#ba68c8"
        for a, b in sorted(edges):
            if kind == "rel" and hl.get((a, b)) is True:
                arrow(a, b, "#66bb6a", 4)
            else:
                arrow(a, b, base, 2)
        for (a, b), v in hl.items():
            if v is False and a in pos and b in pos:
                arrow(a, b, "#ef5350", 3, (5, 3))

    tags = {e: [] for e in dom}
    for pn, ts in I.rels.items():
        if ts and len(next(iter(ts))) == 1:
            for t in ts:
                tags[t[0]].append(pn)
    for fn, tab in I.funcs.items():
        if () in tab:
            tags[tab[()]].append(fn)

    for e in dom:
        x, y = pos[e]
        if e in ring:
            c.create_oval(x - node_r - 5, y - node_r - 5, x + node_r + 5, y + node_r + 5,
                          outline="#66bb6a" if ring[e] else "#ef5350", width=3)
        picked = e in picks
        c.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                      fill="#5d4037" if picked else "#37474f",
                      outline="#ffa726" if picked else "#90a4ae", width=4 if picked else 2)
        c.create_text(x, y, text=e, fill="white",
                      font=("Segoe UI", 11 if node_r >= 18 and len(e) <= 3 else 8, "bold"))
        if tags[e]:
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            ux, uy = (dx / d, dy / d) if d > 1e-9 else (0.0, 1.0)
            c.create_text(x + ux * (node_r + 34), y + uy * (node_r + 34),
                          text=", ".join(tags[e]), fill="#cfd8dc", font=("Segoe UI", 9))
