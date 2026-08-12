"""Freischaltung: Signatur, Schlüsselformat, Testlauf, Grenze.

Der wichtigste Teil steht ganz oben: die **Testvektoren aus RFC 8032 §7.1**.
Eine eigene Krypto-Umsetzung ohne sie wäre unverantwortlich — sie kann für jede
selbst erzeugte Signatur richtig aussehen und trotzdem eine andere Kurve
rechnen als der Rest der Welt.

Geprüft werden beide Richtungen mit denselben Vektoren: die Anwendung prüft
(``ed25519.verify``), das Werkzeug signiert (``make_licence_keys.sign``). Wäre
nur eine Seite geprüft, könnten beide gemeinsam falsch sein und einander
bestätigen.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.core import activation
from app.core.activation import ed25519, key, store
from app.core.errors import LicenceRequired
from tools.make_licence_keys import make_key, public_key, sign

# RFC 8032, §7.1 — (privater Schlüssel, öffentlicher Schlüssel, Nachricht, Signatur)
RFC_8032_VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555"
        "fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da0"
        "85ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
        "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]


def _vector(index: int) -> tuple[bytes, bytes, bytes, bytes]:
    secret, public, message, signature = RFC_8032_VECTORS[index]
    # Die Länge wird zugesichert, nicht aufgefüllt. Ein zfill(128) polsterte
    # links — also in den Punkt R und nicht in den Skalar s — und machte aus
    # einem beim Kopieren verschluckten Zeichen eine unerklärliche Ablehnung
    # in genau dem Test, der die Krypto absichern soll.
    assert len(signature) == 128, "eine Ed25519-Signatur sind 64 Bytes, also 128 Hexzeichen"
    return (
        bytes.fromhex(secret),
        bytes.fromhex(public),
        bytes.fromhex(message),
        bytes.fromhex(signature),
    )


# --- Die Kurve ------------------------------------------------------------------


@pytest.mark.parametrize("index", range(len(RFC_8032_VECTORS)))
def test_verify_accepts_the_rfc_vectors(index: int) -> None:
    """Die Prüfung nimmt an, was die Norm als gültig ausweist."""
    _secret, public, message, signature = _vector(index)
    assert ed25519.verify(public, message, signature)


@pytest.mark.parametrize("index", range(len(RFC_8032_VECTORS)))
def test_signing_reproduces_the_rfc_vectors(index: int) -> None:
    """Und das Werkzeug erzeugt genau dieselben Bytes.

    Damit ist beides an der Norm festgemacht, nicht aneinander.
    """
    secret, public, message, signature = _vector(index)
    assert public_key(secret) == public
    assert sign(secret, message) == signature


def test_a_changed_message_fails() -> None:
    """Eine Signatur gilt der Nachricht, nicht dem Absender allein."""
    _secret, public, _message, signature = _vector(1)
    assert not ed25519.verify(public, b"\x73", signature)


def test_a_changed_signature_fails() -> None:
    _secret, public, message, signature = _vector(1)
    broken = bytearray(signature)
    broken[0] ^= 0x01
    assert not ed25519.verify(public, message, bytes(broken))


def test_nonsense_is_rejected_without_raising() -> None:
    """Ein halb kopierter Schlüssel ist ungültig, kein Programmfehler."""
    assert not ed25519.verify(b"", b"", b"")
    assert not ed25519.verify(bytes(32), b"", bytes(64))
    assert not ed25519.verify(b"\xff" * 32, b"", bytes(64))


def test_zero_bytes_are_a_point_of_small_order() -> None:
    """Zweiunddreißig Nullbytes sind **kein** Nicht-Punkt.

    Sie sind ein gültiger Kurvenpunkt der Ordnung 4 (y = 0, x = ±sqrt(-1)).
    Der Irrtum stand als Begründung am Platzhalter für ``PUBLIC_KEY`` — und
    gegen einen solchen Punkt lässt sich zu jeder Nutzlast eine gültige
    Signatur schmieden, weil ``[k]A`` nur vier Werte annimmt.
    """
    point = ed25519.decompress(bytes(32))
    assert point is not None, "die Nullbytes sind entgegen dem alten Kommentar ein Punkt"
    assert ed25519.has_small_order(point)
    assert not ed25519.has_small_order(ed25519.base_point())


def test_a_forged_signature_against_a_small_order_key_is_rejected() -> None:
    """Die Fälschung, die vorher durchging, geht nicht mehr durch.

    Nachgestellt wird der Angriff selbst: s frei wählen, R = [s]B - [j]A für
    j in 0..3 setzen und das j nehmen, für das die Prüfgleichung aufgeht. Ohne
    die Ordnungsprüfung nimmt ``verify`` das an.
    """
    packed = bytes(32)
    signer = ed25519.decompress(packed)
    assert signer is not None
    message = b"beliebige Nutzlast"

    forged = b""
    for attempt in range(1, 40):
        scalar_s = attempt * 7919 % ed25519.GROUP_ORDER
        base = ed25519.multiply(scalar_s, ed25519.base_point())
        for j in range(4):
            multiple = ed25519.multiply(j, signer)
            negated = (
                (ed25519.FIELD_PRIME - multiple[0]) % ed25519.FIELD_PRIME,
                multiple[1],
                multiple[2],
                (ed25519.FIELD_PRIME - multiple[3]) % ed25519.FIELD_PRIME,
            )
            packed_r = ed25519.compress(ed25519.add(base, negated))
            challenge = ed25519._hash_to_scalar(packed_r, packed, message) % ed25519.GROUP_ORDER
            if challenge % 4 == j:
                forged = packed_r + scalar_s.to_bytes(32, "little")
                break
        if forged:
            break

    assert forged, "der Angriff selbst muss aufgehen, sonst prüft der Test nichts"
    assert not ed25519.verify(packed, message, forged)


# --- Das Schlüsselformat ---------------------------------------------------------

TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
TEST_PUBLIC = public_key(TEST_SEED)

#: Die Hauptversion, für die ein Schlüssel hier gelten muss. Aus der Anwendung
#: gelesen, nicht als 1 hingeschrieben: sie steigt mit der Veröffentlichung von
#: 0 auf 1, und ein Test, der das nicht mitmacht, wird an diesem Tag rot, ohne
#: dass etwas kaputt ist.
MAJOR = key.current_major()


def a_licence(**changes: object) -> key.Licence:
    values: dict[str, object] = {
        "major": MAJOR,
        "purchased_on": date(2026, 8, 6),
        "order": "A-1234",
        "holder": "kaeufer@beispiel.de",
    }
    values.update(changes)
    return key.Licence(**values)  # type: ignore[arg-type]


def test_a_signed_key_reads_back_exactly() -> None:
    """Der Rundgang: erzeugen, lesen, und dieselben Angaben zurückbekommen."""
    licence = a_licence()
    text = make_key(TEST_SEED, licence)
    assert key.parse(text, public_key=TEST_PUBLIC, major=MAJOR) == licence


def test_the_key_survives_being_pasted_from_an_email() -> None:
    """Zeilenumbrüche, Leerzeichen und Kleinschreibung dürfen den Schlüssel
    nicht ungültig machen — so kommt er aus einer Mail zurück."""
    text = make_key(TEST_SEED, a_licence())
    mangled = f"  {text[:40].lower()}\n {text[40:]}  \n"
    assert key.parse(mangled, public_key=TEST_PUBLIC, major=MAJOR) == a_licence()


def test_one_changed_character_is_rejected() -> None:
    """Der Kern der Sache: ohne den privaten Schlüssel gibt es keinen
    gültigen Schlüssel, auch keinen fast gültigen."""
    text = make_key(TEST_SEED, a_licence())
    swapped = "B" if text[-1] != "B" else "C"
    with pytest.raises(key.LicenceKeyError):
        key.parse(text[:-1] + swapped, public_key=TEST_PUBLIC, major=MAJOR)


def test_a_key_for_another_major_version_is_rejected() -> None:
    """„Alle 1.x-Updates inklusive" heißt: 2.0 braucht einen neuen Schlüssel."""
    text = make_key(TEST_SEED, a_licence(major=MAJOR + 1))
    with pytest.raises(key.LicenceKeyError) as raised:
        key.parse(text, public_key=TEST_PUBLIC, major=MAJOR)
    assert raised.value.values["key_major"] == MAJOR + 1


