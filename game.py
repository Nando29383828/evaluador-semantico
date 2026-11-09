"""Juego de evaluación de Hintikka (semántica de juegos).

Dos jugadores: el VERIFICADOR sostiene que la fórmula es verdadera y el
FALSIFICADOR que es falsa. Reglas, en una posición (φ, entorno, Verificador):

    átomo        gana el Verificador si el átomo es verdadero en 𝓘; si no, el Falsificador
    ¬φ           se intercambian los roles y se sigue con φ
    φ ∧ ψ        el Falsificador elige φ o ψ
    φ ∨ ψ        el Verificador elige φ o ψ
    φ → ψ        como ¬φ ∨ ψ: el Verificador elige entre atacar φ (roles
                 intercambiados) o defender ψ
    φ ↔ ψ        como (φ→ψ) ∧ (ψ→φ): el Falsificador elige una implicación
    ∀x φ         el Falsificador elige un elemento e de 𝒟 y se sigue con φ[x:=e]
    ∃x φ         el Verificador elige un elemento e de 𝒟

Teorema (Hintikka): el Verificador tiene una estrategia ganadora si y solo si
la fórmula es verdadera en (𝓘, entorno). La computadora juega de forma óptima
usando el evaluador de Tarski, así que si el usuario está del lado ganador y
juega bien, siempre gana; si está del lado perdedor, pierde.

Jugadores: "U" = usuario, "C" = computadora.
"""
from dataclasses import dataclass

from logic import Pred, Not, Bin, Quant, to_str, evaluate, eval_term

NAME = {"U": "Tú", "C": "La computadora"}


def other(p):
    return "C" if p == "U" else "U"


@dataclass
class Option:
    label: str
    state: tuple  # (formula, entorno, verificador)


class Game:
    def __init__(self, f, I, env, user_is_verifier=True):
        self.I = I
        self.user_is_verifier = user_is_verifier
        self.state = (f, dict(env), "U" if user_is_verifier else "C")
        self.truth = evaluate(f, I, env).value
        self.lines = []        # (texto, etiqueta)
        self.winner = None
        self.options = []      # opciones disponibles cuando juega el usuario
        self.prompt = ""
        self.advance()

    # ---------------------------------------------------------- utilidades
    def log(self, text, tag="sys"):
        self.lines.append((text, tag))

    def user_side_wins(self):
        """¿El usuario tiene estrategia ganadora desde el inicio?"""
        return self.user_is_verifier == self.truth

    def _wins(self, player, state):
        g, env, ver = state
        val = evaluate(g, self.I, env).value
        return (player == ver) == val

    @staticmethod
    def _env_str(env):
        return ", ".join(f"{k}={v}" for k, v in sorted(env.items()))

    def current(self):
        f, env, ver = self.state
        return to_str(f), self._env_str(env), ver

    # ------------------------------------------------------------- reglas
    def _opciones(self, f, env, ver):
        fal = other(ver)
        I = self.I
        if isinstance(f, Bin):
            if f.op == "∧":
                return fal, "elige un conjuntivo; buscas uno FALSO", [
                    Option("izquierdo: " + to_str(f.l), (f.l, env, ver)),
                    Option("derecho: " + to_str(f.r), (f.r, env, ver))]
            if f.op == "∨":
                return ver, "elige un disyuntivo; buscas uno VERDADERO", [
                    Option("izquierdo: " + to_str(f.l), (f.l, env, ver)),
                    Option("derecho: " + to_str(f.r), (f.r, env, ver))]
            if f.op == "→":
                return ver, "atacar el antecedente (se invierten los roles) o defender el consecuente", [
                    Option("Atacar el antecedente: " + to_str(f.l), (f.l, env, fal)),
                    Option("Defender el consecuente: " + to_str(f.r), (f.r, env, ver))]
            a, b = Bin("→", f.l, f.r), Bin("→", f.r, f.l)
            return fal, "elige cuál de las dos implicaciones atacar", [
                Option(to_str(a), (a, env, ver)), Option(to_str(b), (b, env, ver))]
        if f.q == "∀":
            chooser, rule = fal, f"elige un valor para {f.var}; buscas un CONTRAEJEMPLO"
        else:
            chooser, rule = ver, f"elige un valor para {f.var}; buscas un TESTIGO"
        return chooser, rule, [Option(f"{f.var} = {e}", (f.body, {**env, f.var: e}, ver))
                               for e in I.domain]

    def advance(self):
        """Avanza automáticamente hasta que el usuario deba elegir o termine."""
        self.options, self.prompt = [], ""
        while self.winner is None:
            f, env, ver = self.state
            fal = other(ver)
            pos = f"▸ {to_str(f)}"
            if env:
                pos += f"    [{self._env_str(env)}]"
            self.log(pos + f"    (Verificador: {NAME[ver]})")
            if isinstance(f, Pred):
                vals = tuple(eval_term(a, self.I, env) for a in f.args)
                v = vals in self.I.rels[f.name]
                self.winner = ver if v else fal
                shown = "(" + ", ".join(vals) + ")"
                self.log(f"Átomo: {shown} {'∈' if v else '∉'} {f.name}ᴵ, es "
                         f"{'verdadero' if v else 'falso'}. Gana {NAME[self.winner]}.", "fin")
                return
            if isinstance(f, Not):
                self.log(f"¬ → se intercambian los roles: ahora {NAME[fal]} es el Verificador.")
                self.state = (f.f, env, fal)
                continue
            chooser, rule, opts = self._opciones(f, env, ver)
            if chooser == "U":
                role = "Verificador" if chooser == ver else "Falsificador"
                self.options = opts
                self.prompt = f"Eres el {role}: {rule}."
                return
            wins = [o for o in opts if self._wins("C", o.state)]
            pick = (wins or opts)[0]
            self.log(f"La computadora elige → {pick.label}", "c")
            self.state = pick.state

    # ------------------------------------------------------ jugadas del usuario
    def choose(self, i):
        if self.winner is not None or not self.options:
            return
        pick = self.options[i]
        self.log(f"Tú eliges → {pick.label}", "u")
        self.state = pick.state
        self.advance()

    def hint(self):
        """Índices de las opciones ganadoras para el usuario."""
        return [i for i, o in enumerate(self.options) if self._wins("U", o.state)]

    def conclusion(self):
        t = "verdadera" if self.truth else "falsa"
        side = "Verificador" if self.truth else "Falsificador"
        who = NAME["U"] if self.user_side_wins() else NAME["C"]
        return (f"La fórmula es {t} en la interpretación, así que el {side} tiene una "
                f"estrategia ganadora (en esta partida le correspondía a: {who}).")
