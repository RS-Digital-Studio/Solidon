"""Urteile, Abhakliste und Funddatei des Funktionsdurchgangs (RM-737, Paket D0-U).

Was der Prüfstand gemessen hat (``<out>/cases/<nr>/function.json``), wird hier
mit ``tools/function_points.py`` beurteilt und mit den Urteilen der Stufen B
und C (``urteile-<paket>.toml``, Konzept §5, Stufe B) und der Funddatei
(``funde.md``, Konzept §7) zur Abhakliste je Paket zusammengeführt
(``abhakliste-<paket>.md``, Konzept §7). Alle drei liegen unter
``.claude/.state/funktionsdurchgang-2026-10/``; Bilder und Rohdaten bleiben
außerhalb des Baums.

* **Urteile werden geprüft, bevor sie zählen** (:func:`check_verdicts`): ohne
  Bild oder Stelle, ein Bild mit dem Pfad eines Rechners, *offen* ohne RM, ein
  fremder *entfällt*-Grund, G9 schwerer als leicht und „gut“ gegen einen Fund
  der Stufe A werden abgewiesen.
* **Die Urteilsdatei nennt ihren Lauf** (:func:`check_runs`): ``[[run]]`` mit
  Name, Kopf und Siegel; die Bilder stehen relativ dazu, und die Abhakliste
  nennt ihn als Laufordner — nicht die Kopie, aus der sie entstand.
* **Die Abhakliste ist erzeugt, nie von Hand** (:func:`render_checklist`):
  gleiche Eingaben, gleiche Bytes; eine Datei je Paket, damit zwei parallele
  Pakete keine erzeugte Datei mergen.
* **Zwei Prüfer** (:func:`agreement`): Stimmen weniger als 90 % der Urteile je
  Prüfpunkt überein, wird es markiert.
* **Paketanteile** (:func:`input_share`, :func:`goal_share`,
  :func:`solution_count`): E2, I3 und die Zahl von I4.
* **Fensterbefehle** (:func:`compare_window_commands`): die Menüleiste am
  gebauten Fenster gegen die Zeilen der Abhaklisten, für den ``rendered``-Test.

Kein Einstieg: ``tools/file_acceptance.py report`` ruft :func:`write`.
"""

from __future__ import annotations

import ast
import copy
import datetime
import functools
import hashlib
import html
import json
import re
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from app.ui.op_dialog import MAX_FRONT_FIELDS, USUAL_FRONT_SHARE
from tools.function_checks import (
    AGREEMENT,
    CHECKPOINTS,
    COARSE_NOTE,
    CRITERIA,
    FINDING_KINDS,
    GOAL_SHARE,
    GOOD_OVER_FINDING,
    INPUT_SHARE,
    MAX_INPUTS,
    NOT_APPLICABLE_OVER_FINDING,
    SECOND_REVIEW_SHARE,
    SEVERITIES,
    UNMEASURED_VERDICT,
    CaseOutcome,
    Context,
    Issue,
    Outcome,
)
from tools.function_judges import compare_themes, judge_sizes
from tools.function_list import NOT_APPLICABLE_REASONS, ROW_KINDS
from tools.function_points import judge_case, judge_design, judge_licence
from tools.function_samples import BrokenSample, sample_context, sample_protocol

ROOT: Final = Path(__file__).resolve().parent.parent

#: Wo Urteile, Abhaklisten und Funddatei liegen (Konzept §7).
STATE: Final = ROOT / ".claude" / ".state" / "funktionsdurchgang-2026-10"

#: Wortliste für V1 (Teilpaket D0-L): Negativ- und Positivliste.
VOCABULARY: Final = ROOT / "tests" / "data" / "customer_vocabulary.json"

#: Der eingefrorene Bestand zu langer Texte (``tests/test_text_length.py``), V2.
TEXT_LENGTHS: Final = ROOT / "tests" / "data" / "text_lengths"

#: Die häufigsten Kundenziele für I3 (Teilpaket D0-L).
COMMON_GOALS: Final = ROOT / "tests" / "data" / "common_goals.toml"

#: Die Website-Seiten, an denen Prüfpunkt 11 die Fundstellen sucht.
WEBSITE: Final = ROOT / "website"

#: Urteile je Zeile (Konzept §5, Stufe B): Werte und Prüfer.
VERDICTS: Final = ("gut", "gut_nach_fix", "offen", "entfaellt")
REVIEWERS: Final = ("stufe_b", "zweitpruefer", "stufe_c")

#: Der Vergleich mit Slicer, Tinkercad und Shapr3D (Konzept §4, „Der Vergleich“):
#: Zeilen ``vergleich:<ansicht>``, je Z3 bis Z6 besser, gleich oder schlechter.
COMPARISONS: Final = ("besser", "gleich", "schlechter")
COMPARED: Final = frozenset({"Z3", "Z4", "Z5", "Z6"})
COMPARISON_ROW: Final = "vergleich:"

#: Die Schlüssel eines Urteils; ein anderer wird abgewiesen.
VERDICT_KEYS: Final = frozenset(
    {
        "row",
        "point",
        "criterion",
        "verdict",
        "reviewer",
        "reason",
        "image",
        "no_image",
        "place",
        "finding",
        "rm",
        "not_applicable",
        "design_judgement",
        "prediction",
        "comparison",
        "steps",
        "misclicks",
    }
)

#: Wo das Urteil selbst die Messung ist: die Vorhersage (V4), das
#: Gestaltungsurteil zu G9 und das Protokoll der Stufe C (Z7). Nur hier darf
#: „gut“ an einem Ergebnis stehen, das Stufe A nicht gemessen hat.
JUDGED_BY_VERDICT: Final = frozenset({"V4", "G9", "Z7"})

#: Kriterien, deren Urteil als Gestaltungsurteil gekennzeichnet sein muss.
DESIGN_SUBJECTS: Final = frozenset(key for key, c in CRITERIA.items() if c.design_judgement)

#: Wo ein Fund *Vorschlag* sein darf: I ohne Bauplanzusage und G9 (Konzept §4).
#: I6 ist hier nur die Suche mit Frageformen; der Chatweg zu I6 ist eine
#: Bauplanzusage und steht als Fund an Prüfpunkt 17 (Agentenweg), der kein
#: Vorschlag sein kann (:data:`_CHAT_WAY`).
PROPOSALS: Final = frozenset(
    key for key, c in CRITERIA.items() if key[0] == "I" and not c.promised
) | {"G9"}

#: Woran ein Fund zu I6 als Chatweg erkennbar ist: Er spricht vom Chat oder vom
#: Agenten. Dann gilt Prüfpunkt 17 (Konzept §4, I6), und ein Vorschlag geht nicht.
_CHAT_WAY: Final = re.compile(r"\b(?:chat|agent)", re.IGNORECASE)
_CHAT_FIELDS: Final = ("Funktion", "Beleg", "Ursache", "Vorschlag", "Wirkung beim Kunden")

#: Felder eines Funds (Konzept §7); ``Prüfpunkt`` nimmt auch eine Kennung E1 … I6.
FINDING_FIELDS: Final = (
    "Art",
    "Schwere",
    "Funktion",
    "Prüfpunkt",
    "Beleg",
    "Ursache",
    "Vorschlag",
    "Wirkung beim Kunden",
    "Stand",
)

_FD_HEADING: Final = re.compile(r"^###\s+FD-(\d+)\s+(\S.*?)\s*$")
_FIELD_LINE: Final = re.compile(
    r"^\s*(?:[-*]\s+)?\*{0,2}(?P<field>Art|Schwere|Funktion|Prüfpunkt|Kriterium|Beleg|Ursache"
    r"|Vorschlag|Wirkung beim Kunden|Stand)\*{0,2}\s*:\s*\*{0,2}\s*(?P<value>.*?)\s*$"
)
_STAND: Final = (
    re.compile(r"^offen\b.*\bRM-\d+"),
    re.compile(r"^behoben\b.*`[0-9a-f]{7,40}`"),
    # Kein FD ohne Commit oder RM (Konzept §10): auch „gut nach Fix“ nennt
    # den Commit, der behoben hat, dazu den Lauf, der es belegt.
    re.compile(r"^gut nach Fix\b.*`[0-9a-f]{7,40}`"),
)
_RM: Final = re.compile(r"\bRM-\d+\b")