def test_a_key_from_another_signer_is_rejected() -> None:
    """Ein selbst erzeugtes Schlüsselpaar hilft nicht: geprüft wird gegen
    unseren öffentlichen Schlüssel."""
    other = bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")
    text = make_key(other, a_licence())
    with pytest.raises(key.LicenceKeyError):
        key.parse(text, public_key=TEST_PUBLIC, major=MAJOR)


def test_a_foreign_string_is_rejected_by_its_prefix() -> None:
    with pytest.raises(key.LicenceKeyError):
        key.parse("SOMETHING-ELSE-ABCDEFGH", public_key=TEST_PUBLIC, major=MAJOR)


def test_the_three_classic_typos_are_bent_back() -> None:
    """0 gegen O, 1 gegen I, 8 gegen B — genau die Verwechslungen, wegen derer
    Base32 gewählt wurde. Sie dürfen den Schlüssel nicht kosten."""
    text = make_key(TEST_SEED, a_licence())
    head = f"{key.PREFIX}-{key.FORMAT_VERSION}-"
    body = text[len(head) :].replace("O", "0").replace("I", "1").replace("B", "8")
    assert key.parse(head + body, public_key=TEST_PUBLIC, major=MAJOR) == a_licence()


def test_a_stray_character_is_named_and_not_swallowed() -> None:
    """Ein stillschweigend verschlucktes Zeichen verschiebt die Nutzlast um
    fünf Bit, und der Nutzer bekommt „die Signatur passt nicht" statt eines
    Hinweises auf die Stelle."""
    text = make_key(TEST_SEED, a_licence())
    with pytest.raises(key.LicenceKeyError) as raised:
        key.parse(f"{text[:20]}§{text[20:]}", public_key=TEST_PUBLIC, major=MAJOR)
    assert raised.value.values["character"] == "§"


