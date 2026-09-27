# Begründungen zu `app/core/activation/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Formate und
> Stolperfallen verdichtet wurde. Die Karte steht dort; hier stehen die
> ausführlichen Fassungen und der Verlauf ihres Tages — wörtlich, gegliedert
> nach den Überschriften der Karte. *Früher unter …* nennt die Stelle der alten
> Karte.

## Die Karte

Die Punkte der alten „Grenzen“ stehen jetzt unter „Die Karte“ (Netzweg,
kein Dialog, Frist als Zustand) und unter „Das Prüfmodul ist ein Artefakt je
Arbeitsbaum“ (`__init__.py` lädt nichts beim Import).

*Früher unter „Grenzen“.*

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

## Zwei Formate, zwei Lizenzarten

*Früher unter „Zwei Formate, zwei Lizenzarten“.*

Seit dem 15.09.2026 nennt ein Schlüssel seine **Lizenzart** — privat oder
gewerblich. Dafür gibt es ein zweites Nutzlastformat, und das erste bleibt
lesbar:

- `activation_issue` fragt **zuerst**, ob dieses Gerät schon aktiv ist
  (Wiederholung bekommt denselben Platz), und **dann** zählt es gegen die
  Grenze. Die Art kommt aus dem signierten Schlüssel; ein Client kann sie
  nicht behaupten.
- Die Meldung an den Kunden nennt **keine Zahl**
  (`licence_service._error_from`): Wie viele Plätze eine Lizenz hat, hängt an
  ihrer Art, und eine fest eingetragene Zahl wäre für die andere falsch.
- **Die Art steht seit dem 22.09.2026 im Datensatz** (`licences.kind`,
  RM-182). `activation_migrate_licence_kind` legt die Spalte in einer
  Bestandsdatenbank an, und `activation_issue`/`activation_deactivate` tragen
  die signierte Art ein, wo sie fehlt; `operator.php` liefert `kind` und
  `device_limit`, `tools/licence_admin.kind_label` zeigt sie. Das
  Einrichtungswerkzeug migriert dieselbe Spalte.
- **Die Datenbank erzwang die Eins selbst.** Bis zum 15.09.2026 stand ein
  `UNIQUE INDEX one_active_device ON activations(licence_digest)` darüber, und
  der ließ den zweiten Platz als `service_unavailable` scheitern, obwohl die
  Zählung ihn erlaubte. Er heißt jetzt `one_active_entry_per_device` und geht
  über `(licence_digest, device_public)`; **der `DROP INDEX` ist die
  Migration** und steht in `setup_activation_server.py` *und* in
  `activation_create_schema` — eine laufende Datenbank trägt den alten sonst
  weiter, denn `IF NOT EXISTS` fasst ihn nicht an.

## Persönliche Ablagen

*Früher unter „Persönliche Ablagen“.*

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

## Das Prüfmodul ist ein Artefakt je Arbeitsbaum

*Früher unter „Das Lizenzmanifest ist ein Artefakt je Arbeitsbaum“.*

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
