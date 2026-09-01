"""Lizenzprüfung der Abhängigkeiten (Bauplan §36).

Die Richtlinie steht in ``data/licences.toml``; dieses Modul vergleicht sie mit
dem, was wirklich installiert ist. Zwei Dinge werden geprüft: dass nichts eine
GPL-artige Lizenz trägt, und dass nichts von der Sperrliste überhaupt da ist.

Die Prüfung läuft den echten Abhängigkeitsbaum der Laufzeit-Extras ab — ein
transitives Paket kann sich also nicht ungesehen hineinschleichen.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Final

from app.branding import DISTRIBUTION_NAME
from app.core.log import get_logger

_log = get_logger(__name__)

_DATA_FILE: Final = Path(__file__).parent / "data" / "licences.toml"

#: Die Lizenzbeilage, wie sie neben der Anwendung liegt.
#:
#: **Im gebauten Paket ist sie die einzige Quelle.** `runtime_packages` fragt
#: `importlib.metadata` nach der eigenen Distribution, und die gibt es dort
#: unter keinen Umständen: Die Anwendung ist kein installiertes Paket.
#: `packaging/solidon3d.spec` legt die Datei deshalb neben das `app`-Paket, und
#: `tests/test_licences.py` hält sie aktuell — gelesen hat sie bis zum
#: 27.08.2026 niemand. Der Über-Dialog zeigte im Paket also **nie** eine
#: Fremdlizenz, sondern immer den Ersatzsatz aus `dialogs.py`; PySide6 steht
#: unter LGPL, und §36 verlangt die Liste.
NOTICE_FILE: Final = Path(__file__).parents[3] / "THIRD-PARTY-NOTICES.md"

#: Die Extras, deren Abhängigkeiten in der ausgelieferten Anwendung landen.
#: Dieselbe Liste wie im Bau-Workflow (``.[geom,ui,agent,brep]``) — hier
#: standen nur zwei der vier, und acht Pakete reisten ungeprüft und ohne
#: Hinweis im Über-Dialog mit. Heute sind alle zulässig; die Lücke hätte
#: erst das nächste transitive GPL-Paket unter ``agent`` oder ``brep``
#: gezeigt.
RUNTIME_EXTRAS: Final[tuple[str, ...]] = ("geom", "ui", "agent", "brep")

#: Pakete, die nur auf **einer** Plattform installiert werden, mit ihrer
#: Lizenz.
#:
#: ``runtime_packages()`` liest, was hier installiert ist — und das ist auf
#: jedem Betriebssystem etwas anderes: ``keyring`` zieht unter Linux
#: ``SecretStorage`` und ``jeepney`` nach (und mit ihnen ``cryptography``,
#: ``cffi``, ``pycparser``), unter Windows ``pywin32-ctypes``. Eine auf
#: Windows erzeugte Hinweisdatei nennt die fünf Linux-Pakete deshalb nicht,
#: und in der CI wurde ``test_the_notice_file_names_every_runtime_package``
#: unter Linux rot — an einer Datei, die auf der Maschine, die sie erzeugt
#: hat, vollständig war.
#:
#: Die Hinweisdatei reist mit dem Paket und wird für **alle** Plattformen
#: gebaut. Also nennt sie alle, gleich wo sie entstanden ist. Die Lizenzen
#: stehen hier und nicht in ``licences.toml``, weil das die Freigabeliste ist
#: (was ist erlaubt) und dies eine Feststellung (was ist es).
PLATFORM_PACKAGES: Final[dict[str, str]] = {
    "SecretStorage": "BSD-3-Clause",
    "jeepney": "MIT",
    "cryptography": "Apache-2.0 OR BSD-3-Clause",
    "cffi": "MIT",
    "pycparser": "BSD-3-Clause",
    "pywin32-ctypes": "BSD-3-Clause",
}

_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXTRA_MARKER = re.compile(r"extra\s*==\s*[\"']([^\"']+)[\"']")


@dataclass(frozen=True, slots=True)
class Policy:
    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]
    allowed_with: tuple[str, ...]
    banned_packages: tuple[str, ...]
    known: dict[str, dict[str, str]]


@dataclass(frozen=True, slots=True)
class Violation:
    """Eine Abhängigkeit, die nicht zur Richtlinie passt."""

    package: str
    licence: str
    reason: str

    def __str__(self) -> str:
        return f"{self.package} ({self.licence}): {self.reason}"


def load_policy() -> Policy:
    with _DATA_FILE.open("rb") as stream:
        data: dict[str, Any] = tomllib.load(stream)
    policy = data.get("policy", {})
    return Policy(
        allowed=tuple(policy.get("allowed", ())),
        forbidden=tuple(policy.get("forbidden", ())),
        allowed_with=tuple(policy.get("allowed_with", ())),
        banned_packages=tuple(policy.get("banned_packages", ())),
        known=data.get("known", {}),
    )


@dataclass(frozen=True, slots=True)
class LicenceExpression:
    """Ein ausgewerteter Knoten eines SPDX-Lizenzausdrucks."""

    operator: str
    value: str = ""
    left: LicenceExpression | None = None
    right: LicenceExpression | None = None


_SPDX_TOKEN = re.compile(r"\s*(\(|\)|AND\b|OR\b|WITH\b|[A-Za-z0-9][A-Za-z0-9.+-]*)")


class _SpdxParser:
    """Kleiner Parser für die in Paketmetadaten erlaubte SPDX-Grammatik."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = self._tokens(text)
        self.index = 0

    @staticmethod
    def _tokens(text: str) -> tuple[str, ...]:
        tokens: list[str] = []
        position = 0
        while position < len(text):
            match = _SPDX_TOKEN.match(text, position)
            if match is None:
                raise ValueError(f"ungültiges Zeichen an Stelle {position + 1}")
            tokens.append(match.group(1))
            position = match.end()
        return tuple(tokens)

    def parse(self) -> LicenceExpression:
        if not self.tokens:
            raise ValueError("leerer Ausdruck")
        expression = self._or_expression()
        if self.index != len(self.tokens):
            raise ValueError(f"unerwartetes Token {self.tokens[self.index]!r}")
        return expression

    def _or_expression(self) -> LicenceExpression:
        expression = self._and_expression()
        while self._take("OR"):
            expression = LicenceExpression("OR", left=expression, right=self._and_expression())
        return expression

    def _and_expression(self) -> LicenceExpression:
        expression = self._with_expression()
        while self._take("AND"):
            expression = LicenceExpression("AND", left=expression, right=self._with_expression())
        return expression

    def _with_expression(self) -> LicenceExpression:
        expression = self._primary()
        if not self._take("WITH"):
            return expression
        if expression.operator != "ID":
            raise ValueError("WITH braucht links eine Lizenzkennung")
        exception = self._next()
        if exception in {"(", ")", "AND", "OR", "WITH"}:
            raise ValueError("WITH braucht rechts eine Ausnahmekennung")
        return LicenceExpression("WITH", value=f"{expression.value} WITH {exception}")

    def _primary(self) -> LicenceExpression:
        token = self._next()
        if token == "(":
            expression = self._or_expression()
            if not self._take(")"):
                raise ValueError("schließende Klammer fehlt")
            return expression
        if token in {")", "AND", "OR", "WITH"}:
            raise ValueError(f"Lizenzkennung erwartet, {token!r} gefunden")
        return LicenceExpression("ID", value=token)

    def _next(self) -> str:
        if self.index >= len(self.tokens):
            raise ValueError("Ausdruck endet zu früh")
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _take(self, wanted: str) -> bool:
        if self.index >= len(self.tokens) or self.tokens[self.index] != wanted:
            return False
        self.index += 1
        return True


