# `app/core/activation/` — Freischaltung

Lizenzschlüssel, Gerätefreigabe, Demo-Frist — und wo die Grenze verläuft.
Einzuhalten ist `.claude/rules/kern.md` („Die Lizenzgrenze“); Anlässe und
Verlauf dieser Karte: `konzepte/begruendungen/karte-app-core-activation.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `__init__.py` | Die Grenze selbst: was ohne vollständige Freischaltung geht und was nicht |
| `key.py` | Das Format des Lizenzschlüssels: lesen, prüfen, zerlegen — zwei Formate, und die Lizenzart |
| `ed25519.py` | Signieren und Prüfen nach RFC 8032, **in reinem Python** |
| `device.py` | Das Geräte-Schlüsselpaar im Schlüsselbund des Betriebssystems |
| `certificate.py` | Signierte Anforderung, Antwort und Abmeldung für Online- und Dateiweg |
| `store.py` | Wo Schlüssel und Zertifikat liegen und wie befristete Angebote gezählt werden (§38) |
| `integrity.py` | Das signierte Manifest über die eigene Auslieferung |

Der Netzweg liegt in `app/core/licence_service.py` und lädt nur nach einem
ausdrücklichen Klick; der Dateiweg benutzt dieselben Dokumente. Nichts hier
zeigt einen Dialog, und eine abgelaufene Frist ist ein Zustand mit Weg nach
vorn, kein Absturz (Regel 17).

## Zwei Formate, zwei Lizenzarten

Ein Schlüssel nennt seine **Lizenzart** — privat oder gewerblich — im zweiten
Nutzlastformat; das erste bleibt lesbar:

| | Format 1 | Format 2 |
|---|---|---|
| Kopf | `SOLIDON3D-1-` | `SOLIDON3D-2-` |
| Artbyte hinter dem Kaufdatum | nein | ja: 1 privat, 2 gewerblich |
| Wird noch ausgestellt | nein | ja |
| Bedeutet | eine private Lizenz | was darin steht |

**Die Art ist keine Funktionsgrenze**: Beide können dasselbe, getrennt wird
über den Vertrag, und Solidon prüft nicht, ob jemand gewerblich arbeitet
(Begründung: `konzepte/konzept-lizenzarten-2026-09.md`, Entscheidungen A und
J). **Einen Unterschied gibt es, und er sperrt nichts**: die Zahl der
gleichzeitig freigeschalteten Rechner, `key.DEVICE_LIMITS` (privat einer,
gewerblich zwei). Sie steht ein zweites Mal im
Dienst (`ACTIVATION_DEVICE_LIMITS`), weil dort entschieden wird;
`test_the_php_service_knows_the_same_formats_and_kinds` hält beide zusammen.

- `activation_issue` fragt **zuerst**, ob dieses Gerät schon aktiv ist
  (Wiederholung bekommt denselben Platz), **dann** zählt es gegen die Grenze.
  Die Art kommt aus dem signierten Schlüssel; ein Client kann sie nicht
  behaupten.
- Die Meldung an den Kunden nennt **keine Zahl** (`licence_service._error_from`)
  — sie hängt an der Art.
- **Die Art steht im Datensatz** (`licences.kind`):
  `activation_migrate_licence_kind` legt die Spalte in einer Bestandsdatenbank
  an, `activation_issue`/`activation_deactivate` tragen die signierte Art nach,
  wo sie fehlt; `operator.php` liefert `kind` und `device_limit`,
  `tools/licence_admin.kind_label` zeigt sie, das Einrichtungswerkzeug
  migriert dieselbe Spalte.
- **Der eindeutige Index gilt je Gerät**: `one_active_entry_per_device` über
  `(licence_digest, device_public)`. Der alte `one_active_device` über
  `licence_digest` allein ließ den zweiten Platz scheitern; **der `DROP INDEX`
  ist die Migration** und steht in `setup_activation_server.py` *und* in
  `activation_create_schema` — `IF NOT EXISTS` fasst einen alten Index nicht
  an.

**Drei Dinge, die beim Anfassen des Formats schiefgehen:**

- **`encode` schreibt das Format der Lizenz, nicht das neueste.**
  `certificate.licence_digest` hasht die Nutzlast aus `encode`; ein gelesener
  Bestandsschlüssel muss byteweise seine ursprüngliche Nutzlast ergeben, sonst
  passt sein Digest nicht mehr zu dem des Servers, und ein ausgestelltes
  Zertifikat wird wertlos. Dafür trägt `Licence` das Feld `format_version`.
- **Dasselbe Layout steht ein zweites Mal in PHP**
  (`website/api/activation_common.php`, `activation_licence`); wer das eine
  ändert, ändert das andere. Der Test oben hält die Konstanten zusammen, auch
  ohne PHP.
- **Der Kopf ist unsigniert, das erste Nutzlastbyte nicht** — beide nennen
  dieselbe Formatnummer, sonst ist es kein Schlüssel.

## Öffentlich und privat

**Ed25519 von Hand**, damit die Signaturen an keiner Krypto-Bibliothek hängen,
die im Paket fehlen oder eine Lizenzfrage aufwerfen könnte; wenig Code, gegen
die RFC-Vektoren geprüft. Der private Geräteteil liegt nie in einer Datei,
nur im System-Schlüsselbund.

Die **öffentlichen** Schlüssel der Kaufcode- und Aktivierungsaussteller stehen
im Quelltext, sonst könnte die Anwendung nichts prüfen; die **privaten** liegen
weder im Repository noch beim Kunden. Getrennte Paare:
`tools/make_licence_keys.py` erzeugt Kaufcodes,
`tools/setup_activation_server.py` richtet den Aktivierungsdienst ein.

Ein ab `DEVICE_ACTIVATION_FROM` ausgestellter Verkaufscode allein schaltet nichts frei:
Erst ein vom Dienst signiertes, an den privaten Geräteteil gebundenes
Zertifikat öffnet die vier Grenzen. Bestandsschlüssel vor diesem Stichtag
bleiben ohne nachträgliche Gerätebindung gültig. Das Zertifikat läuft nicht
ab: Nach dem Aktivierungsklick bleibt die Anwendung ohne Konto,
Hintergrundprüfung und Netz verwendbar.

## Persönliche Ablagen

- **Die feste Demo** hält einen plausibel erkannten Ablauf als ersten Tag nach
  ihrem Ende in beiden Zeitmarkern fest; ein Zurückstellen der Uhr öffnet sie
  nicht wieder. Eine Uhr jenseits von `DEMO_UNTIL + CLOCK_HORIZON_DAYS` sperrt
  den aktuellen Start, ohne Marker zu ändern — eine falsche Zukunft löscht
  keinen echten Ablauf; Zukunftsmarker früherer Fassungen werden nur außerhalb
  des Horizonts korrigiert. Keine Abwehr gegen eine eingefrorene Uhr oder das
  Löschen aller lokalen Daten (Abschnitt 7 in
  `konzepte/konzept-demo-zu-1.0-2026-09.md`).
- **Kaufcode, Zertifikat, offene Abmeldung und Zeitmarker schreibt
  `store._write_place`**: private Nachbardatei, vollständig schreiben und
  synchronisieren, schließen, atomar ersetzen; ein Schreibfehler bewahrt den
  vorigen Wert. Unter POSIX Ordner 0700 und Datei von Anfang an 0600, auch
  bestehende Dateien beim Lesen; unter Windows gilt die geerbte Zugriffsliste.
- **Verschärfen ist nie der Grund zu scheitern** (`_make_private`): Wo `chmod`
  nicht greift (Datei gehört root, FAT, CIFS), bleiben Lesen und Schreiben
  unberührt — `NamedTemporaryFile` legt ohnehin mit 0600 an.

## Das Prüfmodul ist ein Artefakt je Arbeitsbaum

`tools/build_licence_module.py` baut aus den Grenzdateien das Prüfmodul und
das Lizenzmanifest, **gitignoriert**: Ändert sich eine Grenzdatei, wird
`tests/test_packaging.py` rot, und die Antwort ist ein neuer Bau, kein
Löschen (die CI überspringt den Test). Im eingefrorenen Paket sperrt die
Prüfung auch Nachbardateien, die eine gedeckte Quelle verdrängen könnten: den
aktiven Bytecodecache und alle Erweiterungsendungen des Importfinders samt
ABI-Kennung, dazu `.pyd` und `.so`.

- **Die sieben Module dieses Pakets übersetzt Cython** für das Paket; ihr
  Ruff-Ziel bleibt deshalb Python 3.13 (Cython 3.3 versteht die
  ungeklammerten Ausnahmegruppen von 3.14 nicht), Laufzeit und Erweiterungen
  nehmen die Projektversion. Wer die erlaubte Syntax erweitert, prüft den
  nativen Modulbau, nicht nur den Import.
- **`__init__.py` lädt beim Paketimport kein Untermodul**: Re-Exporte über
  `app.core.lazy`, die Grenzfunktionen importieren `certificate`,
  `integrity`, `key` und `store` erst unmittelbar vor dem Gebrauch — so bleibt
  die Sicherheitsreihenfolge je Funktion, und gleichzeitiger Import bildet
  keinen Modul-Lock-Deadlock.
