"""Wo die Verfeinerung einer Rundform vergeblich rechnen würde — im Stapel vorhergesagt.

Die Einpassungen von Kegel und Ring verfeinern ihren Startwert mit SciPys
``least_squares`` (Trust-Region-Reflective ohne Schranken) und begrenzen den
Lauf auf :data:`~app.core.perceive.features.ROUND_FIT_EVALUATIONS`
Auswertungen. **Wer das Budget ausschöpft, liefert nichts** (RM-210), und an
Gittern und erzeugten Netzen ist das die Regel: An der Kumiko-Schale schöpfen
442 von 467 Kegelläufen ihr Budget aus, am Meshy-Murmelbrett knapp 5 000 von
15 800 — jeder hundert Auswertungen lang für ``None``. Ob ein Lauf das tut,
steht in keinem Merkmal des Flecks (RM-209: neun Siebe gemessen, alle
verworfen); es steht nur im Lauf selbst.

**Deshalb läuft der Löser hier noch einmal, aber für alle Flecken zugleich.**
:func:`exhausted` rechnet denselben Algorithmus — dieselben Schritte, Zweige
und Abbruchregeln wie ``scipy.optimize._lsq.trf.trf_no_bounds`` mit
``tr_solver='exact'`` und ``x_scale=1`` — über einen Stapel von Problemen in
NumPy und sagt je Problem, ob sein Lauf das Budget *sicher* ausschöpft. Nur
dieses Nein wird übernommen; jedes andere Problem rechnet der echte Löser Zahl
für Zahl wie bisher, und damit bleibt jede gefundene Rundform bitgleich.

**Der Stapel rundet anders, also braucht das Nein einen Abstand.** Der
vorhergesagte Lauf weicht vom echten nur um Rundung ab — gemessen an der
Kumiko-Schale und am Drachen nach hundert Auswertungen um höchstens
``3e-11`` relativ in den Parametern, und in 465 von 467 Läufen mit
derselben Auswertungszahl. Übernommen wird ein Nein nur, wenn drei Abstände
halten (Herkunft und Zahlen bei den Konstanten):

* **Kein Zweig steht an der Kippe** (:data:`DECISION_MARGIN`): Jede
  Entscheidung des Algorithmus — Schrittgüte gegen 0,25 und 0,75,
  Randtreffer, Annahme, Gauß-Newton-Schritt, Rang, Abbruch und Neustart der
  inneren Newton-Suche — liegt deutlich neben ihrer Schwelle.
* **Kein Abbruch steht in Sicht** (:data:`STOP_MARGIN_DECADES`):
  Gradient, Kostenabnahme und Schrittweite bleiben über den ganzen Lauf um
  Zehnerpotenzen über ``gtol``, ``ftol`` und ``xtol``.
* **Ein Schattenlauf kommt zum selben Ergebnis** (:data:`SHADOW_NOISE`,
  :data:`SHADOW_AGREEMENT`): Derselbe Lauf, jede Auswertung an einem um
  ``1e-9`` relativ verschobenen Punkt — sechs Größenordnungen mehr als die
  Rundung des echten Laufs —, muss ebenso ausschöpfen und darf sich über den
  ganzen Lauf nicht weiter als ``1e-6`` vom ersten entfernen. Das misst je
  Problem, ob sein Lauf Störungen dämpft oder aufschaukelt.

Die Verschiebung des Schattens ist ein festes Muster, kein Zufall (Regel 9).
Der Stapel entscheidet keine Geometrie: Seine Antwort nimmt nur einen
Löserlauf weg, dessen Ergebnis ``None`` gewesen wäre; wo er zögert, rechnet
der echte Löser. Deshalb darf er schnell rechnen — nicht als nachgeprüfte
Vorauswahl (sein Nein prüft niemand nach, es nimmt den Lauf weg), sondern als
eigene Klasse der Regel: ein sicheres Nein, das nur einen leeren Lauf
auslässt, mit Abstand zu jedem Zweig und Abbruch und bestätigt vom Schatten
(``schichtanalyse.md``; unter Plattformrauschen hält es
``tests/test_refine.py``). Rechnet eine andere Maschine anders, kippt ein
Urteil höchstens zu „nicht sicher“, und das kostet nur Zeit. Die
Reihenfolge der Probleme im Stapel ändert keine Zahl eines Problems: Jedes
wird auf eine Zeilenzahl aufgefüllt, die nur von ihm selbst abhängt.

**Und der echte Lauf selbst steht auch hier** (:func:`solve`): SciPys
``least_squares`` auf diesem Weg, Schritt für Schritt nachgebaut und Bit für
Bit gleich, nur ohne die Hülle aus Argumentprüfung und ``VectorFunction``,
die ein Fünftel der Löserzeit kostete.

Die Rechnung folgt SciPy (BSD-3-Clause; Vermerk, Bedingungen und
Haftungsausschluss stehen wortgleich unter diesem Docstring); die Residuen
und Ableitungen von Kegel und Ring sind dieselben Formeln wie in
:func:`app.core.perceive.features._fit_cone_measured`
und ``_fit_torus_measured`` — wer dort eine ändert, ändert sie hier mit
(``tests/test_refine.py`` hält beide aneinander).
"""

