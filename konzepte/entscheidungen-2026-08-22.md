# Entscheidungen, die anstehen — 22.08.2026

Vier Sitzungen haben das Register durchgearbeitet. Was gebaut werden konnte, ist
gebaut; was hier steht, wartet auf eine Entscheidung, die keine Sitzung selbst
treffen darf. Jede Frage nennt den Vorschlag der Sitzung, die sie ausgearbeitet
hat, und was daran hängt.

Reihenfolge: das Billige und Klare zuerst, das Teure zuletzt.

---

## 1. Trimesh im kritischen Pfad des Starts (3d-druck-64)

**Der Befund.** `load_operations()` brauchte über eine Sekunde, und der
Registerpunkt verlangte eine Messung. Sie liegt vor: `app.core.scene.ops` kostet
**722 der 790 ms**, die anderen achtzehn Module zusammen 67. Eine Ebene tiefer
löst es sich vollständig auf — `import trimesh` **582 ms**, `numpy` 65 ms. Das
Registerfüllen selbst ist billig; die 86 Einträge kosten 11,8 ms.
`load_operations()` ist nur der Erste, der trimesh anfasst.

**Die Frage.** `app/ui/app.py:234` ruft `load_operations()` **vor**
`build_application()`. Trimesh lädt also, während der Startbildschirm
„Operationen werden geladen …" zeigt und Qt noch nicht hochgefahren ist — eine
halbe Sekunde, in der nichts anderes passiert. Soll die Startreihenfolge so
umgebaut werden, dass beides nebeneinander läuft?

**Wofür es spricht:** §31 bindet den Start auf drei Sekunden, gemessen sind 12,9
kalt. Eine halbe Sekunde ist der billigste Posten auf der Liste.
**Wogegen:** Es ist eine Änderung an der Startreihenfolge, und die Menüs brauchen
das Register, bevor das Fenster steht. Ein Vorladethread ist kein Einzeiler.

**Vorschlag:** Nicht jetzt. Die Messung ist der Wert des Punkts, und sie sagt,
dass die Stelle woanders liegt als vermutet. Der Umbau gehört in eine eigene
Runde, wenn der Start als Ganzes drankommt — nicht als Anhängsel.

---

## 2. Zwei fehlgeschlagene Operationen stapeln zwei modale Fehlerfenster (3d-druck-b8)

**Vorschlag: anhängen, mit Zähler im Kopf.** Nicht unterdrücken, nicht bloß zählen.

- *Unterdrücken* fällt aus: Der zweite Fehler ist oft der eigentliche, der erste
  nur die Folge, die zuerst auffällt.
