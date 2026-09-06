# `app/core/knowledge/parts/` — die Bausteinbibliothek

Geprüfte, parametrische Teile, die der Agent und der Nutzer zusammensetzen
(§24).

Die Regeln stehen in `.claude/rules/bausteine.md`.

## Eigene Lizenz — MIT

**Dieses Verzeichnis steht unter MIT**, anders als der Rest der Anwendung;
die `LICENSE`-Datei liegt hier. Der Grund steht in §36: Die Geometrie, die
diese Bausteine erzeugen, landet in den **eigenen Modellen der Nutzer** —
nichts hier darf für sie eine Lizenzfrage aufwerfen.

Wer hier Code hinzufügt, prüft, dass er unter MIT stehen darf.

## Gebaut gegen `manifold3d`

Nicht gegen OpenSCAD. So hängt `insert_part` an keiner externen Installation
und bleibt testbar. Seit dem Ausbau von OpenSCAD (26.08.2026) gibt es die
Alternative ohnehin nicht mehr — `scad.py` **schreibt** eine Datei und führt
nichts aus; das Format bleibt, der Lauf ist weg.

## Die Karte

**Die Bausteine, nach Gruppen**

| Datei | Gruppe |
|---|---|
| `fasteners.py` | Verbindungen — Schrauben, Muttern, Senkungen |
| `mechanics.py` | Mechanik — was sich bewegt und verbindet: Scharniere, Gewinde |
| `mounting.py` | Halterungen — was etwas an etwas anderem hält |
| `structure.py` | Struktur — versteifen, hindurchführen, anbinden |
| `testbodies.py` | Prüfkörper für die Kalibrierung (§28.3) |

**Das Gerüst**

| Datei | Rolle |
|---|---|
| `registry.py` | `register_part`, `PARTS`, `LIBRARY_VERSION`, `changed_since()` |
| `builtin.py` | Lädt die fünf mitgelieferten Gruppen einmalig; `bootstrap.load_operations()` ruft `builtin.load()` vor der Op-Erzeugung, der Paketimport selbst registriert nichts |
| `ops.py` | **Jeder Baustein wird zusätzlich eine Operation** (§24.1, §10) |
| `build.py` | Gemeinsamer Boden für jeden Baustein |
| `shapes.py` | Kleine Formen, aus denen die Bausteine gebaut werden |
| `range_check.py` | Der Bereichstest in der Anwendung |
| `preview.py` | Vorschaubilder — **gerendert, nicht von Hand gepflegt** |
| `scad.py` | Export als OpenSCAD-Quelltext |
| `recipe.py` | Ein eigener Baustein als **Rezept**: Daten statt Programm (§24.5) |
| `shared.py` | Geschlossener Prüfvertrag für lokale Bausteindateien: Form, Mengen, Ops und Payloads |
| `part_file.py` | Netzfreier, verlustfreier Import und Export samt striktem Rezeptbau und Dateiherkunft |
| `user.py` | Eigene Bausteine aus dem Nutzerverzeichnis |
| `check.py` | Was gesagt werden muss, wenn ein Projekt geöffnet wird (§24.4) |

## Rezept gegen `.py` — der Unterschied ist die Sicherheit

Ein Rezept ist eine Liste registrierter Operationen mit Werten. Es **führt
nichts aus**, was eine Projektdatei nicht ohnehin auslöst — deshalb darf es
in einer Projektdatei mitreisen (Regel 13, Entscheidung Robert 24.08.2026).

Ein eigener Baustein als `.py` bleibt dagegen, wo er liegt: im
Nutzerverzeichnis. Ausführbarer Code reist nie mit.

## Lokaler Baustein-Dateiaustausch

`PartFileIO` hat keine Netzfunktion. Import und Export laufen durch denselben
geschlossenen Rezeptvertrag und bauen das Rezept einmal vollständig, bevor es
den Katalog oder das Dateisystem erreicht. Eingebettete Modellbytes dürfen
mitreisen, werden aber begrenzt, einer relativen Quelle zugeordnet und gegen
deren SHA-256 geprüft. Unbekannte Felder oder Ops, absolute und übergeordnete
Pfade sowie widersprüchliche Payloads werden abgewiesen.

