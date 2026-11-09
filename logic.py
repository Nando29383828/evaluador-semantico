"""Núcleo del evaluador semántico (MM3032 Lógica Matemática).

Capas: tokenizer -> parser (AST + validación de símbolos/aridades) ->
validación de la interpretación -> evaluador (Tarski) que devuelve un
árbol de evidencia. No depende de la interfaz gráfica.

Gramática (de menor a mayor precedencia):
    formula := imp ('↔' imp)*                 (asociativo a la izquierda)
    imp     := or ('→' imp)?                  (asociativo a la derecha)
    or      := and ('∨' and)*
    and     := unary ('∧' unary)*
    unary   := '¬' unary | ('∀'|'∃') VAR unary | atom
    atom    := '(' formula ')' | PRED ['(' term {',' term} ')']
    term    := VAR | FUNC ['(' term {',' term} ')']
Nota: un cuantificador abarca solo el 'unary' que le sigue:
    ∀x P(x) → Q(x)   se lee   (∀x P(x)) → Q(x).   Use paréntesis para ampliar.
"""
import re
from dataclasses import dataclass, field
from itertools import product


class LogicError(Exception):
    def __init__(self, msg, pos=None, length=1):
        super().__init__(msg)
        self.msg, self.pos, self.length = msg, pos, length


# ------------------------------------------------------------------ AST
@dataclass(frozen=True)
class Var:
    name: str

@dataclass(frozen=True)
class Func:
    name: str
    args: tuple

@dataclass(frozen=True)
class Pred:
    name: str
    args: tuple

@dataclass(frozen=True)
class Not:
    f: object

@dataclass(frozen=True)
class Bin:
    op: str  # ∧ ∨ → ↔
    l: object
    r: object

@dataclass(frozen=True)
class Quant:
    q: str  # ∀ ∃
    var: str
    body: object


# ------------------------------------------------------------ tokenizer
SYMBOLS = [("<->", "IFF"), ("↔", "IFF"), ("->", "IMP"), ("→", "IMP"),
           ("/\\", "AND"), ("\\/", "OR"), ("¬", "NOT"), ("~", "NOT"),
           ("!", "NOT"), ("∧", "AND"), ("&", "AND"), ("∨", "OR"),
           ("|", "OR"), ("∀", "ALL"), ("∃", "EX"), ("(", "LP"),
           (")", "RP"), (",", "COMMA")]
KEYWORDS = {"forall": "ALL", "exists": "EX", "not": "NOT",
            "and": "AND", "or": "OR"}
IDENT = re.compile(r"[^\W\d]\w*'*")
OPSYM = {"IFF": "↔", "IMP": "→", "AND": "∧", "OR": "∨"}


def tokenize(text):
    toks, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        for s, kind in SYMBOLS:
            if text.startswith(s, i):
                toks.append((kind, s, i))
                i += len(s)
                break
        else:
            m = IDENT.match(text, i)
            if not m:
                raise LogicError(f"carácter no válido '{c}'", i)
            word = m.group()
            toks.append((KEYWORDS.get(word, "ID"), word, i))
            i = m.end()
    toks.append(("EOF", "", len(text)))
    return toks