- *Nur zählen* („2 weitere Fehler") verstößt gegen Regel 17 — eine Ausnahme ohne
  Weg zu ihrem Inhalt trägt keinen Handlungsvorschlag mehr.
- *Anhängen* passt zur Natur des Dialogs: Ein Fehlerbericht ist ohnehin ein
  Sammelbehälter. Zwei Berichte für einen Absturzmoment sind zwei halbe
  Berichte, und der Nutzer schickt einen davon.

**Die Falle, die beim naiven Anhängen zuschnappt:** Das Bildschirmfoto entsteht
**vor** dem Dialog, sonst zeigt es den Dialog statt dessen, was darunter
schiefging. Beim zweiten Fehler steht der erste Dialog schon — sein Foto zeigte
genau das. Also: Foto des ersten Fehlers behalten, für den zweiten keines.

---

## 3. „Eingabe korrigieren" ist ein Satz und kein Knopf (3d-druck-b8)

Der Parameterfall ist gebaut. Offen ist der **Auswahlfall**, und dort ist
`CORRECT_INPUT` nicht nur unverdrahtet, sondern falsch: `field="in"` ist keine
Parameterzeile, `edit_operation` öffnete einen Dialog auf ein Feld, das es nicht
gibt.

**Vorschlag: eine neue Handlung `CHANGE_SELECTION` — „Andere Objekte wählen".**
Kein Dialog: Der Handler markiert den Schritt im Verlauf, wählt seine bisherigen
Eingangsobjekte im Objektbaum aus und wartet auf die neue Auswahl.

Vier Verdrahtungen: `panels.py` (`FINDING_ACTIONS` für `evaluate.missing_input`,
`evaluate.too_few_inputs`, `evaluate.object_count`), `main_window.py`
(`error_handlers`), `core/errors.py` (die neue `Action`), `scene/history.py:288`
(`consumes` bekommt eigene `suggestions`; `:279` stellt von `CHOOSE` um, denn
`choose` ist bewusst nicht verdrahtet und bleibt sonst ein Satz).

**Die offene Frage:** Soll die geänderte Auswahl den Schritt **ersetzen** (so
liest sich §15.4) oder einen **neuen anlegen**? Ohne Antwort wird ersetzt.

---

## 3b. Woher weiß ein Merkmal, welcher Schritt es erzeugt hat? (3d-druck-3a)

**Eine fehlende Voraussetzung, gefunden bevor eine Zeile geschrieben war.** §21.2
verlangt: „Ein erzeugtes Merkmal bietet immer mindestens eine Handlung an — den
Schritt zu ändern, der es erzeugt hat." Um das anzubieten, muss man wissen,
*welcher* Schritt das war. **Diese Information ist nirgends gespeichert.** Drei
Wege geprüft, alle drei tot:

- `Feature.provenance` sagt `"generated"` — also *dass* es erzeugt wurde, nicht
  *von wem*. Mehr trägt das Feld laut §9 nicht.
- Das ID-Präfix `op4.pin_1`, das §21.2 selbst als Beispiel nennt, wird im
  Produktivcode **nirgends vergeben und nirgends gelesen**. Es kommt nur in
  Tests vor, die es von Hand hinschreiben — die belegen die Schreibweise, nicht
  die Vergabe.
- `SceneObject.created_by` ist der falsche Ausweg: `evaluate.py:309` setzt es bei
  **jeder** Operation, die das Objekt ausgibt. Für ein Gewinde, das in Schritt 3
  geschnitten wurde und in Schritt 7 eine Verrundung bekam, steht dort 7.

**Damit ist Punkt 3 keine Menüfrage, sondern erst eine Formatfrage. Zwei Wege:**

**(a) Das Präfix wirklich vergeben**, wie §21.2 es beschreibt: jedes erzeugte
Merkmal heißt `op<N>.<name>`. Dafür: Der Bauplan sagt es bereits so, kein neues
Feld. Dagegen: Die ID ist der Schlüssel, an dem Ops hängen — sie zu ändern heißt,
jede bestehende Projektdatei umzuschreiben, und die Zuordnung vergleicht Namen.
Migrationsschritt 9 → 10.

**(b) Ein Feld an `Feature`**, etwa `created_by: OpId | None`. Dafür: Die IDs
bleiben; die Antwort steht, wo die Frage gestellt wird; alte Dateien lesen `None`
und verlieren nichts. Dagegen: §9 ändert sich, und `Feature` ist die Struktur, an
der sich laut §9 alle Module ausrichten.

**Vorschlag der Sitzung: (b).** Die ID ist ein Schlüssel und trägt schon eine
Bedeutung (Art und Nummer); ihr eine zweite aufzuladen macht jede Änderung am
Erzeuger zu einer Umbenennung — und §21.2 verlangt an derselben Stelle Stabilität
der IDs.

---

## 4. Erzeugen und Ändern sind reine Verteilermenüs (3d-druck-b8)

**Vorschlag: die Regel, die es entscheidet, steht schon im Code — sie schaut nur
auf die falsche Zahl.** `MENU_GROUPS` (`registry.py:80`) sagt im Docstring: „Eine
Gruppe mit einer einzigen Kategorie steht flach, sonst bekommt jede Kategorie ihr
Untermenü." Sie schaut auf die Zahl der **Kategorien**. Die Hausgrenze ist aber
eine **Zeilengrenze** — zwölf je Menü (`test_interface_limits.py`).

Also: Passen die Zeilen aller Kategorien einer Gruppe zusammen ins
Zwölf-Zeilen-Budget, stehen sie flach mit Trennstrichen; passen sie nicht,
bleiben die Untermenüs. *Erzeugen* hat vier Kategorien und würde flach — der
Quader kostet danach zwei Klicks statt drei. *Ändern* hat sieben und bleibt tief.

**Warum das kein Tausch ist:** Die Neun-Menü-Grenze bleibt unberührt. Es fällt
nur Tiefe *innerhalb* eines Menüs weg, wo das Budget es hergibt, und es
entscheidet eine Regel je Menü statt des Geschmacks je Fall.

---

## 5. Die Werkzeugzeile der Skizze verlangt 1007 Bildpunkte (3d-druck-b8)

Der Punkt ist zwei Sachen, und nur eine ist eine Entscheidung.

**(a) Kein Entscheidungsbedarf — der Test ist kaputt.**
`test_the_constraint_buttons_stay_readable_on_a_laptop` ist grün, wenn er allein
läuft, und misst dann etwas, das niemand sieht: Läuft `test_ui.py` davor im
selben Prozess, sind die achtzehn Knöpfe 37 statt 28 Punkte breit. Er misst die
Reihenfolge des Laufs. Wird ohne Rückfrage repariert.

**(b) Was aus der Zeile verschwindet — Vorschlag: ein Überlaufknopf.** Achtzehn
Knöpfe in einer Zeile sind auch ohne das Stylesheet-Problem zu viel, und die
Hausgrenze steht schon: `test_interface_limits.py` erlaubt acht Werkzeuge. Die
acht häufigsten bleiben Knöpfe, der Rest wandert unter einen Überlauf. Welche
acht die häufigsten sind, sollte an Fusion abgelesen werden statt geraten.

---

## 6. Der Startbildschirm — und was die Messung daran gedreht hat (3d-druck-b8)

**Erst offscreen gemessen, dann mit echter Qt-Plattform nachgemessen.** Der
erste Durchgang war unbrauchbar: Offscreen hat Qt keine Schriftfamilie, und
Layouthöhen sind Textmetriken. Die Nachmessung zeigt, wie systematisch der
Fehler ist — und findet dabei etwas anderes als erwartet.

| | offscreen | echt |
|---|---|---|
| Spaltenbreite | 1360 | 1093 |
| `more_area` | 242 | 256 |
| `examples_area` | 232 | 232 |
| Rollweg 1920×1080 | 160 | **198** |
| Rollweg 1600×900 | 340 | **378** |

Die reinen Kachelrechnungen stimmen überein; falsch wird es dort, wo Schrift im
Spiel ist.

**Der eigentliche Fund steckt aber in einer Zeile, die zuerst wie Beiwerk aussah
— jede Größe zweimal gemessen, mit leerer und mit gefüllter Liste „Zuletzt
geöffnet":**

| | leer | 6 Einträge |
|---|---|---|
| Rollweg 1920×1080 | **26** | 198 |
| Rollweg 1600×900 | 206 | 378 |

**Die 26 px bei leerer Liste sind praktisch die 16 px, die der Registerpunkt nach
`571422e` meldet.** Der Fix von damals wirkt also unverändert — die Messung lief
nur auf einem **frischen** Zustand. Der Punkt beschreibt damit einen
Startbildschirm, den nur sieht, wer die Anwendung zum ersten Mal öffnet.

Im echten Gebrauch stehen dort sechs Projekte, und dann sind es 198 px auf einem
1920er Schirm — **genau der Wert, den der Fix beseitigt hatte.** Die Liste kostet
172 px, und sie wächst mit der Benutzung.

**Damit lautet der Punkt anders, als er dasteht.** Nicht „der Startbildschirm
braucht ein Höhenbudget", sondern: **„Die Liste der zuletzt geöffneten Projekte
frisst den Gewinn von `571422e` auf, sobald jemand die Anwendung ein paarmal
benutzt hat."** Das ist entscheidbar, ohne an Kacheln zu rühren — sechs Zeilen
auf vier gekürzt bringen rund 57 px, und der wiederkehrende Kunde verliert
nichts, was er nicht über *Öffnen* erreicht.

**Die Reihenfolge für den Fall, dass mehr nötig ist:**
1. **`more_area` — „Was kann das noch?"** (256 px). Der größte Posten und der
   einzige, der auf dem Startbildschirm nichts startet. Der Abstand zu
   `examples_area` ist mit 24 px allerdings klein: Wer die zwei gegeneinander
   abwägt, entscheidet nach Zweck und nicht nach Höhe.
2. **„Zuletzt geöffnet" kürzen** — siehe oben, und nach der Messung eher Platz 1.
3. **Die Kachelhöhe zuletzt** — 112 px sind knapp, und das Vorschaubild ist der
   Grund, aus dem eine Kachel erkennbar ist.

**Eine Beobachtung ohne Befund, ausdrücklich als solche:** Mit echter Plattform
ist die Spaltenbreite 1093 statt 1360, und drei Kacheln darin sind je rund
355 px breit — unter `TILE_MIN_WIDTH` (420). Das *sieht* nach einem Fehler aus,
aber `TILE_MIN_WIDTH` wird dort als Schwelle für die **Fensterbreite** benutzt
und nicht als Mindestmaß der Kachel. Ob das Absicht ist, sagt der Code nicht.

---

## 7. §35 braucht eine Testart „Anschluss" (3d-druck-33)

**Der Befund ist schärfer als der Punkt.** §35 *beschreibt* den Fall bereits
ausführlich — was fehlt, ist die **Zeile in der Tabelle**. Und die Tabelle ist
es, aus der `AGENTS.md` seine Testarten zieht und an der entlang eine Sitzung
prüft, ob sie fertig ist. Ein Absatz darunter wird gelesen und genickt; eine
Tabellenzeile wird abgehakt. Dasselbe Muster wie die vier Prosa-Punkte ohne
Kästchen in der Roadmap: **Was kein Kästchen hat, zählt niemand.**

**Vorschlag für die Tabelle** (zwischen „Hauptwege" und „Agenten-Suite"):

| Anschluss | jede Zusage, die nur an einer Stelle eingelöst wird, wird an **dieser** Stelle geprüft — nicht „der Cache kann es", sondern „die Anwendung tut es" |

Dazu drei Bauarten im Text: am echten Einstieg messen; wo zwei Wege dieselbe
Fähigkeit anbieten, sie **gegeneinander** prüfen statt gegen einen erwarteten
Wert; und bei einem einzigen Aufrufer den Test an die Aufrufstelle legen.

**Zwei unabhängige Belege am selben Tag:** der Plattencache (vollständig gebaut,
vollständig geprüft, nie angeschlossen — `disk=` kam in ganz `app/` nicht vor)
und `detect()` gegen `detect_holes()` in der Wahrnehmung, wo ein einseitig
versorgter Fix die Anwendung etwas anderes hätte sagen lassen als die
Kommandozeile, bei grünen Tests in beiden Wegen.

**Was ausdrücklich nicht vorgeschlagen wird:** keine neue Dateikonvention, kein
Abdeckungsmaß, keine Pflicht für jede Bauplanzusage. Die Zeile bindet nur, was
**nur an einer Stelle** eingelöst wird.

---

## 8. Eine vierte Falle in CLAUDE.md (3d-druck-33)

Kein Entwurf für Code, sondern für die Datei, die festlegt, wie hier gearbeitet
wird — deshalb hier und nicht unter uns abgemacht.

**Der Anlass.** Heute endete `tests/test_packaging.py` bei allen vier Sitzungen
gleichzeitig mit Exit 1. Beide gemeldeten Dateien waren unverändert; das
Lizenzmanifest war ein lokales Bauartefakt von 07:49, die zwei Commits kamen um
11:39 und 18:08. Der Test tat genau, wozu er da ist. Wer die Vorgeschichte nicht
kennt, sucht ihn eine halbe Stunde im eigenen Diff.

**Vorschlag: als vierter Spiegelstrich unter „Befehle", neben die drei
bestehenden Fallen** — dort, weil diese Falle beim *Fahren* des Tores zuschnappt
und nicht beim Schreiben von Tests. Der Satz, der trägt, ist die Reihenfolge:
**erst `git status` und der Zeitstempel des Artefakts, dann der Code.** Dieselbe
Familie wie `3D Drucker/` im Prüfpfad — beide Male sagt ein rotes Ergebnis nichts
über den geänderten Code.

Und die Grenze dazu, weil sie leicht zu übertreten ist: **Das ist kein Grund, den
Lauf wegzuzählen.** `suite-getrennt.sh` darf Exit 5 entscheiden, weil „nichts
gesammelt" strukturell keine Aussage über Code ist. Ein veraltetes Artefakt
dagegen ist ein echter Fehlschlag eines Tests, der genau das prüft, was er soll —
hätte das Skript ihn weggezählt, wäre eine Lizenzprüfung stillgelegt, damit die
Schlusszahl schöner aussieht. Behoben wird die Ursache, nicht die Meldung.

---

## 9. Der Upload, der einen Kunden ins Leere schickt (3d-druck-64)

Kein Entwurf, sondern eine Freigabe: Die Changelog-Korrektur liegt nur im
Arbeitsbaum. Bis `website/version.json` hochgeladen ist, liest **jedes**
Update-Fenster beim Kunden den alten achten Punkt und schickt ihn ins Handbuch,
wo nichts steht.

Der Upload geht nach außen und wird deshalb nicht ohne Zustimmung gefahren.
Soll er?

---

## Was hier bewusst nicht steht

Punkte, die auf etwas warten, das keine Entscheidung ist: CI-Dienst und
Signaturzertifikat, Apple-Notarisierung, DMARC-Eintrag, das Postfach `support@`,
ein fremder Rechner zum Installieren, zwei Messschieberwerte an einer 2020er und
einer 3030er Schiene, zwei Agenten-Suite-Läufe gegen Sonnet 5 (kosten Geld), und
die Abstürze, die einen Lauf unter einem Werkzeug brauchen, das doppelte
Freigaben sieht. Sie stehen im Register und bleiben dort, bis das Fehlende da
ist.
