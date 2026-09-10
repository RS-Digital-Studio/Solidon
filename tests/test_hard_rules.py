"""Zusagen, die auf jeder Plattform gelten — auch dort, wo der Code nicht läuft.

Ein Zweig hinter ``if sys.platform == "darwin"`` ist auf zwei von drei
Maschinen toter Code. Weder ein Testlauf noch mypy sieht ihn dort; gefunden
wird er von der CI, nach fünfundzwanzig Minuten, und dann liegt der Tag still.
Was hier steht, prüft solche Zweige am **Quelltext** und läuft deshalb überall.

Dazu kommen Zusagen, die gar nicht an einer Plattform hängen, sondern am
Quelltext selbst — dass eine Frage nur an einer Stelle gestellt wird, dass
ein Netzaufruf seine Kopfzeilen unter die Gesamtfrist stellt. Auch sie sind
hier richtig: Es sind harte Regeln, die kein einzelner Testlauf zeigt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import app

PACKAGE_DIR = Path(app.__file__).parent
TOOLS_DIR = PACKAGE_DIR.parent / "tools"

#: Was Pythons ``fcntl`` als Bytes-Argument höchstens annimmt.
#:
#: Die Zahl steht in CPython als ``FCNTL_BUFSZ`` (``Modules/fcntlmodule.c``)
#: und ist eine harte Grenze: Ein längeres Argument endet in
#: ``ValueError: fcntl string arg too long``, **bevor** der Systemaufruf läuft.
#:
#: Sie ist zugleich genau die Größe, die Darwins ``F_GETPATH`` verlangt —
#: ``MAXPATHLEN`` ist dort ``PATH_MAX`` und damit dieselben 1024. Der Puffer
#: ist also nicht knapp bemessen, sondern richtig; wer ihn
#: „sicherheitshalber" vergrößert, bricht den Aufruf.
FCNTL_MAX_ARGUMENT = 1024


def source_files() -> list[Path]:
    """Jede Quelldatei, die ausgeliefert wird oder das Paket baut."""
    found = [
        path
        for folder in (PACKAGE_DIR, TOOLS_DIR)
        for path in sorted(folder.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    assert len(found) > 100, f"nur {len(found)} Quelldateien gefunden — die Suche greift nicht"
    return found


def _byte_length(node: ast.expr) -> int | None:
    """Wie viele Bytes dieser Ausdruck ergibt — oder ``None``, wenn unklar.

    **Ohne ``ast.literal_eval``, und das ist der Punkt.** Die erste Fassung
    dieses Wächters benutzte ihn und fand **nichts**: ``literal_eval`` wertet
    nur Literale aus, und ``b"\\0" * 4096`` ist ein ``BinOp``. Der Ausdruck,
    um den es hier geht, ist also genau der, den er nicht kennt — der Wächter
    war grün, und der Fehler wäre ein zweites Mal in die CI gelaufen.
    Aufgefallen ist das an der Gegenprobe, nicht am Lesen.

    Erkannt werden deshalb die drei Schreibweisen, die im Bestand vorkommen
    können: das nackte Bytes-Literal, ``b"…" * n`` in beiden Reihenfolgen und
    ``bytes(n)``. Was eine Variable enthält, bleibt unsichtbar; das ist die
    zugestandene Grenze einer Quelltextprüfung und steht als Fall in
    :func:`test_the_guard_finds_a_buffer_it_is_given`.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
        return len(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        left, right = node.left, node.right
        for text, count in ((left, right), (right, left)):
            if (
                isinstance(text, ast.Constant)
                and isinstance(text.value, bytes)
                and isinstance(count, ast.Constant)
                and isinstance(count.value, int)
            ):
                return len(text.value) * count.value
        return None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "bytes"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, int)
    ):
        return node.args[0].value
    return None


def oversized_fcntl_buffers(tree: ast.AST) -> list[tuple[int, int]]:
    """Jeder ``fcntl``-Aufruf mit einem zu langen Bytes-Argument: Zeile und Länge.

    Gesucht wird am Aufruf und nicht an einer Dateiliste: Ein Wächter, der
    zwei bekannte Stellen führt, verpasst die dritte. Erkannt wird jedes
    ``fcntl(...)`` — ob als ``fcntl.fcntl``, als ``module.fcntl`` aus einem
    verzögerten Import oder blank —, dessen drittes Argument sich im
    Quelltext auf eine Bytezahl bringen lässt.
    """
    found: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 3:
            continue
        name = (
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        )
        if name != "fcntl":
            continue
        length = _byte_length(node.args[2])
        if length is not None and length > FCNTL_MAX_ARGUMENT:
            found.append((node.lineno, length))
    return found