# Die Funktionen solve, _trust_region_step und der Stapellauf _run/_trust_step
# übertragen Code aus SciPy 1.18.1 (scipy/optimize/_lsq/trf.py, common.py:
# trf_no_bounds, solve_lsq_trust_region, update_tr_radius, check_termination).
# Dafür gilt SciPys Lizenz, wortgleich aus scipy-1.18.1.dist-info/LICENSE.txt:
#
# Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, NamedTuple

import numpy as np

from app.core.units import EPS_GEOM

#: Wie weit jede Entscheidung des vorhergesagten Laufs von ihrer Schwelle
#: liegen muss, relativ zu ihrer Größe.
#:
#: Gemessen an jedem bestätigten Lauf von Kumiko-Schale, Drache und
#: Meshy-Murmelbrett, Schritt für Schritt gegen den protokollierten echten
#: Lauf: Beide gehen denselben Weg mit derselben Zahl innerer Newton-Schritte,
#: und die Abweichung in Schrittgüte, Abnahme, Vorhersage und Newton-Rest
#: nutzt höchstens 5,8e-4 des Abstands zur Schwelle aus — eine Reserve vom
#: Faktor 1 700. Liegt eine Entscheidung näher an ihrer Schwelle, sagt der
#: Stapel zu diesem Problem nichts.
DECISION_MARGIN: Final = 1e-6

#: Um wie viele Zehnerpotenzen Gradient, Kostenabnahme und Schrittweite über
#: den Abbruchschwellen bleiben müssen. Die vergeblichen Läufe an der
#: Kumiko-Schale liegen median sieben bis neun Potenzen darüber, der knappste
#: gut zwei; zwei Potenzen lassen einer Abweichung von ``1e-6`` in den
#: Parametern mehr als genug Raum.
STOP_MARGIN_DECADES: Final = 2.0

#: Die relative Verschiebung jeder Auswertung im Schattenlauf — sechs bis
#: sieben Größenordnungen über der Rundung (``2e-16`` je Schritt), das
#: Dreißigfache der größten gemessenen Wegabweichung zwischen Stapel und
#: echtem Lauf nach hundert Auswertungen (``3e-11``).
SHADOW_NOISE: Final = 1e-9

#: Wie weit sich Schatten und Lauf höchstens voneinander entfernen dürfen,
#: relativ in den Parametern. Kippt ein Zweig, trennen sich die Läufe um
#: Prozente (ein Vertrauensradius halbiert oder viertelt sich); ein ruhiger
#: Lauf trägt die Verschiebung ungefähr unverstärkt weiter.
SHADOW_AGREEMENT: Final = 1e-6

#: Wie viel Speicher ein Stapelblock höchstens belegen soll — eine
#: Speichergrenze, keine Toleranz. Ein Speicherfehler kostet die ganze
#: Erkennung des Körpers (``kern.md``).
BATCH_BYTES: Final = 64 * 2**20

#: Die Spitze eines Blocks als Vielfaches eines Ableitungsfelds von Plan und
#: Schatten (2 mal Probleme mal (Zeilen + 3) mal Größe mal 8 Byte). Gemessen mit
#: ``tracemalloc`` an allen Zeilenzahlen von 16 bis 4 096 am
#: Meshy-Murmelbrett, Kegel und Ring: 4,1 bis 9,9.
BATCH_PEAK_FACTOR: Final = 10

#: Die kleinste Zeilenzahl, auf die ein Problem aufgefüllt wird — Splitter
#: aus sechs bis sechzehn Stützpunkten rechnen in einer Gruppe.
MIN_PADDED_ROWS: Final = 16

#: Ab wie vielen Problemen gleicher Zeilenzahl sich der Stapel lohnt. Ein
#: Stapellauf kostet je Runde einen festen Satz von gut hundert NumPy-Aufrufen
#: (die Newton-Suche des Vertrauensbereichs allein bis zu hundertfünfzig), über
#: hundert Runden also rund hundert Millisekunden je Gruppe, gleich wie groß
#: sie ist; ein vergeblicher echter Lauf spart rund zehn. Bei einem Fünftel
#: vergeblicher Läufe trägt sich das ab etwa neunzig Problemen, bei der Hälfte
#: ab dreißig — gemessen an Kumiko-Schale und Freiform. Eine Rechengrenze,
#: keine Toleranz.
MIN_BATCH: Final = 64

_EPS: Final = float(np.finfo(float).eps)
#: Dieselbe Zahl als NumPy-Skalar, wie SciPy sie in ``solve_lsq_trust_region`` führt.
_EPS_SCIPY: Final = np.finfo(float).eps
_RUNNING: Final = -1


@dataclass(frozen=True, slots=True, eq=False)
class ConeProblem:
    """Eine Kegelverfeinerung, wie ``features._fit_cone_measured`` sie stellt.

    ``points`` sind die Löserzeilen (skaliert), ``apex`` die belegte Spitze
    darunter oder ``None``; ``axis``, ``first`` und ``second`` spannen die
    Achsneigung auf, ``initial`` ist der Startwert (Spitze, zwei Neigungen,
    Winkel).
    """

    points: np.ndarray
    apex: np.ndarray | None
    axis: np.ndarray
    first: np.ndarray
    second: np.ndarray
    initial: np.ndarray