def parse_spdx(text: str) -> LicenceExpression:
    """Parst einen SPDX-Ausdruck oder wirft mit einer prüfbaren Begründung."""
    return _SpdxParser(text.strip()).parse()


def _expression_allowed(expression: LicenceExpression, policy: Policy) -> bool:
    """Ob mindestens eine OR-Wahl vollständig der Richtlinie entspricht."""
    if expression.operator == "ID":
        identifier = expression.value.casefold()
        allowed = {value.casefold() for value in policy.allowed}
        forbidden = {value.casefold() for value in policy.forbidden}
        return identifier in allowed and identifier not in forbidden
    if expression.operator == "WITH":
        allowed_with = {value.casefold() for value in policy.allowed_with}
        return expression.value.casefold() in allowed_with
    if expression.left is None or expression.right is None:  # pragma: no cover - nur interne Abwehr
        return False
    if expression.operator == "AND":
        return _expression_allowed(expression.left, policy) and _expression_allowed(
            expression.right, policy
        )
    if expression.operator == "OR":
        return _expression_allowed(expression.left, policy) or _expression_allowed(
            expression.right, policy
        )
    return False


def licence_allowed(text: str, policy: Policy | None = None) -> bool:
    """Prüft einen vollständigen SPDX-Ausdruck semantisch und exakt."""
    active = policy or load_policy()
    return _expression_allowed(parse_spdx(text), active)


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def declared_licence(distribution: metadata.Distribution) -> str:
    """Liest die Lizenz aus den Paket-Metadaten, wie auch immer sie
    hingeschrieben wurde.
    """
    # Als Any typisiert: das Metadaten-Objekt ist eine email.Message, und die
    # Stubs verbergen das.
    meta: Any = distribution.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    classifiers = [
        value.split("::")[-1].strip()
        for value in meta.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    if classifiers:
        return ", ".join(classifiers)
    licence = meta.get("License")
    if licence and len(licence) < 200:
        return str(licence)
    return ""


def _applies_here(requirement: str) -> bool:
    """False für Anforderungen, deren Umgebungsmarker auf dieser Maschine
    nicht gilt.
    """
    try:
        from packaging.requirements import Requirement
    except ImportError:  # pragma: no cover - packaging kommt mit der Werkzeugkette
        return True
    parsed = Requirement(requirement)
    return parsed.marker is None or parsed.marker.evaluate({"extra": ""})


def requirements_of(distribution: metadata.Distribution) -> set[str]:
    """Laufzeit-Anforderungen — optionale Extras einer Abhängigkeit zählen
    nicht.
    """
    names: set[str] = set()
    for requirement in distribution.requires or ():
        if _EXTRA_MARKER.search(requirement) is not None:
            continue
        if not _applies_here(requirement):
            continue
        match = _REQUIREMENT_NAME.match(requirement)
        if match:
            names.add(normalise(match.group(1)))
    return names


def _direct_requirements(extras: Iterable[str]) -> set[str]:
    """Die eigenen Abhängigkeiten, samt der Laufzeit-Extras."""
    own = metadata.distribution(DISTRIBUTION_NAME)
    wanted = {normalise(entry) for entry in extras}
    names: set[str] = set()
    for requirement in own.requires or ():
        marker = _EXTRA_MARKER.search(requirement)
        if marker is not None and normalise(marker.group(1)) not in wanted:
            continue
        match = _REQUIREMENT_NAME.match(requirement)
        if match:
            names.add(normalise(match.group(1)))
    return names


def runtime_packages(
    extras: Iterable[str] = RUNTIME_EXTRAS, *, strict: bool = False
) -> dict[str, str]:
    """Jedes installierte Paket, das in der Anwendung landet, mit seiner
    Lizenz.
    """
    found: dict[str, str] = {}
    pending = list(_direct_requirements(extras))
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            if strict:
                raise RuntimeError(
                    f"Die deklarierte Laufzeitabhängigkeit {name} ist nicht installiert. "
                    "Die Lizenzbeilage darf nur in einer vollständigen Zielumgebung entstehen."
                ) from None
            _log.warning("dependency %s is declared but not installed", name)
            continue
        found[distribution.metadata["Name"]] = declared_licence(distribution)
        pending.extend(requirements_of(distribution))
    return found


def check(extras: Iterable[str] = RUNTIME_EXTRAS) -> list[Violation]:
    """Vergleicht das Installierte mit der Richtlinie. Leere Liste heißt grün."""
    policy = load_policy()
    banned = {normalise(entry) for entry in policy.banned_packages}
    known = {normalise(key): value for key, value in policy.known.items()}
    direct = _direct_requirements(extras)
    violations: list[Violation] = []

    for package, licence in sorted(runtime_packages(extras).items()):
        key = normalise(package)
        if key in banned:
            violations.append(Violation(package, licence, "steht auf der Sperrliste (§36)"))
            continue
        if key in direct and key not in known:
            violations.append(
                Violation(
                    package,
                    licence or "unbekannt",
                    "direkte Abhängigkeit ohne Eintrag in der Freigabeliste",
                )
            )
            continue
        # Der paketbezogene, von Hand geprüfte SPDX-Ausdruck gewinnt gegen
        # freie Anzeigenamen wie „BSD License“. Die ursprünglichen Wheel-Texte
        # bleiben davon unberührt und gehen vollständig in die Beilage ein.
        text = known.get(key, {}).get("licence", "") or licence
        if not text:
            violations.append(
                Violation(package, "unbekannt", "keine Lizenzangabe und kein Eintrag in der Liste")
            )
            continue
        try:
            allowed = licence_allowed(text, policy)
        except ValueError as problem:
            violations.append(Violation(package, text, f"kein gültiger SPDX-Ausdruck: {problem}"))
            continue
        if not allowed:
            violations.append(
                Violation(package, text, "kein vollständig erlaubter SPDX-Lizenzzweig")
            )

    # Plattformabhängige direkte Komponenten müssen bereits vor einem Bau auf
    # einer anderen Maschine freigegeben sein. Deren Wheel-Texte prüft erst der
    # jeweilige Ziel-Baulauf, der Eintrag selbst ist jedoch plattformneutral.
    for package in PLATFORM_PACKAGES:
        key = normalise(package)
        record = known.get(key)
        if record is None:
            violations.append(
                Violation(
                    package,
                    "unbekannt",
                    "Plattformabhängigkeit ohne Eintrag in der Freigabeliste",
                )
            )
            continue
        expression = record.get("licence", "")
        try:
            allowed = bool(expression) and licence_allowed(expression, policy)
        except ValueError:
            allowed = False
        if not allowed:
            violations.append(
                Violation(package, expression or "unbekannt", "Plattformfreigabe ist unzulässig")
            )
    return violations


def _notices_from_file() -> str | None:
    """Die Tabelle aus der mitgereisten Beilage — ``None``, wenn keine da ist.

    Gelesen wird ab der Kopfzeile der Tabelle: Die Datei trägt darüber eine
    Erklärung, wie sie erzeugt wird, und die gehört nicht in den Dialog.
    """
    try:
        text = NOTICE_FILE.read_text(encoding="utf-8")
    except OSError as problem:
        _log.warning("no licence notice next to the application: %s", problem)
        return None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("| Paket |"):
            table: list[str] = []
            for entry in lines[index:]:
                if not entry.startswith("|"):
                    break
                table.append(entry)
            return "\n".join(table) + "\n" if len(table) > 2 else None
    _log.warning("the licence notice carries no table: %s", NOTICE_FILE)
    return None


def notices(extras: Iterable[str] = RUNTIME_EXTRAS) -> str:
    """Die Liste für den Über-Dialog und die Drittanbieter-Hinweise (§36,
    §37.2).
    """
    lines = ["| Paket | Lizenz |", "|---|---|"]
    policy = load_policy()
    known = {normalise(key): value for key, value in policy.known.items()}
    # Was hier installiert ist, **und** was auf einer anderen Plattform
    # dazukommt: Die Datei reist mit jedem Paket, und ein Hinweis, der nur die
    # Pakete des Baurechners nennt, fehlt auf allen anderen.
    try:
        found = dict(runtime_packages(extras))
    except metadata.PackageNotFoundError:
        # Im gebauten Paket ist die Anwendung keine installierte Distribution.
        # Dann steht die Liste in der Beilage, die neben ihr liegt — sonst
        # sieht der Kunde an dieser Stelle einen Ersatzsatz statt der
        # Lizenzhinweise, die BSD, MIT und LGPL verlangen.
        from_file = _notices_from_file()
        if from_file is None:
            raise
        return from_file
    for package, licence in PLATFORM_PACKAGES.items():
        found.setdefault(package, licence)
    for package, licence in sorted(found.items()):
        text = known.get(normalise(package), {}).get("licence", "") or licence or "—"
        lines.append(f"| {package} | {text} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - maintenance helper
    print(notices(), end="")
    for violation in check():
        print(f"VERSTOSS: {violation}")
