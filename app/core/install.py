"""Fehlendes installieren, aus der Anwendung heraus (Bauplan §36, §38).

Solidon kommt ohne Slicer und ohne B-Rep-Kern — beim ersten aus
Lizenzgründen, beim zweiten wegen der Größe (§36). Das ist eine gute
Entscheidung und eine schlechte Erfahrung: wer eine Verrundung will, soll kein
README lesen müssen, um herauszufinden, welches Paket zu installieren ist.

Also zählt dieses Modul auf, was fehlt, und installiert es — unter drei
Regeln, die nicht verhandelbar sind:

* **Die Namen sind Konstanten in dieser Datei.** Nichts, was aus einem Modell,
  einer Projektdatei oder einer Webseite ankommt, wird je an einen Installer
  übergeben.
* **Nur offizielle Quellen.** Python-Pakete aus dem Index, für den der
  Interpreter ohnehin eingerichtet ist, Programme über die Paketverwaltung des
  Systems. Solidon lädt keine eigenen Installer herunter.
* **Nie ungefragt.** Die Liste wird gezeigt, den Knopf drückt ein Mensch. Eine
  Anwendung, die Software installiert, weil sie glaubt, sie zu brauchen, hat
  eine Entscheidung getroffen, die nicht ihre war.

**Drei Paketverwaltungen, eine je System.** Bis hierhin war es eine: ``winget``.
Auf macOS und Linux — für die dieselbe CI Pakete baut — bekam jedes der vier
Programme denselben Satz, „Auf diesem System ist keine Paketverwaltung gefunden
worden", und damit war der ganze Weg dort eine Sackgasse. Dazugekommen sind
Homebrew und Flatpak, und die Auswahl steht in :data:`MANAGERS`.

Eine Bedingung schließt zwei naheliegende Kandidaten aus: **kein ``sudo``.**
``apt`` und ``dnf`` verlangen Rechte, die eine Passwortabfrage in einem
Unterprozess bräuchten, den niemand sieht — der Aufruf hinge, bis das Zeitmaß
abläuft. Flatpak installiert mit ``--user`` ins Heimatverzeichnis und braucht
keine, Homebrew arbeitet ohnehin ohne.

Wo eine Installation unmöglich ist — eine paketierte Anwendung hat kein pip,
ein System keine der drei Verwaltungen, ein Programm keine Kennung darin — ist
die Antwort der Befehl zum Kopieren, die Download-Seite und ein Satz, der sagt
warum. Kein stilles Scheitern.
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, Final, Literal

from app.core import discover, tools
from app.core.log import get_logger
from app.i18n import TranslatableText, _, tr

_log = get_logger(__name__)

Kind = Literal["package", "program"]

#: Wie lange eine Installation dauern darf, bevor sie aufgegeben wird.
#: Paketverwaltungen laden herunter; eine Minute reicht nicht, und eine
#: Stunde hilft niemandem.
TIMEOUT_SECONDS = 900.0

ProgressFn = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class Manager:
    """Eine Paketverwaltung, die diese Anwendung ansteuern darf.

    ``before`` und ``after`` umschließen die Kennung: winget will sie hinter
    ``--id`` und danach drei Zusagen, Flatpak will eine Referenzdatei und
    sonst nichts. Der Befehl entsteht daraus und aus der Kennung des
    Requirements — aus nichts anderem.
    """

    id: str
    program: str
    before: tuple[str, ...]
    after: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()

    def command(self, identifier: tuple[str, ...]) -> list[str]:
        """Die Befehlszeile für diese Kennung.

        **Der Paketmanager liegt auf dem Rechner, nie im Sandkasten.** In
        einem Flatpak findet ``shutil.which("flatpak")`` nichts — dort gibt es
        keinen —, und ohne ``on_host`` fiele die ganze Installationsspalte
        weg: Auf Windows (winget) und macOS (brew) bietet Solidon an,
        Fehlendes nachzuinstallieren, auf Linux nicht.

        Im Flatpak bleibt der blanke Name stehen: ``which`` kann ihn hier
        nicht auflösen, und ``flatpak-spawn --host`` löst ihn draußen selbst
        auf.
        """
        found = shutil.which(self.program) or self.program
        return discover.on_host([found, *self.before, *identifier, *self.after])


#: Die Kennung wird zur Adresse einer Referenzdatei. Ohne sie bräuchte Flatpak
#: eine eingerichtete Flathub-Quelle — und wer die nicht hat, sähe „remote
#: flathub not found" statt einer Installation. Die Datei bringt Quelle und
#: Laufzeitquelle mit, also gibt es diesen Vorschritt nicht mehr.
FLATHUB_REFERENCE: Final = "https://dl.flathub.org/repo/appstream/{id}.flatpakref"

#: Was auf welchem System ansteuerbar ist. Reihenfolge = Vorrang; gewählt wird
#: die erste, deren Programm auf diesem Rechner liegt.
MANAGERS: Final[tuple[Manager, ...]] = (
    Manager(
        id="winget",
        program="winget",
        before=("install", "--exact", "--id"),
        after=(
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--disable-interactivity",
        ),
        platforms=("win32",),
    ),
    Manager(
        id="brew",
        program="brew",
        before=("install",),
        platforms=("darwin",),
    ),
    Manager(
        # ``--user`` ist der Grund, warum Flatpak hier steht und ``apt`` nicht:
        # es installiert ins Heimatverzeichnis und fragt nach keinem Passwort.
        id="flatpak",
        program="flatpak",
        before=("install", "--user", "--assumeyes"),
        platforms=("linux",),
    ),
)


def for_platform() -> Manager | None:
    """Die Verwaltung, die zu diesem System gehört — ob sie daliegt oder nicht.

    Der Unterschied zu :func:`manager` ist der ganze Punkt: „nicht
    eingerichtet" und „kennt dieses Programm nicht" sind zwei verschiedene
    Auskünfte, und wer sie zusammenwirft, sagt einem Mac-Nutzer, ihm fehle
    Homebrew — für ComfyUI, das dort auch mit Homebrew nicht liegt.
    """
    return next(
        (
            entry
            for entry in MANAGERS
            if any(sys.platform.startswith(name) for name in entry.platforms)
        ),
        None,
    )


def manager() -> Manager | None:
    """Die Paketverwaltung dieses Rechners, wenn eine da ist.

    Ein Linux ohne Flatpak ist kein Sonderfall, sondern der Normalfall auf
    einer schlanken Installation.
    """
    found = for_platform()
    return found if found is not None and shutil.which(found.program) else None


def _silent(line: str) -> None:
    del line


@dataclass(frozen=True, slots=True)
class Requirement:
    """Eine Sache, die Solidon benutzen kann, und wie sie auf den Rechner kommt."""

    id: str
    title: TranslatableText | str
    what_for: TranslatableText | str
    kind: Kind
    package: str = ""
    """Distributionsname für pip. Nur bei Paketen."""
    winget: str = ""
    """Kennung in der Windows-Paketverwaltung."""
    brew: tuple[str, ...] = ()
    """Was hinter ``brew install`` steht — bei einer Anwendung mit ``--cask``."""
    flatpak: str = ""
    """Anwendungskennung auf Flathub."""
    module: str = ""
    """Was importiert wird, um festzustellen, ob es da ist. Nur bei Paketen."""
    url: str = ""
    """Die offizielle Seite, für wenn Installieren von hier nicht geht."""
    follow_up: str = ""
    """Was nach der Installation noch nötig ist — als Kennung einer Handlung,
    die die Oberfläche kennt. Leer heißt: installiert ist fertig.

    **Der Schritt, den es nicht gab.** Ollama installiert bringt kein Modell
    mit und läuft nicht zwangsläufig; ComfyUI installiert kennt die Knoten
    nicht und hat das Modell nicht. Beides stand in Sätzen mit einem Befehl
    darin, und einer dieser Befehle zeigte auf eine Datei, die im Paket nicht
    existiert. Ein zweiter Schritt ist damit kein Sonderfall der Oberfläche,
    sondern eine Eigenschaft der Sache — und steht hier."""
    follow_up_title: TranslatableText | str = ""
    """Was auf dem Knopf für diesen zweiten Schritt steht."""

    def identifier(self, chosen: Manager) -> tuple[str, ...]:
        """Wie dieses Programm in dieser Paketverwaltung heißt, oder nichts.

        Leer heißt: von Hand. Nicht jedes Programm liegt in jeder Verwaltung —
        Ollama hat kein Flathub-Paket, ComfyUI liegt in keiner der drei.
        """
        if chosen.id == "winget":
            return (self.winget,) if self.winget else ()
        if chosen.id == "brew":
            return self.brew
        if chosen.id == "flatpak":
            return (FLATHUB_REFERENCE.format(id=self.flatpak),) if self.flatpak else ()
        return ()

    def by_hand(self) -> str:
        """Der Befehl zum Abschreiben, wenn Solidon ihn nicht selbst ausführt.

        Er entsteht aus denselben Konstanten wie der ausgeführte, und er steht
        da, weil „auf diesem System geht es nicht" niemandem weiterhilft: Wer
        Homebrew nachinstalliert, soll die Zeile schon gelesen haben.
        """
        chosen = for_platform()
        if chosen is None:
            return ""
        wanted = self.identifier(chosen)
        return " ".join((chosen.program, *chosen.before, *wanted, *chosen.after)) if wanted else ""


#: Alles, was die Anwendung installieren kann. Die Namen stehen mit Absicht
#: fest hier — siehe Modul-Docstring.
REQUIREMENTS: Final[tuple[Requirement, ...]] = (
    Requirement(
        id="brep",
        title="OpenCASCADE",
        what_for=_("Bearbeitbare Kanten für Fasen, Verrundungen und STEP."),
        kind="package",
        package="cadquery-ocp-novtk",
        module="OCP.BRepPrimAPI",
        url="https://github.com/CadQuery/OCP",
    ),
    Requirement(
        id="vhacd",
        title="V-HACD",
        what_for=_("Hinweis, wo ein Körper von selbst auseinanderfällt."),
        kind="package",
        package="vhacdx",
        module="vhacdx",
        url="https://github.com/trimesh/vhacdx",
    ),
    Requirement(
        id="keyring",
        title=_("Schlüsselbund"),
        what_for=_(
            "Legt die Geräteidentität der Lizenz und den Schlüssel für den Chat im System ab."
        ),
        kind="package",
        package="keyring",
        module="keyring",
        url="https://github.com/jaraco/keyring",
    ),
    Requirement(
        id="slicer",
        # Nicht „OrcaSlicer": erkannt wird jeder der üblichen Slicer, und wer
        # ElegooSlicer oder PrusaSlicer benutzt, soll hier nicht lesen, ihm
        # fehle ein Programm. Installiert wird OrcaSlicer, weil eine Vorgabe
        # sein muss — dranstehen tut das am Knopf.
        title=_("Slicer"),
        what_for=_("Für die Druckdatei und die Gegenprobe aus dem G-Code."),
        kind="program",
        winget="SoftFever.OrcaSlicer",
        brew=("--cask", "orcaslicer"),
        # Auf Flathub liegt es unter der eigenen Domain, nicht unter der des
        # ursprünglichen Urhebers — ``io.github.softfever.OrcaSlicer`` gibt es
        # dort nicht, und winget führt die alte Kennung weiter.
        flatpak="com.orcaslicer.OrcaSlicer",
        url="https://orcaslicer.com",
    ),
    Requirement(
        id="ollama",
        title="Ollama",
        what_for=_("Sprachmodell lokal, statt mit eigenem Schlüssel."),
        kind="program",
        winget="Ollama.Ollama",
        # Die Formel und nicht das Cask: Solidon redet über HTTP mit dem
        # Server, und den bringt ``brew install ollama`` mit. Das Cask
        # ``ollama-app`` liefert die Oberfläche dazu, die hier niemand braucht.
        brew=("ollama",),
        # Auf Flathub liegt Ollama nicht — was dort unter ähnlichem Namen
        # steht, sind Klienten dafür. Also bleibt es unter Linux die
        # Herstellerseite, und der Satz daneben sagt das.
        url="https://ollama.com/download",
        # Installiert ist hier erst die Hälfte: Ollama muss laufen und braucht
        # ein Modell. Beides tut der Einrichtungsdialog des Chats.
        follow_up="chat",
        follow_up_title=_("Modell einrichten …"),
    ),
    Requirement(
        id="comfyui",
        title="ComfyUI",
        # ComfyUI allein erzeugt noch nichts: Es braucht die Knoten und das
        # Modell dazu. Dass der zweite Schritt existiert, gehört an die
        # Stelle, an der jemand den ersten tut — sonst installiert er ComfyUI
        # und findet den Menüeintrag weiterhin ausgegraut.
        what_for=_(
            "3D-Modell aus Text oder Bild erzeugen. Solidon richtet danach die "
            "benötigten Zusatzbausteine und das Erzeugungsmodell ein."
        ),
        kind="program",
        url="https://www.comfy.org/download",
        # Und den zweiten Schritt macht Solidon selbst. Der Satz hier nannte
        # bis zu dieser Sitzung „«python tools/setup_comfyui.py»" — einen
        # Befehl, den ein Kunde nicht ausführen kann, weil ``tools/`` im Paket
        # nicht mitreist.
        follow_up="comfyui",
        follow_up_title=_("Knoten und Modell einrichten …"),
    ),
)


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Was passiert ist. ``output`` ist das Ende dessen, was der Installer
    gesagt hat."""

    requirement: Requirement
    installed: bool
    output: str = ""
    reason: TranslatableText | str = ""