#: Ein Bild steht relativ zum Laufordner (``--out``), mit ``/`` und als PNG;
#: eines aus einer anderen Runde trägt die Kennung ihres ``[[run]]`` davor
#: (``v4:cases/001/v4-nachher.png``). So hängt kein Urteil im Baum an einem
#: Rechner, und das Bildfeld trägt nur Bilder (RD-5).
_IMAGE: Final = re.compile(r"(?:(?P<run>[a-z][a-z0-9_-]+):)?(?P<path>[^\\:]+\.png)")

#: Ein Pfad mit Laufwerk — er gilt nur an dem Rechner, der ihn schrieb.
_MACHINE_PATH: Final = re.compile(r"(?<!\w)[A-Za-z]:[\\/]")

#: Die Schlüssel einer Laufangabe ``[[run]]``; ``key`` fehlt am Laufordner.
RUN_KEYS: Final = frozenset({"key", "name", "head", "seal"})
_RUN_KEY: Final = re.compile(r"[a-z][a-z0-9_-]+")
_HEAD: Final = re.compile(r"[0-9a-f]{7,40}")
_SHA256: Final = re.compile(r"\b[0-9a-f]{64}\b")


# --- Kontext aus dem Baum ---------------------------------------------------


def read_negative_words(path: Path = VOCABULARY) -> tuple[tuple[str, str, str], ...]:
    """Die Negativliste aus ``customer_vocabulary.json`` (Teilpaket D0-L).

    Je Eintrag unter ``negative`` Wort, Sprache und Suchmuster (``pattern``,
    ``re``); ohne Muster steht das Wort als ganzes Wort. Dieselbe Liste baut
    ``tests/test_wording.py`` zu seinen Wächtern — eine Quelle für beide.
    Fehlt die Datei, ist die Liste leer, und V1 ist „nicht prüfbar“, nie „gut“.
    """
    if not path.is_file():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("negative", ()) if isinstance(data, Mapping) else ()
    found = []
    for entry in entries:
        if not isinstance(entry, Mapping) or not str(entry.get("word") or "").strip():
            continue
        word = str(entry["word"]).strip()
        pattern = str(entry.get("pattern") or rf"(?<!\w){re.escape(word)}(?!\w)")
        found.append((word, str(entry.get("language") or "de"), pattern))
    return tuple(found)


def read_frozen_texts(folder: Path = TEXT_LENGTHS) -> frozenset[str]:
    """Der eingefrorene Bestand zu langer Texte, über alle Arten (V2)."""
    texts: set[str] = set()
    for path in sorted(folder.rglob("*.json")):
        texts.update(str(text) for text in json.loads(path.read_text(encoding="utf-8")))
    return frozenset(texts)


def read_common_goals(path: Path = COMMON_GOALS) -> dict[str, str]:
    """Die häufigsten Kundenziele für I3: Kennung des Ziels → Ziel der Zeile.

    ``[[goal]]`` mit ``id`` und ``target`` (Teilpaket D0-L): ``operation:<op>``
    als Hauptaktion, ``feature:<schlüssel>`` oder ``edge:<op>`` als Feld oben.
    Gezählt wird an der Zeile, deren ``target`` dasselbe Ziel nennt.
    """
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        str(goal["id"]): str(goal["target"])
        for goal in data.get("goal", ())
        if isinstance(goal, Mapping) and goal.get("id") and goal.get("target")
    }


def _translated(msgid: str) -> Callable[[str], str]:
    """Ein Quelltext in einer Sprache, aus ihrem Katalog."""

    @functools.cache
    def in_language(language: str) -> str:
        from app.i18n import SOURCE_LANGUAGE
        from app.i18n.catalog import read_catalog

        if language == SOURCE_LANGUAGE:
            return msgid
        return read_catalog(language).get(msgid) or msgid

    return in_language


@functools.cache
def _manual_index() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    """Seiten und Sprungmarken des Handbuchs, einmal erzeugt."""
    from app.core import manual

    keys = frozenset(page.key for page in manual.pages())
    anchors = {
        key: frozenset(anchor for anchor, _title in manual.reference_anchors(key))
        for key in keys
        if key.startswith(manual.REFERENCE_PAGE_PREFIX)
    }
    return keys, anchors


def manual_place(row: Mapping[str, Any]) -> str | None:
    """Seite und Stelle im Handbuch (``manual.help_for``) — nur, wenn es sie gibt."""
    from app.core import manual
    from app.core.registry import REGISTRY

    name = str(row.get("id", ""))
    if not REGISTRY.has(name):
        return None
    page, anchor = manual.help_for(name)
    keys, anchors = _manual_index()
    if page not in keys:
        return None
    if anchor and anchor.lstrip("#") not in anchors.get(page, frozenset()):
        return None
    return f"{page}{anchor}"


@functools.cache
def _website_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    return html.unescape(re.sub(r"<[^>]+>", " ", raw)).lower()


def _website_pages() -> dict[str, Path]:
    """Die Funktionsseite je Sprache: ``funktionen.html`` und ``<sprache>/features.html``."""
    from app.i18n import SOURCE_LANGUAGE
    from app.i18n.catalog import available_languages

    pages = {SOURCE_LANGUAGE: WEBSITE / "funktionen.html"}
    for language in available_languages():
        if language != SOURCE_LANGUAGE:
            pages[language] = WEBSITE / language / "features.html"
    return {language: path for language, path in pages.items() if path.is_file()}