# --------------------------------------------------------------- parser
class Parser:
    def __init__(self, toks, funcs, preds):
        self.t, self.i, self.funcs, self.preds = toks, 0, funcs, preds

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, kind, msg):
        tok = self.peek()
        if tok[0] != kind:
            raise LogicError(msg, tok[2], max(1, len(tok[1])))
        return self.next()

    def formula(self):
        left = self.imp()
        while self.peek()[0] == "IFF":
            self.next()
            left = Bin("↔", left, self.imp())
        return left

    def imp(self):
        left = self.or_()
        if self.peek()[0] == "IMP":
            self.next()
            return Bin("→", left, self.imp())
        return left

    def or_(self):
        left = self.and_()
        while self.peek()[0] == "OR":
            self.next()
            left = Bin("∨", left, self.and_())
        return left

    def and_(self):
        left = self.unary()
        while self.peek()[0] == "AND":
            self.next()
            left = Bin("∧", left, self.unary())
        return left

    def unary(self):
        kind, text, pos = self.peek()
        if kind == "NOT":
            self.next()
            return Not(self.unary())
        if kind in ("ALL", "EX"):
            self.next()
            v = self.expect("ID", "después de un cuantificador debe ir una variable")
            if v[1] in self.funcs or v[1] in self.preds:
                raise LogicError(f"'{v[1]}' es un símbolo del lenguaje; no puede usarse como variable", v[2], len(v[1]))
            return Quant("∀" if kind == "ALL" else "∃", v[1], self.unary())
        return self.atom()

    def atom(self):
        kind, name, pos = self.peek()
        if kind == "LP":
            self.next()
            f = self.formula()
            self.expect("RP", "falta cerrar el paréntesis ')'")
            return f
        if kind == "ID":
            if name in self.preds:
                self.next()
                return Pred(name, self.args(name, self.preds[name], pos))
            if name in self.funcs or self.peek(1)[0] != "LP":
                raise LogicError(f"'{name}' es un término, no una fórmula (falta un predicado)", pos, len(name))
            raise LogicError(f"símbolo '{name}' no declarado", pos, len(name))
        tok = self.peek()
        raise LogicError("se esperaba una fórmula" + (f", se encontró '{tok[1]}'" if tok[0] != "EOF" else " (la entrada terminó antes)"), tok[2], max(1, len(tok[1])))

    def args(self, name, arity, pos):
        if arity == 0:
            if self.peek()[0] == "LP":
                self.next()
                self.expect("RP", f"'{name}' tiene aridad 0: use '{name}' o '{name}()'")
            return ()
        self.expect("LP", f"'{name}' tiene aridad {arity}: faltan sus argumentos entre paréntesis")
        out = [self.term()]
        while self.peek()[0] == "COMMA":
            self.next()
            out.append(self.term())
        end = self.expect("RP", "falta cerrar el paréntesis ')' o una coma entre argumentos")
        if len(out) != arity:
            raise LogicError(f"'{name}' tiene aridad {arity} pero recibió {len(out)} argumento(s)", pos, end[2] - pos + 1)
        return tuple(out)

    def term(self):
        kind, name, pos = self.peek()
        if kind != "ID":
            raise LogicError("se esperaba un término (variable, constante o función)", pos, max(1, len(self.peek()[1])))
        if name in self.preds:
            raise LogicError(f"'{name}' es un predicado; no puede usarse como término", pos, len(name))
        self.next()
        if name in self.funcs:
            return Func(name, self.args(name, self.funcs[name], pos))
        if self.peek()[0] == "LP":
            raise LogicError(f"símbolo '{name}' no declarado", pos, len(name))
        return Var(name)


def parse_formula(text, funcs, preds):
    if not text.strip():
        raise LogicError("la fórmula está vacía", 0)
    p = Parser(tokenize(text), funcs, preds)
    f = p.formula()
    tok = p.peek()
    if tok[0] != "EOF":
        raise LogicError(f"símbolo inesperado '{tok[1]}'", tok[2], len(tok[1]))
    return f


# ---------------------------------------------------------- utilidades
def term_vars(t):
    if isinstance(t, Var):
        return {t.name}
    return set().union(*[term_vars(a) for a in t.args]) if t.args else set()


def free_vars(f):
    if isinstance(f, (Var, Func)):
        return term_vars(f)
    if isinstance(f, Pred):
        return set().union(*[term_vars(a) for a in f.args]) if f.args else set()
    if isinstance(f, Not):
        return free_vars(f.f)
    if isinstance(f, Bin):
        return free_vars(f.l) | free_vars(f.r)
    return free_vars(f.body) - {f.var}


def to_str(f, inner=False):
    if isinstance(f, Var):
        return f.name
    if isinstance(f, (Func, Pred)):
        return f.name if not f.args else f"{f.name}({', '.join(to_str(a) for a in f.args)})"
    if isinstance(f, Not):
        return "¬" + to_str(f.f, True)
    if isinstance(f, Bin):
        s = f"{to_str(f.l, True)} {f.op} {to_str(f.r, True)}"
        return f"({s})" if inner else s
    # el cuantificador abarca solo su 'unary' (ver gramática), así que no
    # necesita paréntesis propios; su cuerpo binario sí queda entre paréntesis
    return f"{f.q}{f.var} {to_str(f.body, True)}"