def present(requirement: Requirement) -> bool:
    """Ist es schon da?

    Pakete werden importiert, Programme gesucht. Bei einem Dienst zählt hier
    „auf dem Rechner" und nicht „läuft gerade" — sonst böte diese Liste an, ein
    ComfyUI ein zweites Mal zu installieren, das nur nicht gestartet ist.
    """
    if requirement.kind == "package":
        if not requirement.module:
            return False
        try:
            __import__(requirement.module)
        except Exception:  # eine kompilierte Erweiterung scheitert vielfältiger als ImportError
            return False
        return True

    tool = tools.by_id(requirement.id)
    return tools.state_of(tool).installed if tool is not None else False


def location_of(requirement: Requirement) -> str:
    """Wo es liegt oder unter welcher Adresse es erreichbar ist — für die Zeile daneben."""
    tool = tools.by_id(requirement.id)
    if tool is None:
        return ""
    found = tool.path()
    if found is not None:
        return str(found)
    return tool.address()


def missing() -> list[Requirement]:
    """Alles, was auf diesem Rechner fehlt. Fehlen ist normal, kein Fehler."""
    return [entry for entry in REQUIREMENTS if not present(entry)]


def shown() -> tuple[Requirement, ...]:
    """Welche Zeilen jemandem etwas sagen, der diese Anwendung benutzt.

    In der gebauten Anwendung reisen die Python-Pakete mit — OpenCASCADE und
    V-HACD stehen in der Spec, der Schlüsselbund seit dieser Sitzung auch.
    Drei Zeilen „vorhanden", an denen es nichts zu tun gibt, mit einem Knopf,
    der von Entwicklungsumgebungen redet: Das war Rauschen vor den vier
    Zeilen, um die es geht.

    Sie verschwinden nur, solange sie da sind. **Fehlt** eines im Paket, ist
    das eine Auskunft, die jemand braucht — Fasen und STEP fehlen dann still,
    und stille Lücken sind das Gegenteil von §36.
    """
    if not packaged():
        return REQUIREMENTS
    return tuple(entry for entry in REQUIREMENTS if entry.kind != "package" or not present(entry))