def _website_hits(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Welche Funktionsseiten den Titel der Operation in ihrer Sprache nennen."""
    from app.core.registry import REGISTRY
    from app.i18n import source_text

    name = str(row.get("id", ""))
    if not REGISTRY.has(name):
        return ()
    title = source_text(REGISTRY.get(name).title)
    hits = []
    for language, path in sorted(_website_pages().items()):
        said = _translated(title)(language).lower()
        if said and said in _website_text(path):
            hits.append(path.relative_to(ROOT).as_posix())
    return tuple(hits)


def agent_place(row: Mapping[str, Any]) -> tuple[str, str] | None:
    """Ort und Menüpfad, die das Agentenwerkzeug nennt.

    Der Ort kommt aus ``registry.menu_place`` — derselben Verzweigung, der
    ``menu_path`` folgt —, nicht aus einer zweiten Herleitung über Kategorien.
    """
    from app.core.registry import REGISTRY, menu_path, menu_place

    name = str(row.get("id", ""))
    if row.get("kind") != "operation" or not REGISTRY.has(name):
        return None
    spec = REGISTRY.get(name)
    return menu_place(spec), menu_path(spec)


def repository_context() -> Context:
    """Der Kontext aus dem Baum: Wortliste, eingefrorene Texte, Handbuch, Website, Register."""
    from app.core.bootstrap import load_operations

    load_operations()
    return Context(
        negative_words=read_negative_words(),
        frozen_texts=read_frozen_texts(),
        coarse_note=_translated(COARSE_NOTE),
        manual_place=manual_place,
        website_hits=_website_hits,
        agent_place=agent_place,
        common_goal_targets=frozenset(read_common_goals().values()),
    )


def finding_solutions(app_root: Path = ROOT / "app") -> dict[str, bool]:
    """I4: je Befundart, ob der Prüfbericht eine behebende Handlung anbietet.

    Befundarten sind die festen Codes, mit denen ``Finding(code=…)`` im Code
    steht, und die Schlüssel von ``panels.FINDING_ACTIONS``. Die Befunde des
    Agenten (``app/core/agent``) erscheinen im Chat und nicht im Prüfbericht;
    Codes, die zur Laufzeit zusammengesetzt werden (``op.<op>.<Ausnahme>``),
    sind keine Art, sondern eine Familie, und zählen nicht mit.
    """
    from app.ui.panels import FINDING_ACTIONS

    codes: set[str] = set()
    files = sorted(app_root.rglob("*.py"))
    assert files, f"keine Quelltexte unter {app_root}"
    for path in files:
        if "agent" in path.relative_to(app_root).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else None
            name = node.func.id if isinstance(node.func, ast.Name) else name
            if name != "Finding":
                continue
            for keyword in node.keywords:
                value = keyword.value
                if (
                    keyword.arg == "code"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    codes.add(value.value)
    codes |= set(FINDING_ACTIONS)
    return {code: code in FINDING_ACTIONS for code in sorted(codes)}


# --- Urteile (Konzept §5, Stufe B) ---------------------------------------------------------


def subject_of(entry: Mapping[str, Any]) -> int | str | None:
    """Prüfpunkt oder Kriterium eines Urteils."""
    if "point" in entry:
        point = entry["point"]
        return point if isinstance(point, int) else None
    criterion = entry.get("criterion")
    return str(criterion) if criterion is not None else None


def read_verdict_file(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Urteile ``[[verdict]]`` und Laufangaben ``[[run]]`` einer Urteilsdatei; fehlt sie, keine."""
    if not path.is_file():
        return [], []
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    def tables(name: str) -> list[dict[str, Any]]:
        return [dict(entry) for entry in data.get(name, []) if isinstance(entry, Mapping)]

    return tables("verdict"), tables("run")


def image_problem(image: str) -> str | None:
    """Warum ein Bildverweis nicht trägt — ``None``, wenn er relativ zum Laufordner steht."""
    found = _IMAGE.fullmatch(image)
    parts = found.group("path").split("/") if found else []
    if found is None or any(part in {"", ".", ".."} or part != part.strip() for part in parts):
        return f"Bild nicht relativ zum Laufordner: {image}"
    return None


def image_run(image: str) -> str | None:
    """Die Kennung des ``[[run]]`` vor einem Bild; ``None`` heißt Laufordner."""
    found = _IMAGE.fullmatch(image)
    return found.group("run") if found else None


def run_folder(runs: Iterable[Mapping[str, Any]]) -> str | None:
    """Der Name des Laufordners aus den Laufangaben — der Lauf ohne Kennung."""
    return next((str(run.get("name")) for run in runs if run.get("key") is None), None)


def check_runs(
    runs: Sequence[Mapping[str, Any]],
    entries: Iterable[Mapping[str, Any]],
    commits: Iterable[str] = (),
) -> list[str]:
    """Warum die Laufangaben einer Urteilsdatei nicht tragen — leer, wenn sie es tun.

    Jeder Lauf nennt Name, Kopf und ein Siegel mit SHA256; eine Kennung steht
    für genau einen Lauf, der Lauf ohne Kennung ist der Laufordner (``--out``).
    Jede Runde einer Datei darf ihre Läufe wiederholen, gleich lautend. Ein Bild
    braucht seinen Lauf, und der Laufordner hat den Kopf der Protokolle — sonst
    nennte die Abhakliste einen Lauf, den sie nicht gelesen hat.
    """
    problems: list[str] = []
    known: dict[str | None, Mapping[str, Any]] = {}
    for run in runs:
        label = run.get("key")
        name = str(run.get("name") or "").strip()
        title = f"Lauf {name or '?'}"
        problems += [f"{title}: unbekannter Schlüssel {key}" for key in sorted(set(run) - RUN_KEYS)]
        if label is not None and not _RUN_KEY.fullmatch(str(label)):
            problems.append(
                f"{title}: Kennung {label} besteht nicht aus Kleinbuchstaben, Ziffern, - und _"
            )
        if not name or _MACHINE_PATH.search(name):
            problems.append(f"{title}: ohne Namen oder mit Pfad dieses Rechners")
        if not _HEAD.fullmatch(str(run.get("head") or "")):
            problems.append(f"{title}: Kopf {run.get('head')} ist kein Commit")
        if not _SHA256.search(str(run.get("seal") or "")):
            problems.append(f"{title}: Siegel ohne SHA256")
        if label in known and dict(known[label]) != dict(run):
            problems.append(f"Kennung {label or '(Laufordner)'} steht für zwei Läufe")
        known.setdefault(label, run)
    used = {
        image_run(str(entry["image"])) for entry in entries if str(entry.get("image") or "").strip()
    }
    for label in sorted(used - set(known), key=str):
        problems.append(
            "Bilder ohne Laufangabe" if label is None else f"Bilder aus unbekanntem Lauf {label}"
        )
    main = known.get(None)
    shown = [commit for commit in commits if _HEAD.fullmatch(commit)]
    if main is not None and shown:
        head = str(main.get("head"))
        if not any(commit.startswith(head) or head.startswith(commit) for commit in shown):
            problems.append(
                f"Laufordner {main.get('name')} hat Kopf {head}, die Protokolle {', '.join(shown)}"
            )
    return problems


@dataclass(frozen=True)
class Finding:
    """Ein Fund aus der Funddatei (Konzept §7)."""

    number: int
    title: str
    fields: Mapping[str, str]

    @property
    def key(self) -> str:
        return f"FD-{self.number}"

    @property
    def subjects(self) -> tuple[int | str, ...]:
        """Prüfpunkte und Kriterien aus ``Prüfpunkt`` und ``Kriterium``."""
        raw = ", ".join(self.fields.get(name, "") for name in ("Prüfpunkt", "Kriterium"))
        found: list[int | str] = []
        for token in re.split(r"\s*(?:,|;|\bund\b)\s*", raw):
            token = token.strip().rstrip(".")
            if token.isdigit():
                found.append(int(token))
            elif token:
                found.append(token)
        return tuple(found)

    @property
    def rows(self) -> frozenset[str]:
        """Die Zeilen aus ``Funktion``, getrennt wie die Prüfpunkte (FD-143).

        Zeilenkennungen tragen weder Komma, Semikolon noch „und“; ein Fund, der
        mehrere Zeilen nennt, gehört so jeder von ihnen.
        """
        raw = self.fields.get("Funktion", "")
        parts = (
            part.strip().strip("`").strip() for part in re.split(r"\s*(?:,|;|\bund\b)\s*", raw)
        )
        return frozenset(part for part in parts if part)

    @property
    def severity(self) -> str:
        return self.fields.get("Schwere", "").rstrip(".")

    @property
    def stand(self) -> str:
        return self.fields.get("Stand", "")


@dataclass(frozen=True)
class Checked:
    """Geprüfte Urteile: angenommen und abgewiesen, mit Grund."""

    accepted: tuple[dict[str, Any], ...]
    rejected: tuple[tuple[dict[str, Any], tuple[str, ...]], ...]


def _verdict_problems(
    entry: Mapping[str, Any],
    outcomes: Mapping[str, CaseOutcome],
    rows: frozenset[str] | None,
    findings: Mapping[str, Finding] | None,
) -> list[str]:
    """Warum ein Urteil abgewiesen wird — leer, wenn es zählt."""
    problems = [f"unbekannter Schlüssel: {key}" for key in sorted(set(entry) - VERDICT_KEYS)]
    for key in ("row", "verdict", "reviewer", "reason"):
        if not str(entry.get(key) or "").strip():
            problems.append(f"{key} fehlt")
    if ("point" in entry) == ("criterion" in entry):
        problems.append("genau eines von point und criterion")
    subject = subject_of(entry)
    if "point" in entry and subject not in CHECKPOINTS:
        problems.append(f"kein Prüfpunkt: {entry.get('point')}")
    if "criterion" in entry and subject not in CRITERIA:
        problems.append(f"kein Kriterium: {entry.get('criterion')}")
    verdict, reviewer = entry.get("verdict"), entry.get("reviewer")
    if verdict is not None and verdict not in VERDICTS:
        problems.append(f"unbekanntes Urteil: {verdict}")
    if reviewer is not None and reviewer not in REVIEWERS:
        problems.append(f"unbekannter Prüfer: {reviewer}")
    # Bild oder ausdrücklich keins: ``no_image`` sagt, warum der Lauf keins hat.
    image = str(entry.get("image") or "").strip()
    place = str(entry.get("place") or "")
    if verdict != "entfaellt" and not (
        (image or str(entry.get("no_image") or "").strip()) and place.strip()
    ):
        problems.append("ohne Bild oder Stelle")
    if "image" in entry and "no_image" in entry:
        problems.append("Bild und Grund ohne Bild zugleich")
    if image and (problem := image_problem(str(entry["image"]))):
        problems.append(problem)
    if _MACHINE_PATH.search(place):
        problems.append("Stelle mit Pfad dieses Rechners")
    if verdict == "offen" and not _RM.search(str(entry.get("rm") or "")):
        problems.append("offen ohne RM-Nummer")
    if verdict == "entfaellt" and entry.get("not_applicable") not in NOT_APPLICABLE_REASONS:
        problems.append(f"fremder entfällt-Grund: {entry.get('not_applicable')}")
    if verdict != "entfaellt" and "not_applicable" in entry:
        problems.append("Grund für entfällt ohne Urteil entfällt")
    finding = entry.get("finding")
    if finding is not None and not re.fullmatch(r"FD-\d+", str(finding)):
        problems.append(f"Fund nicht als FD-n: {finding}")
    if verdict == "gut_nach_fix" and finding is None:
        problems.append("gut nach Fix ohne Fund")
    if finding is not None and findings is not None and str(finding) not in findings:
        problems.append(f"{finding} steht nicht in der Funddatei")
    comparison = entry.get("comparison")
    designed = subject in DESIGN_SUBJECTS or comparison is not None
    if designed and entry.get("design_judgement") is not True:
        problems.append("Gestaltungsurteil nicht als solches gekennzeichnet")
    if entry.get("design_judgement") and not designed and subject != 19:
        problems.append("Gestaltungsurteil an einem Kriterium, das kein Urteil ist")
    if comparison is not None:
        if comparison not in COMPARISONS or subject not in COMPARED:
            problems.append(f"Vergleich {comparison} an {subject}")
        if not str(entry.get("row")).startswith(COMPARISON_ROW):
            problems.append(f"Vergleich an einer Zeile ohne {COMPARISON_ROW}")
    if subject == "V4" and not str(entry.get("prediction") or "").strip():
        problems.append("V4 ohne vorher geschriebene Vorhersage")
    if subject == "Z7":
        if reviewer != "stufe_c":
            problems.append("Z7 urteilt nur Stufe C")
        for key in ("steps", "misclicks"):
            if not isinstance(entry.get(key), int) or entry[key] < 0:
                problems.append(f"Z7-Protokoll ohne Zahl {key}")
    if (
        subject == "G9"
        and findings is not None
        and finding in findings
        and findings[str(finding)].severity not in {"leicht", "Vorschlag"}
    ):
        problems.append("G9 schwerer als leicht")
    row = str(entry.get("row") or "")
    if rows is not None and row not in rows and not row.startswith(COMPARISON_ROW):
        problems.append(f"unbekannte Zeile: {row}")
    case = outcomes.get(row)
    measured = case.get(subject) if case is not None and subject is not None else None
    if measured is not None:
        if verdict in {"gut", "gut_nach_fix"} and measured.verdict == "fund":
            problems.append(GOOD_OVER_FINDING)
        # Was Stufe A nicht gemessen hat oder nicht prüfen konnte, macht ein
        # Urteil nicht grün — außer wo das Urteil selbst die Messung ist (V4,
        # G9, Z7: Vorhersage, Gestaltungsurteil, Protokoll der Stufe C).
        if (
            verdict in {"gut", "gut_nach_fix"}
            and measured.verdict in {"nicht_gelaufen", "nicht_pruefbar"}
            and subject not in JUDGED_BY_VERDICT
        ):
            problems.append(UNMEASURED_VERDICT)
        # *entfällt* deckt keinen Fund zu: was gemessen schiefging, gilt.
        if verdict == "entfaellt" and measured.verdict == "fund":
            problems.append(NOT_APPLICABLE_OVER_FINDING)
    return problems


def check_verdicts(
    entries: Iterable[Mapping[str, Any]],
    *,
    outcomes: Mapping[str, CaseOutcome] | None = None,
    rows: Iterable[str] | None = None,
    findings: Mapping[str, Finding] | None = None,
) -> Checked:
    """Prüft Urteile gegen das Format, die Messung der Stufe A und die Funddatei.

    Das Format steht in Konzept §5, Stufe B.
    """
    known = frozenset(rows) if rows is not None else None
    accepted: list[dict[str, Any]] = []
    rejected: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        problems = _verdict_problems(entry, outcomes or {}, known, findings)
        key = (str(entry.get("row")), str(subject_of(entry)), str(entry.get("reviewer")))
        if key in seen:
            problems.append("doppeltes Urteil derselben Stufe")
        seen.add(key)
        if problems:
            rejected.append((dict(entry), tuple(problems)))
        else:
            accepted.append(dict(entry))
    return Checked(tuple(accepted), tuple(rejected))


# --- Funddatei (Konzept §7) --------------------------------------------------------


def parse_findings(text: str) -> tuple[list[Finding], list[str]]:
    """Die Funde der Funddatei und was an ihrer Form nicht stimmt.

    Je Fund eine Überschrift ``### FD-<n> <Kurztitel>``, darunter Zeilen
    ``**Feld:** Wert``; Folgezeilen gehören zum Feld darüber.
    """
    findings: list[Finding] = []
    problems: list[str] = []
    current: tuple[int, str, dict[str, str]] | None = None
    last: str | None = None

    def close() -> None:
        if current is not None:
            findings.append(Finding(current[0], current[1], dict(current[2])))

    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            close()
            current, last = None, None
            heading = _FD_HEADING.match(line)
            if heading:
                current = (int(heading.group(1)), heading.group(2), {})
            elif re.match(r"^#+\s+FD", line):
                problems.append(f"Zeile {number}: Überschrift nicht als ### FD-<n> <Kurztitel>")
            continue
        if current is None:
            continue
        field_line = _FIELD_LINE.match(line)
        if field_line:
            last = field_line.group("field")
            current[2][last] = field_line.group("value")
        elif last is not None and line.strip():
            current[2][last] = f"{current[2][last]} {line.strip()}".strip()
    close()
    return findings, problems


def check_findings(findings: Sequence[Finding]) -> list[str]:
    """Nummern eindeutig, Art und Schwere aus der Liste, Stand gesetzt (Konzept §7)."""
    problems = []
    numbers = [finding.number for finding in findings]
    for number in sorted({n for n in numbers if numbers.count(n) > 1}):
        problems.append(f"FD-{number} kommt mehrfach vor")
    for finding in findings:
        name = finding.key
        for key in FINDING_FIELDS:
            if key == "Prüfpunkt":
                continue
            if not finding.fields.get(key, "").strip():
                problems.append(f"{name}: {key} fehlt")
        kind = finding.fields.get("Art", "").rstrip(".")
        if kind and kind not in FINDING_KINDS:
            problems.append(f"{name}: Art {kind} nicht aus der Liste")
        severity = finding.severity
        if severity and severity not in SEVERITIES:
            problems.append(f"{name}: Schwere {severity} nicht aus der Liste")
        subjects = finding.subjects
        if not subjects:
            problems.append(f"{name}: Prüfpunkt oder Kriterium fehlt")
        for subject in subjects:
            if subject not in CHECKPOINTS and subject not in CRITERIA:
                problems.append(f"{name}: {subject} ist weder Prüfpunkt noch Kriterium")
        if "G9" in subjects and severity not in {"leicht", "Vorschlag"}:
            problems.append(f"{name}: G9 ist höchstens leicht, nicht {severity}")
        if severity == "Vorschlag" and not (subjects and set(subjects) <= PROPOSALS):
            problems.append(
                f"{name}: Vorschlag nur bei I ohne Bauplanzusage oder G9, nicht bei {subjects}"
            )
        elif (
            severity == "Vorschlag"
            and "I6" in subjects
            and any(_CHAT_WAY.search(finding.fields.get(key, "")) for key in _CHAT_FIELDS)
        ):
            problems.append(
                f"{name}: Der Chatweg zu I6 ist eine Bauplanzusage — Fund an Prüfpunkt 17, "
                "kein Vorschlag"
            )
        stand = finding.stand
        if stand and not any(pattern.search(stand) for pattern in _STAND):
            problems.append(
                f"{name}: Stand „{stand}“ ist weder offen RM-…, behoben `…` noch gut nach Fix"
            )
    return problems


def read_findings(path: Path) -> tuple[dict[str, Finding], list[str]]:
    """Die Funddatei: Funde nach Nummer und alle Probleme; fehlt sie, nichts."""
    if not path.is_file():
        return {}, []
    findings, problems = parse_findings(path.read_text(encoding="utf-8"))
    problems += check_findings(findings)
    return {finding.key: finding for finding in findings}, problems


# --- Zwei Prüfer und Paketanteile ------------------------------------------------


@dataclass(frozen=True)
class Share:
    """Ein gemessener Anteil gegen seine Schwelle."""

    hits: int
    total: int
    threshold: float

    @property
    def value(self) -> float | None:
        return self.hits / self.total if self.total else None

    @property
    def flagged(self) -> bool:
        """Unter der Schwelle — oder gar nicht gemessen, was nie „erfüllt“ heißt."""
        return self.value is None or self.value < self.threshold

    def text(self) -> str:
        if self.value is None:
            return "nicht gemessen"
        return f"{self.value:.0%} ({self.hits} von {self.total})"


def agreement(entries: Iterable[Mapping[str, Any]]) -> dict[str, Share]:
    """Übereinstimmung von Stufe B und Zweitprüfer je Prüfpunkt und Kriterium."""
    first: dict[tuple[str, str], str] = {}
    second: dict[tuple[str, str], str] = {}
    for entry in entries:
        key = (str(entry.get("row")), str(subject_of(entry)))
        if entry.get("reviewer") == "stufe_b":
            first[key] = str(entry.get("verdict"))
        elif entry.get("reviewer") == "zweitpruefer":
            second[key] = str(entry.get("verdict"))
    pairs: dict[str, list[bool]] = {}
    for key in sorted(set(first) & set(second)):
        pairs.setdefault(key[1], []).append(first[key] == second[key])
    return {
        subject: Share(sum(same), len(same), AGREEMENT)
        for subject, same in sorted(pairs.items(), key=lambda item: _subject_order(item[0]))
    }


def input_share(inputs: Iterable[int]) -> Share:
    """E2: Anteil der Zeilen mit höchstens einer Pflichteingabe."""
    counted = list(inputs)
    return Share(sum(1 for n in counted if n <= MAX_INPUTS), len(counted), INPUT_SHARE)


def front_share(fronts: Iterable[int]) -> Share:
    """E5: Anteil der Zeilen mit höchstens drei Feldern vorn — vier sind die Ausnahme.

    Dieselbe Schwelle wie ``test_interface_limits`` über das Register
    (``op_dialog.USUAL_FRONT_SHARE``), hier am offenen Dialog gemessen.
    """
    counted = list(fronts)
    usual = sum(1 for n in counted if n <= MAX_FRONT_FIELDS - 1)
    return Share(usual, len(counted), USUAL_FRONT_SHARE)


def goal_share(reached: Iterable[bool]) -> Share:
    """I3: Anteil der häufigsten Kundenziele, die ohne Suche und Aufklappen dastehen."""
    counted = list(reached)
    return Share(sum(1 for hit in counted if hit), len(counted), GOAL_SHARE)


@dataclass(frozen=True)
class Solutions:
    """I4: Befundarten mit und ohne behebende Handlung."""

    with_action: int
    without: tuple[str, ...]

    def text(self) -> str:
        total = self.with_action + len(self.without)
        return f"{self.with_action} von {total} mit Handlung, {len(self.without)} Vorschläge"


def solution_count(kinds: Mapping[str, bool]) -> Solutions:
    """I4: Zahl genannt; jede Art ohne Handlung ist ein Vorschlag."""
    return Solutions(
        sum(1 for has in kinds.values() if has),
        tuple(sorted(kind for kind, has in kinds.items() if not has)),
    )


# --- Fälle zusammenführen ------------------------------------------------------

_BADNESS: Final = {
    "fund": 5,
    "nicht_pruefbar": 4,
    "stufe_b": 3,
    "erfuellt": 2,
    "entfaellt": 1,
    "nicht_gelaufen": 0,
}


def _subject_order(subject: int | str) -> tuple[int, int, str]:
    """Prüfpunkte nach Nummer, dann Kriterien in der Reihenfolge E, V, G, Z, I."""
    if isinstance(subject, int) or str(subject).isdigit():
        return (0, int(subject), "")
    key = str(subject)
    return (1, "EVGZI".find(key[:1]), key)


def _merge(outcomes: Sequence[Outcome]) -> Outcome:
    """Ein Ergebnis aus allen Varianten: der Fund vor allem anderen (Sprachen, Zoll, Thema)."""
    worst = max(outcomes, key=lambda outcome: _BADNESS[outcome.verdict])
    if worst.verdict != "fund":
        return worst
    issues: list[Issue] = []
    for outcome in outcomes:
        for issue in outcome.issues:
            if issue not in issues:
                issues.append(issue)
    return replace(worst, issues=tuple(issues))


def _theme_case(protocols: Sequence[Mapping[str, Any]], theme: str) -> Mapping[str, Any] | None:
    """Der Fall eines Themas, der die Hauptknöpfe gemessen hat — bevorzugt der Satz ``basis``.

    Der Lizenzfall misst kein Layout; ihn gegen den dunklen Fall zu halten,
    ergäbe einen Unterschied, den es nicht gibt.
    """
    measured = [
        protocol
        for protocol in protocols
        if (protocol.get("variant") or {}).get("theme") == theme
        and any(
            isinstance(entry, Mapping) and entry.get("kind") == "primary"
            for entry in protocol.get("layout") or ()
        )
    ]
    basis = [p for p in measured if (p.get("variant") or {}).get("set") == "basis"]
    chosen = basis or measured
    return chosen[0] if chosen else None


def merge_cases(
    cases: Sequence[CaseOutcome], protocols: Sequence[Mapping[str, Any]] = ()
) -> CaseOutcome:
    """Alle Fälle einer Zeile zu einem Ergebnis; hell gegen dunkel für Z6.

    Prüfpunkt 18 urteilt einmal je Zeile über die Lizenzläufe aller ihrer Fälle:
    Der Prüfstand fährt je Lizenzzustand einen Fall mit genau einem Lauf. Ebenso
    Z6 über die Fenstergrößen — je Größe ein Fall — und mit ihm Prüfpunkt 19.
    """
    points = {
        number: _merge([case.points[number] for case in cases if number in case.points])
        for number in sorted({n for case in cases for n in case.points})
    }
    criteria = {
        key: _merge([case.criteria[key] for case in cases if key in case.criteria])
        for key in sorted({k for case in cases for k in case.criteria}, key=_subject_order)
    }
    runs: dict[str, Any] = {}
    for protocol in protocols:
        given = protocol.get("licence_runs")
        if isinstance(given, Mapping):
            runs.update(given)
    if runs:
        points[18] = judge_licence(runs, complete=True)
    sized = judge_sizes(protocols, complete=True)
    if sized is not None and "Z6" in criteria and criteria["Z6"].verdict != "entfaellt":
        criteria["Z6"] = replace(sized, evidence=criteria["Z6"].evidence)
        if 19 in points and points[19].verdict != "entfaellt":
            points[19] = replace(judge_design(criteria), evidence=points[19].evidence)
    light, dark = _theme_case(protocols, "light"), _theme_case(protocols, "dark")
    if light is not None and dark is not None:
        issues = compare_themes(light, dark)
        if issues:
            base = criteria.get("Z6") or Outcome("Z6", "A", "fund")
            criteria["Z6"] = replace(
                base, verdict="fund", stage="A", issues=(*base.issues, *issues)
            )
            point = points.get(19) or Outcome(19, "A", "fund")
            points[19] = replace(point, verdict="fund", stage="A", issues=(*point.issues, *issues))
    problems = tuple(problem for case in cases for problem in case.problems)
    return CaseOutcome(cases[0].row, cases[0].variant, points, criteria, problems)


# --- Abhakliste (Konzept §7) --------------------------------------------------------


def package_slug(package: str) -> str:
    """``D4`` → ``d04``: der Dateiname je Paket."""
    number = int(re.sub(r"\D", "", package))
    return f"d{number:02d}"


def package_name(package: str) -> str:
    """``d04``, ``D04`` oder ``D4`` → ``D4``: der Wert der Zeilen (Konzept §3)."""
    return f"D{int(re.sub(r'\D', '', package))}"


def _cell_text(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


@dataclass(frozen=True)
class Cell:
    """Ein Feld der Tabelle 1 und was es für das Urteil der Zeile heißt."""

    text: str
    status: str  # erledigt, offen, behoben, ausstehend
    rm: tuple[str, ...] = ()


def _finding_for(row: str, subject: int | str, findings: Mapping[str, Finding]) -> Finding | None:
    """Der Fund einer Zelle; ein offener geht jedem behobenen vor (FD-85).

    Tragen mehrere Funde dieselbe Zeile und denselben Punkt, hält der offene
    die Zelle offen — ein älterer behobener darf ihn nicht verdecken.
    """
    matching = [
        finding
        for finding in sorted(findings.values(), key=lambda f: f.number)
        if row in finding.rows and subject in finding.subjects
    ]
    return next((f for f in matching if f.stand.startswith("offen")), None) or next(
        iter(matching), None
    )


def _cell(
    row: str,
    outcome: Outcome | None,
    verdict: Mapping[str, Any] | None,
    findings: Mapping[str, Finding],
) -> Cell:
    """Das Feld eines Prüfpunkts in der Abhakliste: ja, FD-n, —, B, C, ? oder n.p.

    Die Messung der Stufe A geht vor dem Urteil: Ein Fund bleibt Fund, bis er
    *offen* mit RM steht oder ein neuer Lauf ihn nicht mehr findet; was nicht
    gemessen oder nicht prüfbar ist, schließt nur *entfällt* mit Grund.
    Ein offener Fund aus der Funddatei hält auch einen erfüllten Punkt offen.
    """
    if outcome is None:
        return Cell("?", "ausstehend")
    known = _finding_for(row, outcome.subject, findings)
    number = str(verdict.get("finding")) if verdict and verdict.get("finding") else None
    number = number or (known.key if known else None)
    said = verdict.get("verdict") if verdict else None
    rms = tuple(_RM.findall(str((verdict or {}).get("rm") or "")))
    known_open = known is not None and known.stand.startswith("offen")
    # Eine offene Zelle nennt den Fund ihres Urteils oder einen offenen; ein
    # behobener ist kein Grund dafür, dass sie offen ist (Zwilling von FD-85).
    reason = (verdict or {}).get("finding") or (known.key if known_open else None)
    if outcome.verdict == "entfaellt":
        return Cell("—", "erledigt")
    if outcome.verdict == "fund":
        if said == "offen":
            return Cell(str(reason or "offen"), "offen", rms)
        if known is not None and known_open:
            return Cell(known.key, "offen", tuple(_RM.findall(known.stand)))
        return Cell(number or "Fund", "ausstehend")
    if said == "entfaellt":
        return Cell("—", "erledigt")
    if said == "offen":
        return Cell(str(reason or "offen"), "offen", rms)
    if outcome.verdict == "nicht_pruefbar":
        return Cell("n.p.", "ausstehend")
    if outcome.verdict == "nicht_gelaufen":
        return Cell("C" if outcome.stage == "C" else "?", "ausstehend")
    if known is not None and known_open:
        return Cell(known.key, "offen", tuple(_RM.findall(known.stand)))
    if said == "gut_nach_fix":
        return Cell(number or "ja", "behoben")
    if said == "gut" or outcome.verdict == "erfuellt":
        return Cell("ja", "behoben" if known is not None else "erledigt")
    return Cell("B", "ausstehend")


#: Welches Urteil an einem Punkt gilt, wenn Stufe B und C beide urteilen:
#: das strengere, gleich in welcher Folge sie in der Datei stehen.
_VERDICT_RANK: Final = {"offen": 0, "gut_nach_fix": 1, "entfaellt": 2, "gut": 3}


def primary_verdicts(
    accepted: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Das geltende Urteil je Zeile und Punkt aus den Stufen B und C (Zweitprüfer zählt nicht)."""
    chosen: dict[tuple[str, str], Mapping[str, Any]] = {}
    for entry in accepted:
        if entry.get("reviewer") not in {"stufe_b", "stufe_c"}:
            continue
        key = (str(entry["row"]), str(subject_of(entry)))
        known = chosen.get(key)
        rank = _VERDICT_RANK.get(str(entry.get("verdict")), 9)
        if known is None or rank < _VERDICT_RANK.get(str(known.get("verdict")), 9):
            chosen[key] = entry
    return chosen


def _row_verdict(cells: Sequence[Cell], ran: bool) -> str:
    if not ran or any(cell.status == "ausstehend" for cell in cells):
        return "nicht geprüft"
    rms = sorted({rm for cell in cells for rm in cell.rm}, key=lambda rm: int(rm[3:]))
    if any(cell.status == "offen" for cell in cells):
        return "offen " + ", ".join(rms)
    if any(cell.status == "behoben" for cell in cells):
        return "gut nach Fix"
    return "gut"


@dataclass(frozen=True)
class PackageValues:
    """Die Paketwerte der Abhakliste (Konzept §7)."""

    inputs: Share
    fronts: Share
    goals: Share
    solutions: Solutions
    agreement: Mapping[str, Share]
    second_review: Share


def package_values(
    cases: Mapping[str, CaseOutcome],
    verdicts: Sequence[Mapping[str, Any]],
    *,
    common_goals: Mapping[str, str],
    solutions: Mapping[str, bool],
) -> PackageValues:
    """E2-, E5- und I3-Anteil, I4-Zahl und die Übereinstimmung der Prüfer eines Pakets.

    I3 zählt je Kundenziel, dessen Zeile (``target``) im Paket gemessen ist;
    zwei Ziele an derselben Zeile zählen beide.
    """
    inputs = [
        int(case.criteria["E2"].measurement["inputs"])
        for case in cases.values()
        if "E2" in case.criteria and "inputs" in case.criteria["E2"].measurement
    ]
    fronts = [
        int(case.criteria["E5"].measurement["front"])
        for case in cases.values()
        if "E5" in case.criteria and "front" in case.criteria["E5"].measurement
    ]
    by_target = {
        str(case.row.get("target")): case
        for case in cases.values()
        if "I3" in case.criteria and "way_clicks" in case.criteria["I3"].measurement
    }
    reached = [
        int(by_target[target].criteria["I3"].measurement["way_clicks"]) == 0
        for _goal, target in sorted(common_goals.items())
        if target in by_target
    ]
    reviewed = {
        str(entry.get("row")) for entry in verdicts if entry.get("reviewer") == "zweitpruefer"
    }
    return PackageValues(
        input_share(inputs),
        front_share(fronts),
        goal_share(reached),
        solution_count(solutions),
        agreement(verdicts),
        Share(len(reviewed & set(cases)), len(cases), SECOND_REVIEW_SHARE),
    )


_KIND_ORDER: Final = {kind: index for index, kind in enumerate(ROW_KINDS)}


def render_checklist(
    package: str,
    *,
    rows: Sequence[Mapping[str, Any]],
    cases: Mapping[str, CaseOutcome],
    verdicts: Checked,
    findings: Mapping[str, Finding],
    values: PackageValues,
    commit: str,
    date: str,
    out: str,
) -> str:
    """Die Abhakliste eines Pakets — gleiche Eingaben, gleiche Bytes."""
    primary = primary_verdicts(verdicts.accepted)
    ordered = sorted(rows, key=lambda r: (_KIND_ORDER.get(str(r.get("kind")), 9), str(r.get("id"))))
    table: list[str] = []
    second: list[str] = []
    tally = {"gut": 0, "gut nach Fix": 0, "offen": 0, "nicht geprüft": 0}
    for row in ordered:
        row_id = str(row.get("id"))
        case = cases.get(row_id)
        cells = [
            _cell(
                row_id,
                case.points.get(number) if case else None,
                primary.get((row_id, str(number))),
                findings,
            )
            for number in sorted(CHECKPOINTS)
        ]
        said = _row_verdict(cells, case is not None)
        tally["offen" if said.startswith("offen") else said] += 1
        numbers = {cell.text for cell in cells if cell.text.startswith("FD-")}
        numbers |= {f.key for f in findings.values() if row_id in f.rows}
        shown = ", ".join(sorted(numbers, key=lambda key: int(key[3:])))
        table.append(
            "| "
            + " | ".join(
                _cell_text(text)
                for text in (
                    row_id,
                    row.get("kind", ""),
                    row.get("start_scene", ""),
                    *(cell.text for cell in cells),
                    said,
                    shown,
                )
            )
            + " |"
        )
        for key, outcome in sorted(
            (case.criteria if case else {}).items(), key=lambda i: _subject_order(i[0])
        ):
            entry = primary.get((row_id, key))
            if outcome.verdict != "fund" and not (entry and entry.get("verdict") == "offen"):
                continue
            known = _finding_for(row_id, key, findings)
            # Wie in ``_cell``: Ein offenes Urteil nennt keinen behobenen Fund als Grund.
            said_open = bool(entry and entry.get("verdict") == "offen")
            if said_open and known is not None and not known.stand.startswith("offen"):
                known = None
            number = (entry or {}).get("finding") or (known.key if known else "—")
            measured = "; ".join(issue.text for issue in outcome.issues) or outcome.summary
            second.append(
                "| "
                + " | ".join(
                    _cell_text(text)
                    for text in (row_id, key, measured, CRITERIA[key].threshold, number)
                )
                + " |"
            )
    header_points = " | ".join(str(number) for number in sorted(CHECKPOINTS))
    lines = [
        f"# Abhakliste {package}",
        "",
        "Erzeugt von `tools/function_report.py` (Konzept Funktionsdurchgang §7); "
        "nicht von Hand bearbeiten — die Prüfsumme merkt es.",
        "",
        "| | |",
        "|---|---|",
        f"| Paket | {package} |",
        _CHECKSUM_SLOT,
        f"| Commit | {_cell_text(commit)} |",
        f"| Datum | {date} |",
        f"| Laufordner | `{_cell_text(out)}` |",
        f"| Zeilen | {len(ordered)} |",
        f"| gut | {tally['gut']} |",
        f"| gut nach Fix | {tally['gut nach Fix']} |",
        f"| offen mit RM | {tally['offen']} |",
        f"| nicht geprüft | {tally['nicht geprüft']} |",
        "",
        "## Funktionen",
        "",
        "`ja` erfüllt · `FD-n` Fund · `—` entfällt · `B` Urteil der Stufe B steht aus · "
        "`C` nur Stufe C · `?` nicht gelaufen · `n.p.` nicht prüfbar",
        "",
        f"| Kennung | Art | Szene | {header_points} | Urteil | Funde |",
        "|" + "---|" * (len(CHECKPOINTS) + 5),
        *table,
        "",
        "## Kriterien, die nicht erfüllt sind",
        "",
    ]
    if second:
        lines += [
            "| Kennung | Kriterium | Messwert | Schwelle | Fund |",
            "|---|---|---|---|---|",
            *second,
        ]
    else:
        lines.append("Keine.")
    lines += [
        "",
        "## Paketwerte",
        "",
        "| Wert | Messung | Schwelle | Stand |",
        "|---|---|---|---|",
        _value_line("E2-Anteil", values.inputs, f"≥ {INPUT_SHARE:.0%}"),
        _value_line("E5-Anteil", values.fronts, f"≥ {USUAL_FRONT_SHARE:.0%}"),
        _value_line("I3-Anteil", values.goals, f"≥ {GOAL_SHARE:.0%}"),
        f"| I4-Zahl | {values.solutions.text()} | Zahl genannt | — |",
        _value_line("Zweitprüfer", values.second_review, f"≥ {SECOND_REVIEW_SHARE:.0%} der Zeilen"),
    ]
    if values.agreement:
        lines += [
            _value_line(f"Übereinstimmung {subject}", share, f"≥ {AGREEMENT:.0%}")
            for subject, share in values.agreement.items()
        ]
    else:
        lines.append(f"| Übereinstimmung | keine Doppelprüfung | ≥ {AGREEMENT:.0%} | markiert |")
    if verdicts.rejected:
        lines += [
            "",
            "## Abgewiesene Urteile",
            "",
            "| Kennung | Prüfpunkt | Prüfer | Grund |",
            "|---|---|---|---|",
        ]
        lines += [
            "| "
            + " | ".join(
                _cell_text(text)
                for text in (
                    entry.get("row", "?"),
                    subject_of(entry),
                    entry.get("reviewer", "?"),
                    "; ".join(reasons),
                )
            )
            + " |"
            for entry, reasons in verdicts.rejected
        ]
    body = "\n".join(line for line in lines if line != _CHECKSUM_SLOT) + "\n"
    sealed = f"| Prüfsumme | {_digest(body)} |"
    return "\n".join(sealed if line == _CHECKSUM_SLOT else line for line in lines) + "\n"


#: Der Platz der Prüfsumme in der Kopftabelle, bis sie gerechnet ist.
_CHECKSUM_SLOT: Final = "\x00Prüfsumme"
_CHECKSUM_LINE: Final = re.compile(r"^\| Prüfsumme \| ([0-9a-f]{64}) \|$", re.MULTILINE)


def _digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def checklist_intact(text: str) -> bool:
    """Ob eine Abhakliste so dasteht, wie ``render_checklist`` sie schrieb.

    Die Prüfsumme in der Kopftabelle deckt alles übrige; eine Änderung von Hand
    — ein „gut“ eingetragen, eine Zeile gestrichen — macht sie ungültig.
    """
    found = _CHECKSUM_LINE.search(text)
    if found is None:
        return False
    body = text[: found.start()] + text[found.end() + 1 :]
    return _digest(body) == found.group(1)


def _value_line(title: str, share: Share, threshold: str) -> str:
    stand = "markiert" if share.flagged else "erfüllt"
    return f"| {title} | {share.text()} | {threshold} | {stand} |"


@dataclass(frozen=True)
class Checklist:
    """Was der ``rendered``-Test aus einer Abhakliste liest."""

    package: str
    rows: Mapping[str, str] = field(default_factory=dict)  # Kennung → Art

    @property
    def window_commands(self) -> frozenset[str]:
        return frozenset(row for row, kind in self.rows.items() if kind == "fensterbefehl")


def _cells(line: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [part.strip().replace("\\|", "|") for part in parts]


def read_checklist(text: str) -> Checklist:
    """Paket und Zeilen einer erzeugten Abhakliste."""
    package = ""
    rows: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        if not line.startswith("|"):
            inside = False
            continue
        cells = _cells(line)
        if cells[:2] and cells[0] == "Paket":
            package = cells[1]
        if cells[:3] == ["Kennung", "Art", "Szene"]:
            inside = True
            continue
        if inside and cells and not set(cells[0]) <= set("-"):
            rows[cells[0]] = cells[1]
    return Checklist(package, rows)


def read_checklists(folder: Path = STATE) -> dict[str, Checklist]:
    """Alle Abhaklisten eines Ordners nach Paket."""
    found = {}
    for path in sorted(folder.glob("abhakliste-*.md")):
        checklist = read_checklist(path.read_text(encoding="utf-8"))
        found[checklist.package] = checklist
    return found


@dataclass(frozen=True)
class WindowCommands:
    """Menüleiste gegen Abhaklisten: was fehlt, was veraltet ist, was noch keine Liste hat."""

    missing: tuple[tuple[str, str], ...]
    stale: tuple[tuple[str, str], ...]
    unchecked: tuple[str, ...]


def window_commands_of(window: Any) -> dict[str, str]:
    """Die Fensterbefehle eines gebauten Fensters mit ihrem Paket, wie der Prüfstand sie zählt.

    Die Menüleiste über ``function_list.menubar_of``, die Zeilen über
    ``function_list.rows`` — so gehören die Aktionen der Auswahlkarte
    (``command:edit.auto_split``) dazu, und nichts wird hier nachgebaut.
    """
    from tools.function_list import menubar_of
    from tools.function_list import rows as function_rows

    return {
        row.id: row.package
        for row in function_rows(menubar_of(window), with_specs=False)
        if row.kind == "fensterbefehl"
    }


def compare_window_commands(
    menubar: Mapping[str, str], checklists: Mapping[str, Iterable[str]]
) -> WindowCommands:
    """Die Fensterbefehle der Menüleiste (Kennung → Paket) gegen die Zeilen je Abhakliste.

    Fehlend ist ein Befehl, dessen Paket eine Abhakliste hat, die ihn nicht
    nennt; veraltet eine Zeile, die die Menüleiste nicht mehr hat oder einem
    anderen Paket zuordnet. Pakete ohne Abhakliste sind noch nicht gelaufen.
    """
    listed = {package: frozenset(ids) for package, ids in checklists.items()}
    missing = sorted(
        (package, command)
        for command, package in menubar.items()
        if package in listed and command not in listed[package]
    )
    stale = sorted(
        (package, command)
        for package, ids in listed.items()
        for command in ids
        if menubar.get(command) != package
    )
    unchecked = sorted({package for package in menubar.values() if package not in listed})
    return WindowCommands(tuple(missing), tuple(stale), tuple(unchecked))


# --- Gegenproben fahren ------------------------------------------------------------


def is_red(sample: BrokenSample) -> tuple[bool, str]:
    """Wird eine Gegenprobe rot? Mit dem, was rot wurde."""
    protocol = copy.deepcopy(sample_protocol())
    if sample.change is not None:
        sample.change(protocol)
    context = replace(sample_context(), **dict(sample.context))
    if sample.kind == "protocol":
        outcome = judge_case(protocol, context).get(sample.subject)
        got = outcome.verdict if outcome else "gilt nicht"
        red = got == sample.expect and got not in {"erfuellt", "entfaellt"}
        return red, f"{got}: " + "; ".join(i.text for i in (outcome.issues if outcome else ()))
    if sample.kind == "verdict":
        case = judge_case(protocol, context)
        assert sample.verdict is not None
        checked = check_verdicts([sample.verdict], outcomes={case.row_id: case})
        reasons = [reason for _entry, why in checked.rejected for reason in why]
        # Rot zählt nur aus dem genannten Grund: Ein Urteil, das an etwas
        # anderem scheitert, belegt die Gegenprobe nicht.
        return any(sample.reason in reason for reason in reasons), "; ".join(reasons)
    if sample.kind == "finding":
        findings, problems = parse_findings(sample.finding or "")
        problems += check_findings(findings)
        return any(sample.reason in problem for problem in problems), "; ".join(problems)
    if sample.kind == "share":
        if sample.subject == "E2":
            share = input_share(int(value) for value in sample.values)
        elif sample.subject == "E5":
            share = front_share(int(value) for value in sample.values)
        else:
            share = goal_share(bool(value) for value in sample.values)
        return share.flagged, share.text()
    if sample.kind == "count":
        solved = solution_count(dict(sample.values))
        return bool(solved.without), solved.text()
    raise ValueError(f"unbekannte Art einer Gegenprobe: {sample.kind}")


# --- Bericht ------------------------------------------------------------------


#: Wo ein Fall seine Protokolle ablegt: ein Funktionsfall ``function.json``,
#: ein Sprachfall je Fläche ``surfaces/<zeile>.json`` — beide nach demselben
#: Schema (``function_checks.PROTOCOL_SCHEMA``), damit Prüfpunkt 9 die Sprachen
#: an der Zeile sieht.
PROTOCOL_FILES: Final = ("function.json", "surfaces/*.json")


def read_protocols(out: Path) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Die Messprotokolle eines Laufs in Fallfolge, je mit ihrer Datei relativ zu ``cases``.

    Dazu, was an ihnen unlesbar ist.
    """
    protocols: list[tuple[str, dict[str, Any]]] = []
    problems: list[str] = []
    folders = (out / "cases").glob("*") if (out / "cases").is_dir() else iter(())
    cases = sorted(
        (folder for folder in folders if folder.is_dir()),
        key=lambda folder: (int(folder.name) if folder.name.isdigit() else 0, folder.name),
    )
    for folder in cases:
        for pattern in PROTOCOL_FILES:
            for path in sorted(folder.glob(pattern)):
                where = path.relative_to(out / "cases").as_posix()
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as problem:
                    problems.append(f"{where}: nicht lesbar ({problem})")
                    continue
                if not isinstance(data, dict):
                    problems.append(f"{where}: kein Protokoll")
                    continue
                protocols.append((where, data))
    return protocols, problems


def _rows_of(out: Path, protocols: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Die Zeilen des Laufs: ``rows.json`` des Inventars (Paket P), sonst aus den Protokollen."""
    listed = out / "rows.json"
    if listed.is_file():
        return [dict(row) for row in json.loads(listed.read_text(encoding="utf-8"))]
    rows: dict[str, dict[str, Any]] = {}
    for protocol in protocols:
        row = protocol.get("row")
        if isinstance(row, Mapping):
            rows.setdefault(str(row.get("id")), dict(row))
    return list(rows.values())


def write(
    out: Path,
    *,
    package: str | None = None,
    verdicts: Path | None = None,
    checklist: Path | None = None,
    findings: Path | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    date: str | None = None,
    commit: str | None = None,
    context: Context | None = None,
    solutions: Mapping[str, bool] | None = None,
    common_goals: Mapping[str, str] | None = None,
    state: Path = STATE,
) -> int:
    """Beurteilt einen Lauf und schreibt Ergebnisse und Abhakliste je Paket.

    Ausgang 1 nur bei ungültigen Eingaben (Kommandozeile des Prüfstands,
    ``file_acceptance.py report``): kein Protokoll, ein unlesbares oder
    ungültiges Protokoll, ein Fall, an dem das Urteil scheitert, ein
    abgewiesenes Urteil, eine fehlerhafte Funddatei. Eine Abhakliste bekommt nur
    ein Paket mit mindestens einem Fall — ein leerer oder verirrter Laufordner
    überschreibt keine; sie nennt abgewiesene Urteile in einem eigenen Abschnitt.
    """
    readings, invalid = read_protocols(out)
    if not readings:
        print(f"ungültig: keine Protokolle unter {out / 'cases'}")
        for problem in invalid:
            print(f"ungültig: {problem}")
        return 1
    protocols = [protocol for _where, protocol in readings]
    all_rows = [dict(row) for row in rows] if rows is not None else _rows_of(out, protocols)
    used = context if context is not None else repository_context()
    judged: list[tuple[str, Mapping[str, Any], CaseOutcome]] = []
    for where, protocol in readings:
        try:
            case = judge_case(protocol, used, source=where)
        except (TypeError, ValueError, KeyError, AttributeError, IndexError) as error:
            # Ein Protokoll, an dem das Urteil scheitert, ist eine ungültige
            # Eingabe — der Bericht über die übrigen Fälle entsteht trotzdem.
            invalid.append(f"{where}: {type(error).__name__}: {error}")
            continue
        invalid += [f"{where}: {problem}" for problem in case.problems]
        judged.append((where, protocol, case))
    grouped: dict[str, list[tuple[Mapping[str, Any], CaseOutcome]]] = {}
    for _where, measured, case in judged:
        grouped.setdefault(case.row_id, []).append((measured, case))
    merged = {
        row: merge_cases([case for _p, case in pairs], [p for p, _case in pairs])
        for row, pairs in sorted(grouped.items())
    }
    measured_packages = {
        package_name(str(row.get("package")))
        for row in all_rows
        if row.get("package") and str(row.get("id")) in merged
    }
    if package:
        packages = [package_name(package)]
        if packages[0] not in measured_packages:
            invalid.append(f"{packages[0]}: kein Fall im Lauf — keine Abhakliste geschrieben")
            packages = []
    else:
        packages = sorted(measured_packages, key=lambda name: int(name[1:]))
    if (checklist is not None or verdicts is not None) and len(packages) != 1:
        invalid.append("--checklist und --verdicts verlangen genau ein Paket")
        packages = []
    found, finding_problems = read_findings(findings or state / "funde.md")
    invalid += [f"funde.md: {problem}" for problem in finding_problems]
    commits = sorted(
        {str((p.get("version") or {}).get("commit")) for p in protocols if p.get("version")}
    )
    shown_commit = commit or (", ".join(commits) if commits else "unbekannt")
    shown_date = date or datetime.date.today().isoformat()
    goals = common_goals if common_goals is not None else read_common_goals()
    kinds = solutions if solutions is not None else finding_solutions()
    for name in packages:
        package_rows = [
            row for row in all_rows if package_name(str(row.get("package", "D0"))) == name
        ]
        ids = {str(row.get("id")) for row in package_rows}
        cases = {row: case for row, case in merged.items() if row in ids}
        entries, runs = read_verdict_file(verdicts or state / f"urteile-{package_slug(name)}.toml")
        checked = check_verdicts(entries, outcomes=cases, rows=ids, findings=found)
        invalid += [
            f"{name} {entry.get('row')} {subject_of(entry)}: {'; '.join(reasons)}"
            for entry, reasons in checked.rejected
        ]
        invalid += [f"{name}: {problem}" for problem in check_runs(runs, entries, commits)]
        values = package_values(cases, checked.accepted, common_goals=goals, solutions=kinds)
        text = render_checklist(
            name,
            rows=package_rows,
            cases=cases,
            verdicts=checked,
            findings=found,
            values=values,
            commit=shown_commit,
            date=shown_date,
            # Der Lauf, den die Urteile nennen, nicht die bildlose Kopie,
            # aus der die Protokolle hier gelesen werden.
            out=run_folder(runs) or str(out),
        )
        target = checklist or state / f"abhakliste-{package_slug(name)}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        print(f"{name}: {len(package_rows)} Zeilen, {len(cases)} gemessen -> {target}")

    def linked(case: CaseOutcome, outcome: Outcome) -> dict[str, Any]:
        # ``finding`` ist die FD-Nummer, sobald die Funddatei eine vergibt.
        known = _finding_for(case.row_id, outcome.subject, found)
        return replace(outcome, finding=known.key if known else None).record()

    results = [
        {
            "case": where,
            "row": case.row_id,
            "variant": dict(case.variant),
            "results": [
                linked(case, outcome)
                for outcome in (*case.points.values(), *case.criteria.values())
            ],
        }
        for where, _protocol, case in judged
    ]
    (out / "function_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    for problem in invalid:
        print(f"ungültig: {problem}")
    return 1 if invalid else 0