def test_the_shipped_public_key_is_sound_and_accepts_no_stranger() -> None:
    """Der echte Schlüssel ist eingetragen — und taugt.

    Drei Zusicherungen: er ist ein gültiger Punkt der Kurve (kein Platzhalter
    mehr), er hat keine kleine Ordnung (gegen einen solchen ließe sich jede
    Nutzlast signieren), und ein mit einem fremden Paar signierter Schlüssel
    wird gegen ihn abgelehnt. Ob der passende private Teil Schlüssel erzeugt,
    die er annimmt, lässt sich hier nicht prüfen — der liegt absichtlich
    nicht im Repository (§8).
    """
    point = ed25519.decompress(key.PUBLIC_KEY)
    assert point is not None, "der eingetragene Schlüssel muss ein Punkt der Kurve sein"
    assert not ed25519.has_small_order(point)
    with pytest.raises(key.LicenceKeyError):
        key.parse(make_key(TEST_SEED, a_licence()), major=MAJOR)


def test_every_rejection_carries_a_way_out() -> None:
    """Regel 17 gilt auch hier: kein Fehler endet mit „ungültig"."""
    with pytest.raises(key.LicenceKeyError) as raised:
        key.parse("SOLIDON3D-1-AAAA", public_key=TEST_PUBLIC, major=MAJOR)
    assert raised.value.suggestions
    assert raised.value.detail is not None


# --- Der Testlauf ---------------------------------------------------------------


