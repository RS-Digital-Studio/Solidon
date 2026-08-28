"""Freischaltung: Testlauf, Lizenzschlüssel, und wo die Grenze verläuft.

Die Grenze in einem Satz: **was das Dokument ändert oder ein Ergebnis
herausgibt, braucht einen Schlüssel — was nur liest, nicht.** Nach Ablauf des
Testlaufs bleibt Solidon damit ein vollständiger Betrachter seiner eigenen
Projekte: öffnen, drehen, messen, Prüfbericht lesen, Schichtanalyse ansehen,
speichern, zurücknehmen. Wer nichts mehr ändern kann, kann auch nichts kaputt
speichern; die Freigabe kostet nichts und nimmt dem Ablauf die Härte an der
einen Stelle, an der sie niemandem nützt.

Geprüft wird an vier Stellen, und alle vier liegen im **Datenpfad**,
nicht an der Oberfläche:

======================  ==============================================
``History.apply``       jede Dokumentänderung — nichts schreibt daran
                        vorbei, das ist eine Kernregel
``export.writer``       jeder Export
``export.handover``     Slicer-Übergabe und Druckdatei
``agent.session``       der Chat
======================  ==============================================

Jede holt den Zustand selbst und wirft selbst. Die Oberfläche graut
gesperrte Einträge vorher aus — sie ist Freundlichkeit, nicht die Hürde. Ein
Patch an einem Menüeintrag bringt darum nichts. Was die vier Dateien selbst
schützt, ist das signierte Manifest aus :mod:`integrity` (H4) — es wird beim
ersten Zustandsabruf geprüft.

**Ein gebrochenes Manifest sperrt, aber es heißt nicht „abgelaufen".** Der
Zustand trägt dafür :attr:`Activation.damaged`, und der abgelegte Schlüssel
wird auch dann gelesen: Wer bezahlt hat, ist erkannt und bekommt den Weg zur
Neuinstallation statt einer Kaufaufforderung (Regel 17). Freigeschaltet wird
davon nichts — das wäre die Hintertür, die H4 gerade zumacht.

Es gibt **keine Hintertür**: keine Umgebungsvariable, keinen Schalter, keine
Freigabedatei. Die Suite setzt den Zustand über eine Fixture, die dieses Modul
patcht — ein eingebauter Umschalter wäre genau das, was ein Angreifer sucht.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from app.core.activation import certificate as certificates
from app.core.activation import integrity, store
from app.core.activation.certificate import ActivationCertificate
from app.core.activation.key import Licence, LicenceKeyError, parse
from app.core.activation.store import TRIAL_DAYS, TRIAL_FROM, read_key
from app.core.errors import (
    ActiveLicenceCannotBeReplaced,
    DeviceActivationRequired,
    InstallationDamaged,
    LicenceRequired,
)
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

__all__ = [
    "CHANGE",
    "CHAT",
    "DEVICE_ACTIVATION_FROM",
    "EXPORT",
    "SLICER",
    "TRIAL_DAYS",
    "TRIAL_FROM",
    "Activation",
    "ActivationCertificate",
    "ActiveLicenceCannotBeReplaced",
    "DeviceActivationRequired",
    "InstallationDamaged",
    "Licence",
    "LicenceKeyError",
    "LicenceRequired",
    "create_activation_request",
    "create_deactivation_request",
    "forget_cache",
    "forget_key",
    "install_certificate",
    "read_key",
    "remember",
    "remove_certificate",
    "require",
    "state",
    "stored_problem",
]

#: Die vier Handlungen, die einen Schlüssel brauchen. Der Name reist in die
#: Ausnahme und ins Protokoll — damit sich später sagen lässt, an welcher
#: Grenze Leute tatsächlich anstoßen.
CHANGE: Final = "change"
EXPORT: Final = "export"
SLICER: Final = "slicer"
CHAT: Final = "chat"

#: Kaufcodes ab diesem Tag gehören zur Verkaufsversion mit Gerätebindung.
#: Ältere, bereits ausgegebene Schlüssel behalten ihre zugesagte rein lokale
#: Gültigkeit. Der Stichtag ist Teil des Lizenzvertrags und darf deshalb nicht
#: aus dem Vorhandensein einer Zertifikatsdatei geraten werden.
DEVICE_ACTIVATION_FROM: Final = date(2026, 11, 1)


@dataclass(frozen=True, slots=True)
class Activation:
    """Der Freischaltzustand dieses Rechners."""

    licence: Licence | None = None
    certificate: ActivationCertificate | None = None
    """Geräte-Zertifikat der Lizenz. Ohne Lizenz hat es keine Wirkung."""
    days_left: int = 0
    """Resttage des Testlaufs oder der Demo. Ohne Belang, sobald eine Lizenz
    vorliegt."""
    damaged: bool = False
    """Ob das Manifest gebrochen ist (H4) — die Auslieferung ist nicht die,
    die der Bau signiert hat.

    **Ein eigener Zustand, und zwar aus Kundensicht.** Er sperrt wie ein
    abgelaufener Testlauf, aber er heißt nicht so: Wer bezahlt hat, bekommt
    hier keine Kaufaufforderung, sondern den Weg zur Neuinstallation. Damit
    :attr:`licence` in diesem Fall überhaupt etwas enthalten kann, liest
    :func:`_determine` den Schlüssel auch bei gebrochenem Manifest — er
    schaltet nichts frei (siehe :attr:`unlocked`), er sagt nur, wer da vor dem
    Fenster sitzt.
    """
    deadline: date | None = None
    """Letzter Tag einer befristeten Demo, sonst ``None``.

    Die Oberfläche nennt ihn dauerhaft, nicht erst am vorletzten Tag: eine
    Demo, die am 30.10. endet, darf niemanden überraschen, der am 28.10. ein
    Projekt anfängt.
    """

    @property
    def unlocked(self) -> bool:
        """Ob die schreibenden Funktionen offenstehen.

        ``damaged`` schlägt jeden Schlüssel — sonst wäre aus der freundlicheren
        Meldung ein Weg an H4 vorbei geworden: Wer eine Grenzdatei ändert,
        legte einfach einen gültigen Schlüssel daneben.
        """
        return not self.damaged and (self.licensed or self.days_left > 0)

    @property
    def requires_device_activation(self) -> bool:
        """Ob dieser Kaufcode zur Verkaufslizenz mit Gerätebindung gehört."""
        return self.licence is not None and self.licence.purchased_on >= DEVICE_ACTIVATION_FROM

    @property
    def licensed(self) -> bool:
        """Ob der Kaufcode auf diesem Rechner vollständig freigeschaltet ist.

        Bestandskeys von vor Einführung der Gerätebindung brauchen absichtlich
        kein nachträgliches Zertifikat. Neue Verkaufsschlüssel öffnen dagegen
        erst zusammen mit dem lokal geprüften Geräte-Zertifikat.
        """
        return self.licence is not None and (
            not self.requires_device_activation or self.certificate is not None
        )

    @property
    def needs_activation(self) -> bool:
        """Ob ein gültiger Kaufcode auf seine Gerätefreigabe wartet."""
        return not self.damaged and self.requires_device_activation and self.certificate is None

    @property
    def trial_offered(self) -> bool:
        """Ob diese Fassung überhaupt einen Testzeitraum anbietet.

        Null Resttage reichen dafür nicht: Die Verkaufsversion vom 01.11.2026
        startet bewusst **ohne** Testphase und hat ebenfalls null freie Tage.
        Wer beide Fälle zusammenwirft, sagt einem Neukunden, sein nie
        angebotener Test sei abgelaufen. Die Angebotsentscheidung liegt bei
        :data:`store.TRIAL_FROM`; der Demo-Stichtag bezeichnet ein anderes
        Produkt und schließt den Testzustand aus.
        """
        return self.deadline is None and store.TRIAL_FROM is not None

    @property
    def in_trial(self) -> bool:
        return (
            not self.damaged and self.licence is None and self.trial_offered and self.days_left > 0
        )

    @property
    def sale_without_trial(self) -> bool:
        """Ob die lesende Verkaufsversion ohne aktuelles Testangebot läuft."""
        return (
            not self.damaged
            and self.licence is None
            and self.deadline is None
            and not self.trial_offered
        )

    @property
    def expired(self) -> bool:
        """Ob der Testlauf herum ist — und nur das.

        Eine beschädigte Installation ist nicht „abgelaufen", auch wenn sie
        genauso sperrt. Die beiden Zustände auseinanderzuhalten ist der ganze
        Sinn von :attr:`damaged`; wer sie hier wieder zusammenwirft, bekommt
        die Kaufaufforderung an anderer Stelle zurück.
        """
        return (
            not self.damaged and self.licence is None and self.trial_offered and self.days_left <= 0
        )

    @property
    def in_demo(self) -> bool:
        """Ob diese Version eine befristete Demo ist — ob sie noch läuft, sagt
        :attr:`days_left`."""
        return self.deadline is not None

    @property
    def over(self) -> bool:
        """Ob hier endgültig Schluss ist: der Stichtag einer Demo ist herum.

        Der Unterschied zu :attr:`expired` ist der Unterschied zwischen zwei
        Produkten. Ein abgelaufener Testlauf lässt alles Lesende offen — wer
        nichts mehr ändern kann, soll wenigstens an seine Arbeit kommen. Eine
        abgelaufene Demo dagegen startet nicht mehr: sie ist ein Angebot auf
        Zeit, kein beschnittenes Programm, und ein unbegrenzt weiterlaufender
        Betrachter wäre eine zweite kostenlose Version, die niemand pflegt.

        Wer das auswertet, schuldet dem Nutzer die Erklärung dazu: was
        abgelaufen ist, wo es weitergeht, und wo seine Projekte liegen (sie
        bleiben, wo sie sind, und öffnen sich mit der nächsten Version).
        """
        return self.deadline is not None and not self.unlocked and self.days_left <= 0


_cached: Activation | None = None


def state() -> Activation:
    """Der Zustand, einmal je Prozess ermittelt.

    Gehalten, weil ``History.apply`` bei jeder Änderung fragt und eine
    Signaturprüfung in reinem Python nicht kostenlos ist. Nach dem Eintragen
    eines Schlüssels räumt :func:`forget_cache` ihn weg.
    """
    global _cached
    if _cached is None:
        _cached = _determine()
    return _cached


def forget_cache() -> None:
    """Vergisst den gehaltenen Zustand — nach dem Eintragen eines Schlüssels."""
    global _cached
    _cached = None


def _determine() -> Activation:
    # **Der Schlüssel wird immer gelesen, auch bei gebrochenem Manifest.**
    # Vorher stand die Integritätsprüfung davor und kehrte sofort mit einem
    # leeren Zustand zurück: Ein zahlender Kunde, dessen Installation ein
    # Virenscanner angefasst hatte, las „Der Testzeitraum ist abgelaufen" und
    # bekam *Solidon kaufen* angeboten — für etwas, das er besitzt. Gelesen
    # heißt hier nicht freigeschaltet; ``Activation.unlocked`` sperrt bei
    # ``damaged`` unabhängig von der Lizenz (H4).
    licence: Licence | None = None
    stored = read_key()
    if stored is not None:
        try:
            licence = parse(stored)
        except LicenceKeyError as problem:
            # Ein abgelegter Schlüssel, der nicht mehr passt: nach einem
            # Hauptversionswechsel der normale Fall. Der Testlauf entscheidet
            # dann weiter, und der Dialog holt sich den Grund über
            # stored_problem().
            _log.info("stored licence key not accepted: %s", problem.detail)

    if not integrity.intact():
        # H4: Eine veränderte Grenzdatei nimmt der Freischaltung die
        # Grundlage. Gesperrt wie ein abgelaufener Testlauf — nicht
        # abgestürzt, und der ehrliche Nutzer sieht diesen Zweig nie. Die
        # Frist wird hier nicht gezählt: ``store.days_left`` schreibt den
        # Marker fort, und eine beschädigte Installation soll niemandem
        # Testtage verbrauchen.
        _log.warning("licence manifest broken — the writing side stays closed")
        loaded = certificates.load_for(licence) if licence is not None else None
        return Activation(licence=licence, certificate=loaded, damaged=True)
    if licence is not None:
        return Activation(licence=licence, certificate=certificates.load_for(licence))
    return Activation(days_left=store.days_left(), deadline=store.DEMO_UNTIL)


def stored_problem() -> LicenceKeyError | None:
    """Warum der abgelegte Schlüssel nicht zählt — oder ``None``.

    Damit der Freischaltdialog den Grund nennen kann, statt einen sichtbaren
    Schlüssel neben einer Testlaufmeldung unerklärt stehen zu lassen.
    """
    stored = read_key()
    if stored is None:
        return None
    try:
        parse(stored)
    except LicenceKeyError as problem:
        return problem
    return None


def remember(text: str) -> Activation:
    """Prüft einen eingegebenen Schlüssel und legt ihn bei Erfolg ab.

    Wirft :class:`LicenceKeyError` mit Grund, wenn er nicht passt — der Dialog
    zeigt den Grund, nicht ein „ungültig".

    Der Zustand wird aus der eben geprüften Lizenz gesetzt und nicht über
    :func:`state` neu ermittelt: das läse die Datei ein zweites Mal und
    rechnete dieselbe Signaturprüfung noch einmal. Es hält den Schlüssel auch
    dann für diese Sitzung gültig, wenn das Profil nicht beschreibbar war.
    """
    global _cached
    licence = parse(text)  # wirft, wenn er nicht passt — abgelegt wird nur Geprüftes
    previous_text = read_key()
    if previous_text is not None and store.read_certificate() is not None:
        try:
            previous = parse(previous_text)
        except LicenceKeyError:
            previous = None
        if previous is not None and previous != licence:
            # Die Oberfläche sperrt das Feld ebenfalls, doch sie ist nur die
            # freundliche erste Linie. Auch ein Agent oder ein späterer
            # Einstellungsweg darf eine bestehende Gerätebindung nicht durch
            # bloßes Eintragen eines anderen Kaufcodes verwaisen lassen.
            raise ActiveLicenceCannotBeReplaced()
    store.write_key(text)
    # **Die Integritätsprüfung gehört auch hierher (H4).** Der Zustand wird aus
    # der eben geprüften Lizenz gesetzt, und dabei fiel ``damaged`` heraus: Wer
    # eine Grenzdatei veränderte und danach seinen gültigen Schlüssel eintippte,
    # hob die Sperre für die ganze Sitzung auf — dieselbe Hintertür, die
    # :func:`_determine` schließt, nur durch die andere Tür. Die einzige Hürde
    # davor war der graue Prüfknopf im Dialog, und die Oberfläche ist nie die
    # Hürde (``kern.md``). Der Schlüssel wird trotzdem gelesen und abgelegt:
    # Erkannt heißt nicht freigeschaltet, und der zahlende Kunde soll nach der
    # Reparatur nicht noch einmal tippen.
    _cached = Activation(
        licence=licence,
        certificate=certificates.load_for(licence),
        damaged=not integrity.intact(),
    )
    return _cached


def create_activation_request(device_name: str) -> str:
    """Erzeugt die signierte Geräteanforderung für Online- und Dateiweg."""
    stored = read_key()
    if stored is None:
        raise LicenceKeyError()
    return certificates.create_request(stored, device_name)


def install_certificate(text: str) -> ActivationCertificate:
    """Prüft und speichert eine Aktivierungsantwort für diesen Rechner."""
    global _cached
    installed = certificates.install(text)
    stored = read_key()
    if stored is None:  # durch ``install`` bereits erklärt; nur Typverengung
        raise LicenceKeyError()
    licence = parse(stored)
    _cached = Activation(
        licence=licence,
        certificate=installed,
        damaged=not integrity.intact(),
    )
    return installed


def create_deactivation_request() -> str:
    """Belegt gegenüber dem Server die Freigabe des aktuellen Geräteplatzes."""
    current = state()
    stored = read_key()
    if stored is None or current.certificate is None:
        raise DeviceActivationRequired()
    return certificates.create_deactivation(stored, current.certificate)


def remove_certificate() -> bool:
    """Entfernt nur die lokale Gerätefreigabe und leert den Zustandscache."""
    removed = store.forget_certificate()
    forget_cache()
    return removed


def forget_key() -> bool:
    """Entfernt den abgelegten Schlüssel und den gehaltenen Zustand mit ihm.

    Der gehaltene Zustand gehört dazu: ohne ihn bliebe die Anwendung bis zum
    Neustart freigeschaltet, und ein Dialog zeigte weiter „Freigeschaltet für
    …" zu einem Schlüssel, den es nicht mehr gibt.
    """
    certificate_removed = store.forget_certificate()
    removed = store.forget_key()
    forget_cache()
    return removed and certificate_removed


def require(action: str) -> None:
    """Lässt durch oder wirft — :class:`InstallationDamaged` oder
    :class:`LicenceRequired`.

    Die eine Funktion, die alle vier Grenzstellen aufrufen. Sie gibt nichts
    zurück: ein Rückgabewert wäre ein Wahrheitswert, den eine Stelle
    versehentlich ignoriert.

    **Zwei Absagen, weil es zwei Lagen sind** (Regel 17). Gesperrt wird in
    beiden gleich; was sich unterscheidet, ist der Weg hinaus. Eine gebrochene
    Auslieferung wird nicht besser, wenn man einen Schlüssel kauft — sie wird
    besser, wenn man Solidon neu installiert.
    """
    current = state()
    if current.damaged:
        raise InstallationDamaged(action=action)
    if current.needs_activation:
        raise DeviceActivationRequired(action=action)
    if not current.unlocked:
        if current.expired:
            raise LicenceRequired(
                action=action,
                title=_(
                    "Der Testzeitraum ist abgelaufen — dafür braucht Solidon einen Lizenzschlüssel."
                ),
            )
        raise LicenceRequired(action=action)