# ------------------------------------------------- lenguaje (firmas)
def parse_signature(text, what):
    """'f/1, g/2, c/0' -> {'f':1,'g':2,'c':0}"""
    d = {}
    for part in re.split(r"[,;\n]", text):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"([^\W\d]\w*'*)\s*/\s*(\d+)", part)
        if not m:
            raise LogicError(f"{what}: '{part}' no tiene el formato nombre/aridad (ej. R/2)")
        name, ar = m.group(1), int(m.group(2))
        if name in KEYWORDS:
            raise LogicError(f"{what}: '{name}' es una palabra reservada")
        if name in d:
            raise LogicError(f"{what}: '{name}' está declarado dos veces")
        d[name] = ar
    return d


def check_language(funcs, preds):
    clash = set(funcs) & set(preds)
    if clash:
        raise LogicError("nombres repetidos entre funciones y predicados: " + ", ".join(sorted(clash)))


# -------------------------------------------------------- interpretación
@dataclass
class Interp:
    domain: list
    funcs: dict  # nombre -> {tupla: valor}
    rels: dict   # nombre -> {tuplas}


ELEM = re.compile(r"[^\s,()=]+")
LINE = re.compile(r"([^\W\d]\w*'*)\s*(?:\(([^)]*)\))?\s*(?:=\s*(.+))?")


def _fmt(t):
    return "(" + ", ".join(t) + ")"


def build_interp(funcs, preds, domain_text, interp_text):
    """Devuelve (Interp | None, lista_de_errores)."""
    errs = []
    dom = [x.strip() for x in domain_text.split(",") if x.strip()]
    if not dom:
        errs.append("Dominio: debe tener al menos un elemento (no puede ser vacío)")
    for e in dom:
        if not ELEM.fullmatch(e):
            errs.append(f"Dominio: '{e}' no es un nombre de elemento válido (sin espacios, comas, paréntesis ni '=')")
    if len(set(dom)) != len(dom):
        dup = sorted({e for e in dom if dom.count(e) > 1})
        errs.append("Dominio: elementos repetidos: " + ", ".join(dup))
    D = set(dom)
    F = {n: {} for n in funcs}
    R = {n: set() for n in preds}

    for ln, raw in enumerate(interp_text.splitlines(), 1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        m = LINE.fullmatch(line)
        if not m:
            errs.append(f"Línea {ln}: no se entiende '{line}' (use f(a,b)=c  ó  R(a,b))")
            continue
        name, a, val = m.group(1), m.group(2), m.group(3)
        args = tuple(x.strip() for x in a.split(",")) if a and a.strip() else ()
        val = val.strip() if val else None
        if name not in funcs and name not in preds:
            errs.append(f"Línea {ln}: símbolo '{name}' no declarado en el lenguaje")
            continue
        bad = [x for x in args + ((val,) if val else ()) if x not in D]
        if bad:
            errs.append(f"Línea {ln}: {', '.join(repr(b) for b in bad)} no pertenece(n) al dominio")
            continue
        if name in funcs:
            if val is None:
                errs.append(f"Línea {ln}: '{name}' es función; falta '= valor'")
            elif len(args) != funcs[name]:
                errs.append(f"Línea {ln}: '{name}' tiene aridad {funcs[name]} pero se dieron {len(args)} argumento(s)")
            elif args in F[name] and F[name][args] != val:
                errs.append(f"Línea {ln}: {name}{_fmt(args)} ya tenía valor {F[name][args]} (contradicción)")
            else:
                F[name][args] = val
        else:
            if val is not None:
                errs.append(f"Línea {ln}: '{name}' es predicado; no lleva '='")
            elif len(args) != preds[name]:
                errs.append(f"Línea {ln}: '{name}' tiene aridad {preds[name]} pero la tupla tiene {len(args)} elemento(s)")
            else:
                R[name].add(args)

    if not errs:
        for n, ar in funcs.items():
            missing = [t for t in product(dom, repeat=ar) if t not in F[n]]
            if missing:
                ej = ", ".join(f"{n}{_fmt(t)}" for t in missing[:4])
                errs.append(f"Función '{n}': falta definirla en {len(missing)} de {len(dom) ** ar} tupla(s) (ej. {ej}); debe ser total")
        for n in preds:
            if not R[n]:
                errs.append(f"Predicado '{n}': su relación no puede ser vacía")
    return (None if errs else Interp(dom, F, R)), errs


def parse_env(text, free, I):
    """'x=a, y=b' -> (entorno, errores, avisos)"""
    env, errs, warns = {}, [], []
    for part in re.split(r"[,;\n]", text):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"([^\W\d]\w*'*)\s*=\s*(\S+)", part)
        if not m:
            errs.append(f"Entorno: '{part}' no tiene el formato variable=elemento")
            continue
        v, e = m.groups()
        if v in env:
            errs.append(f"Entorno: la variable '{v}' se asignó dos veces")
        elif e not in I.domain:
            errs.append(f"Entorno: '{e}' (valor de {v}) no pertenece al dominio")
        else:
            env[v] = e
        if v not in free:
            warns.append(f"'{v}' no es variable libre de la fórmula; se ignora")
    for v in sorted(free):
        if v not in env and not any(v in e for e in errs):
            errs.append(f"Entorno: falta asignar un valor a la variable libre '{v}'")
    return env, errs, warns


