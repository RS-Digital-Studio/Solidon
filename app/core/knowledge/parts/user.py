"""Eigene Bausteine aus dem Nutzerverzeichnis (Bauplan §24.5).

Dieselbe Registrierung, gelesen aus ``<Nutzerdaten>/parts/*.py`` beim Start.
**Das ist kein Plugin-System**, und der Unterschied ist die Reichweite:

* eigene Bausteine gelten auf der Maschine, auf der sie liegen, und **reisen
  nie in einer Projektdatei mit** — sonst wäre die Regel aus §32 umgangen, dass
  eine hereinkommende Datei nie Code ausführt. **Das gilt für den Baustein als
  ``.py``, also für dieses Modul.** Seit dem 24.08.2026 kennt §24.5 daneben den
  Baustein als *Rezept* — Daten statt Funktion —, und der darf mitreisen; er
  wird nicht hier geladen, sondern aus dem Dokument gelesen;
* ein Projekt zu öffnen, das einen unbekannten eigenen Baustein benutzt, **hält
  an** und sagt, was fehlt (§15.2), statt etwas anderes zu rechnen;
* sie erweitern die Bibliothek, nicht die Anwendung: keine neuen Operationen,
  keine Änderungen an der Oberfläche, kein Zugriff auf den Op-Stapel.

Eine Datei, die sich nicht importieren lässt, wird gemeldet und übersprungen.
Ein kaputter eigener Baustein darf die Anwendung nicht am Starten hindern.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.core.knowledge.parts.registry import PARTS, PartRegistry
from app.core.log import get_logger
from app.core.paths import user_parts_dir
from app.core.types import Finding
from app.i18n import _

_log = get_logger(__name__)

#: Präfix der Modulnamen, unter denen eigene Bausteine importiert werden —
#: damit sie mit nichts kollidieren können, was die Anwendung mitbringt.
MODULE_PREFIX = "solidon_user_parts"

#: Unter welchem Präfix der Abdruck eines eigenen Bausteins im Dokument steht
#: (in ``libs``, §24.4). Ein Schlüssel je benutztem eigenen Baustein.
FINGERPRINT_KEY = "own_part:"


@dataclass(slots=True)
class LoadResult:
    """Was aus dem Nutzerverzeichnis herausgekommen ist."""

    loaded: tuple[str, ...] = ()
    findings: list[Finding] = field(default_factory=list)


def load(directory: Path | None = None, registry: PartRegistry | None = None) -> LoadResult:
    """Liest eigene Bausteine. Ein fehlendes Verzeichnis ist kein Fehler, es
    ist der Normalfall.
    """
    target = directory or user_parts_dir()
    result = LoadResult()
    if not target.is_dir():
        return result

    before = set((registry or PARTS).versions())
    for path in sorted(target.glob("*.py")):
        try:
            _import_file(path)
        except Exception as problem:  # a user file fails in user ways
            _log.warning("own part %s could not be loaded: %s", path.name, problem)
            result.findings.append(
                Finding(
                    code="parts.user_failed",
                    severity="warning",
                    message=_("Ein eigener Baustein ließ sich nicht laden."),
                    values={"file": path.name, "reason": str(problem)[:200]},
                )
            )

    after = (registry or PARTS).versions()
    result.loaded = tuple(sorted(set(after) - before))
    for name in result.loaded:
        _mark_as_own(name, registry)
    if result.loaded:
        _log.info("loaded %d own parts", len(result.loaded))
    return result


def _import_file(path: Path) -> None:
    """Importiert eine Datei unter ihrem eigenen Modulnamen.

    Das Verzeichnis des Nutzers liegt nicht im Importpfad und wird auch nicht
    Teil davon: das Modul wird von seinem Ort geladen und so benannt, dass es
    nichts überdecken kann (§32).
    """
    name = f"{MODULE_PREFIX}.{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"{path.name} is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)


def _mark_as_own(name: str, registry: PartRegistry | None) -> None:
    """Der Katalog kennzeichnet eigene Bausteine (§24.5) — die Herkunft muss
    also festgehalten werden.
    """
    (registry or PARTS).mark_source(name, "user")


def fingerprint(name: str, registry: PartRegistry | None = None) -> str:
    """Ein Abdruck der Datei, aus der ein eigener Baustein stammt — oder nichts.

    **Wozu.** Die Bibliotheksversion deckt alles ab, was mit einer Auslieferung
    kommt; ein eigener Baustein hat keine. Ändert der Nutzer darin ein Maß,
    bleiben Name, Parameter und ``version`` gleich, ``changed_since_library``
    liest gepflegte Änderungsverläufe — und die pflegt beim Ausprobieren
    niemand. Das Projekt rechnet beim nächsten Öffnen anders, ohne dass es
    jemand sagt, und das bricht Leitprinzip 4.

    **Warum der Inhalt und nicht die Zeit.** Eine Datei zu kopieren ändert ihre
    Änderungszeit und nicht ihren Inhalt; ein Abdruck über die Zeit meldete
    dann eine Änderung, die keine ist. ``paths._own_parts_stamp()`` nimmt für
    den Plattencache trotzdem die Zeit, und richtig so: Dort geht es um
    „irgendetwas hat sich bewegt", hier um „welcher Baustein war es".

    Ein mitgelieferter Baustein hat keinen Abdruck — er ist über
    ``parts_version`` gedeckt. Was sich nicht lesen lässt, ergibt ebenfalls
    nichts: Ein fehlender Abdruck heißt „keine Aussage möglich" und erzeugt
    nie einen Befund.
    """
    source = registry or PARTS
    if not source.has(name):
        return ""
    spec = source.get(name)
    if not spec.own:
        return ""
    module = inspect.getmodule(spec.fn)
    path = getattr(module, "__file__", None)
    if not path:
        return ""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()[:12]


def travelling_parts(used: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Eigene Bausteine, die ein Projekt bräuchte — die, die nie mit ihm
    reisen.

    Benutzt beim Speichern und beim Öffnen: auf dem Weg hinaus zum Warnen, auf
    dem Weg hinein zum Anhalten, statt etwas anderes zu rechnen.

    Gemeint sind die aus diesem Modul, also die ``.py``-Bausteine aus dem
    Nutzerordner. Ein Rezept (§24.5, seit dem 24.08.2026) steht im Dokument
    selbst und fehlt darum nie — es taucht hier gar nicht erst auf.
    """
    source = registry or PARTS
    return tuple(name for name in sorted(used) if source.has(name) and source.get(name).own)
