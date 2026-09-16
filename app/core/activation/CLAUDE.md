# `app/core/activation/` — Freischaltung

Lizenzschlüssel, Gerätefreigabe, Demo-Frist — und wo die Grenze verläuft.

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

## Zwei Formate, zwei Lizenzarten

Seit dem 15.09.2026 nennt ein Schlüssel seine **Lizenzart** — privat oder
gewerblich. Dafür gibt es ein zweites Nutzlastformat, und das erste bleibt
lesbar:

| | Format 1 | Format 2 |
|---|---|---|
| Kopf | `SOLIDON3D-1-` | `SOLIDON3D-2-` |
| Artbyte hinter dem Kaufdatum | nein | ja: 1 privat, 2 gewerblich |
| Wird noch ausgestellt | nein | ja |
| Bedeutet | eine private Lizenz | was darin steht |

**Die Art ist keine Funktionsgrenze.** Beide Arten können dasselbe; getrennt
wird über den Vertrag, nicht über eine Sperre. Und Solidon prüft nicht, ob
jemand tatsächlich gewerblich arbeitet — das kann es nicht und soll es nicht.
Warum so und nicht anders, steht in `konzepte/konzept-lizenzarten-2026-09.md`
(Entscheidungen A und J).

**Einen Unterschied im Programm gibt es doch, und er sperrt nichts:** die Zahl
der gleichzeitig freigeschalteten Rechner. `key.DEVICE_LIMITS` nennt sie —
privat einer, gewerblich zwei — und `device_limit(kind)` fragt sie ab. Die
Zahl steht ein zweites Mal im Dienst (`ACTIVATION_DEVICE_LIMITS`), weil dort
entschieden wird; `test_the_php_service_knows_the_same_formats_and_kinds` hält
beide zusammen.

Drei Stellen hängen daran, und die dritte ist die, die sich nicht ansieht:

- `activation_issue` fragt **zuerst**, ob dieses Gerät schon aktiv ist
  (Wiederholung bekommt denselben Platz), und **dann** zählt es gegen die
  Grenze. Die Art kommt aus dem signierten Schlüssel; ein Client kann sie
  nicht behaupten.
- Die Meldung an den Kunden nennt **keine Zahl**
  (`licence_service._error_from`): Wie viele Plätze eine Lizenz hat, hängt an
  ihrer Art, und eine fest eingetragene Zahl wäre für die andere falsch.
- **Die Datenbank erzwang die Eins selbst.** Bis zum 15.09.2026 stand ein
  `UNIQUE INDEX one_active_device ON activations(licence_digest)` darüber, und
  der ließ den zweiten Platz als `service_unavailable` scheitern, obwohl die
  Zählung ihn erlaubte. Er heißt jetzt `one_active_entry_per_device` und geht
  über `(licence_digest, device_public)`; **der `DROP INDEX` ist die
  Migration** und steht in `setup_activation_server.py` *und* in
  `activation_create_schema` — eine laufende Datenbank trägt den alten sonst
  weiter, denn `IF NOT EXISTS` fasst ihn nicht an.

**Drei Dinge, die beim Anfassen dieses Formats leicht schiefgehen:**

- **`encode` schreibt das Format der Lizenz, nicht das neueste.**
  `certificate.licence_digest` hasht die Nutzlast aus `encode`; ein gelesener
  Bestandsschlüssel muss dabei byteweise seine ursprüngliche Nutzlast ergeben,
  sonst passt sein Digest nicht mehr zu dem, den der Server bildet — und ein
  ausgestelltes Zertifikat wird wertlos. Dafür trägt `Licence` das Feld
  `format_version`.
- **Dasselbe Layout steht ein zweites Mal in PHP**
  (`website/api/activation_common.php`, `activation_licence`). Wer das eine
  ändert, ändert das andere; `test_the_php_service_knows_the_same_formats_and_kinds`
  hält die Konstanten zusammen, auch auf einer Maschine ohne PHP.
- **Der Kopf ist unsigniert, das erste Nutzlastbyte nicht.** Beide müssen
  dieselbe Formatnummer nennen — sonst ist es kein Schlüssel, sondern ein halb
  gelesener.

## Warum Ed25519 von Hand

Damit die Signaturen an keiner Krypto-Bibliothek hängen, die im gebauten Paket
fehlen oder eine Lizenzfrage aufwerfen könnte. Es ist wenig Code und er ist
gegen die RFC-Vektoren geprüft. Der private Geräteteil liegt trotzdem nicht in
einer Datei, sondern ausschließlich im System-Schlüsselbund.

## Öffentlich und privat

Die **öffentlichen** Schlüssel der Kaufcode- und Aktivierungsaussteller stehen
im Quelltext — sie müssen dort stehen, sonst kann die Anwendung nichts prüfen.
Die **privaten** Teile liegen weder im Repository noch beim Kunden. Es sind
getrennte Paare: `tools/make_licence_keys.py` erzeugt Kaufcodes,
`tools/setup_activation_server.py` richtet den Aktivierungsdienst ein.