@dataclass(frozen=True, slots=True)
class Status:
    """Eine Zeile der Liste, in einem Stück erhoben.

    **Warum das ein eigener Typ ist.** Der Dialog fragte je Zeile dreimal
    dasselbe — ``present``, dann der Fundort, dann die Erklärung —, und jede
    Frage suchte von vorn: Registry, Installationsordner, bei den Diensten
    eine Socket-Probe. Gemessen kostete das Öffnen so 2,97 Sekunden und jede
    Auffrischung weitere 2,10, alles im Oberflächen-Thread. Erhoben wird
    jetzt einmal, und §38 verlangt dafür ohnehin einen Arbeiter.
    """

    requirement: Requirement
    present: bool
    location: str = ""
    installable: bool = False
    reason: TranslatableText | str = ""
    by_hand: str = ""
    running: bool = False
    """Bei einem Dienst: Sein Port antwortet bereits."""
    startable: bool = False
    """Ein lokales Startprogramm liegt da und der Dienst läuft noch nicht."""
    address: str = ""
    """Die derzeit aktive Dienstadresse."""
    remote_address: str = ""
    """Eine gespeicherte Netzadresse, auch wenn gerade lokal gearbeitet wird."""
    using_remote_address: bool = False
    """Die Netzadresse ist aktiv statt der lokalen Vorgabe."""


