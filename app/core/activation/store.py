"""Wo der Lizenzschlüssel liegt und wie Demo oder Testlauf gezählt werden (§38).

**Stand dieser Fassung:** Die öffentliche Demo läuft bis einschließlich
30.10.2026. Die Verkaufsversion ab 01.11.2026 wird mit
``DEMO_UNTIL = None`` und ``TRIAL_FROM = None`` gebaut und bietet damit keinen
Testlauf an. Der unten beschriebene Markerpfad bleibt für ein späteres,
ausdrücklich per neuem ``TRIAL_FROM`` freigeschaltetes Angebot erhalten.

**Als Datei, nicht im Schlüsselbund** — anders als der API-Schlüssel des
Nutzers (``backends/keys.py``). Zwei Gründe, und beide wiegen mehr als das
Gefühl, ein Schlüsselbund sei immer sicherer: der Lizenzschlüssel ist nicht
geheim, er ist personalisiert — wer ihn hat, hat auch den Namen darin. Und ein
Schlüsselbund kann gesperrt sein. Dann fragt das Betriebssystem beim Start nach
einem Passwort, und ein Lizenzschlüssel ist der falsche Anlass für diese Frage.

Der Testlaufmarker ist **unterschrieben und liegt doppelt** (Entscheidung
Robert, 26.08.2026 — sie ersetzt die frühere Haltung, die Frist sei nur eine
Erinnerung): Die Testphase ist eine harte Grenze, und was einen weiterbringt,
läuft danach über den Lizenzschlüssel. Drei Bausteine tragen das:

* **Jeder Marker trägt eine Unterschrift** über seine beiden Tage. Ein
  editierter Marker fällt damit auf und beendet die Frist, statt sie zu
  verlängern. Ein Marker **ohne** Unterschrift wird gelesen — er stammt aus
  einer Fassung vor dieser Härtung, und den Bestandskunden trifft keine
  Schuld; verlängern kann er nichts, weil die Zusammenführung darunter das
  frühere Datum gewinnen lässt.
* **Zwei Orte, eine Wahrheit.** Der Marker liegt im Einstellungs- und im
  Datenordner; gelesen wird der frühere erste Start und der spätere gesehene
  Tag aus beiden, geschrieben wird immer an beide. Wer einen löscht, hat den
  anderen noch — und beim nächsten Start beide wieder.
* **Wer beide löscht, beginnt neu.** Das bleibt, und es ist kein Versehen:
  Die Alternative wäre ein Konto oder ein Aktivierungsserver, und §2 sagt zu,
  dass Solidon ohne Netz und ohne Konto läuft. Die Hürde ist bewusst so hoch
  wie das Neuaufsetzen des Profils, nicht höher.

Eine zurückgestellte Systemuhr verlängert trotzdem nichts: gespeichert wird
auch der höchste je gesehene Tag, und die Frist läuft nie rückwärts. Ein Tag
weit jenseits des ersten Starts wird dabei verworfen und nicht festgeschrieben
— sonst nähme ein einziger Start mit falsch gestellter Uhr den Testlauf
dauerhaft weg, auch nachdem die Uhr wieder stimmt. In der Demo ist der Maßstab
dafür :data:`DEMO_UNTIL` und nicht der erste Start: ein gespeicherter Tag
jenseits des Demo-Endes kann keine echte Zeit sein — er wird auf die echte Uhr
zurückgenommen, weil sonst schon der allererste Start mit einer Uhr in der
Zukunft (leere BIOS-Batterie) die Demo dauerhaft beendete.

**Und die beiden Zugeständnisse gelten einzeln, nicht zusammen.** Ist ein
späterer Testlauf ausdrücklich aktiv, fängt er nach dem Löschen beider Marker
neu an — das steht oben und bleibt so. Wer sie löscht *und* die Uhr
zurückstellt, hätte in der Demo damit beides umgangen: Ohne Marker gab es
keinen höchsten Tag, gegen den sich die Uhr messen lassen musste. Dagegen steht
:data:`DEMO_FROM`, der Tag der Auslieferung — vor ihm kann die Demo nicht
gelaufen sein, gleich was die Uhr behauptet.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Final, Literal

from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir, user_data_dir

_log = get_logger(__name__)

#: Wie lange ein später ausdrücklich angebotener Testlauf dauert.
TRIAL_DAYS: Final = 14

#: Frühester Tag eines angebotenen Testlaufs. ``None`` heißt: Diese Fassung
#: bietet keinen Testlauf an. Die Verkaufsversion ab 01.11.2026 startet genau
#: so; ein späteres Angebot braucht einen neuen, bewusst gebauten Release.
TRIAL_FROM: Final[date | None] = None

#: Letzter Tag der öffentlichen Demo — oder ``None`` in der Verkaufsversion.
#: Ob diese dann einen Testlauf anbietet, entscheidet allein ``TRIAL_FROM``;
#: zum Verkaufsstart ist auch dieser Wert ``None``.
#:
#: Ein Stichtag statt einer Frist ab dem ersten Start: die Demo endet für alle
#: am selben Tag, der Tag selbst gehört noch dazu. Der Testlaufmarker verliert
#: damit seine Bedeutung — wer ihn löscht, gewinnt keinen Tag, und wer die Uhr
#: zurückstellt, verschiebt nur sein eigenes Kalenderblatt.
#:
#: Er steht hier und nicht in ``branding.py``, weil dieses Paket seit V4c mit
#: Cython übersetzt ausgeliefert wird: der Stichtag reist in der Erweiterung
#: statt als lesbare Zeile daneben. Öffnen kann er ohnehin nichts, was ein
#: Schlüssel nicht öffnete — er kann nur sperren.
DEMO_UNTIL: Final[date | None] = date(2026, 10, 30)

#: Der Tag, an dem die Demo erschienen ist — die Untergrenze jeder Zählung.
#:
#: Sie schließt die Lücke, die beide Schutze **zusammen** offen ließen: Der
#: Marker fängt die zurückgestellte Uhr, und wer ihn löscht, hat wieder keinen
#: — dann stand in :func:`days_left` der erste gesehene Tag frei zur Wahl, und
#: eine Uhr auf 2020 hieß 2495 Resttage. Der Auslieferungstag kann nicht
#: unterschritten werden, weil es die Demo vorher nicht gab; er reist mit dem
#: Stichtag in derselben übersetzten Erweiterung und ist so wenig zu ändern wie
#: dieser.
DEMO_FROM: Final[date] = date(2026, 8, 20)

#: Dateiname des Schlüssels im Einstellungsordner.
KEY_FILE: Final = "licence.key"

#: Das vom Aktivierungsdienst signierte, an den lokalen Geräteteil gebundene
#: Zertifikat. Es reist nie in einer Projektdatei.
CERTIFICATE_FILE: Final = "activation.certificate"

#: Signierte Geräteabmeldung, deren Serverbestätigung noch aussteht. Sie wird
#: vor dem Entfernen des Zertifikats atomar abgelegt. Ein Verbindungsabbruch
#: kann dadurch niemals die lokale Freischaltung wiederherstellen; derselbe
#: idempotente Auftrag lässt sich stattdessen nach einem Neustart wiederholen.
PENDING_DEACTIVATION_FILE: Final = "deactivation.pending"

#: Dateiname des Testlaufmarkers.
TRIAL_FILE: Final = "trial.json"

#: Der zweite Ort desselben Markers, im Datenordner. Kein Tarnname — Solidon
#: versteckt nichts vor seinen Nutzern; der Ort ist nur ein anderer Baum, damit
#: das Löschen des einen den anderen stehen lässt.
STATE_FILE: Final = "activation.state"

#: Der Schlüssel, mit dem der Marker unterschrieben wird. Er reist im
#: übersetzten Prüfmodul (dieses Paket wird mit Cython gebaut, §36) — wer ihn
#: herausholen kann, kann auch die Datei zweimal löschen, und mehr gewinnt er
#: hier nicht. Die Unterschrift hält den einfachen Fall auf: den Editor.
_MARKER_SECRET: Final = bytes.fromhex(
    "769e4e5415d9bca7294b17a625671d43cafc68a8652ee240409f50f259644244"
)

#: Was :func:`_read_trial` meldet, wenn eine Unterschrift nicht zu ihren Tagen
#: passt: Der Marker wurde angefasst. Ein eigener Wert und kein ``None``, weil
#: die zwei Fälle entgegengesetzt behandelt werden — fehlend heißt frisch,
#: angefasst heißt vorbei.
FORGED: Final = "forged"

#: Ab welchem Abstand zum ersten Start ein gespeicherter Tag keine verstrichene
#: Zeit mehr sein kann, sondern eine falsch gestellte Uhr. Ein Jahr ist
#: großzügig genug, dass ein Nutzer, der Solidon nach Monaten wieder öffnet,
#: den Rückwärtsschutz behält.
CLOCK_HORIZON_DAYS: Final = 365


def key_path() -> Path:
    return user_config_dir() / KEY_FILE


def trial_path() -> Path:
    return user_config_dir() / TRIAL_FILE


def read_key() -> str | None:
    """Der abgelegte Schlüsseltext, oder ``None``.

    ``ValueError`` fängt den ``UnicodeDecodeError`` einer beschädigten Datei
    mit ab. Ohne ihn schlägt eine unlesbare ``licence.key`` bis in jede
    Dokumentänderung durch — und bis in den Dialog, mit dem sie zu ersetzen
    wäre.
    """
    path = key_path()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


def write_key(text: str) -> bool:
    """Legt den Schlüssel ab. Geprüft wird vorher, nicht hier.

    ``False`` heißt: das Profil ist nicht beschreibbar. Kein Abbruch — der
    Schlüssel gilt dann für diese Sitzung, und der Dialog sagt, dass er beim
    nächsten Start wieder gebraucht wird. Ein Absturz beim Eintragen des
    bezahlten Schlüssels wäre die falsche Richtung des Fehlers.
    """
    try:
        ensure_dir(user_config_dir())
        key_path().write_text(text.strip(), encoding="utf-8")
    except OSError as problem:
        _log.warning("licence key could not be written: %s", problem)
        return False
    _log.info("licence key stored")
    return True


def forget_key() -> bool:
    """Entfernt den Schlüssel — das eine, was ein Einstellungsdialog können
    muss, etwa vor dem Verkauf des Rechners.

    ``missing_ok``, weil „es lag keiner da" das Ziel erreicht und kein
    Fehlschlag ist. ``False`` bleibt dem Fall vorbehalten, dass die Datei da
    ist und sich nicht entfernen lässt.
    """
    try:
        key_path().unlink(missing_ok=True)
    except OSError:
        return False
    return True


def certificate_path() -> Path:
    """Ablageort des Geräte-Zertifikats im Einstellungsordner."""
    return user_config_dir() / CERTIFICATE_FILE


def read_certificate() -> str | None:
    """Das abgelegte Geräte-Zertifikat, oder ``None`` bei jedem Lesefehler."""
    try:
        text = certificate_path().read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


def write_certificate(text: str) -> bool:
    """Legt ein zuvor vollständig geprüftes Geräte-Zertifikat ab."""
    try:
        ensure_dir(user_config_dir())
        scratch = certificate_path().with_suffix(".tmp")
        scratch.write_text(text.strip(), encoding="utf-8")
        scratch.replace(certificate_path())
    except OSError as problem:
        _log.warning("activation certificate could not be written: %s", problem)
        return False
    return True


def forget_certificate() -> bool:
    """Entfernt die lokale Gerätefreigabe; fehlend gilt bereits als entfernt."""
    try:
        certificate_path().unlink(missing_ok=True)
    except OSError:
        return False
    return True


def pending_deactivation_path() -> Path:
    """Ablageort einer noch nicht bestätigten Geräteabmeldung."""
    return user_config_dir() / PENDING_DEACTIVATION_FILE


def read_pending_deactivation() -> str | None:
    """Liest die wiederholbare Geräteabmeldung, falls eine aussteht."""
    try:
        text = pending_deactivation_path().read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


def write_pending_deactivation(text: str) -> bool:
    """Legt eine signierte Geräteabmeldung vor der lokalen Sperre atomar ab."""
    try:
        ensure_dir(user_config_dir())
        target = pending_deactivation_path()
        scratch = target.with_suffix(".tmp")
        scratch.write_text(text.strip(), encoding="utf-8")
        scratch.replace(target)
    except OSError as problem:
        _log.warning("pending deactivation could not be written: %s", problem)
        return False
    return True


def forget_pending_deactivation() -> bool:
    """Entfernt den Auftrag erst nach bestätigter Serverfreigabe."""
    try:
        pending_deactivation_path().unlink(missing_ok=True)
    except OSError:
        return False
    return True


def second_trial_path() -> Path:
    return user_data_dir() / STATE_FILE


def _marker_signature(first_run: date, last_seen: date) -> str:
    payload = f"{first_run.isoformat()}|{last_seen.isoformat()}".encode()
    return hmac.new(_MARKER_SECRET, payload, hashlib.sha256).hexdigest()


def _read_place(path: Path) -> tuple[date, date] | Literal["forged"] | None:
    """Ein Ort des Markers: seine Tage, ``FORGED``, oder ``None``.

    ``None`` heißt fehlend oder unlesbar — beides kann ehrlich passieren
    (frische Installation, Stromausfall beim Schreiben), und der andere Ort
    deckt es. Eine **vorhandene, aber falsche** Unterschrift kann nicht
    ehrlich passieren: Die Tage wurden geändert, ohne neu unterschreiben zu
    können. Ein Marker **ohne** Unterschrift stammt aus einer Fassung vor der
    Härtung und wird gelesen — beim nächsten Schreiben trägt er eine.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        first_run = date.fromisoformat(data["first_run"])
        last_seen = date.fromisoformat(data["last_seen"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    stated = data.get("signature")
    if stated is None:
        return first_run, last_seen
    # ``compare_digest`` verlangt ASCII und wirft sonst ``TypeError`` — und
    # dieser Aufruf steht **außerhalb** des ``try`` darüber. Ein von Hand
    # geänderter Marker, dessen Unterschrift einen Umlaut trägt, ließ damit
    # jede Dokumentänderung mit einem rohen Programmfehler abbrechen, statt
    # die Frist zu beenden (Sicherheitsdurchsicht 04.09.2026). Eine
    # Unterschrift ist ein Hex-Digest; was kein ASCII ist, ist keine — und
    # fällt damit in denselben Zweig wie eine falsche.
    signature = str(stated)
    if not signature.isascii() or not hmac.compare_digest(
        signature, _marker_signature(first_run, last_seen)
    ):
        _log.warning("trial marker at %s does not match its signature", path)
        return FORGED
    return first_run, last_seen


def _read_trial() -> tuple[date, date] | Literal["forged"] | None:
    """Beide Orte, zusammengeführt zur strengeren Auskunft.

    Der **frühere** erste Start und der **spätere** gesehene Tag gewinnen —
    damit ist das Editieren oder Löschen eines einzelnen Ortes wirkungslos:
    Was dem Schummler nützen würde, verliert die Zusammenführung wieder. Ein
    angefasster Ort macht das Ganze angefasst.
    """
    places = (_read_place(trial_path()), _read_place(second_trial_path()))
    if any(place == FORGED for place in places):
        return FORGED
    read = [place for place in places if isinstance(place, tuple)]
    if not read:
        return None
    return min(first for first, _ in read), max(last for _, last in read)


def _places_complete() -> bool:
    """Ob der Marker an beiden Orten liegt — sonst heilt der nächste Schreiber."""
    return trial_path().is_file() and second_trial_path().is_file()


def _write_place(path: Path, text: str) -> None:
    """Ein Ort, atomar geschrieben — halbe Marker sähen wie angefasste aus."""
    ensure_dir(path.parent)
    scratch = path.parent / (path.name + ".tmp")
    scratch.write_text(text, encoding="utf-8")
    scratch.replace(path)


def _write_trial(first_run: date, last_seen: date) -> None:
    text = json.dumps(
        {
            "first_run": first_run.isoformat(),
            "last_seen": last_seen.isoformat(),
            "signature": _marker_signature(first_run, last_seen),
        }
    )
    for path in (trial_path(), second_trial_path()):
        try:
            _write_place(path, text)
        except OSError as problem:
            # Ein schreibgeschützter Ort heißt: dort steht der Marker eben
            # nicht — der andere trägt weiter. Sind beide geschützt, beginnt
            # der Testlauf bei jedem Start neu; das ist die freundliche
            # Richtung des Fehlers, und ein Abbruch wäre die falsche.
            _log.warning("trial marker could not be written to %s: %s", path, problem)


def days_left(today: date | None = None) -> int:
    """Wie viele Tage die schreibende Seite noch offensteht. Null heißt zu.

    Die eine Stelle, an der sich die drei Zustände unterscheiden: Mit einem
    Demo-Stichtag zählt der Kalender. Ohne Stichtag zählt ein ausdrücklich
    angebotener Testlauf ab dem ersten Start; ohne ``TRIAL_FROM`` bleibt die
    schreibende Seite bis zur Lizenzierung geschlossen. Alles darüber — die
    vier Grenzstellen, die ausgegraute Oberfläche, der Freischaltdialog — sieht
    in allen Fällen dieselbe Zahl.
    """
    if DEMO_UNTIL is None:
        return 0 if TRIAL_FROM is None else trial_days_left(today)
    # Auch die Demo führt den höchsten je gesehenen Tag: „Wer die Uhr
    # zurückstellt, verschiebt nur sein eigenes Kalenderblatt" stand als
    # Zusage im Modulkopf, gehalten hat sie nur der Testlauf-Zweig — Uhr auf
    # 2020 hieß zweieinhalbtausend Tage Demo (Gesamtreview L-1). Der Marker
    # ist derselbe, samt Horizontprüfung gegen die leere BIOS-Batterie.
    now = today or date.today()
    stored = _read_trial()
    if isinstance(stored, str):  # FORGED
        # Ein angefasster Marker beendet die Frist, statt sie zu verlängern —
        # wer die Tage editiert, hat gesagt, was er von ihnen hält.
        return 0
    if stored is None:
        # **Ohne Marker zählt trotzdem nicht die Uhr allein.** Beide Schutze
        # einzeln hielten; zusammen — Datei löschen *und* Uhr zurückstellen —
        # blieb hier der frei gewählte Tag stehen, und 2020 hieß 2495 Resttage.
        # Vor der Auslieferung gab es die Demo nicht, also ist ihr Erscheinen
        # der früheste Tag, an dem jemand sie gestartet haben kann.
        effective = max(now, DEMO_FROM)
        # Beide Felder auf denselben Tag: Ein ``first_run`` aus der falschen
        # Uhr läge jenseits von CLOCK_HORIZON_DAYS und ließe den nächsten Lauf
        # genau den Tag verwerfen, der hier gerade festgehalten wird.
        _write_trial(effective, effective)
    else:
        first_run, last_seen = stored
        # Ein gespeicherter Tag jenseits des Demo-Endes kann keine verstrichene
        # Zeit innerhalb der Demo sein — die Demo läuft nur bis DEMO_UNTIL. Er
        # stammt aus einer in die Zukunft gestellten Uhr (leere BIOS-Batterie)
        # und wird auf die echte Zeit zurückgenommen, statt die Frist dauerhaft
        # zu beenden (Gesamtreview Infra 1). Ohne diesen Deckel nahm ein
        # einziger Start mit einer Uhr auf 2099 die Demo für immer weg: Der
        # höchste gesehene Tag lag dann jenseits von DEMO_UNTIL, und weil die
        # Frist nie rückwärts läuft, blieb sie auch nach dem Richtigstellen der
        # Uhr bei null. Der Deckel liegt enger als die Horizontprüfung darunter
        # und fängt auch den Fall, dass schon der erste Start in der Zukunft lag
        # — dann ist first_run selbst verdächtig, und die von ihm ausgehende
        # Horizontprüfung greift nicht.
        if last_seen > DEMO_UNTIL:
            _log.warning("demo marker holds a date past the deadline, ignoring it: %s", last_seen)
            last_seen = now
        if last_seen > first_run + timedelta(days=CLOCK_HORIZON_DAYS):
            _log.warning("trial marker holds an implausible date, ignoring it: %s", last_seen)
            last_seen = max(now, first_run)
        effective = max(now, last_seen, DEMO_FROM)
        # Ein fehlender Ort ist ein Schreibgrund — wie im Testlauf-Zweig.
        if effective != stored[1] or not _places_complete():
            _write_trial(first_run, effective)
    # Der Stichtag selbst gehört noch dazu: am 30.10. bleibt ein Tag übrig,
    # am 31.10. keiner. Die freundliche Richtung, und die, die auf der Website
    # steht („bis zum 30.10.").
    return max(0, (DEMO_UNTIL - effective).days + 1)


def trial_days_left(today: date | None = None) -> int:
    """Wie viele Tage der Testlauf noch hat. Null heißt abgelaufen.

    Der erste Aufruf legt den Marker an — der Testlauf beginnt also beim ersten
    Start, nicht bei der Installation.
    """
    offer_from = TRIAL_FROM
    if offer_from is None:
        return 0
    now = today or date.today()
    trial_floor = max(DEMO_FROM, offer_from)
    stored = _read_trial()
    if now < offer_from and not (isinstance(stored, tuple) and stored[0] >= offer_from):
        # Vor dem Angebot startet kein neuer Test. Ein bereits danach
        # begonnener Marker darf bei zurückgestellter Uhr aber nicht auf null
        # springen — sein höchster gesehener Tag bleibt die strengere Uhr.
        return 0
    if isinstance(stored, str):  # FORGED
        # Wie im Demo-Zweig: Ein angefasster Marker beendet die Frist. Fehlend
        # und angefasst sind Gegensätze — fehlend heißt frisch, angefasst vorbei.
        return 0
    if stored is None:
        if now < trial_floor:
            # Eine Uhr vor der Auslieferung ist beweisbar falsch — die
            # Software gab es da nicht. Was sie sagt, wird nicht
            # festgeschrieben: Der Testlauf beginnt beim ersten Start mit
            # einer glaubwürdigen Uhr, nicht bei einer leeren BIOS-Batterie.
            _log.warning("clock reads %s, before the release — not starting the trial", now)
            return TRIAL_DAYS
        _write_trial(now, now)
        return TRIAL_DAYS
    first_run, last_seen = stored
    # Die Untergrenze auch für den Bestand: Ein erster Start vor der
    # Auslieferung stammt aus einer falsch gestellten Uhr (leere BIOS-Batterie
    # beim Erststart) und nahm dem ehrlichen Kunden sonst den ganzen Testlauf,
    # dauerhaft — used war dann jahrelang.
    if first_run < trial_floor:
        _log.warning("trial marker begins before the release, lifting it: %s", first_run)
        first_run = trial_floor
    # **Auch der erste Start kann falsch datiert sein**, und dagegen hilft der
    # Horizont darunter nicht: Er misst ``last_seen`` gegen ``first_run``, und
    # bei einem falschen Erststart stehen beide auf demselben falschen Tag.
    # Gemessen ging es in beide Richtungen schief — eine Uhr in der Zukunft
    # ließ ``used`` auf null einfrieren und den Testlauf **nie** ablaufen (14
    # Tage in 2026, 14 in 2027, 14 in 2030), eine Uhr in der Vergangenheit nahm
    # dem ehrlichen Kunden mit leerer BIOS-Batterie den ganzen Testlauf,
    # ebenfalls dauerhaft.
    #
    # Beide Deckel hat der Demo-Zweig seit je (:data:`DEMO_FROM` und der
    # Stichtag); hier fehlten sie — derselbe Fehler an der Nachbarstelle.
    # Vor dem Auslieferungstag gab es nichts zu starten, und ein erster Start
    # jenseits der Uhr ist keiner.
    # Gemessen wird am **Horizont**, nicht an der Uhr: ``min(first_run, now)``
    # war der erste Entwurf und nahm dem ehrlichen Kunden seinen Resttag,
    # sobald seine Uhr zurücksprang — sie ist ja genau die Größe, der hier
    # nicht zu trauen ist. Ein Jahr Abstand ist dagegen keine Uhr mehr, die
    # ungenau geht, sondern eine, die nie gestellt wurde.
    #
    # **Und nur, wenn die Uhr selbst glaubwürdig ist** (``now >= DEMO_FROM``):
    # Springt sie in die Vergangenheit, liegt ein völlig echter erster Start
    # ebenfalls „jenseits des Horizonts" — der Deckel schriebe dann ``now``
    # fest und nähme dem ehrlichen Kunden beim Richtigstellen die schon
    # verbrauchte Spanne doppelt. Ein 2099-Marker und ein echter Marker bei
    # zurückgesprungener Uhr sehen von innen gleich aus; was sie trennt, ist
    # allein, welche der beiden Uhren beweisbar lügt.
    if now >= trial_floor and first_run > now + timedelta(days=CLOCK_HORIZON_DAYS):
        _log.warning("trial marker holds an implausible first run, correcting: %s", first_run)
        first_run = now
    # Ein Tag jenseits des Horizonts ist keine verstrichene Zeit, sondern eine
    # leere BIOS-Batterie. Er wird verworfen statt festgeschrieben — sonst
    # kostet ein einziger Start mit falscher Uhr den ganzen Testlauf, und zwar
    # dauerhaft, weil er unten als höchster gesehener Tag zurückkäme.
    if last_seen > first_run + timedelta(days=CLOCK_HORIZON_DAYS):
        _log.warning("trial marker holds an implausible date, ignoring it: %s", last_seen)
        last_seen = max(now, first_run)
    # Die Uhr darf vorgehen, aber nicht zurück: sonst verlängert ein
    # zurückgedrehtes Systemdatum die Frist beliebig.
    effective = max(now, last_seen)
    # Auch ein berichtigter erster Start wird festgehalten: Bliebe er in der
    # Datei stehen, käme derselbe unmögliche Tag bei jedem Start zurück, und
    # die Prüfung darüber liefe für immer gegen denselben falschen Wert. Und
    # ein fehlender Ort ist ebenfalls ein Schreibgrund — die Heilung des
    # gelöschten Zwillings soll beim nächsten Start geschehen, nicht erst am
    # nächsten Tag, wenn sich zufällig ein Wert bewegt.
    if effective != stored[1] or first_run != stored[0] or not _places_complete():
        _write_trial(first_run, effective)
    used = (effective - first_run).days
    return max(0, TRIAL_DAYS - used)