Ein ab dem 01.11.2026 ausgestellter Verkaufscode allein schaltet nichts frei.
Erst ein vom Dienst signiertes und an den privaten Geräteteil gebundenes
Zertifikat öffnet die vier Grenzen. Bereits ausgegebene Bestandsschlüssel vor
diesem Stichtag bleiben ohne nachträgliche Gerätebindung gültig. Das Zertifikat
hat kein Ablaufdatum: Nach dem ausdrücklichen Aktivierungsklick bleibt die
Anwendung ohne Konto, Hintergrundprüfung und Netz verwendbar.

## Persönliche Ablagen

Die feste Demo hält einen plausibel erkannten Ablauf als ersten Tag nach
ihrem Ende in beiden Zeitmarkern fest. Ein späteres Zurückstellen der Uhr
öffnet sie nicht wieder. Eine Uhr jenseits von `DEMO_UNTIL + CLOCK_HORIZON_DAYS`
sperrt den aktuellen Start, verändert aber keine Marker. Dadurch kann auch
der Umweg über eine offensichtlich falsche Zukunft einen echten Ablauf nicht
löschen. Zukunftsmarker früherer Fassungen werden nur außerhalb dieses
Horizonts korrigiert. Das schützt weder vor einer eingefrorenen Uhr noch vor
der Rücksetzung aller lokalen Daten; der laufende Zustands-Cache ist davon
getrennt (Abschnitt 7 in `konzepte/konzept-demo-zu-1.0-2026-09.md`).

Kaufcode, Geräte-Zertifikat, offene Abmeldung und Zeitmarker schreiben über
`store._write_place`: eine eindeutige private Nachbardatei, vollständiges
Schreiben und Synchronisieren, Schließen, dann atomarer Ersatz. Ein
Schreibfehler bewahrt den vollständigen vorigen Wert; eigene temporäre
Dateien werden aufgeräumt. Unter POSIX sind der Zielordner 0700 und die
Datei von der Anlage an 0600. Auch bestehende Kaufcode-/Zertifikats-/
Abmeldedateien erhalten beim Lesen diese privaten Rechte. Unter Windows
gilt die vom Benutzerprofil geerbte Zugriffsliste.

Das Verschärfen ist dabei der Nebenzweck und nie der Grund zu scheitern
(`_make_private`): Wo `chmod` nicht greift — eine Datei, die nach einer
Migration mit `sudo` root gehört, ein Heimatverzeichnis auf FAT oder einer
CIFS-Freigabe —, bleiben Lesen und Schreiben unberührt. Die Ablage selbst legt
`NamedTemporaryFile` ohnehin mit 0600 an; ein Ordner ohne setzbare Rechte
kostet die Verschwiegenheit des Ordners und nicht die eines bezahlten
Kaufcodes.

## Das Lizenzmanifest ist ein Artefakt je Arbeitsbaum

`tools/build_licence_module.py` baut das Prüfmodul aus den Grenzdateien. Es
ist **gitignoriert** — ändert sich eine der Grenzdateien, wird
`tests/test_packaging.py` rot, und die Antwort ist ein neuer Bau, kein
Löschen. Die CI überspringt diesen Test.

Im eingefrorenen Paket sperrt die Prüfung auch Nachbardateien, die eine
gedeckte Quelle verdrängen könnten: den aktiven Bytecodecache und alle
Erweiterungsendungen des Importfinders einschließlich ABI-Kennung. Die
bisherigen allgemeinen Endungen `.pyd` und `.so` bleiben ebenfalls gesperrt.

Diese sieben Python-Quellen werden zusätzlich von Cython übersetzt. Ihr
Ruff-Ziel bleibt deshalb Python 3.13: Cython 3.3 versteht die ungeklammerten
Ausnahmegruppen von Python 3.14 noch nicht. Laufzeit und erzeugte Erweiterungen
verwenden weiterhin die aktuelle Projektversion von Python. Bei einer
Erweiterung der erlaubten Syntax gehört der tatsächliche native Modulbau zur
Prüfung; ein erfolgreicher Python-Import allein reicht nicht.

## Grenzen

- Nichts hier zeigt einen Dialog. Der Kern meldet, die Oberfläche fragt.
- `__init__.py` lädt kein Untermodul beim Paketimport. Öffentliche Re-Exporte
  kommen über `app.core.lazy`; die Grenzfunktionen importieren
  `certificate`, `integrity`, `key` und `store` erst unmittelbar vor ihrem
  Gebrauch. So bleibt die Sicherheitsreihenfolge innerhalb jeder Funktion
  erhalten, während gleichzeitiger Paket-/Untermodulimport keinen
  Modul-Lock-Deadlock mehr bilden kann.
- Der Netzweg liegt in `app/core/licence_service.py` und wird nur nach einem
  ausdrücklichen Klick geladen; der Dateiweg benutzt dieselben Dokumente.
- Eine abgelaufene Frist ist kein Absturz, sondern ein Zustand mit Weg nach
  vorn (Regel 17).