def status_of(requirement: Requirement) -> Status:
    """Eine Anforderung einmal ansehen — alles, was die Zeile braucht."""
    can = installable(requirement)
    tool = tools.by_id(requirement.id)
    if tool is None:
        here = present(requirement)
        return Status(
            requirement=requirement,
            present=here,
            location=location_of(requirement) if here else _explain(requirement),
            installable=can,
            reason="" if can or here else why_not(requirement),
            by_hand="" if can or here else requirement.by_hand(),
        )

    tool_state = tools.state_of(tool)
    here = tool_state.installed
    address = tool.address()
    if tool_state.path is not None:
        location = str(tool_state.path)
    elif here:
        location = address
    else:
        location = str(tool_state.explain())
    return Status(
        requirement=requirement,
        present=here,
        location=location,
        installable=can,
        reason="" if can or here else why_not(requirement),
        by_hand="" if can or here else requirement.by_hand(),
        running=tool_state.running,
        startable=bool(
            here
            and not tool_state.running
            and tool_state.path is not None
            and tool_state.tool.startable
        ),
        address=address,
        remote_address=tool.remote_address(),
        using_remote_address=tool.using_remote_address,
    )


def _explain(requirement: Requirement) -> str:
    """Der Satz, der neben einem fehlenden Programm steht, statt eines Pfades."""
    tool = tools.by_id(requirement.id)
    return str(tools.state_of(tool).explain()) if tool is not None else ""