@pytest.fixture
def own_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Ein eigener Einstellungsordner je Test — sonst trägt der Marker des
    einen in den nächsten hinein."""
    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    yield tmp_path
    activation.forget_cache()


def test_the_trial_starts_at_first_run(own_config: Path) -> None:
    assert store.trial_days_left(date(2026, 8, 6)) == store.TRIAL_DAYS
    assert store.trial_path().is_file()


def test_the_trial_counts_down_and_ends(own_config: Path) -> None:
    start = date(2026, 8, 6)
    store.trial_days_left(start)
    assert store.trial_days_left(start + timedelta(days=1)) == store.TRIAL_DAYS - 1
    assert store.trial_days_left(start + timedelta(days=store.TRIAL_DAYS)) == 0
    assert store.trial_days_left(start + timedelta(days=99)) == 0


def test_turning_the_clock_back_does_not_extend_it(own_config: Path) -> None:
    """Sonst verlängert ein zurückgedrehtes Systemdatum die Frist beliebig.

    Gespeichert wird auch der höchste je gesehene Tag; die Frist läuft nie
    rückwärts.
    """
    start = date(2026, 8, 6)
    store.trial_days_left(start)
    store.trial_days_left(start + timedelta(days=13))
    assert store.trial_days_left(start - timedelta(days=365)) == 1


def test_a_wildly_wrong_clock_does_not_burn_the_trial(own_config: Path) -> None:
    """Eine leere BIOS-Batterie darf keine vierzehn Tage kosten.

    Ein Start mit einem Datum weit in der Zukunft schrieb den Tag als höchsten
    je gesehenen fest — und weil die Frist nie rückwärts läuft, blieb der
    Testlauf auch nach dem Richtigstellen der Uhr für immer abgelaufen.
    """
    start = date(2026, 8, 6)
    store.trial_days_left(start)
    assert store.trial_days_left(date(2030, 1, 1)) == 0, "mit falscher Uhr abgelaufen — richtig"
    assert store.trial_days_left(start + timedelta(days=1)) == store.TRIAL_DAYS - 1


def test_a_plausible_gap_still_blocks_the_clock_going_back(own_config: Path) -> None:
    """Der Deckel darf den Rückwärtsschutz nicht aushebeln: wer Solidon nach
    Monaten wieder öffnet, bekommt seine Frist nicht zurück."""
    start = date(2026, 8, 6)
    store.trial_days_left(start)
    store.trial_days_left(start + timedelta(days=200))
    assert store.trial_days_left(start + timedelta(days=2)) == 0


def test_a_missing_marker_starts_over(own_config: Path) -> None:
    """Bewusst so: der Marker liegt offen im Nutzerprofil, und wer ihn löscht,
    hat wieder vierzehn Tage. Ihn zu verstecken bräuchte Verstecke im System.
    """
    start = date(2026, 8, 6)
    store.trial_days_left(start)
    store.trial_days_left(start + timedelta(days=13))
    store.trial_path().unlink()
    assert store.trial_days_left(start + timedelta(days=13)) == store.TRIAL_DAYS


# --- Die Demo -------------------------------------------------------------------


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch) -> Iterator[date]:
    """Ein bekannter Stichtag statt des ausgelieferten.

    Die Suite läuft sonst ohne (siehe `conftest._the_calendar_stays_out_of_it`);
    hier wird die Frist selbst geprüft, also muss sie hier stehen.
    """
    deadline = date(2026, 10, 30)
    monkeypatch.setattr(store, "DEMO_UNTIL", deadline)
    activation.forget_cache()
    yield deadline
    activation.forget_cache()


def test_the_demo_runs_up_to_and_including_its_deadline(demo: date) -> None:
    assert store.days_left(demo - timedelta(days=70)) == 71
    assert store.days_left(demo) == 1, "der Stichtag selbst gehört noch dazu"
    assert store.days_left(demo + timedelta(days=1)) == 0


def test_the_demo_does_not_count_from_the_first_run(own_config: Path, demo: date) -> None:
    """Der Testlaufmarker entscheidet in der Demo nichts mehr.

    Das ist der Unterschied der beiden Modelle in einem Test: eine Frist ab
    dem ersten Start ließe sich durch Löschen der Datei erneuern, ein
    Kalendertag nicht. Deshalb steht in der Demo auch keine Zusicherung über
    ihn — er wird schlicht nicht gelesen.
    """
    store.trial_path().write_text(
        '{"first_run": "2026-01-01", "last_seen": "2026-08-06"}', encoding="utf-8"
    )
    assert store.days_left(demo - timedelta(days=1)) == 2
    store.trial_path().unlink()
    assert store.days_left(demo - timedelta(days=1)) == 2


def test_after_its_deadline_the_demo_is_over(
    own_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nicht Betrachter, sondern Schluss (Demo-Konzept §2 B2)."""
    monkeypatch.setattr(store, "DEMO_UNTIL", date.today() - timedelta(days=1))
    activation.forget_cache()
    state = activation.state()
    assert state.over
    assert state.in_demo
    assert not state.unlocked
    with pytest.raises(LicenceRequired):
        activation.require(activation.CHANGE)


def test_a_running_demo_knows_its_last_day(own_config: Path, demo: date) -> None:
    """Die Oberfläche nennt den Stichtag dauerhaft — sie holt ihn hier."""
    state = activation.state()
    assert state.in_demo
    assert state.deadline == demo
    assert state.unlocked
    assert not state.over