@dataclass(frozen=True, slots=True, eq=False)
class TorusProblem:
    """Eine Ringverfeinerung, wie ``_fit_torus_measured`` sie stellt.

    ``initial``: Mitte, zwei Neigungen, Ring- und Röhrenradius.
    """

    points: np.ndarray
    axis: np.ndarray
    first: np.ndarray
    second: np.ndarray
    initial: np.ndarray


Problem = ConeProblem | TorusProblem


@dataclass(frozen=True, slots=True, eq=False)
class Solution:
    """Was :func:`solve` zurückgibt: die gelesenen Felder von SciPys ``OptimizeResult``."""

    x: np.ndarray
    fun: np.ndarray
    jac: np.ndarray
    nfev: int
    status: int

    @property
    def success(self) -> bool:
        """Wie ``OptimizeResult.success``: ein Abbruch über eine Toleranz, nicht über das Budget."""
        return self.status > 0


def solve(
    fun: Callable[[np.ndarray], np.ndarray],
    jac: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    *,
    precision: float,
    evaluations: int,
) -> Solution:
    """SciPys ``least_squares`` mit Ableitung, ohne Schranken, Schritt für Schritt nachgebaut.

    **Dieselben Gleitkommaschritte in derselben Folge** wie SciPy 1.18 auf
    diesem Weg — ``least_squares`` → ``trf`` → ``trf_no_bounds`` mit
    ``tr_solver='exact'`` und ``x_scale=1`` —, nur ohne ``VectorFunction``,
    Argumentprüfung und ``OptimizeResult``: Dieselben NumPy- und
    SciPy-Aufrufe (``np.dot``, ``norm``, ``scipy.linalg.svd``) auf denselben
    Feldern, die Multiplikation mit dem Einheitsmaßstab entfällt, weil sie
    nichts ändert. Gemessen bitgleich in ``x``, Residuen, Ableitung,
    Auswertungszahl und Status an 5 033 Läufen der Erkennung (Kumiko-Schale,
    Drache, Bowlingkugel) und am Korpus; die Hülle um SciPy kostete ein
    Fünftel der Löserzeit. ``tests/test_refine.py`` hält beide Wege aneinander.

    Nachbau von Code aus SciPy (BSD-3-Clause).
    """
    from scipy.linalg import svd  # schwer; erst beim ersten Lauf laden (wie deferred.py)

    x0 = np.atleast_1d(x0).astype(float)
    f0 = np.atleast_1d(fun(x0.copy()))
    jacobian = np.atleast_2d(jac(x0.copy()))
    if not np.all(np.isfinite(f0)):
        raise ValueError("Residuals are not finite in the initial point.")
    x = x0.copy()
    f = f0
    f_true = f.copy()
    nfev = 1
    m, n = jacobian.shape
    cost = 0.5 * np.dot(f, f)
    gradient = jacobian.T.dot(f)
    delta = np.linalg.norm(x0)
    if delta == 0:
        delta = 1.0
    alpha: Any = 0.0
    status: int | None = None
    while True:
        if np.linalg.norm(gradient, ord=np.inf) < precision:
            status = 1
        if status is not None or nfev == evaluations:
            break
        u, s, v = svd(jacobian, full_matrices=False)
        v = v.T
        uf = u.T.dot(f)
        reduction: Any = -1
        while reduction <= 0 and nfev < evaluations:
            step, alpha = _trust_region_step(n, m, uf, s, v, delta, alpha)
            moved = jacobian.dot(step)
            predicted = -(0.5 * np.dot(moved, moved) + np.dot(step, gradient))
            x_new = x + step
            f_new = np.atleast_1d(fun(x_new.copy()))
            nfev += 1
            step_norm = np.linalg.norm(step)
            if not np.all(np.isfinite(f_new)):
                delta = 0.25 * step_norm
                continue
            cost_new = 0.5 * np.dot(f_new, f_new)
            reduction = cost - cost_new
            ratio: Any
            if predicted > 0:
                ratio = reduction / predicted
            elif predicted == reduction == 0:
                ratio = 1
            else:
                ratio = 0
            delta_new = delta
            if ratio < 0.25:
                delta_new = 0.25 * step_norm
            elif ratio > 0.75 and step_norm > 0.95 * delta:
                delta_new *= 2.0
            by_cost = reduction < precision * cost and ratio > 0.25
            by_step = step_norm < precision * (precision + np.linalg.norm(x))
            if by_cost and by_step:
                status = 4
            elif by_cost:
                status = 2
            elif by_step:
                status = 3
            if status is not None:
                break
            alpha *= delta / delta_new
            delta = delta_new
        if reduction > 0:
            x = x_new
            f = f_new
            f_true = f.copy()
            cost = cost_new
            jacobian = np.atleast_2d(jac(x.copy()))
            gradient = jacobian.T.dot(f)
    return Solution(
        x=x, fun=f_true, jac=jacobian, nfev=nfev, status=0 if status is None else status
    )