Ein Import erhält eine geschlossene `ImportedOrigin`-Quittung aus Prüfsumme der
exakten Eingangsbytes und UTC-Importzeit — nie aus Pfad, Dateiname oder
Kontaktangabe. Autor, Lizenz, Parameter, Quellherkunft und Payloads bleiben
unverändert. `load_all()` und `replace()` stellen die fremde Katalogquelle
sofort und nach einem Neustart wieder her; erneutes Speichern oder Exportieren
macht daraus keinen eigenen Baustein. Ein gleichnamiger eigener Baustein wird
nicht still ersetzt; dieser Konflikt gehört sichtbar in den Importablauf.

Eine Rezeptdatei wird zuerst vollständig in eine Tempdatei ihres Zielordners
geschrieben und synchronisiert. Erst danach wird sie atomar veröffentlicht:
beim Import ohne Überschreiben, beim ausdrücklichen Ersetzen per Replace. Die
vollständigen Folgezustände von Katalog und Operationsregister entstehen vorher
in isolierten Registern. Nach dem Plattenwechsel werden nur noch diese geprüften
Zustände aktiviert; auch bei einer Unterbrechung wird vorwärts auf den neuen
Stand abgeschlossen und niemals die Platte zurückgerollt. Verwaiste eigene
Tempdateien werden mit Namensraum-, Besitzer- und Altersgrenze beseitigt. So ist
nach einem Prozessabbruch entweder die alte oder die neue vollständige Datei
sichtbar, nie ein halbes Rezept oder ein davon abweichendes Register.

Auch das Entfernen ist eine Dateiaktion und kein Szenenschritt. Nur lokale
Quellen `recipe` und `imported` dürfen diesen Weg nehmen. Der Dateiname wird
zuerst atomar in einen exklusiven Quarantänenamen desselben Ordners verschoben;
Hash, Rückgängig-Bytes und Metadaten stammen danach genau aus diesem Eintrag.
Eine noch nicht festgeschriebene Quarantäne wird beim nächsten Laden
zurückgelegt, eine festgeschriebene wird aufgeräumt. Nach dem Platten-Commit
werden Katalog und Operationsregister wie beim Installieren ausschließlich auf
den vorbereiteten neuen Stand vorwärts gerollt. Die unmittelbare
Wiederherstellung veröffentlicht die gesicherten Bytes samt Modus und Zeiten
wieder ohne Überschreiben. Offene Dokumente und ihr Undo bleiben davon
unberührt.

## Ein neuer Baustein

1. `@register_part(...)` mit `params`, `features`, `preview`, `doc`
2. Umsetzung gegen `manifold3d`
3. **Benannte Features zurückgeben** — das sind die Provenienz-IDs, an denen
   später Ops und Passungen ansetzen
4. `to_scad()` für den Quelltext-Export
5. Test über den **gesamten** Parameterbereich: wasserdicht,
   Mindestwandstärke, keine Selbstdurchdringung an den Grenzen
6. Normteilmaße aus `standards.py`, **nie im Baustein hart eintragen**
7. Vorschaubild rendern lassen
8. Maß an einem bestehenden Baustein geändert? `LIBRARY_VERSION` erhöhen und
   den Änderungsverlauf ergänzen (§24.4) — alte Projekte melden es beim
   Öffnen

## Zwei Versionen, die leicht zu verwechseln sind

- **`LIBRARY_VERSION`** steht in `registry.py` und beschreibt **die
  Bibliothek**. Sie wird erhöht, wenn sich ein Maß ändert.
- **`parts_version`** ist ein Feld **im Dokument** und hält fest, gegen
  welchen Stand das Projekt gebaut wurde.