def test_a_sale_build_is_never_over(own_config: Path) -> None:
    """Ohne Stichtag bleibt es beim Testlauf: abgelaufen ja, zu nein.

    Der abgelaufene Testlauf lässt alles Lesende offen (Veröffentlichungs-
    konzept §2 C) — genau das, was die Demo nicht tut.
    """
    store.trial_path().write_text(
        '{"first_run": "2026-01-01", "last_seen": "2026-08-06"}', encoding="utf-8"
    )
    state = activation.state()
    assert state.expired
    assert not state.over
    assert not state.in_demo


def test_a_sale_version_carries_no_deadline(shipped_demo_until: object) -> None:
    """Eine 1.x-Fassung darf keinen Stichtag tragen.

    Der teuerste Fehler, den dieses Paket zulässt: die Verkaufsfassung mit
    einem Ablaufdatum ausliefern. Sie ließe sich nach dem Tag nicht mehr
    starten — bei jedem, der bezahlt hat.
    """
    from app.branding import APP_VERSION

    if int(APP_VERSION.split(".")[0]) >= 1:
        assert shipped_demo_until is None, (
            f"{APP_VERSION} ist eine Verkaufsfassung und trägt trotzdem einen "
            f"Stichtag ({shipped_demo_until}) — er gehört in store.DEMO_UNTIL auf None"
        )


def test_the_shipped_deadline_has_not_passed(shipped_demo_until: object) -> None:
    """Der Wecker: läuft die ausgelieferte Demo noch?

    Wird dieser Test rot, ist nichts kaputt — es ist der 31.10.2026 oder
    später. Dann trägt die nächste Fassung entweder einen neuen Stichtag
    (zweite Demo) oder keinen mehr (Verkaufsfassung, §6 des Demo-Konzepts).
    Ein Bau in diesem Zustand ließe sich beim Nutzer nicht starten.
    """
    if shipped_demo_until is None:
        return
    assert isinstance(shipped_demo_until, date)
    assert shipped_demo_until >= date.today(), (
        f"Die Demo ist am {shipped_demo_until} abgelaufen — neuer Stichtag oder None"
    )


# --- Der Zustand ----------------------------------------------------------------


def test_a_fresh_machine_is_in_trial(own_config: Path) -> None:
    state = activation.state()
    assert state.in_trial
    assert state.unlocked
    assert not state.expired


def test_an_expired_trial_locks_the_writing_side(own_config: Path) -> None:
    store.trial_path().write_text(
        '{"first_run": "2026-01-01", "last_seen": "2026-08-06"}', encoding="utf-8"
    )
    state = activation.state()
    assert state.expired
    assert not state.unlocked
    with pytest.raises(LicenceRequired) as raised:
        activation.require(activation.EXPORT)
    assert raised.value.suggestions
    assert raised.value.values["action"] == activation.EXPORT