def _trust_region_step(
    n: int, m: int, uf: np.ndarray, s: np.ndarray, v: np.ndarray, delta: Any, alpha: Any
) -> tuple[np.ndarray, Any]:
    """``scipy.optimize._lsq.common.solve_lsq_trust_region`` mit ``rtol=0.01``, ``max_iter=10``."""

    def phi_and_derivative(value: Any) -> tuple[Any, Any]:
        denominator = s**2 + value
        p_norm = np.linalg.norm(suf / denominator)
        return p_norm - delta, -np.sum(suf**2 / denominator**3) / p_norm

    suf = s * uf
    full_rank = s[-1] > _EPS_SCIPY * m * s[0] if m >= n else False
    if full_rank:
        step = -v.dot(uf / s)
        if np.linalg.norm(step) <= delta:
            return step, 0.0
    upper = np.linalg.norm(suf) / delta
    if full_rank:
        phi, derivative = phi_and_derivative(0.0)
        lower = -phi / derivative
    else:
        lower = 0.0
    if not full_rank and alpha == 0:
        alpha = max(0.001 * upper, (lower * upper) ** 0.5)
    for _iteration in range(10):
        if alpha < lower or alpha > upper:
            alpha = max(0.001 * upper, (lower * upper) ** 0.5)
        phi, derivative = phi_and_derivative(alpha)
        if phi < 0:
            upper = alpha
        ratio = phi / derivative
        lower = max(lower, alpha - ratio)
        alpha -= (phi + delta) * ratio / delta
        if np.abs(phi) < 0.01 * delta:
            break
    step = -v.dot(suf / (s**2 + alpha))
    step *= delta / np.linalg.norm(step)
    return step, alpha