`check.py` vergleicht die beiden beim Öffnen — daher die Meldung „dieser
Baustein hat sich geändert". `AGENTS.md` sagt verkürzt „`parts_version`
erhöhen"; gemeint ist die Konstante der Bibliothek.

## Material, Messkörper und Reise

Beim Einsetzen bestimmt `profiles.for_object` das Material des Zielkörpers,
auch für `build_with_profile` eines Rezepts. `grip_from_profile` kennzeichnet
Materialübermaß; eine konstruktive Verengung wie am Kabelclip ist davon
unabhängig und wird gegen den Kabeldurchmesser bemessen. Unmögliche
Parameterkombinationen werden mit Änderungsvorschlag abgewiesen; Messwinkel
werden nicht still gekappt. Innen- und Außengewinde teilen denselben
helikalen Flankenverlauf, mit dem eingestellten Spiel dazwischen.

Die Spaltprüfung berücksichtigt alle Komponentenpaare und den tatsächlichen
Flächenabstand, einschließlich Kanteninnerem. Der Körperaufbau bleibt
vom Bereichsbericht getrennt.

Ein erfasster Geometrieausschnitt enthält keine Auftragseinstellungen.
Projektcontainer sammeln Rezeptabhängigkeiten transitiv mit Besuchsmenge.
Mitgereiste Namenskonflikte erhalten einen freien abgeleiteten Namen;
vorhandene lokale oder bereits mitgereiste Fassungen bleiben unverändert.

Das eigenständige Rezeptformat v2 trägt benötigte Rezepte in einer flachen
`dependencies`-Tabelle. v1 wird ohne Änderung der Quelldaten migriert; die
Dokumentmigration bleibt davon getrennt. Der Graph ist auf 32 Beilagen und
64 tatsächlich expandierte Operationen begrenzt, kreisfrei und vollständig
erreichbar. Jede Beilage durchläuft denselben Daten- und Quellenprüfer wie
das Hauptrezept. Ein privates Operationsregister löst die eingebetteten
Fassungen auf, ohne lokale Katalogeinträge oder eingebaute Teile zu ersetzen.
Import, Export, erneutes Laden und Bauen benutzen denselben Vertrag.

Freie Oberflächenplatzierung speichert `x/y/z` und die Außenrichtung
`nx/ny/nz`. Drei Nullen erhalten die frühere `axis`-Semantik; ein echtes
`at_feature` hat Vorrang. Freie Richtungen verwenden den Rahmen aus
`sketch.planes.frame_of`, der auch die Vorschau orientiert. `placement_tool`
liefert die Originalgeometrie bereits mit lokaler Drehung, Einsenkung und
gegebenenfalls Schnittspiegelung; die Oberfläche legt nur die Rahmenmatrix
darüber. Vorschau und Operation teilen den Aufbau mit dem Materialprofil
des Zielkörpers. Ein abziehendes Werkzeug wächst ins Material, ein
hinzufügendes von seiner Basis nach außen.

Ein eigener Baustein darf `nx`, `ny` oder `nz` als fachliches Maß besitzen.
`build_params` verschiebt in diesem Fall alle drei Richtungsfelder gemeinsam
in einen freien `surface_`-Namensraum, bei weiterer Kollision wiederholt.
`normal_fields(op_schema)` ist die einzige Zuordnung für Vorbelegung,
Vorschau und Auswertung. Eigene Maße und bereits gespeicherte Werte bleiben
dabei unverändert; die Richtungsfelder haben weiterhin Null als Vorgabe.

Schraubenbohrung, Senkkegel und Kopfzone haben getrennte benannte Merkmale.
Der Senkkegel behält `countersink_1` mit Art `cone`, Öffnungswinkel und
Innenraumkennzeichnung; `head_room_1` nennt die zylindrische Kopfzone.
Kopfzylinder und Kegel teilen ihren vollständigen Stirnrand. Ein Überstand
unter diesen Rand würde einen Ringsims erzeugen und die Hohlraumkette trennen.