def statuses() -> tuple[Status, ...]:
    """Die ganze Liste in einem Durchgang. Gehört in einen Arbeiter (§38)."""
    found = tuple(status_of(entry) for entry in shown())
    _log.info("%d of %d extras present", sum(1 for e in found if e.present), len(found))
    return found


def packaged() -> bool:
    """Ist das die gebaute Anwendung? Dann gibt es kein pip zum Installieren."""
    return bool(getattr(sys, "frozen", False))


def installable(requirement: Requirement) -> bool:
    """Lässt sich das von hier aus überhaupt installieren?"""
    if requirement.kind == "package":
        return bool(requirement.package) and not packaged()
    chosen = manager()
    return chosen is not None and bool(requirement.identifier(chosen))


def why_not(requirement: Requirement) -> TranslatableText | str:
    """Der Satz neben einem Knopf, der sich nicht drücken lässt (§33.1).

    Vier Gründe, und jeder sagt etwas anderes. Bis hierhin sagten drei von
    ihnen dasselbe — „keine Paketverwaltung gefunden" —, und auf macOS und
    Linux stand das an jedem der vier Programme, unabhängig davon, ob eine
    fehlte oder das Programm dort schlicht keine Kennung hat.
    """
    if requirement.kind == "package":
        if not requirement.package:
            return _("Dieses Paket wird von Hand installiert — die Seite steht daneben.")
        return _(
            "Die gebaute Anwendung bringt keine Paketverwaltung mit. "
            "In einer Entwicklungsumgebung ginge es von hier aus."
        )
    # Der Name der Paketverwaltung ist ein Eigenname und steht deshalb neben
    # dem Satz, nicht als Platzhalter darin — dasselbe Vorgehen wie bei den
    # Fehlertexten in ``backends/mesh.py``: einen übersetzten Satz formatiert
    # niemand nach, er wird angezeigt, wie er im Katalog steht.
    wanted = for_platform()
    if wanted is None:
        return _("Für dieses System kennt Solidon keine Paketverwaltung, die das kann.")
    if not requirement.identifier(wanted):
        return (
            f"{tr('In der Paketverwaltung dieses Systems liegt es nicht')}: "
            f"{wanted.program}. "
            f"{tr('Es wird von Hand installiert, und die Seite steht daneben.')}"
        )
    return (
        f"{tr('Dafür braucht Solidon hier eine Paketverwaltung, und sie ist nicht eingerichtet')}: "
        f"{wanted.program}. "
        f"{tr('Die Seite des Herstellers führt die Datei zum Selbstinstallieren.')}"
    )


