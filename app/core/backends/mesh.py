"""Mesh-Erzeugung, lokal oder gehostet (Bauplan §27, Säule B).

Die Schnittstelle kennt zwei Aufrufe und sonst nichts: ``text_to_mesh`` und
``image_to_mesh``. Kein Nutzercode, keine Dateipfade, kein Zustand — ein
gehosteter Dienst kann später dieselben zwei Aufrufe bedienen, ohne dass
darüber irgendetwas davon merkt (§27).

Lokal ist das ComfyUI, erreicht über seine HTTP-API: ein Workflow-Graph geht
hinein, eine Auftrags-ID kommt zurück, das Ergebnis wird geholt, wenn es
fertig ist. Der Graph ist eine Datendatei, kein Code — wer einen anderen
Generator installiert hat, tauscht die Datei aus, statt Python zu flicken.

Woran die mitgelieferten Graphen hängen, steht deshalb hier und nicht im Code:
an der Knotensammlung ``ComfyUI-TripoSG-Solidon`` samt dem Modell ``TripoSG``
unter ``models/triposg``, an einem BiRefNet-Gewicht unter
``models/background_removal`` fürs Freistellen, und ``text_to_mesh``
zusätzlich an einem SDXL-Modell. Letzteres ist kein Umweg,
sondern die Sache selbst: TripoSG kennt keinen Texteingang, Text wird erst zu
einem Bild und das Bild zum Körper. Fehlt eines davon, sagt ComfyUI beim
Abschicken, welcher Knoten fehlt — die Meldung reicht bis zum Nutzer durch.
Über die HTTP-API muss dabei **jeder** Eingang gesetzt sein, auch ein als
``optional`` deklarierter: die Oberfläche schickt sie immer alle mit, und
mancher Knoten liest sie ungeprüft.

**Warum TripoSG und nicht Hunyuan3D.** Die Lizenz der Gewichte ist nicht
unsere, und sie entscheidet, wer die Anwendung benutzen darf. Hunyuan3D 2.1
steht unter der Tencent Community License, deren Geltungsbereich die
Europäische Union, das Vereinigte Königreich und Südkorea ausdrücklich
ausnimmt — für eine Anwendung, die hier verkauft wird, ist das keine
Fußnote, sondern ein Ausschluss. TripoSG (VAST-AI-Research) steht unter MIT,
Quelltext wie Gewichte, und liefert Formen derselben Güte. Gemessen an vier
Fällen vom glatten Drehkörper bis zur Figur mit dünnen Fortsätzen kam jedes
Mal ein geschlossener Körper aus einem Stück heraus.

Solidon liefert weiterhin keine Gewichte mit und lädt keine — der Nutzer
installiert ComfyUI und seine Modelle selbst, und was er einsetzt, entscheidet
er. Der mitgelieferte Graph nennt deshalb Rollen (``{model:shape}``) und keine
Datei: wer ein anderes Modell mit derselben Rolle installiert, benutzt es ohne
eine Zeile Code zu ändern. Weitere frei lizenzierte Kerne für dieselbe Aufgabe
sind Step1X-3D (Apache-2.0) und TRELLIS (MIT).

**Freigestellt wird mit ComfyUIs eigenen Knoten**, und dahinter steht eine
Lizenzsache: Der Ablauf sprach ``RMBG`` aus ``ComfyUI-RMBG`` an, und das ist
GPL-3.0 — Regel 15 lässt keine GPL-Abhängigkeit zu. Aufgefallen ist es, als
der Weg zum ersten Mal wirklich gefahren wurde. ComfyUI kann es seit 0.33
selbst (``LoadBackgroundRemovalModel`` und ``RemoveBackground``), die Gewichte
sind BiRefNet unter MIT, und damit fällt neben der Lizenzfrage auch ein
Installationsschritt weg. Ein älteres ComfyUI kennt die Knoten nicht — dann
nennt :meth:`ComfyBackend.missing_nodes` sie mit Namen.

Die Zahlen im Graphen sind gemessen, nicht geraten: ``octree_depth`` steht auf
8, weil 9 bei vierfacher Dreieckszahl und doppelter Laufzeit keinen sichtbaren
Unterschied brachte; ``steps`` steht auf 50, weil bei 25 die dünnen Flächen
sichtbar ausfransen. Zusammen sind das rund dreizehn Sekunden je Körper auf
einer RTX 4080.

Was herauskommt, wird nie geglaubt — Generatoren erzeugen Netze mit Löchern,
losen Komponenten und umgedrehten Normalen als Normalfall. Die Reparaturkette,
die sich darum kümmert, steht aber nicht hier: sie gehört auf den Stapel, wo
sie sichtbar und rücknehmbar ist (§2.2, Weg 3, und :mod:`app.core.generate`).
Ein Backend liefert, es urteilt nicht.
"""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Final, Protocol

from app.core.discover import BROKEN_ADDRESS, PROBE_SECONDS, UNUSABLE_ADDRESS, opener_for
from app.core.errors import CANCEL, INSTALL_MISSING, Action, AppError, OperationCancelled
from app.core.geom.mesh import MeshData, read_mesh
from app.core.log import get_logger
from app.core.types import ProgressFn
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie lange eine Erzeugung dauern darf. Minuten, keine Sekunden — das ist ein
#: Diffusionsmodell auf jemandes Grafikkarte, keine Datenbankabfrage.
TIMEOUT_SECONDS = 600.0

#: Wie oft der Auftrag gefragt wird, ob er fertig ist.
POLL_SECONDS = 1.0

#: Die harte Grenze, hinter der auch ein Auftrag aufgegeben wird, der laut
#: Warteschlange noch läuft. Sie fängt den Fall, dass ComfyUI seine Schlange
#: falsch beantwortet — nicht den langsamen Rechner, dafür ist
#: :data:`TIMEOUT_SECONDS` da.
STUCK_SECONDS = 3600.0

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"

#: Die mitgelieferten Workflow-Graphen, einer je Aufruf. Platzhalter darin
#: werden vor dem Senden gefüllt: ``{prompt}``, ``{seed}``, ``{image}``.
WORKFLOW_DIR = Path(__file__).parent / "data"

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")