@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_no_fcntl_call_hands_over_more_than_python_takes(path: Path) -> None:
    """Ein zu großer Puffer bricht auf dem Mac und ist sonst unsichtbar.

    Am 02.09.2026 stand in ``scene/project.py`` und in ``updates.py``
    ``fcntl(fd, F_GETPATH, b"\\0" * 4096)``. Auf Windows und Linux läuft die
    Zeile nie, mypy hat nichts zu beanstanden, die Suite ist grün — und der
    Tag-Lauf meldete dreiundzwanzig rote Tests mit derselben Zeile
    ``ValueError: fcntl string arg too long``. Fünfundzwanzig Minuten für
    einen Zahlendreher, und der Tag stand still.

    **Gegenprobe gefahren**, damit diese Zusage nicht nur so aussieht:
    Derselbe Quelltext mit ``4096`` statt ``1024`` — im Speicher mutiert,
    ohne die Datei anzufassen — gibt in beiden Dateien einen Treffer
    (``project.py:391 -> 4096``, ``updates.py:939 -> 4096``); unverändert
    findet der Lauf über alle 297 Quelldateien keinen. Die erste Fassung
    dieses Wächters bestand dieselbe Probe **nicht** — warum, steht in
    :func:`_byte_length`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    oversized = oversized_fcntl_buffers(tree)

    assert not oversized, "\n".join(
        f"{path.name}:{line} übergibt {length} Byte an fcntl — höchstens "
        f"{FCNTL_MAX_ARGUMENT} sind erlaubt (CPython FCNTL_BUFSZ), und genau so viele "
        "verlangt Darwins F_GETPATH."
        for line, length in oversized
    )


@pytest.mark.parametrize(
    ("quelle", "erwartet"),
    (
        ('fcntl.fcntl(3, 50, b"x" * 4096)\n', [(1, 4096)]),
        ('fcntl.fcntl(3, 50, b"x" * 1024)\n', []),
        ("module.fcntl(descriptor, 50, bytes(2048))\n", [(1, 2048)]),
        ('fcntl(3, 50, b"x" * 1025)\n', [(1, 1025)]),
        ('fcntl.fcntl(3, 50, 4096 * b"x")\n', [(1, 4096)]),
        ("fcntl.flock(3, 2)\n", []),
        ('size = 4096\nfcntl.fcntl(3, 50, b"x" * size)\n', []),
    ),
    ids=(
        "zu_gross",
        "genau_richtig",
        "ueber_modul_mit_bytes",
        "eins_zu_viel",
        "andere_reihenfolge",
        "flock",
        "zur_laufzeit_unsichtbar",
    ),
)
def test_the_guard_finds_a_buffer_it_is_given(quelle: str, erwartet: list[tuple[int, int]]) -> None:
    """Der Prüfer bekommt Fälle, deren Ausgang feststeht.

    Ein Wächter, der über den Bestand läuft und nichts findet, ist von einem
    kaputten nicht zu unterscheiden — solange niemand ihm einen Fall vorlegt,
    den er finden **muss**. Genau daran ist die erste Fassung gescheitert.

    Der letzte Fall ist die zugegebene Grenze: Eine Länge, die erst zur
    Laufzeit entsteht, sieht eine Quelltextprüfung nicht. Er steht hier, damit
    niemand die Zusage für größer hält, als sie ist.
    """
    assert oversized_fcntl_buffers(ast.parse(quelle)) == erwartet


# --- Nutzerverzeichnisse: drei Plattformen, eine Maschine ----------------------


@pytest.mark.parametrize(
    ("funktion", "mac_ende", "windows_variable", "linux_variable", "linux_rueckfall"),
    (
        (
            "user_data_dir",
            ("Library", "Application Support"),
            "LOCALAPPDATA",
            "XDG_DATA_HOME",
            (".local", "share"),
        ),
        ("user_config_dir", ("Library", "Preferences"), "APPDATA", "XDG_CONFIG_HOME", (".config",)),
        ("user_cache_dir", ("Library", "Caches"), "LOCALAPPDATA", "XDG_CACHE_HOME", (".cache",)),
    ),
    ids=("data", "config", "cache"),
)
def test_every_user_directory_lands_where_its_platform_expects_it(
    monkeypatch: pytest.MonkeyPatch,
    funktion: str,
    mac_ende: tuple[str, ...],
    windows_variable: str,
    linux_variable: str,
    linux_rueckfall: tuple[str, ...],
) -> None:
    """Wo Lizenz, Zertifikat, Profile und Cache liegen — auf **allen** drei Systemen.

    Diese vier Funktionen entscheiden, wo ``licence.key`` und
    ``activation.certificate`` liegen. Eine falsche Zeile im macOS-Zweig nähme
    einem Mac-Kunden nach dem Update seine Freischaltung — und bis zum
    03.09.2026 hätte das **keine Prüfung gemerkt**: Die Tests, die ``paths``
    nennen, ersetzen die Funktionen per monkeypatch, statt ihre Zweige zu
    betreten, und die drei Stellen, die ``sys.platform`` auf „darwin" setzen,
    liegen in ``test_discover``, ``test_install`` und ``test_updates``. Ein
    Zweig, den nur ein Mac sehen kann, wird nirgends geprüft (``kern.md``).

    Geprüft wird die **Form**, nicht der absolute Pfad: ``Path.home()`` liest
    auf Windows ``USERPROFILE`` und auf POSIX ``HOME``, und ``conftest`` biegt
    nur das zweite um (§38). Was hier zählt, ist, dass jeder Zweig unter der
    richtigen Wurzel im richtigen Ordner endet.
    """
    from app.branding import APP_NAME, APP_VENDOR
    from app.core import paths

    ziel = getattr(paths, funktion)

    monkeypatch.setattr(paths.sys, "platform", "darwin")
    mac = ziel()
    assert mac.parts[-1] == APP_NAME, f"{funktion} auf macOS endet nicht auf {APP_NAME}: {mac}"
    assert mac.parts[-len(mac_ende) - 1 : -1] == mac_ende, (
        f"{funktion} auf macOS liegt in {mac.parts[-3:-1]} statt in {mac_ende} — "
        "Apples Konvention ist ~/Library/<Bereich>/<Anwendung>"
    )
    assert Path.home() in mac.parents, f"{funktion} auf macOS liegt außerhalb von ~: {mac}"

    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv(windows_variable, str(Path("D:/AppDaten")))
    windows = ziel()
    assert windows.parts[:2] == Path("D:/AppDaten").parts, (
        f"{funktion} auf Windows liest {windows_variable} nicht: {windows}"
    )
    assert APP_VENDOR in windows.parts and APP_NAME in windows.parts, (
        f"{funktion} auf Windows liegt nicht unter {APP_VENDOR}/{APP_NAME}: {windows}"
    )

    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv(linux_variable, str(Path("/xdg-ziel")))
    linux = ziel()
    assert linux.parts[-1] == APP_NAME and "xdg-ziel" in linux.parts, (
        f"{funktion} auf Linux liest {linux_variable} nicht: {linux}"
    )

    monkeypatch.delenv(linux_variable, raising=False)
    ohne_variable = ziel()
    assert ohne_variable.parts[-len(linux_rueckfall) - 1 : -1] == linux_rueckfall, (
        f"{funktion} fällt ohne {linux_variable} nicht auf ~/{'/'.join(linux_rueckfall)} "
        f"zurück, sondern auf {ohne_variable}"
    )


def test_the_log_directory_follows_the_same_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """``user_log_dir`` hat nur zwei Zweige — und beide waren ungeprüft.

    Auf dem Mac gehört das Protokoll nach ``~/Library/Logs``; überall sonst
    liegt es neben den übrigen Daten. Das Protokoll verlässt den Rechner nie
    von selbst (§33.2), aber ein Fehler hier legte es an eine Stelle, an der
    der Kunde es im Fehlerbericht nicht findet.
    """
    from app.branding import APP_NAME
    from app.core import paths

    monkeypatch.setattr(paths.sys, "platform", "darwin")
    mac = paths.user_log_dir()
    assert mac.parts[-2:] == ("Logs", APP_NAME), f"macOS-Protokoll liegt in {mac}"
    assert Path.home() in mac.parents

    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(Path("/xdg-daten")))
    linux = paths.user_log_dir()
    assert linux.parts[-1] == "logs" and "xdg-daten" in linux.parts, (
        f"Linux-Protokoll liegt nicht unter den Nutzerdaten: {linux}"
    )


def test_the_install_roots_are_named_for_every_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wo Solidon nach fremden Programmen sucht, die nicht im PATH stehen.

    Der darwin-Zweig war ungeprüft, und er ist der Grund, warum ein Slicer aus
    einem Homebrew-Cask überhaupt gefunden wird (``/Applications``).
    """
    from app.core import discover

    monkeypatch.setattr(discover.sys, "platform", "darwin")
    mac = discover._install_roots()
    assert Path("/Applications") in mac, f"macOS sucht nicht in /Applications: {mac}"

    monkeypatch.setattr(discover.sys, "platform", "linux")
    linux = discover._install_roots()
    assert Path("/opt") in linux and Path("/usr/local") in linux, (
        f"Linux sucht nicht in /opt und /usr/local: {linux}"
    )