def install(requirement: Requirement, progress: ProgressFn = _silent) -> InstallResult:
    """Installiert eine Sache. Von einem Knopf aufgerufen, nie von allein
    (siehe oben)."""
    if present(requirement):
        return InstallResult(requirement=requirement, installed=True)
    if not installable(requirement):
        return InstallResult(requirement=requirement, installed=False, reason=why_not(requirement))

    command = _command(requirement)
    _log.info("installing %s", requirement.id)
    progress(" ".join(command))
    try:
        # Der Befehl entsteht aus den Konstanten oben und aus sonst nichts.
        code, output = _stream(command, progress)
    except subprocess.TimeoutExpired as expired:
        # **Die Frist ist etwas anderes als ein Fehlstart.** Sie fällt in die
        # Sammelklausel darunter, denn ``TimeoutExpired`` erbt von
        # ``SubprocessError`` — und dann las jemand nach einer Viertelstunde
        # Wartezeit „Die Paketverwaltung ließ sich nicht starten.". Sie war
        # gestartet, sie lief, und sie ist mitten in der Arbeit abgebrochen
        # worden: Genau das gehört dagestanden, samt der halb fertigen
        # Installation, die dabei zurückbleiben kann (Regel 17, §33.1).
        minutes = int(TIMEOUT_SECONDS // 60)
        _log.warning("install of %s hit the deadline after %s min", requirement.id, minutes)
        # Die Minutenzahl steht **neben** dem Satz und nicht als Platzhalter
        # darin: Ein übersetzter Text wird angezeigt, wie er im Katalog steht,
        # nicht nachformatiert — dieselbe Bauart wie in ``why_not`` darüber.
        what_now = tr(
            "Ein zweiter Versuch nimmt den Rest; sonst führt die Seite des "
            "Herstellers die Datei zum Selbstinstallieren."
        )
        return InstallResult(
            requirement=requirement,
            installed=False,
            output=str(expired),
            reason=(
                f"{tr('Die Paketverwaltung lief noch, als die Zeitgrenze kam')}: "
                f"{minutes} min. "
                f"{tr('Sie ist beendet worden, die Installation kann halb fertig sein.')} "
                f"{what_now}"
            ),
        )
    except (OSError, subprocess.SubprocessError) as problem:
        return InstallResult(
            requirement=requirement,
            installed=False,
            output=str(problem),
            reason=_("Die Paketverwaltung ließ sich nicht starten."),
        )

    if code:
        output = output + chr(10) + f"exit {code}"

    # Die Suche merkt sich, was sie nicht gefunden hat. Nach einer Installation
    # ist diese Antwort veraltet — sonst bliebe das gerade Installierte bis zum
    # nächsten Start unsichtbar. Und die Umgebung dieses Prozesses ist es
    # ebenfalls: das Installationsprogramm hat den PATH des Systems ergänzt,
    # unsere Kopie davon stammt vom Start.
    discover.forget_cache()
    discover.refresh_path()

    done = code == 0 and present(requirement)
    if code == 0 and not done:
        # Der Rest der Fälle: eine Anwendung, die ihren Ordner nirgends anmeldet
        # und außerhalb der bekannten Stellen liegt. Dann hilft der Ort von
        # Hand — und der Knopf dafür steht in derselben Zeile.
        return InstallResult(
            requirement=requirement,
            installed=False,
            output=output[-2000:],
            reason=_(
                "Installiert — gefunden hat Solidon es noch nicht. Nach einem "
                "Neustart ist es meist da; sonst hilft „Ort angeben …“ daneben."
            ),
        )
    _log.info("install of %s finished: %s", requirement.id, done)
    if done:
        return InstallResult(requirement=requirement, installed=True, output=output[-2000:])
    # **Ein Grund, kein Rückgabewert.** Ohne ihn antwortete der Dialog mit
    # „Das hat nicht geklappt." — Regel 17 verlangt, was jetzt möglich ist, und
    # die Zahl dahinter ist die Auskunft, die der Nutzer weitergeben kann. Die
    # rohe Ausgabe bleibt in ``output``, wo sie hingehört: hinter „Details".
    return InstallResult(
        requirement=requirement,
        installed=False,
        output=output[-2000:],
        reason=(
            _(
                "Die Paketverwaltung hat abgebrochen. Was sie gemeldet hat, steht "
                "unter „Details“; die Seite des Herstellers führt die Datei zum "
                "Selbstinstallieren."
            )
            if code
            else _(
                "Der Befehl lief durch, das Programm ist danach trotzdem nicht zu "
                "finden. Ein Neustart von Solidon hilft oft; sonst steht die Datei "
                "zum Selbstinstallieren auf der Seite des Herstellers."
            )
        ),
    )


def _stream(command: list[str], progress: ProgressFn) -> tuple[int, str]:
    """Den Installer laufen lassen und **währenddessen** melden, was er sagt.

        **Vorher kam die Rückmeldung erst am Ende.** ``subprocess.run`` sammelt die
        Ausgabe und gibt sie zurück, wenn der Prozess fertig ist — die
        Fortschrittszeilen wurden also erst dann durchgereicht, wenn niemand sie
        mehr brauchte. Bei OrcaSlicer sind das mehrere Minuten, in denen ein
        unbestimmter Balken lief und sonst nichts geschah.

        Gelesen wird zeilenweise im Textmodus, und das ist hier der Trick: winget
        zeichnet seinen Fortschrittsbalken mit Wagenrücklauf und ohne
        Zeilenumbruch. Der Textmodus übersetzt ``
    `` in ein Zeilenende, also
        kommt jede Aktualisierung als eigene Zeile an — sonst käme bis zum Schluss
        keine.

        ``stderr`` läuft in denselben Strom: Zwei getrennt zu lesen hieße, auf
        einem zu blocken, während der andere vollläuft.

        **Und gewartet wird auf die Uhr, nicht auf die nächste Zeile.** Die
        Frist stand hier im Schleifenkörper — geprüft also erst, wenn eine
        Zeile ankam. Ein stiller Installer hing damit unbegrenzt, und der
        Arbeiter-Thread überlebte sein Fenster (Gesamtreview L-2). Ein
        Leser-Thread reicht die Zeilen durch eine Warteschlange; das Warten
        darauf trägt die Frist.
    """
    lines: list[str] = []
    deadline = time.monotonic() + TIMEOUT_SECONDS
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        feed: queue.Queue[str | None] = queue.Queue()

        def drain(stdout: IO[str] = process.stdout) -> None:
            # Läuft als Daemon: Nach einem Abbruch endet er, sobald das Rohr
            # schließt, und hält sonst nichts am Leben.
            for raw in stdout:
                feed.put(raw)
            feed.put(None)

        threading.Thread(target=drain, daemon=True, name="install-stream").start()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                raise subprocess.TimeoutExpired(command, TIMEOUT_SECONDS)
            try:
                raw = feed.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if raw is None:
                break
            line = raw.strip()
            if line:
                lines.append(line)
                progress(line)
        code = process.wait()
    # Nur das Ende: Eine Paketverwaltung schreibt hunderte Fortschrittszeilen,
    # und was jemand weitergeben will, sind die letzten.
    return code, chr(10).join(lines[-40:])


def _command(requirement: Requirement) -> list[str]:
    """Die genaue Befehlszeile. Gebaut allein aus den Konstanten dieser Datei."""
    if requirement.kind == "package":
        return [sys.executable, "-m", "pip", "install", "--upgrade", requirement.package]
    chosen = manager()
    if chosen is None:
        raise ValueError(f"no package manager for {requirement.id}")
    return chosen.command(requirement.identifier(chosen))