def exhausted(
    problems: Sequence[Problem],
    *,
    precision: float,
    evaluations: int,
    check_cancelled: Callable[[], None] | None = None,
    progress: Callable[[float], None] | None = None,
) -> list[bool]:
    """Je Problem, ob sein Löserlauf das Budget sicher ausschöpft.

    ``precision`` ist ``ftol = xtol = gtol`` des echten Laufs, ``evaluations``
    sein ``max_nfev``. ``True`` heißt: Der echte Lauf hätte nach
    ``evaluations`` Auswertungen ohne Abbruch aufgehört und damit nichts
    geliefert. ``False`` heißt nicht das Gegenteil, sondern nur: nicht sicher.
    ``progress`` erfährt den erledigten Anteil, gezählt in Problemen.

    Plan und Schatten laufen übereinander im selben Stapel, und ein Paar
    verlässt ihn, sobald eine Hälfte nicht mehr sicher werden kann — ein
    Lauf, der abbricht, einen Abstand verfehlt oder unendlich wird. Eine
    Gruppe unter :data:`MIN_BATCH` Problemen fragt der Stapel nicht: Dort
    rechnet der echte Löser schneller, als sich die feste Arbeit je Runde
    lohnt.
    """
    answers = [False] * len(problems)
    groups: dict[tuple[str, int], list[int]] = {}
    for index, problem in enumerate(problems):
        key = (type(problem).__name__, _padded_rows(len(problem.points)))
        groups.setdefault(key, []).append(index)
    done = 0
    for (kind, rows), members in sorted(groups.items()):
        if len(members) < MIN_BATCH:
            done += len(members)
            continue
        columns = 6 if kind == ConeProblem.__name__ else 7
        chunk = max(1, BATCH_BYTES // (2 * (rows + 3) * columns * 8 * BATCH_PEAK_FACTOR))
        for start in range(0, len(members), chunk):
            part = members[start : start + chunk]
            chosen = [problems[index] for index in part]
            cone = kind == ConeProblem.__name__
            data, size = _cone_data(chosen, rows) if cone else _torus_data(chosen, rows)
            evaluate = _cone_residual if cone else _torus_residual
            count = len(part)
            stacked = {key: np.concatenate((value, value)) for key, value in data.items()}
            safe, apart, _status, _x = _run(
                stacked, size, evaluate, precision, evaluations, check_cancelled
            )
            verdicts = safe[:count] & safe[count:] & (apart <= SHADOW_AGREEMENT)
            for index, verdict in zip(part, verdicts.tolist(), strict=True):
                answers[index] = verdict
            done += len(part)
            if progress is not None:
                progress(done / len(problems))
    return answers


def _padded_rows(count: int) -> int:
    """Die Zeilenzahl nach dem Auffüllen — sie hängt nur an ``count``, nicht am Stapel."""
    rows = MIN_PADDED_ROWS
    while rows < count:
        rows *= 2
    return rows


#: Die Felder eines Stapels, je Zeile ein Problem — Plan und Schatten übereinander.
_Data = dict[str, np.ndarray]
_Evaluate = Callable[[np.ndarray, _Data, bool], tuple[np.ndarray, np.ndarray | None]]


def _padded(problems: Sequence[Problem], rows: int) -> _Data:
    """Punkte je Koordinate auf ``rows`` aufgefüllt, dazu Gültigkeit, Achsbasis und Start."""
    count = len(problems)
    coordinates = np.zeros((3, count, rows))
    valid = np.zeros((count, rows), dtype=bool)
    used = np.zeros(count, dtype=np.int64)
    for index, problem in enumerate(problems):
        length = len(problem.points)
        coordinates[:, index, :length] = np.asarray(problem.points, dtype=float).T
        valid[index, :length] = True
        used[index] = length
    data = {
        "px": coordinates[0],
        "py": coordinates[1],
        "pz": coordinates[2],
        "valid": valid,
        "rows": used,
        "axis": np.asarray([problem.axis for problem in problems], dtype=float),
        "first": np.asarray([problem.first for problem in problems], dtype=float),
        "second": np.asarray([problem.second for problem in problems], dtype=float),
        "initial": np.asarray([problem.initial for problem in problems], dtype=float),
    }
    return data


def _cone_data(problems: Sequence[Problem], rows: int) -> tuple[_Data, int]:
    """Die Kegelprobleme eines Stapels; die belegte Spitze zählt als drei Zeilen mehr."""
    data = _padded(problems, rows)
    apex = np.zeros((len(problems), 3))
    has_apex = np.zeros(len(problems), dtype=bool)
    for index, problem in enumerate(problems):
        if isinstance(problem, ConeProblem) and problem.apex is not None:
            apex[index] = problem.apex
            has_apex[index] = True
    data["apex"] = apex
    data["has_apex"] = has_apex
    # Die Zeilen, die der echte Löser sieht — sie entscheiden seinen Rangtest.
    data["rows"] = data["rows"] + np.where(has_apex, 3, 0)
    return data, 6


def _torus_data(problems: Sequence[Problem], rows: int) -> tuple[_Data, int]:
    """Die Ringprobleme eines Stapels."""
    return _padded(problems, rows), 7


def _direction(data: _Data, values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Achse aus Startachse und zwei Neigungen: roh, Länge, Einheitsvektor."""
    raw = data["axis"] + data["first"] * values[:, 3:4] + data["second"] * values[:, 4:5]
    length = np.sqrt(raw[:, 0] * raw[:, 0] + raw[:, 1] * raw[:, 1] + raw[:, 2] * raw[:, 2])
    return raw, length, raw / length[:, None]


def _cone_residual(
    values: np.ndarray, data: _Data, want_jacobian: bool
) -> tuple[np.ndarray, np.ndarray | None]:
    """Der Kegelabstand aus ``_fit_cone_measured``, Koordinate für Koordinate."""
    _raw, length, direction = _direction(data, values)
    dx, dy, dz = direction[:, 0:1], direction[:, 1:2], direction[:, 2:3]
    cosine, sine = np.cos(values[:, 5:6]), np.sin(values[:, 5:6])
    rx = data["px"] - values[:, 0:1]
    ry = data["py"] - values[:, 1:2]
    rz = data["pz"] - values[:, 2:3]
    along = rx * dx + ry * dy + rz * dz
    qx, qy, qz = rx - along * dx, ry - along * dy, rz - along * dz
    radial = np.sqrt(qx * qx + qy * qy + qz * qz)
    valid = data["valid"]
    errors = np.where(valid, radial * cosine - along * sine, 0.0)
    tip = np.where(data["has_apex"][:, None], values[:, :3] - data["apex"], 0.0)
    residual = np.concatenate((errors, tip), axis=1)
    if not want_jacobian:
        return residual, None
    safe = np.where(radial > EPS_GEOM, radial, EPS_GEOM)
    ux, uy, uz = qx / safe, qy / safe, qz / safe
    count, rows = errors.shape
    jacobian = np.zeros((count, rows + 3, 6))
    jacobian[:, :rows, 0] = -cosine * ux + sine * dx
    jacobian[:, :rows, 1] = -cosine * uy + sine * dy
    jacobian[:, :rows, 2] = -cosine * uz + sine * dz
    for column, basis in ((3, data["first"]), (4, data["second"])):
        along_basis = np.sum(direction * basis, axis=1)[:, None]
        turned = (basis - direction * along_basis) / length[:, None]
        tx, ty, tz = turned[:, 0:1], turned[:, 1:2], turned[:, 2:3]
        d_along = rx * tx + ry * ty + rz * tz
        d_radial = -along * (ux * tx + uy * ty + uz * tz)
        jacobian[:, :rows, column] = cosine * d_radial - sine * d_along
    jacobian[:, :rows, 5] = -radial * sine - along * cosine
    jacobian[:, :rows] *= valid[:, :, None]
    tips = np.where(data["has_apex"], 1.0, 0.0)
    for axis_index in range(3):
        jacobian[:, rows + axis_index, axis_index] = tips
    return residual, jacobian


def _torus_residual(
    values: np.ndarray, data: _Data, want_jacobian: bool
) -> tuple[np.ndarray, np.ndarray | None]:
    """Der Meridianabstand aus ``_fit_torus_measured``, Koordinate für Koordinate."""
    _raw, length, direction = _direction(data, values)
    dx, dy, dz = direction[:, 0:1], direction[:, 1:2], direction[:, 2:3]
    ring, tube = values[:, 5:6], values[:, 6:7]
    rx = data["px"] - values[:, 0:1]
    ry = data["py"] - values[:, 1:2]
    rz = data["pz"] - values[:, 2:3]
    along = rx * dx + ry * dy + rz * dz
    qx, qy, qz = rx - along * dx, ry - along * dy, rz - along * dz
    radial = np.sqrt(qx * qx + qy * qy + qz * qz)
    offset = radial - ring
    distance = np.hypot(offset, along)
    valid = data["valid"]
    residual = np.where(valid, distance - tube, 0.0)
    if not want_jacobian:
        return residual, None
    safe_radial = np.where(radial > EPS_GEOM, radial, EPS_GEOM)
    ux, uy, uz = qx / safe_radial, qy / safe_radial, qz / safe_radial
    safe = np.where(distance > EPS_GEOM, distance, EPS_GEOM)
    outward, upward = offset / safe, along / safe
    count, rows = residual.shape
    jacobian = np.empty((count, rows, 7))
    jacobian[:, :, 0] = -ux * outward - upward * dx
    jacobian[:, :, 1] = -uy * outward - upward * dy
    jacobian[:, :, 2] = -uz * outward - upward * dz
    for column, basis in ((3, data["first"]), (4, data["second"])):
        along_basis = np.sum(direction * basis, axis=1)[:, None]
        turned = (basis - direction * along_basis) / length[:, None]
        tx, ty, tz = turned[:, 0:1], turned[:, 1:2], turned[:, 2:3]
        d_along = rx * tx + ry * ty + rz * tz
        d_radial = -along * (ux * tx + uy * ty + uz * tz)
        jacobian[:, :, column] = (offset * d_radial + along * d_along) / safe
    jacobian[:, :, 5] = -outward
    jacobian[:, :, 6] = -1.0
    jacobian *= valid[:, :, None]
    return residual, jacobian


def _shadow_pattern(evaluation: np.ndarray, size: int) -> np.ndarray:
    """Das feste Verschiebungsmuster des Schattens je Auswertung und Größe, Werte in [-1, 1]."""
    columns = np.arange(size)
    pattern: np.ndarray = (((evaluation[:, None] * 5 + columns[None, :] * 3) % 7) - 3) / 3.0
    return pattern


class _Outcome(NamedTuple):
    """Was ein Stapellauf zurückgibt: je Zeile sicher ja/nein, Status (0 = Budget, 1/2 = Abbruch
    über eine Toleranz, 3 = nicht sicher zu machen) und letzte angenommene Parameter; je Paar
    das größte Auseinander von Plan und Schatten."""

    safe: np.ndarray
    apart: np.ndarray
    status: np.ndarray
    x: np.ndarray


def _run(
    data: _Data,
    size: int,
    evaluate: _Evaluate,
    precision: float,
    evaluations: int,
    check_cancelled: Callable[[], None] | None,
) -> _Outcome:
    """Ein Stapellauf über Plan und Schatten: je Zeile sicher ja/nein, je Paar ihr Abstand.

    Die zweite Hälfte der Zeilen ist der Schatten der ersten: Jede ihrer
    Auswertungen ist um :data:`SHADOW_NOISE` im festen Muster verschoben
    (:func:`_shadow_pattern`). Plan und Schatten gehen im Gleichschritt — je
    Runde eine Auswertung —, also vergleicht der Lauf nach jeder Runde ihre
    angenommenen Parameter und behält nur das größte Auseinander, bezogen auf
    den größten Betrag des Plans (mindestens eins); der ganze Weg wog an einem
    vollen Block 149 MiB (Review B4). Eine Zeile verlässt den Stapel mit ihrem
    Partner, sobald eine von beiden nicht mehr sicher werden kann; was sie zum
    Urteil beitragen, steht in den Feldern über alle Zeilen (``final_*``).
    Zerlegungen und Produkte rechnen über BLAS und LAPACK: Der Lauf ist eine
    Vorhersage mit Abstand, keine Geometrie (``kern.md``).
    """
    count = len(data["initial"])
    half = count // 2
    ftol = xtol = gtol = precision
    data = dict(data)
    noise = np.where(np.arange(count) >= half, SHADOW_NOISE, 0.0)
    final_status = np.full(count, _RUNNING, dtype=np.int64)
    final_stop = np.full(count, np.inf)
    final_decision = np.full(count, np.inf)
    final_x = np.full((count, size), np.nan)
    apart = np.zeros(half)
    width = np.ones(half)
    position = np.full(count, -1, dtype=np.int64)
    pairs = np.arange(half)

    ids = np.arange(count)
    x = data.pop("initial").copy()

    def follow() -> None:
        """Nach jeder Runde: größter Betrag des Plans, größtes Auseinander von Plan und Schatten."""
        position[:] = -1
        position[ids] = np.arange(len(ids))
        planned = ids < half
        width[ids[planned]] = np.maximum(width[ids[planned]], np.max(np.abs(x[planned]), axis=1))
        both = pairs[(position[pairs] >= 0) & (position[pairs + half] >= 0)]
        if len(both):
            gap = np.max(np.abs(x[position[both]] - x[position[both + half]]), axis=1)
            apart[both] = np.maximum(apart[both], gap)

    nfev = np.ones(count, dtype=np.int64)

    def shaded(
        values: np.ndarray, rows: _Data, spent: np.ndarray, shade: np.ndarray, want_jacobian: bool
    ) -> tuple[np.ndarray, np.ndarray | None]:
        values = values * (1.0 + shade[:, None] * _shadow_pattern(spent, size))
        return evaluate(values, rows, want_jacobian)

    f, jacobian = shaded(x, data, nfev, noise, True)
    assert jacobian is not None
    sound = np.all(np.isfinite(f), axis=1) & np.all(np.isfinite(jacobian), axis=(1, 2))
    cost = 0.5 * np.einsum("kr,kr->k", f, f)
    gradient = np.einsum("krn,kr->kn", jacobian, f)
    delta = np.sqrt(np.einsum("kn,kn->k", x, x))
    delta = np.where(delta == 0.0, 1.0, delta)
    alpha = np.zeros(count)
    fresh = np.ones(count, dtype=bool)
    stop = np.full(count, np.inf)
    decision = np.full(count, np.inf)
    singular = np.zeros((count, size))
    turn = np.zeros((count, size, size))
    projected = np.zeros((count, size))
    status = np.where(sound, _RUNNING, 0)
    follow()
    tiny = float(np.finfo(float).tiny)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        while True:
            if check_cancelled is not None:
                check_cancelled()
            # Die äußere Prüfung: nach jeder Annahme Gradient und Budget, dann die Zerlegung.
            if fresh.any():
                norm = np.where(fresh, np.max(np.abs(gradient), axis=1), np.inf)
                stop = np.minimum(stop, np.where(fresh, np.log10(norm / gtol), np.inf))
                status = np.where(fresh & (status == _RUNNING) & (norm < gtol), 1, status)
                status = np.where(fresh & (status == _RUNNING) & (nfev >= evaluations), 0, status)
            # Wer einen Abstand verfehlt, wird nicht mehr sicher (3) — und sein Partner auch nicht.
            hopeless = (decision < DECISION_MARGIN) | (stop < STOP_MARGIN_DECADES) | ~sound
            status = np.where((status == _RUNNING) & hopeless, 3, status)
            closed = ids[(status != _RUNNING) & (status != 0)]
            if len(closed):
                partners = np.where(closed < half, closed + half, closed - half)
                status = np.where((status == _RUNNING) & np.isin(ids, partners), 3, status)
            # Beendete Zeilen verlassen den Stapel.
            leaving = status != _RUNNING
            if leaving.any():
                gone = ids[leaving]
                final_status[gone] = status[leaving]
                final_x[gone] = x[leaving]
                final_stop[gone] = stop[leaving]
                final_decision[gone] = np.where(sound[leaving], decision[leaving], -np.inf)
                keep = ~leaving
                ids, x, nfev, f, jacobian = ids[keep], x[keep], nfev[keep], f[keep], jacobian[keep]
                cost, gradient, delta, alpha = cost[keep], gradient[keep], delta[keep], alpha[keep]
                fresh, stop, decision, status = (
                    fresh[keep],
                    stop[keep],
                    decision[keep],
                    status[keep],
                )
                singular, turn, projected = singular[keep], turn[keep], projected[keep]
                sound, noise = sound[keep], noise[keep]
                data = {key: value[keep] for key, value in data.items()}
            if not len(ids):
                break
            if fresh.any():
                solve = np.flatnonzero(fresh)
                u, s, vt = np.linalg.svd(jacobian[solve], full_matrices=False)
                singular[solve] = s
                turn[solve] = np.swapaxes(vt, 1, 2)
                projected[solve] = np.einsum("krn,kr->kn", u, f[solve])
                fresh[:] = False
            # Der innere Schritt, für jede verbliebene Zeile genau einer.
            step, alpha_new, margin = _trust_step(
                size, data["rows"], projected, singular, turn, delta, alpha
            )
            decision = np.minimum(decision, margin)
            moved = np.einsum("krn,kn->kr", jacobian, step)
            predicted = -(
                0.5 * np.einsum("kr,kr->k", moved, moved) + np.einsum("kn,kn->k", step, gradient)
            )
            x_new = x + step
            # Residuen und Ableitung in einem Zug: Die Ableitung am neuen Punkt
            # braucht SciPy nach jeder Annahme, und abgelehnt wird selten.
            f_new, jacobian_new = shaded(x_new, data, nfev, noise, True)
            assert jacobian_new is not None
            nfev = nfev + 1
            step_norm = np.sqrt(np.einsum("kn,kn->k", step, step))
            finite = np.all(np.isfinite(f_new), axis=1)
            sound &= finite
            cost_new = 0.5 * np.einsum("kr,kr->k", f_new, f_new)
            reduction = cost - cost_new
            positive = predicted > 0
            ratio = np.where(
                positive,
                reduction / np.where(positive, predicted, 1.0),
                np.where((predicted == 0) & (reduction == 0), 1.0, 0.0),
            )
            bound_hit = step_norm > 0.95 * delta
            delta_new = np.where(
                ratio < 0.25,
                0.25 * step_norm,
                np.where((ratio > 0.75) & bound_hit, 2.0 * delta, delta),
            )
            x_norm = np.sqrt(np.einsum("kn,kn->k", x, x))
            ended = finite & (
                ((reduction < ftol * cost) & (ratio > 0.25)) | (step_norm < xtol * (xtol + x_norm))
            )
            scale = np.maximum(np.abs(cost), tiny)
            decision = np.minimum(
                decision,
                np.minimum.reduce(
                    [
                        np.abs(ratio - 0.25),
                        np.where(bound_hit, np.abs(ratio - 0.75), np.inf),
                        np.where(ratio > 0.75, np.abs(step_norm - 0.95 * delta) / delta, np.inf),
                        np.abs(reduction) / scale,
                        np.abs(predicted) / scale,
                    ]
                ),
            )
            stop = np.minimum(
                stop,
                np.minimum(
                    np.where(ratio > 0.25, np.log10(reduction / (ftol * cost)), np.inf),
                    np.log10(step_norm / (xtol * (xtol + x_norm))),
                ),
            )
            status = np.where(ended, 2, status)
            going = finite & ~ended
            # Nicht endlich: kleinerer Radius, derselbe innere Lauf (wie SciPy).
            alpha = np.where(going, alpha_new * (delta / delta_new), alpha_new)
            delta = np.where(going, delta_new, np.where(finite, delta, 0.25 * step_norm))
            accepted = going & (reduction > 0)
            if accepted.all():
                x, f, jacobian, cost = x_new, f_new, jacobian_new, cost_new
                gradient = np.einsum("krn,kr->kn", jacobian, f)
                sound &= np.all(np.isfinite(jacobian), axis=(1, 2))
            elif accepted.any():
                taken = np.flatnonzero(accepted)
                x[taken] = x_new[taken]
                f[taken] = f_new[taken]
                jacobian[taken] = jacobian_new[taken]
                cost[taken] = cost_new[taken]
                gradient[taken] = np.einsum("krn,kr->kn", jacobian_new[taken], f_new[taken])
                sound[taken] &= np.all(np.isfinite(jacobian_new[taken]), axis=(1, 2))
            # Nach einer Annahme wird neu zerlegt; aufgebrauchtes Budget geht zur äußeren Prüfung.
            fresh = accepted | (~ended & (nfev >= evaluations))
            follow()
    safe: np.ndarray = (
        (final_status == 0)
        & (final_stop >= STOP_MARGIN_DECADES)
        & (final_decision >= DECISION_MARGIN)
    )
    return _Outcome(safe, apart / width, final_status, final_x)


def _trust_step(
    size: int,
    rows: np.ndarray,
    projected: np.ndarray,
    singular: np.ndarray,
    turn: np.ndarray,
    delta: np.ndarray,
    initial_alpha: np.ndarray,
    rtol: float = 0.01,
    max_iter: int = 10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``solve_lsq_trust_region`` je Problem, dazu der kleinste Abstand jeder Entscheidung darin."""
    tiny = float(np.finfo(float).tiny)
    scaled = singular * projected
    threshold = _EPS * rows * singular[:, 0]
    square = rows >= size
    full_rank = square & (singular[:, -1] > threshold)
    margin = np.where(
        square, np.abs(singular[:, -1] - threshold) / np.maximum(threshold, tiny), np.inf
    )
    gauss = -np.einsum("kij,kj->ki", turn, projected / singular)
    gauss_norm = np.sqrt(np.einsum("ki,ki->k", gauss, gauss))
    gauss_newton = full_rank & (gauss_norm <= delta)
    margin = np.minimum(margin, np.where(full_rank, np.abs(gauss_norm - delta) / delta, np.inf))
    squares = singular * singular

    def phi_and_derivative(alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        denominator = squares + alpha[:, None]
        ratio = scaled / denominator
        p_norm = np.sqrt(np.sum(ratio * ratio, axis=1))
        return p_norm - delta, -np.sum(ratio * ratio / denominator, axis=1) / p_norm

    upper = np.sqrt(np.sum(scaled * scaled, axis=1)) / delta
    phi, derivative = phi_and_derivative(np.zeros(len(delta)))
    lower = np.where(full_rank, -phi / derivative, 0.0)
    restart = ~full_rank & (initial_alpha == 0)
    alpha = np.where(restart, np.maximum(0.001 * upper, np.sqrt(lower * upper)), initial_alpha)
    done = gauss_newton.copy()
    for _ in range(max_iter):
        active = ~done
        if not active.any():
            break
        outside = (alpha < lower) | (alpha > upper)
        near_bound = np.minimum(
            np.abs(alpha - lower) / np.maximum(np.abs(lower), tiny),
            np.abs(alpha - upper) / np.maximum(np.abs(upper), tiny),
        )
        margin = np.minimum(margin, np.where(active, near_bound, np.inf))
        alpha = np.where(active & outside, np.maximum(0.001 * upper, np.sqrt(lower * upper)), alpha)
        phi, derivative = phi_and_derivative(alpha)
        upper = np.where(active & (phi < 0), alpha, upper)
        ratio = phi / derivative
        lower = np.where(active, np.maximum(lower, alpha - ratio), lower)
        alpha = np.where(active, alpha - (phi + delta) * ratio / delta, alpha)
        margin = np.minimum(
            margin, np.where(active, np.abs(np.abs(phi) - rtol * delta) / delta, np.inf)
        )
        done = done | (active & (np.abs(phi) < rtol * delta))
    step = -np.einsum("kij,kj->ki", turn, scaled / (squares + alpha[:, None]))
    step = step * (delta / np.sqrt(np.einsum("ki,ki->k", step, step)))[:, None]
    step = np.where(gauss_newton[:, None], gauss, step)
    alpha = np.where(gauss_newton, 0.0, alpha)
    margin = np.where(np.isnan(margin), -np.inf, margin)
    return step, alpha, margin