#: Was gesetzt wird, und womit es wieder abgeräumt wird.
#:
#: Beides sind Zustände der **Anwendung**, nicht eines Objekts: Ein blockiertes
#: Widget schweigt weiter, ein aufgesetzter Wartecursor bleibt über dem ganzen
#: Programm stehen. Wer sie setzt und auf einem Weg nicht zurücknimmt,
#: hinterlässt eine Oberfläche, die aussieht, als arbeite sie, und nichts tut.
RESTORED_STATES: dict[str, str] = {
    "blockSignals": "blockSignals",
    "setOverrideCursor": "restoreOverrideCursor",
}


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    """Für jeden Knoten seinen Elternknoten — der AST trägt ihn nicht selbst."""
    found: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            found[id(child)] = node
    return found


def _restores(block: list[ast.stmt], restore: str) -> bool:
    """Räumt einer dieser Zweige ``restore`` ab?"""
    return any(
        isinstance(inner, ast.Call) and _name_of(inner) == restore
        for statement in block
        for inner in ast.walk(statement)
    )


def _guarded(call: ast.Call, parents: dict[int, ast.AST], restore: str) -> bool:
    """Nimmt ein ``finally`` oder ein ``with`` diesen Aufruf zurück?

    Zwei Formen zählen, und die zweite hat diesen Wächter beim ersten Lauf
    viermal falsch anschlagen lassen:

    * **Innen:** Der Aufruf steht unter einem ``try``, dessen ``finally``
      abräumt — oder unter einem ``with``, das beim Verlassen selbst abräumt.
    * **Davor:** Der Aufruf steht **vor** einem ``try``, dessen ``finally``
      abräumt. Das ist nicht die schlechtere Form, sondern die richtigere:
      Wirft das Setzen selbst, darf das ``finally`` gerade **nicht** laufen —
      es gäbe nichts zurückzunehmen, und ``restoreOverrideCursor`` nähme dem
      Aufrufer darunter seinen Cursor weg.

    Ein Wächter, der nur nach oben sieht, hält alle vier Cursor-Stellen des
    Bestands für Fehler. Vier Fälle mit bekanntem Ausgang haben ihn widerlegt,
    bevor er jemanden in die Irre schicken konnte.
    """
    node: ast.AST | None = call
    while node is not None:
        if isinstance(node, ast.Try) and _restores(node.finalbody, restore):
            return True
        if isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    return True
        parent = parents.get(id(node))
        # Der Aufruf als Geschwister: Steht danach im selben Block ein ``try``,
        # dessen ``finally`` abräumt?
        for branch in ("body", "orelse", "finalbody"):
            block = getattr(parent, branch, None)
            if not isinstance(block, list) or node not in block:
                continue
            later = block[block.index(node) + 1 :]
            if any(isinstance(one, ast.Try) and _restores(one.finalbody, restore) for one in later):
                return True
        node = parent
    return False