#: Ein Modellplatzhalter nennt nicht die Datei, sondern die Rolle:
#: ``{model:shape}``. Aufgelöst wird er erst gegen den Rechner, auf dem es
#: läuft — siehe :data:`MODEL_ROLES`.
_MODEL_PLACEHOLDER = re.compile(r"^\{model:([a-z_]+)\}$")


@dataclass(frozen=True, slots=True)
class ModelRole:
    """Woran ein Modell für seine Aufgabe erkannt wird.

    ``prefer`` ist eine Rangfolge, nicht eine Menge: das erste Muster, auf das
    etwas passt, gewinnt. ``avoid`` schließt vorher aus, denn manche Namen
    liegen im selben Ordner und sehen nur ähnlich aus — der Formkern und die
    Bildmodelle wohnen beide unter ``checkpoints``.
    """

    prefer: tuple[str, ...]
    avoid: tuple[str, ...] = ()


#: Die Rollen, die ein mitgelieferter Graph benennen darf. Wer einen eigenen
#: Graphen einsetzt, benutzt dieselben Namen — oder trägt die Datei fest ein,
#: was weiterhin erlaubt ist und dann eben nicht mitwandert.
MODEL_ROLES: Final[dict[str, ModelRole]] = {
    "image": ModelRole(
        prefer=("juggernaut", "dreamshaper", "sd_xl", "sdxl", "xl"),
        avoid=("hunyuan", "3d", "vae", "refiner", "inpaint", "turbo"),
    ),
    # TripoSG steht vorn, weil der mitgelieferte Graph es benutzt und weil es
    # das einzige der drei ist, dessen Lizenz hier keine Frage aufwirft. Die
    # Hunyuan-Muster bleiben stehen: wer sie installiert hat und einen eigenen
    # Graphen fährt, soll nicht deshalb ins Leere greifen.
    # ``scribble`` ist ausgeschlossen, weil es nicht dasselbe Modell in einer
    # anderen Größe ist, sondern ein anderes: es erwartet eine Kritzelei als
    # Eingang und macht aus einem Lichtbild Unsinn.
    "shape": ModelRole(
        prefer=("triposg", "tripo", "step1x", "hunyuan3d-dit", "hunyuan3d", "hunyuan"),
        avoid=("vae", "scribble"),
    ),
    "shape_vae": ModelRole(prefer=("hunyuan3d-vae", "hunyuan3d", "vae"), avoid=("dit",)),
    # Freistellen. ``lucida`` steht vorn, weil es die feinere Kante zieht und
    # doppelt so groß ist — wer beides hat, will das bessere; wer nur
    # ``birefnet`` hat, bekommt es. Beide sind BiRefNet-Gewichte unter MIT.
    "background": ModelRole(prefer=("lucida", "birefnet")),
}


def _silent(fraction: float, text: str) -> None:
    del fraction, text


CancelledFn = Callable[[], bool]
"""``() -> bool``: Hat der Nutzer abgebrochen?

Ein Rückruf und kein Qt-Objekt — der Kern weiß nichts vom Fenster (§7,
:data:`app.core.types.ProgressFn` nebenan folgt derselben Regel).
"""


def _never() -> bool:
    return False


def _configured_url() -> str:
    """Die eingetragene ComfyUI-Adresse, sonst die auf dieser Maschine.

    Der Import steht hier und nicht oben, weil :mod:`app.core.discover` die
    Nutzerkonfiguration liest — das gehört in den Aufruf und nicht in den
    Modulimport, damit eine Testumgebung sie noch umlenken kann.
    """
    from app.core import discover

    return discover.service_url("comfyui", DEFAULT_COMFY_URL)


def comfy_base(url: str | None) -> str:
    """Die Basisadresse von ComfyUI aus dem, was jemand eingetragen hat.

    **„127.0.0.1:8188" ist keine Nachlässigkeit, sondern die Schreibweise, in
    der Adressen weitergegeben werden** — ComfyUI selbst schreibt sie so in
    seine Startzeile. Ohne Schema war sie hier trotzdem dauerhaft unbrauchbar:
    :func:`reachable` fand keinen Rechnernamen und meldete „nicht erreichbar",
    der Generator blieb ausgegraut, und der Satz „Die Adresse von ComfyUI ist
    keine Adresse" — der einzige, der auf das Feld gezeigt hätte — war damit
    unerreichbar, weil vorher schon niemand mehr fragte.

    Dieselbe Normalisierung, die der Ollama-Weg seit dem 24.08.2026 hat
    (:func:`~app.core.backends.llm.ollama_endpoint`), und aus demselben Grund.
    Ein eigener Pfad bleibt stehen: Hinter einem Reverse-Proxy liegt ComfyUI
    unter ``/comfy``, und wer das einträgt, meint es so.
    """
    address = (url or "").strip() or DEFAULT_COMFY_URL
    if "://" not in address:
        address = f"http://{address}"
    return address.rstrip("/")


@dataclass(frozen=True, slots=True)
class GeneratedMesh:
    """Ein erzeugter Körper, wie er kam, plus woher er kam (§11.3).

    Die Bytes werden mit Absicht neben dem geparsten Körper aufgehoben: sie
    sind das, was ins Projekt eingebettet wird (§16.1), und sie hier neu zu
    kodieren würfe die Textur weg, an der der ganze Farbweg von Säule B
    hängt (§20).
    """

    mesh: MeshData
    payload: bytes
    suffix: str
    backend: str
    prompt: str = ""
    seed: int = 0