def test_a_stored_key_unlocks_it(own_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(key, "PUBLIC_KEY", TEST_PUBLIC)
    store.trial_path().write_text(
        '{"first_run": "2026-01-01", "last_seen": "2026-08-06"}', encoding="utf-8"
    )
    activation.forget_cache()
    state = activation.remember(make_key(TEST_SEED, a_licence()))
    assert state.unlocked
    assert state.licence is not None
    assert state.licence.holder == "kaeufer@beispiel.de"
    activation.require(activation.CHANGE)


def test_a_rejected_key_is_not_stored(own_config: Path) -> None:
    """Abgelegt wird nur Geprüftes — sonst stünde beim nächsten Start Unsinn
    im Profil und die Anwendung müsste ihn jedes Mal neu verwerfen."""
    with pytest.raises(key.LicenceKeyError):
        activation.remember("SOLIDON3D-1-AAAAAAAA")
    assert store.read_key() is None


def test_a_stored_key_for_the_wrong_major_falls_back_to_the_trial(
    own_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach einem Hauptversionswechsel der normale Fall: der alte Schlüssel
    bleibt liegen, entscheidet aber nichts mehr."""
    monkeypatch.setattr(key, "PUBLIC_KEY", TEST_PUBLIC)
    store.write_key(make_key(TEST_SEED, a_licence(major=99)))
    activation.forget_cache()
    assert activation.state().in_trial
    # Und der Grund ist abrufbar: der Dialog zeigt den Schlüssel im Feld und
    # muss danebenschreiben können, warum er nicht zählt.
    problem = activation.stored_problem()
    assert problem is not None
    assert problem.values["key_major"] == 99


def test_forgetting_the_key_returns_to_the_trial(
    own_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne ein ``forget_cache`` von Hand — das ist der Punkt.

    Vergäße ``forget_key`` den gehaltenen Zustand nicht mit, bliebe die
    Anwendung bis zum Neustart freigeschaltet und der Dialog zeigte weiter
    „Freigeschaltet für …" zu einem Schlüssel, den es nicht mehr gibt.
    """
    monkeypatch.setattr(key, "PUBLIC_KEY", TEST_PUBLIC)
    activation.remember(make_key(TEST_SEED, a_licence()))
    assert activation.forget_key()
    assert activation.state().licence is None


def test_forgetting_a_key_that_was_never_there_is_no_failure(own_config: Path) -> None:
    """„Es lag keiner da" erreicht das Ziel und ist kein Fehlschlag —
    sonst meldete ein Dialog „konnte nicht entfernt werden" für einen
    erfolgreichen Zustand."""
    assert store.read_key() is None
    assert activation.forget_key()


def test_an_unreadable_key_file_does_not_break_the_state(own_config: Path) -> None:
    """Eine beschädigte ``licence.key`` darf nicht jede Dokumentänderung
    mitreißen — und erst recht nicht den Dialog, mit dem sie zu ersetzen wäre.
    """
    store.key_path().write_bytes(b"\xff\xfe kein gueltiges UTF-8")
    assert store.read_key() is None
    assert activation.state().in_trial


def test_a_read_only_profile_still_unlocks_the_session(
    own_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein nicht beschreibbares Profil kostet die Ablage, nicht die Sitzung.

    Ein Absturz genau beim Eintragen des bezahlten Schlüssels wäre die
    falsche Richtung des Fehlers.
    """
    monkeypatch.setattr(key, "PUBLIC_KEY", TEST_PUBLIC)

    def refuse(*_arguments: object, **_keywords: object) -> None:
        raise OSError("read-only profile")

    monkeypatch.setattr(store, "ensure_dir", refuse)
    state = activation.remember(make_key(TEST_SEED, a_licence()))
    assert state.unlocked
    assert store.read_key() is None, "abgelegt wurde nichts — der Dialog sagt das auch"


# --- Haltung --------------------------------------------------------------------


def _sources() -> list[Path]:
    return sorted(Path(activation.__file__).parent.glob("*.py"))


def _imported_modules(source: Path) -> set[str]:
    """Jedes Modul, das diese Datei importiert — über den Syntaxbaum.

    Eine Textsuche nach ``import urllib`` ginge an ``from urllib.request
    import urlopen`` vorbei, und das ist die Form, in der jemand es
    tatsächlich schriebe.
    """
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_the_activation_never_asks_the_network() -> None:
    """Offline ist eine Zusicherung, keine Eigenschaft des heutigen Codes.

    ``datenschutz.html`` sagt „sendet von sich aus keine Daten". Eine
    Prüfung über das Netz wäre der Bruch dieses Satzes — also wird hier
    gemessen, dass keine Zeile davon in Reichweite ist.
    """
    forbidden = {"socket", "urllib", "http", "requests", "ssl", "ftplib", "asyncio"}
    for source in _sources():
        for module in _imported_modules(source):
            root = module.split(".")[0]
            assert root not in forbidden, f"{source.name} reaches for {module}"


def test_there_is_no_switch_to_flip() -> None:
    """Keine Umgebungsvariable, keine Freigabedatei, kein Schalter.

    Ein eingebauter Umschalter wäre genau das, was ein Angreifer sucht — und
    das erste, wonach er greift. Die Suite setzt den Zustand über eine
    Fixture, die das Modul patcht; im Paket gibt es diesen Weg nicht.

    Gemessen wird am Syntaxbaum und nicht am Text: ``from os import environ``
    enthält die gesuchte Zeichenkette an einer Stelle, an der eine Textsuche
    sie erst nach dem Umschreiben fände. Die Zusicherung gilt diesen Modulen —
    dass ``paths.user_config_dir`` weiter unten ``APPDATA`` liest, ist der
    Ablageort und kein Schalter.
    """
    for source in _sources():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            reached = (
                node.attr
                if isinstance(node, ast.Attribute)
                else node.id
                if isinstance(node, ast.Name)
                else ""
            )
            assert reached not in {"environ", "getenv"}, f"{source.name} reads the environment"
        assert "os" not in _imported_modules(source), f"{source.name} imports os"