def _name_of(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def test_a_state_that_is_set_is_taken_back_on_every_path() -> None:
    """Wer einen Zustand setzt, gibt ihn auf **jedem** Weg wieder frei.

    **Der Fall, der diese Prüfung veranlasst hat.** Am 03.09.2026 standen elf
    Stellen in ``app/ui`` so da: ``blockSignals(True)``, dann Arbeit, dann
    ``blockSignals(False)`` — und dazwischen Wege, auf denen eine Ausnahme das
    Freigeben übersprang. Bei ``header.show_plates`` lagen fünfundzwanzig
    Zeilen dazwischen, darunter ein ``tr()`` mit Platzhalter und ein ``max()``.
    Ein Wähler, der danach stumm bleibt, sieht aus wie einer, der funktioniert:
    Der Nutzer klickt, und nichts geschieht.

    **Die Zahl der Setzungen gegen die Zahl der Rücknahmen zu zählen findet das
    nicht.** ``setOverrideCursor`` führt in Qt einen Stapel, mehrfaches Setzen
    ist erlaubt und häufig richtig — die Differenz ist deshalb kein Befund
    (Hinweis 3d-druck-c7). Was zählt, ist die **Absicherung**: ein ``finally``
    oder ein ``with``, das auch dann greift, wenn dazwischen etwas wirft.

    Erlaubt sind damit zwei Formen, und beide stehen im Bestand:
    ``with QSignalBlocker(widget):`` und ``try: … finally: widget.blockSignals(
    was_blocked)``. Verboten ist die dritte, die nur den Erfolgspfad kennt.
    """
    unguarded: list[str] = []
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _parents(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _name_of(node)
            if name not in RESTORED_STATES:
                continue
            # Nur das Setzen zählt: ``blockSignals(False)`` und
            # ``blockSignals(was_blocked)`` sind die Rücknahme selbst.
            if name == "blockSignals":
                if not node.args:
                    continue
                first = node.args[0]
                if not (isinstance(first, ast.Constant) and first.value is True):
                    continue
            if _guarded(node, parents, RESTORED_STATES[name]):
                continue
            unguarded.append(f"{path.name}:{node.lineno}: {name} ohne finally oder with")

    assert not unguarded, "gesetzt und nicht auf jedem Weg zurückgenommen:\n  " + "\n  ".join(
        unguarded
    )


def _asks_the_system_for_a_handle_path(tree: ast.AST) -> bool:
    """Ob diese Datei das Betriebssystem nach dem Pfad eines offenen Handles fragt.

    Zwei Fragen, eine je Plattformfamilie: ``GetFinalPathNameByHandleW`` unter
    Windows, ``fcntl(fd, 50, …)`` — Darwins ``F_GETPATH`` — darunter. Wer eine
    davon stellt, baut den Weg; wer nur ``/proc/self/fd`` liest, tut etwas
    anderes und wird hier bewusst nicht gezählt (``updates._inherited_descriptor_path``
    gibt den Deskriptorpfad **zur Weitergabe** zurück und löst ihn gerade nicht auf).

    **Gefragt wird am Syntaxbaum und nicht im Text**, und das war eine
    Messung: Die erste Fassung suchte den Windows-Namen als Zeichenkette und
    meldete ``updates.py`` weiterhin — sie hatte den Docstring gelesen, der
    dort seit der Zusammenführung erklärt, was die Datei **nicht** mehr tut.
    Ein Wächter, der Prosa mitzählt, ist im Neubau rot und wird abgeschaltet.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "GetFinalPathNameByHandleW":
            return True
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        if _name_of(node) != "fcntl":
            continue
        second = node.args[1]
        if isinstance(second, ast.Constant) and second.value == 50:
            return True
    return False


def test_the_path_behind_an_open_handle_is_asked_in_exactly_one_place() -> None:
    """Diese Frage steht einmal — sonst altert eine der Antworten.

    Bis zum 10.09.2026 stand sie zweimal: ``scene.project._opened_file_path``
    für verknüpfte Quellen, ``updates._descriptor_path`` für den Deskriptor,
    den das Update an den Installer weiterreicht. Beide fragen aus einem
    Sicherheitsgrund, beide waren „dieselbe Frage in derselben Reihenfolge" —
    der Kommentar in ``updates`` sagte das ausdrücklich. Gleich waren sie
    trotzdem nicht.

    **Was der älteren fehlte**, und es war die einzige Abweichung mit Folgen:
    Unter Windows nennt ``GetFinalPathNameByHandleW`` beim zweiten Aufruf
    entweder die geschriebene Länge oder — wenn der Puffer nicht reicht — die
    benötigte. Wächst der Pfad zwischen den beiden Aufrufen, etwa weil jemand
    einen Ordner darüber umbenennt, kommt der zweite Fall. ``project`` prüfte
    ``written >= len(buffer)`` und hielt an; ``updates`` prüfte nur gegen Null
    und rechnete mit einer abgeschnittenen Zeichenkette weiter — als Antwort
    auf eine Sicherheitsfrage.

    Der Wächter zählt Dateien und nicht Zeilen, weil eine dritte Kopie genauso
    entstünde wie die zweite: nicht durch Ändern der ersten, sondern daneben.
    Gegenprobe gefahren: Vor der Zusammenführung nennt derselbe Lauf zwei
    Dateien (``scene/project.py`` und ``updates.py``), danach eine.
    """
    asking = [
        path
        for path in source_files()
        if _asks_the_system_for_a_handle_path(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        )
    ]

    assert [path.name for path in asking] == ["paths.py"], (
        "Der Pfad hinter einem offenen Handle wird an mehr als einer Stelle ermittelt:\n  "
        + "\n  ".join(str(path) for path in asking)
        + "\nEine gemeinsame Fassung steht in app/core/paths.opened_path."
    )


def _opens_with_a_timeout(node: ast.AST) -> bool:
    """Ein Netzaufruf über urllib — ``…​.open(…, timeout=…)`` oder ``urlopen(…)``.

    **Beide Schreibweisen**, und die zweite hat gefehlt: Der erste Anlauf
    fragte nur nach ``.open`` und übersah damit drei ``urlopen``-Aufrufe in
    ``tools/measure_local_model.py``, die genau denselben Fehler trugen.
    Ein Wächter, der die naheliegendste Schreibweise nicht kennt, prüft die
    Gewohnheit und nicht die Zusage.
    """
    if not isinstance(node, ast.Call):
        return False
    if _name_of(node) not in {"open", "urlopen"}:
        return False
    return any(keyword.arg == "timeout" for keyword in node.keywords)


def unfristed_network_calls(tree: ast.AST) -> list[int]:
    """Netzaufrufe, in deren Funktion keine Kopfzeilenfrist gesetzt wird."""
    found: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        calls = [inner for inner in ast.walk(node) if _opens_with_a_timeout(inner)]
        if not calls:
            continue
        fristed = any(
            isinstance(inner, ast.Call) and _name_of(inner) == "apply_header_deadline"
            for inner in ast.walk(node)
        )
        if not fristed:
            found.extend(call.lineno for call in calls)
    return sorted(found)


def test_every_network_call_puts_its_headers_under_a_deadline() -> None:
    """``timeout`` ist ein Zeitlimit je Leseoperation, keine Gesamtfrist.

    Ein Gegenüber, das seine Kopfzeilen byteweise mit Pausen unterhalb des
    Zeitlimits schickt, hält die Verbindung beliebig lange offen, ohne es je zu
    verletzen. Gemessen am 10.09.2026: Statuszeile und Kopfzeilen brauchten
    eine volle Sekunde, das Zeitlimit stand auf fünfzig Millisekunden, und die
    Antwort kam mit 200 zurück (``test_http_security.py::
    test_an_opener_puts_its_headers_under_the_same_deadline``).

    **Der Wächter steht hier, weil zehn solche Stellen über Monate entstanden
    sind** — drei im Sprachbackend, eine im Mesh-Backend, dazu Support,
    Update, Aktivierung und drei Werkzeuge. Keine davon war falsch geschrieben;
    jede hat nur eine Zusage nicht mitgenommen, die es an einer anderen Stelle
    schon gab. Die elfte entstünde genauso.

    Gefragt wird je Funktion und nicht je Datei: Wer ein
    ``…​.open(request, timeout=…)`` schreibt, ruft in derselben Funktion
    ``apply_header_deadline``. ``http.open_public_url`` kommt hier nicht vor —
    es baut seine Verbindung selbst und setzt die Antwortklasse direkt.

    **Gemessene Gegenprobe:** Derselbe Lauf über ``HEAD`` nennt zehn Stellen,
    über den Arbeitsbaum keine. Die Zusicherung auf die Grundmenge darunter
    steht, weil ein Verbotstest über eine leere Menge immer grün ist: Griffe
    das Muster nicht mehr, meldete dieser Test „alles in Ordnung", ohne eine
    einzige Zeile geprüft zu haben.
    """
    offenders: list[str] = []
    calls = 0
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls += sum(1 for node in ast.walk(tree) if _opens_with_a_timeout(node))
        offenders.extend(f"{path.name}:{line}" for line in unfristed_network_calls(tree))

    assert calls >= 13, f"nur {calls} Netzaufrufe gefunden — das Muster greift nicht mehr"
    assert not offenders, (
        "Netzaufruf ohne Frist über Statuszeile und Kopfzeilen:\n  "
        + "\n  ".join(offenders)
        + "\n`timeout` gilt je Leseoperation; die Gesamtfrist setzt "
        "app.core.http.apply_header_deadline."
    )