class MeshBackend(Protocol):
    """Die zwei Aufrufe aus §27, und nicht mehr."""

    @property
    def id(self) -> str: ...

    @property
    def available(self) -> bool:
        """False, wenn nichts läuft — die Erzeugen-Aktion graut aus."""
        ...

    def text_to_mesh(
        self,
        prompt: str,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        """``cancelled`` wird während des Wartens regelmäßig gefragt (§15.6).

        **Ohne ihn ließ sich eine laufende Erzeugung nicht abbrechen** — bis zu
        einer Stunde (:data:`STUCK_SECONDS`). Der Dialog wartete beim Schließen
        fünfzig Millisekunden auf seinen Arbeiter und ließ dann los; der
        Arbeiter rechnete weiter und meldete sein Ergebnis an ein Fenster, das
        es nicht mehr gab. Ein Backend, für das Abbrechen nichts bedeutet, darf
        den Rückruf ignorieren — geliefert wird er trotzdem."""
        ...

    def image_to_mesh(
        self,
        image: bytes,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh: ...


class GenerationFailed(AppError):
    """Der Generator hat keinen Körper geliefert."""

    default_title = _("Die 3D-Modell-Erzeugung hat kein Modell geliefert.")

    def __init__(
        self,
        detail: TranslatableText | str = "",
        *,
        title: TranslatableText | str | None = None,
        values: dict[str, Any] | None = None,
        suggestions: tuple[Action, ...] = (),
    ) -> None:
        # Ein anderer Titel ist nicht Zierde: „hat kein Modell geliefert" ist
        # falsch, wenn der Lauf nie begonnen hat — weil eine Modelldatei fehlt
        # oder weil ComfyUI gar nicht antwortet.
        super().__init__(
            title=title,
            detail=detail or None,
            values=values or {},
            suggestions=suggestions,
        )


# --- Transporte -------------------------------------------------------------------

Fetch = Callable[[str, bytes | None, dict[str, str]], bytes]
"""``url, body, headers -> bytes``. Austauschbar — genau das lässt die Suite
den ganzen Weg ohne Grafikkarte fahren."""


def fetch(url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
    """Eine Anfrage, Bytes zurück. POST, wenn es einen Rumpf gibt, sonst GET."""
    request = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with opener_for(url).open(request, timeout=TIMEOUT_SECONDS) as answer:
            return bytes(answer.read())
    except urllib.error.HTTPError as error:
        raise GenerationFailed(
            detail=f"{error.code}: {error.read().decode('utf-8', errors='replace')[:300]}"
        ) from error
    except ConnectionError as error:
        # **Der Abbruch mitten in der Antwort**, und deshalb vor dem Fall
        # darunter: urllib wickelt einen Verbindungsfehler beim
        # *Aufbau* in ``URLError``, beim **Lesen** nicht — dort kommt
        # ``ConnectionResetError`` nackt durch und wäre ein
        # ``InternalError`` geworden: „Im Programm ist ein unerwarteter
        # Fehler aufgetreten." Genau so traf es am 26.08.2026 einen
        # Kunden beim Sprachmodell (S-20260826-1db075); hier ist
        # derselbe Fehler an derselben Art von Stelle.
        #
        # Der Unterschied zum Satz darunter ist für den Kunden echt:
        # Dort hat ComfyUI **nie angefangen**, hier hat es angefangen
        # und mittendrin aufgelegt — typisch, wenn ein Modell den
        # Speicher sprengt. „Läuft es?" wäre dann die falsche Frage.
        raise GenerationFailed(
            title=_("Die 3D-Modell-Erzeugung wurde unterbrochen."),
            detail=_(
                "ComfyUI hat die Verbindung mitten in der Antwort beendet. "
                "Meist fehlt Arbeitsspeicher: ein kleineres Modell wählen "
                "oder das Bild verkleinern. Sein Protokoll nennt den Grund."
            ),
            values={"url": _origin(url), "reason": str(error)},
            suggestions=(CANCEL,),
        ) from error
    except urllib.error.URLError as error:
        # Hier endet der häufigste Fall überhaupt: ComfyUI läuft nicht mehr.
        # Ohne eigenen Satz stünde davon „[WinError 10061] Es konnte keine
        # Verbindung hergestellt werden" im Dialog — Fremdtext, technisch, und
        # ohne einen Hinweis, was jetzt hilft. Der Titel ist derselbe Fehler:
        # geliefert hat der Generator nichts, weil er nie angefangen hat.
        raise GenerationFailed(
            title=_("Die 3D-Modell-Erzeugung konnte nicht starten."),
            # Die Adresse gehört in die Werte daneben, nicht als Platzhalter in
            # den Satz: einen Fehlertext formatiert niemand nach, er wird
            # angezeigt wie er ist.
            detail=_(
                "ComfyUI antwortet nicht. Läuft es? Steht es auf einem anderen "
                "Rechner, gehört seine Adresse in die Einstellungen."
            ),
            values={"url": _origin(url), "reason": str(error.reason)},
            suggestions=(INSTALL_MISSING, CANCEL),
        ) from error
    except BROKEN_ADDRESS as error:
        # **Getrennt vom Fall darüber, weil der Nutzer etwas anderes tun muss.**
        # „ComfyUI antwortet nicht" schickt ihn zum Programm; hier liegt es an
        # der Adresse, und dann hilft nur das Feld in den Einstellungen. Der
        # Satz nennt deshalb ein Beispiel — wer noch nie eine Dienstadresse
        # eingetragen hat, weiß sonst nicht, wie eine aussieht.
        raise GenerationFailed(
            title=_("Die Adresse von ComfyUI ist keine Adresse."),
            detail=_(
                "In den Einstellungen steht etwas, das Solidon nicht als Adresse "
                "lesen kann — meist ein Ordner oder ein Programmpfad. Erwartet "
                "wird die Adresse, unter der ComfyUI im Browser erreichbar ist: "
                "http://127.0.0.1:8188, oder Rechnername und Port, wenn es auf "
                "einem anderen Rechner läuft."
            ),
            values={"url": url, "reason": str(error)},
            suggestions=(INSTALL_MISSING, CANCEL),
        ) from error


def _origin(url: str) -> str:
    """Nur Rechner und Port — der Pfad dahinter sagt einem Nutzer nichts."""
    parts = urllib.parse.urlparse(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.netloc else url


def reachable(url: str, seconds: float = PROBE_SECONDS) -> bool:
    """Ein Socket, keine Anfrage: ein geschlossener Port antwortet sofort,
    HTTP nicht.

    Gefragt wird die normalisierte Adresse (:func:`comfy_base`) — sonst gilt
    eine Eingabe ohne Schema als unerreichbar, und das ist sie nicht.
    """
    try:
        parts = urllib.parse.urlparse(comfy_base(url))
        if not parts.hostname:
            # **Ohne Rechnernamen wird gar nicht erst gefragt.** Ein leerer Host
            # ist für ``socket`` nicht „nichts", sondern *localhost* — eine
            # Adresse wie ``C:\Users\...`` hätte damit auf jedem Rechner,
            # auf dem irgendetwas auf Port 80 lauscht, „erreichbar" gemeldet.
            # Gefunden hat das die CI: derselbe Test war auf dieser Maschine
            # grün und auf dem Windows-Runner rot (24.08.2026).
            return False
        with socket.create_connection((parts.hostname, parts.port or 80), timeout=seconds):
            return True
    except UNUSABLE_ADDRESS:
        # ``ValueError`` gehört dazu: Steht im Adressfeld ein Pfad statt einer
        # Adresse, liest ``urlparse`` alles hinter ``C:`` als Port und wirft
        # beim Zugriff darauf. Eine unbrauchbare Adresse heißt „nicht
        # erreichbar", nicht „Absturz" (Regel 17, derselbe Fall wie bei Ollama
        # am 24.08.2026).
        return False


# --- ComfyUI ----------------------------------------------------------------------


class Readiness(StrEnum):
    """Wie weit dieses ComfyUI vorbereitet ist.

    Vier Antworten statt eines Wahrheitswerts, und jede zieht einen anderen
    Satz und einen anderen Knopf nach sich: Wo nichts läuft, hilft die Liste
    der zusätzlichen Programme; wo die Knoten fehlen, hilft der
    Einrichtungsdialog; und wo etwas antwortet, das wir nicht kennen, wird
    nichts behauptet.
    """

    READY = "ready"
    ABSENT = "absent"
    NO_NODES = "no_nodes"
    NO_MODEL = "no_model"
    UNKNOWN = "unknown"


#: Woran ein Knoten aus unserer Sammlung zu erkennen ist. Der Ablauf nennt ihn
#: mit vollem Namen; hier steht nur der Anfang, damit ein zweiter Knoten aus
#: derselben Sammlung nicht nachgetragen werden muss.
OWN_NODE_PREFIX: Final = "TripoSG"


def _failed(entry: dict[str, Any]) -> None:
    """Wirft, wenn ComfyUI diesen Auftrag mit einem Fehler beendet hat.

    **Zehn Minuten auf einen toten Auftrag gewartet.** Geprüft wurde nur, ob
    Ausgaben da sind — ein Auftrag, den ComfyUI nach Sekunden mit
    ``execution_error`` beendet hatte, sah genauso aus wie einer, der noch
    rechnet. Am Ende stand „Die Erzeugung hat ihr Zeitlimit erreicht", und der
    Grund hatte die ganze Zeit im Verlauf gestanden: „Torch not compiled with
    CUDA enabled", gemeldet vom Knoten mit Namen. Gemessen an einer Maschine
    mit Intel-Arc-Grafik, wo genau das der Fall ist.

    Der Satz von ComfyUI reist mit, und zwar unübersetzt: Was dort steht, ist
    genauer als jede Umschreibung, und wer damit zum Support geht, bringt die
    Zeile mit, die dort weiterhilft. Der Knotenname steht davor — er sagt, in
    welchem Schritt es gerissen ist.

    **Angeboten wird nur Abbrechen, und das ist hier die Entscheidung und kein
    Versäumnis.** Regel 17 verlangt entweder eine Handlung mit Wirkung oder
    einen Rat zum Lesen; der Rat steht im ``detail``. Eine Handlung gäbe es
    nur für einen Teil der Fälle: „No module named …" führt zur Einrichtung,
    „Torch not compiled with CUDA enabled" nirgendwohin, und Speichermangel
    wieder woandershin. Ein Knopf, der bei einem Drittel der Gründe passt, ist
    schlechter als keiner — er behauptet einen Weg, den es nicht gibt. Wer
    diese Stelle einmal aufteilt (etwa nach Mustern im Grund), soll den Knopf
    genau dort anbieten, wo er trägt.
    """
    status = entry.get("status")
    if not isinstance(status, dict) or status.get("status_str") != "error":
        return
    node, reason = "", ""
    for message in status.get("messages") or ():
        if not (isinstance(message, list) and len(message) == 2):
            continue
        kind, fields = message
        if kind != "execution_error" or not isinstance(fields, dict):
            continue
        node = str(fields.get("node_type") or fields.get("node_id") or "")
        reason = str(fields.get("exception_message") or "").strip()
    raise GenerationFailed(
        title=_("Der Generator hat den Auftrag abgebrochen."),
        detail=_(
            "ComfyUI hat die Erzeugung mit einem Fehler beendet. Was es dazu "
            "sagt, steht daneben — meist fehlt dem Rechner etwas, das der "
            "Ablauf verlangt."
        ),
        values={"node": node, "reason": reason or "-"},
        suggestions=(CANCEL,),
    )


@dataclass(slots=True)
class ComfyBackend:
    """ComfyUI auf diesem Rechner, über seine HTTP-API (§27).

    Drei Anfragen: den Graphen abschicken, auf den Auftrag warten, die Datei
    holen. Die Client-ID ist jedes Mal neu — das Backend führt keinen Zustand,
    also tut dieses hier es auch nicht (§27).
    """

    # Die Adresse ist nicht fest: wer ComfyUI auf einem zweiten Rechner oder
    # auf einem anderen Port betreibt, trägt sie einmal ein (§38). Ohne
    # Eintrag bleibt es bei dieser Maschine.
    url: str = field(default_factory=lambda: _configured_url())
    transport: Fetch = fetch
    poll_seconds: float = POLL_SECONDS
    timeout_seconds: float = TIMEOUT_SECONDS
    workflows: Path = WORKFLOW_DIR

    @property
    def id(self) -> str:
        return "comfyui"

    @property
    def base(self) -> str:
        """Die Adresse, an die wirklich gefragt wird (:func:`comfy_base`).

        ``url`` bleibt, was jemand eingetragen hat — hier steht, was daraus
        wird. Getrennt, damit die Einstellungen weiter den eigenen Text zeigen
        und nicht eine Fassung, die niemand geschrieben hat."""
        return comfy_base(self.url)

    @property
    def available(self) -> bool:
        return reachable(self.url)

    def readiness(self, workflow: str = "image_to_mesh") -> Readiness:
        """Läuft es — und kennt es die Knoten, die der Ablauf anspricht?

        **Zwei Fragen, und bis hierhin wurde nur die erste gestellt.** Der
        Dialog sagte „Bereit", sobald ein Port antwortete. Wer ComfyUI
        installiert und gestartet hatte, ohne die Knoten einzurichten, tippte
        also seinen Satz, drückte *Erzeugen*, wartete — und bekam dann zu
        lesen, dass die Knotensammlung fehlt. Die Auskunft war die ganze Zeit
        einen HTTP-Aufruf entfernt.

        Gefragt wird nach den Knoten, die der mitgelieferte Ablauf wirklich
        benutzt, und nicht nach Namen aus einer zweiten Liste: Wer den Ablauf
        austauscht (§27), tauscht damit auch, was geprüft wird.

        **Und nach allen, nicht nach einem.** Gefragt wurde bis hierhin nur der
        Knoten aus unserer eigenen Sammlung — der lag nach der Einrichtung
        vor, also stand „Bereit" da, und abgeschickt scheiterte der Auftrag
        trotzdem an einem *anderen* Knoten, den derselbe Ablauf anspricht.
        Gemessen an einem frischen ComfyUI: unsere vier Knoten geladen, der
        fünfte fehlte, und die Anwendung behauptete Bereitschaft. Wer prüft,
        prüft den ganzen Ablauf.
        """
        if not reachable(self.url):
            return Readiness.ABSENT
        wanted = self._graph_nodes(workflow)
        if not wanted:
            return Readiness.READY
        try:
            missing = self.missing_nodes(workflow)
        except (OSError, ValueError):
            # Antwortet der Port und nicht diese Frage, ist es kein ComfyUI,
            # das wir kennen — behauptet wird dann nichts.
            return Readiness.UNKNOWN
        if missing:
            return Readiness.NO_NODES
        try:
            if self.missing_models(workflow):
                return Readiness.NO_MODEL
        except (AppError, OSError, ValueError):
            return Readiness.UNKNOWN
        return Readiness.READY

    def missing_models(self, workflow: str = "image_to_mesh") -> tuple[str, ...]:
        """Welche Modellrollen dieses ComfyUI **nicht** ausfüllen kann.

        **Der Textweg erfuhr es beim Abschicken.** Er braucht zusätzlich ein
        SDXL-Modell — TripoSG kennt keinen Texteingang, Text wird erst zu einem
        Bild. Wer keines installiert hatte, tippte seinen Satz, drückte
        *Erzeugen* und bekam „ComfyUI hat für diese Aufgabe kein Modell
        anzubieten". Die Auskunft war die ganze Zeit einen Aufruf entfernt, und
        zwar denselben, den die Auflösung ohnehin macht.

        Gefragt wird je Rolle und nicht je Datei: Was die Rolle ausfüllt,
        entscheidet der Rechner, auf dem es läuft (:data:`MODEL_ROLES`).
        """
        graph = self._read_graph(workflow)
        if graph is None:
            return ()
        offered: dict[str, list[str]] = {}
        missing: list[str] = []
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            kind = str(node.get("class_type", ""))
            for field_name, value in inputs.items():
                if not isinstance(value, str):
                    continue
                found = _MODEL_PLACEHOLDER.match(value)
                if found is None:
                    continue
                role = found.group(1)
                key = f"{kind}.{field_name}"
                if key not in offered:
                    offered[key] = self._offered(kind, field_name)
                if not offered[key] and role not in missing:
                    missing.append(role)
        return tuple(missing)

    def missing_nodes(self, workflow: str = "image_to_mesh") -> tuple[str, ...]:
        """Welche Knoten des Ablaufs dieses ComfyUI **nicht** kennt.

        Die Namen, nicht bloß ihre Anzahl: „ein Knoten fehlt" schickt niemanden
        weiter, „RMBG fehlt" nennt die Sammlung, die zu installieren ist
        (Regel 17). Eingebaute Knoten stehen mit in der Frage und kosten
        nichts — sie sind da, und wären sie es nicht, wäre das genauso
        berichtenswert.

        **Eine Frage je Knoten und nicht eine für alle**, und das ist gemessen:
        ``/object_info`` ohne Knotennamen liefert auf einem ComfyUI mit 856
        Knoten 1,6 MB und braucht dafür 346 ms; die vierzehn Einzelfragen des
        Textwegs kosten zusammen 88 ms. Die naheliegende Sparsamkeit wäre hier
        viermal langsamer. Wer die Zahl der Fragen erhöht, misst sie nach — der
        Aufruf steht in einem Fenster, das gerade aufgeht.
        """
        missing: list[str] = []
        for kind in self._graph_nodes(workflow):
            answer = self.transport(f"{self.base}/object_info/{urllib.parse.quote(kind)}", None, {})
            described = json.loads(answer.decode("utf-8"))
            if kind not in described:
                missing.append(kind)
        return tuple(missing)

    def _read_graph(self, workflow: str) -> dict[str, Any] | None:
        """Der Ablauf als Daten, oder ``None`` wenn er nicht zu lesen ist."""
        try:
            loaded = json.loads((self.workflows / f"{workflow}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def _graph_nodes(self, workflow: str = "image_to_mesh") -> tuple[str, ...]:
        """Die Knotenarten, die der Ablauf anspricht — aus ihm gelesen.

        Nicht eingetragen: Ein ausgetauschter Graph bringt seine eigenen Knoten
        mit, und eine feste Liste wäre am Tag danach falsch.

        **Welcher Ablauf, sagt der Aufrufer.** Der Textweg spricht andere Knoten
        an als der Bildweg und braucht ein Modell mehr; geprüft wurde bis
        hierhin immer der Bildweg, auch wenn der Textweg lief.
        """
        graph = self._read_graph(workflow)
        if graph is None:
            return ()
        found: list[str] = []
        for node in graph.values():
            kind = str(node.get("class_type", "")) if isinstance(node, dict) else ""
            if kind and kind not in found:
                found.append(kind)
        return tuple(found)

    def text_to_mesh(
        self,
        prompt: str,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        if not prompt.strip():
            raise GenerationFailed(detail=_("Die Beschreibung ist leer."))
        graph = self._graph("text_to_mesh", {"prompt": prompt, "seed": seed})
        return self._run(graph, prompt=prompt, seed=seed, progress=progress, cancelled=cancelled)

    def image_to_mesh(
        self,
        image: bytes,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        if not image:
            raise GenerationFailed(detail=_("Das Bild ist leer."))
        progress(0.05, str(_("Bild übertragen")))
        name = self._upload(image)
        graph = self._graph("image_to_mesh", {"image": name, "seed": seed})
        return self._run(graph, prompt="", seed=seed, progress=progress, cancelled=cancelled)

    # --- die drei Schritte ---

    def _graph(self, name: str, values: dict[str, Any]) -> dict[str, Any]:
        """Lädt den mitgelieferten Workflow und setzt die Werte hinein."""
        path = self.workflows / f"{name}.json"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as problem:
            raise GenerationFailed(
                detail=_("Die Workflow-Datei fehlt."),
                values={"name": name},
            ) from problem
        graph = self._with_models(json.loads(text))
        return dict(_filled(graph, values))

    def _with_models(self, graph: dict[str, Any]) -> dict[str, Any]:
        """Setzt für jede Modellrolle ein, was auf diesem Rechner wirklich liegt.

        Ein Graph mit fest eingetragenen Dateinamen läuft nur dort, wo genau
        diese Dateien liegen — überall sonst bricht er mit einer Meldung über
        einen Wert, den der Nutzer nie gesetzt hat. Deshalb nennt der Graph die
        Rolle, und welche Datei sie ausfüllt, entscheidet sich hier gegen den
        laufenden Server.

        Gefragt wird nur, wenn wirklich eine Rolle im Graphen steht: ein
        Graph mit festen Namen kostet weiterhin keine einzige Anfrage.
        """
        offered: dict[str, list[str]] = {}
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            for key, value in list(inputs.items()):
                if not isinstance(value, str):
                    continue
                found = _MODEL_PLACEHOLDER.match(value)
                if found is None:
                    continue
                inputs[key] = self._pick(
                    found.group(1), str(node.get("class_type", "")), key, offered
                )
        return graph

    def _pick(self, role: str, class_type: str, field: str, offered: dict[str, list[str]]) -> str:
        """Die Datei, die diese Rolle auf diesem Rechner ausfüllt."""
        wanted = MODEL_ROLES.get(role)
        if wanted is None:
            raise GenerationFailed(
                detail=_("Der Workflow verlangt eine unbekannte Modellrolle."),
                values={"role": role},
            )

        key = f"{class_type}.{field}"
        if key not in offered:
            offered[key] = self._offered(class_type, field)
        options = offered[key]
        if not options:
            raise GenerationFailed(
                detail=_(
                    "ComfyUI hat für diese Aufgabe kein Modell anzubieten. Es "
                    "fehlt die Modelldatei, nicht die Einstellung."
                ),
                values={"role": role, "node": class_type},
            )

        usable = [
            entry for entry in options if not any(bad in entry.lower() for bad in wanted.avoid)
        ] or options
        for hint in wanted.prefer:
            for entry in usable:
                if hint in entry.lower():
                    return entry
        # Keines der Muster passte. Das ist kein Fehler: der Nutzer hat ein
        # Modell, das wir nicht kennen, und eines ist besser als keines.
        _log.info("no model matched role %s, taking %s", role, usable[0])
        return usable[0]

    def _offered(self, class_type: str, field: str) -> list[str]:
        """Was ComfyUI für diesen Eingang zur Auswahl stellt."""
        answer = self.transport(
            f"{self.base}/object_info/{urllib.parse.quote(class_type)}", None, {}
        )
        try:
            described = json.loads(answer.decode("utf-8"))
        except ValueError as problem:
            raise GenerationFailed(
                detail=_(
                    "ComfyUI hat den Knoten in einer Form beschrieben, die sich nicht lesen lässt."
                ),
                values={"node": class_type},
            ) from problem

        # Ein ComfyUI ohne diesen Knoten antwortet mit einem leeren Objekt,
        # nicht mit einem Fehler. Wer das nicht unterscheidet, meldet gleich
        # darauf „es fehlt die Modelldatei" — und schickt jemanden Gewichte
        # suchen, dem in Wahrheit die Knotensammlung fehlt.
        if class_type not in described:
            raise GenerationFailed(
                title=_("Die 3D-Modell-Erzeugung konnte nicht starten."),
                # Der Satz nannte hier „«python tools/setup_comfyui.py»" — einen
                # Befehl, den ein Kunde nicht ausführen kann: ``tools/`` reist
                # im Paket nicht mit. Solidon richtet die Knoten selbst ein,
                # und der Weg dorthin ist der Knopf, den der Vorschlag anbietet.
                detail=_(
                    "Dieses ComfyUI kennt den Knoten nicht, den der Ablauf "
                    "benutzt. Die Knotensammlung fehlt — nicht das Modell. "
                    "Einrichten lässt sie sich unter „Zusätzliche Programme“; "
                    "danach ComfyUI neu starten."
                ),
                values={"node": class_type},
                suggestions=(INSTALL_MISSING, CANCEL),
            )

        inputs = described.get(class_type, {}).get("input", {})
        for group in ("required", "optional"):
            entry = (inputs.get(group) or {}).get(field)
            if not isinstance(entry, list) or not entry:
                continue
            # **Zwei Formen, und beide kommen aus demselben Server.** Klassisch
            # steht die Auswahlliste als erstes Element (``[["TripoSG"], {…}]``)
            # — ein Typname wie ``"INT"`` steht an derselben Stelle und ist
            # keine. Die neuen eingebauten Knoten schreiben statt der Liste
            # ``"COMBO"`` und legen die Namen in die Beschreibung daneben
            # (``["COMBO", {"options": […]}]``).
            #
            # Gemessen an einem ComfyUI 0.33: ``TripoSGLoader`` klassisch,
            # ``LoadBackgroundRemovalModel`` neu. Wer nur die alte Form liest,
            # hält jede neue Auswahl für leer und meldet „es fehlt die
            # Modelldatei", obwohl sie daliegt — genau das ist passiert.
            if isinstance(entry[0], list):
                return [str(name) for name in entry[0]]
            if entry[0] == "COMBO" and len(entry) > 1 and isinstance(entry[1], dict):
                offered = entry[1].get("options")
                if isinstance(offered, list):
                    return [str(name) for name in offered]
        return []

    def _upload(self, image: bytes) -> str:
        """Legt das Bild dorthin, wo ComfyUI es sehen kann, und gibt den Namen
        zurück, den es bekommen hat.
        """
        name = f"solidon_{uuid.uuid4().hex}.png"
        boundary = uuid.uuid4().hex
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'.encode(),
                b"Content-Type: image/png\r\n\r\n",
                image,
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        answer = self.transport(
            f"{self.base}/upload/image",
            body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        given = json.loads(answer.decode("utf-8")).get("name")
        return str(given or name)

    def _run(
        self,
        graph: dict[str, Any],
        *,
        prompt: str,
        seed: int,
        progress: ProgressFn,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        progress(0.1, str(_("Auftrag abschicken")))
        payload = json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode("utf-8")
        answer = self.transport(
            f"{self.base}/prompt", payload, {"Content-Type": "application/json"}
        )
        job = json.loads(answer.decode("utf-8")).get("prompt_id")
        if not job:
            raise GenerationFailed(detail=_("Das Backend hat keinen Auftrag angenommen."))

        outputs = self._wait(str(job), progress, cancelled or _never)
        progress(0.9, str(_("Modell holen")))
        payload_bytes, suffix = self._download(outputs)
        return GeneratedMesh(
            mesh=read_mesh(payload_bytes, suffix),
            payload=payload_bytes,
            suffix=suffix,
            backend=self.id,
            prompt=prompt,
            seed=seed,
        )

    def _wait(
        self, job: str, progress: ProgressFn, cancelled: CancelledFn = _never
    ) -> dict[str, Any]:
        """Fragt, bis der Auftrag im Verlauf steht. Es gibt kein Push zum Zuhören.

        Der Satz dazu sagt die verstrichene Zeit, und das ist keine Zierde: ein
        Lauf dauert hier vierzig bis siebzig Sekunden, und „Modell wird
        erzeugt" allein steht die ganze Zeit unbewegt da — von einem Programm,
        das hängt, ist das nicht zu unterscheiden (§2.8). Eine erfundene
        Prozentzahl wäre die schlechtere Antwort: ComfyUI meldet echten
        Fortschritt nur über seinen Websocket, und was hier zählbar ist, ist
        die Zeit.

        Wartet der Auftrag noch hinter anderen, steht das dort statt der Zeit —
        wer eine Warteschlange vor sich hat, wartet auf etwas anderes als auf
        seine eigene Rechnung.

        **Das Zeitlimit gilt dem Hängen, nicht der Langsamkeit.** Es stand auf
        zehn Minuten, gemessen an einer RTX 4080, auf der ein Körper dreizehn
        Sekunden braucht. Auf einer Intel-Arc-Grafik dauerte derselbe Lauf
        länger als das Limit: Solidon gab auf, ComfyUI rechnete weiter, und der
        Kunde hatte zehn Minuten gewartet und nichts. Solange der Auftrag in
        ComfyUIs Warteschlange **läuft**, ist er nicht hängengeblieben — dann
        wird weiter gewartet. Erst wenn er dort verschwindet, ohne ein Ergebnis
        zu hinterlassen, greift die Zeit; und :data:`STUCK_SECONDS` deckelt auch
        das, damit ein ComfyUI, das seine Schlange falsch beantwortet, nicht
        endlos wartet.
        """
        started = time.monotonic()
        while True:
            if cancelled():
                # **Abgebrochen wird das Warten, nicht die fremde Rechnung.**
                # Dasselbe, was der Satz zu :data:`STUCK_SECONDS` sagt: Der
                # Auftrag steht in ComfyUIs Schlange, gehört ihm, und ihn dort
                # zu unterbrechen träfe unter Umständen den Auftrag eines
                # anderen Programms. Was Solidon aufhört, ist das Warten — und
                # das ist genau das, was der Nutzer angeklickt hat.
                _log.info("waiting for %s cancelled", job)
                raise OperationCancelled
            answer = self.transport(f"{self.base}/history/{job}", None, {})
            history = json.loads(answer.decode("utf-8"))
            entry = history.get(job)
            if entry and entry.get("outputs"):
                return dict(entry["outputs"])
            if isinstance(entry, dict):
                _failed(entry)
            waited = time.monotonic() - started
            if waited > self.timeout_seconds and not self._still_working(job):
                raise GenerationFailed(detail=_("Die Erzeugung hat ihr Zeitlimit erreicht."))
            if waited > STUCK_SECONDS:
                raise GenerationFailed(
                    detail=_(
                        "Der Generator rechnet seit einer Stunde an diesem Auftrag. "
                        "Abgebrochen wird er hier, in ComfyUI läuft er "
                        "gegebenenfalls weiter."
                    )
                )
            progress(0.5, self._waiting_text(job, waited))
            time.sleep(self.poll_seconds)

    def _still_working(self, job: str) -> bool:
        """Steht dieser Auftrag in ComfyUIs Warteschlange — laufend oder wartend?

        Ein Fehlschlag heißt hier **False**: Lässt sich die Schlange nicht
        abfragen, ist das kein Beweis für Leben, und das Zeitlimit soll dann
        greifen dürfen.
        """
        try:
            answer = self.transport(f"{self.base}/queue", None, {})
            queue = json.loads(answer.decode("utf-8"))
        except (AppError, OSError, ValueError):
            return False
        for group in ("queue_running", "queue_pending"):
            for entry in queue.get(group) or ():
                if isinstance(entry, list) and job in [str(field) for field in entry]:
                    return True
        return False

    def _waiting_text(self, job: str, seconds: float) -> str:
        ahead = self._ahead_in_queue(job)
        if ahead:
            return f"{_('Wartet auf den Generator')} ({ahead})"
        return f"{_('Modell wird erzeugt')} ({seconds:.0f} s)"

    def _ahead_in_queue(self, job: str) -> int:
        """Wie viele Aufträge vor diesem liegen. Null heißt: er ist an der Reihe.

        Ein Fehlschlag hier ist keiner — die Warteschlange ist eine Zugabe zum
        Text, und ein Lauf soll nicht daran scheitern, dass sie sich nicht
        abfragen ließ.
        """
        try:
            answer = self.transport(f"{self.base}/queue", None, {})
            queue = json.loads(answer.decode("utf-8"))
        except (AppError, OSError, ValueError):
            return 0
        pending = queue.get("queue_pending") or ()
        for index, entry in enumerate(pending):
            if isinstance(entry, list) and job in [str(field) for field in entry]:
                return index + 1
        return 0

    def _download(self, outputs: dict[str, Any]) -> tuple[bytes, str]:
        """Findet das Netz unter den Ausgaben und holt es."""
        for node in outputs.values():
            for key in ("meshes", "3d", "result", "files"):
                for entry in node.get(key, ()) or ():
                    located = _located(entry)
                    if located is None:
                        continue
                    query, suffix = located
                    return self.transport(f"{self.base}/view?{query}", None, {}), suffix
        raise GenerationFailed(detail=_("Der Auftrag hat keine Netzdatei erzeugt."))


# --- Geskriptet, für die Suite ------------------------------------------------------


@dataclass(slots=True)
class ScriptedMeshBackend:
    """Ein Generator, der eine vorbereitete Datei zurückgibt (§35).

    Weg 3 muss ohne Grafikkarte testbar sein, und ein Test, der nur saubere
    Geometrie zu sehen bekäme, bewiese nichts — vorbereitet werden hier also
    die kaputten Körper, die ein Generator wirklich liefert.
    """

    answers: dict[str, bytes] = field(default_factory=dict)
    fallback: bytes | None = None
    suffix: str = ".stl"
    calls: list[tuple[str, int]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "scripted"

    @property
    def available(self) -> bool:
        return bool(self.answers) or self.fallback is not None

    def text_to_mesh(
        self,
        prompt: str,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        self.calls.append((prompt, seed))
        progress(0.5, str(_("Modell wird erzeugt")))
        # Auch der Doppel fragt: Ein Test soll den Abbruchweg fahren können,
        # ohne eine Grafikkarte und ohne eine Sekunde Wartezeit.
        if cancelled is not None and cancelled():
            raise OperationCancelled
        payload = self.answers.get(prompt, self.fallback)
        if payload is None:
            raise GenerationFailed(detail=f"nothing scripted for {prompt!r}")
        return self._as_result(payload, prompt, seed)

    def image_to_mesh(
        self,
        image: bytes,
        *,
        seed: int = 0,
        progress: ProgressFn = _silent,
        cancelled: CancelledFn | None = None,
    ) -> GeneratedMesh:
        self.calls.append((f"<image {len(image)}>", seed))
        if cancelled is not None and cancelled():
            raise OperationCancelled
        if self.fallback is None:
            raise GenerationFailed(detail="nothing scripted for an image")
        return self._as_result(self.fallback, "", seed)

    def _as_result(self, payload: bytes, prompt: str, seed: int) -> GeneratedMesh:
        return GeneratedMesh(
            mesh=read_mesh(payload, self.suffix),
            payload=payload,
            suffix=self.suffix,
            backend=self.id,
            prompt=prompt,
            seed=seed,
        )


#: Endungen, unter denen ein Körper unter den Ausgaben erkannt wird. Ein
#: Auftrag legt neben ihm auch Bilder ab — die gehören nicht uns.
MESH_SUFFIXES = (".glb", ".obj", ".ply", ".stl")


def _located(entry: Any) -> tuple[str, str] | None:
    """Aus einem Ausgabeeintrag die Abfrage für ``/view`` und die Endung.

    Zwei Schreibweisen kommen wirklich vor, und beide müssen ankommen: ein
    Eintrag mit Feldern, wie ihn die Bildknoten liefern, und ein blanker Pfad
    relativ zum Ausgabeordner, wie ihn die 3D-Vorschau zurückgibt. Wer nur die
    erste liest, findet nach einem erfolgreichen Auftrag nichts und meldet, es
    sei kein Modell erzeugt worden.

    ``None`` heißt „nicht unsere Datei" — kein Fehler, der Aufrufer sieht weiter.
    """
    if isinstance(entry, str):
        path = PurePosixPath(entry.replace("\\", "/"))
        name = path.name
        subfolder = "" if str(path.parent) == "." else str(path.parent)
        kind = "output"
    elif isinstance(entry, dict):
        name = str(entry.get("filename", ""))
        subfolder = str(entry.get("subfolder", ""))
        kind = str(entry.get("type", "output"))
    else:
        return None

    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in MESH_SUFFIXES:
        return None
    query = urllib.parse.urlencode({"filename": name, "subfolder": subfolder, "type": kind})
    return query, suffix


def _filled(node: Any, values: dict[str, Any]) -> Any:
    """Setzt die Werte in den Graphen ein und behält ihren Typ.

    Ein Platzhalter, der allein steht, wird zum Wert selbst — ``"{seed}"``
    kommt also als Zahl an: ComfyUI prüft die Typen seiner Eingänge, und ein
    Startwert als Text wird vom Knoten abgelehnt, nicht von uns.
    """
    if isinstance(node, dict):
        return {key: _filled(value, values) for key, value in node.items()}
    if isinstance(node, list):
        return [_filled(entry, values) for entry in node]
    if isinstance(node, str):
        alone = _PLACEHOLDER.fullmatch(node)
        if alone is not None and alone.group(1) in values:
            return values[alone.group(1)]
        return _PLACEHOLDER.sub(lambda found: str(values.get(found.group(1), found.group(0))), node)
    return node