# ------------------------------------------------------------ evaluador
@dataclass
class Node:
    label: str
    value: bool
    why: str
    children: list = field(default_factory=list)
    key: list = field(default_factory=list)  # hijos decisivos
    atom: tuple = None   # (predicado, tupla de elementos) si el nodo es un átomo
    pick: tuple = None   # (variable, elemento) si el nodo es el cuerpo de un cuantificador


def eval_term(t, I, env):
    if isinstance(t, Var):
        return env[t.name]
    return I.funcs[t.name][tuple(eval_term(a, I, env) for a in t.args)]


def evaluate(f, I, env):
    """Satisfacción de Tarski: devuelve un Node con valor y evidencia."""
    label = to_str(f)
    if isinstance(f, Pred):
        vals = tuple(eval_term(a, I, env) for a in f.args)
        v = vals in I.rels[f.name]
        return Node(label, v, f"{_fmt(vals)} {'∈' if v else '∉'} {f.name}ᴵ",
                    atom=(f.name, vals))
    if isinstance(f, Not):
        c = evaluate(f.f, I, env)
        return Node(label, not c.value,
                    f"la subfórmula es {'verdadera' if c.value else 'falsa'}", [c], [c])
    if isinstance(f, Bin):
        a, b = evaluate(f.l, I, env), evaluate(f.r, I, env)
        A, B = a.value, b.value
        if f.op == "∧":
            v = A and B
            key = [a, b] if v else [a if not A else b]
            why = "ambas son verdaderas" if v else ("la 1ª es falsa" if not A else "la 2ª es falsa")
        elif f.op == "∨":
            v = A or B
            key = [a if A else b] if v else [a, b]
            why = ("la 1ª es verdadera" if A else "la 2ª es verdadera") if v else "ambas son falsas"
        elif f.op == "→":
            v = (not A) or B
            if v:
                key = [a] if not A else [b]
                why = "el antecedente es falso" if not A else "el consecuente es verdadero"
            else:
                key = [a, b]
                why = "antecedente verdadero y consecuente falso"
        else:
            v = A == B
            key = [a, b]
            why = "ambas tienen el mismo valor" if v else "tienen valores distintos"
        return Node(label, v, why, [a, b], key)
    # cuantificadores: se revisa TODO el dominio
    kids = []
    for e in I.domain:
        n = evaluate(f.body, I, {**env, f.var: e})
        n.label = f"[{f.var}={e}] {n.label}"
        n.pick = (f.var, e)
        kids.append((e, n))
    ok = [(e, n) for e, n in kids if n.value]
    ko = [(e, n) for e, n in kids if not n.value]
    nodes = [n for _, n in kids]
    if f.q == "∀":
        if ko:
            e, n = ko[0]
            return Node(label, False, f"contraejemplo: {f.var} = {e}", nodes, [n])
        return Node(label, True, f"se cumple para los {len(nodes)} elementos del dominio", nodes, nodes)
    if ok:
        e, n = ok[0]
        return Node(label, True, f"testigo: {f.var} = {e}", nodes, [n])
    return Node(label, False, f"ninguno de los {len(nodes)} elementos lo cumple", nodes, nodes)


def explain(node, limit=60):
    """Líneas de explicación siguiendo solo los nodos decisivos."""
    out = []

    def go(n, d):
        if len(out) >= limit:
            if not out[-1].endswith("…"):
                out.append("  …(ver árbol completo)…")
            return
        out.append("  " * d + f"{'✔' if n.value else '✘'} {n.label}  →  {n.why}")
        for k in n.key:
            go(k, d + 1)

    go(node, 0)
    return out
