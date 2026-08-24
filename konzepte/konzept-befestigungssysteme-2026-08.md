# Befestigungssysteme — ein fremdes Raster als Baustein

> **Stand 24.08.2026.** Entwurf, nichts davon ist gebaut. Anlass ist eine
> Kundenanfrage vom 24.08.2026 (Alexander Schneider): SKÅDIS-Haken an ein
> heruntergeladenes Modell hängen, ohne es in einem CAD-Programm
> nachzukonstruieren. Robert hat dem Kunden zugesagt, es zu bauen — für die
> nächste oder übernächste Fassung — und den Katalog um weitere Systeme zu
> erweitern.
>
> Was dieses Dokument beantwortet: **ob** es hierhergehört, **was** dabei
> entsteht, **was heute im Weg steht** und **in welcher Reihenfolge** es
> abgearbeitet wird. Was es nicht beantwortet: die Maße. Die sind ungeklärt,
> und §5 sagt, warum das die erste Aufgabe ist und keine Fußnote.
>
> Alle Messungen dieses Dokuments stammen vom 24.08.2026 gegen den Stand von
> `b979b0c`.

---

## 1. Was der Kunde will

Wörtlich, in sechs Schritten: Datei importieren, Rückseite wählen,
„SKÅDIS-Befestigung" wählen, Anzahl und Position festlegen, bei Bedarf
Abstand, Versatz und Toleranz einstellen, verbinden lassen.

Das ist kein Sonderwunsch, sondern **Weg 1 aus Bauplan §2.2** in seiner
reinsten Form: ein fremdes Netz kommt herein, eine Fläche wird angeklickt, ein
geprüfter Baustein setzt sich daran, und heraus geht ein druckbares Teil. Der
Kunde hat den Ablauf nicht erfunden — er hat ihn beschrieben, weil die
Anwendung ihn verspricht.

Der zweite Teil seiner Anfrage ist der interessantere: eine **allgemeine
Bibliothek für Befestigungssysteme**, SKÅDIS und Gridfinity und was sonst
verbreitet ist. §10 sagt, wie weit diese Verallgemeinerung trägt — kürzer, als
sie klingt.

---

## 2. Gehört das hierher?

Ja, und zwar ohne Dehnung des Bauplans.

| Prüfung | Ergebnis |
|---|---|
| Steht es auf der Liste dessen, was **nicht** gebaut wird (AGENTS.md)? | Nein. Kein Plugin-System, kein Slicer, keine Cloud — ein Baustein mehr in einer Bibliothek, die es gibt |
| Deckt §24 es ab? | Ja. Die Erstbestückung nennt Wandhalter und Schlüsselloch-Aufhängung; ein Lochwand-Einhänger ist derselbe Gedanke an einem fremden Raster |
| Ist es ein Nachschlagewert im Sinn von §24.2? | Ja, und das ist der Kern. „Loch für M4-Einpressmutter" und „Zapfen für SKÅDIS" sind dieselbe Sorte Frage |
| Verletzt es eine der 22 Regeln? | Nein, sofern die Maße in die Tabelle gehen und nicht in den Code (Regel 7 sinngemäß, §24.2 wörtlich) |

**Der Baustein ist der billigste Neuzugang, den diese Architektur kennt.** Eine
Deklaration erzeugt Menüeintrag, Dialog, Kommandozeilenbefehl,
Agentenwerkzeug, Katalogkachel und Vorschaubild — `parts/ops.py` sagt es im
Kopf selbst: „einen Baustein zur Bibliothek hinzuzufügen fügt ihn überall
hinzu". Was Arbeit macht, ist nicht der Baustein. Es sind die drei Stellen in
§4, §5 und §8, an denen dieser Fall etwas verlangt, was die Bibliothek noch
nicht kann.

---

## 3. Was heute schon trägt

Gemessen, nicht angenommen:

* **Ein fremdes Netz kommt herein und behält seine Merkmale.** `ingest/` liest
  STL und 3MF, `perceive/` erkennt Flächen und vergibt stabile IDs.
* **Ein Baustein setzt sich an ein Merkmal.** `parts/ops.py:_anchor` liest
  `centre` und die Richtung aus `normal` beziehungsweise `axis`. Seit
  Bibliotheksversion 4 (`FACE_GIVES_DIRECTION`, 23.08.2026) bestimmt die
  angeklickte Fläche auch, **wohin** der Baustein schaut — vorher stand er
  stur auf Z, und wer eine Seitenwand anklickte, bekam ein Schraubenloch in
  die Decke.
* **Additiv wird vereinigt, subtraktiv geschnitten**, und ein aufgesetzter
  Baustein sinkt `BOOLEAN_OVERLAP` ein, damit zwei Volumen sich nicht nur in
  einer Fläche berühren (§39).
* **Ein Baustein, der den Körper verfehlt, sagt das** — `without_effect`
  vergleicht die Volumen und liefert einen Befund (§2.7).
* **Der nächste Verwandte existiert schon.** `profile_tongue` in
  `structure.py` ist eine T-Feder für die Nut einer Aluschiene: ein additives
  Teil, das in ein **fremdes, gegebenes** System greift, alle vier Maße aus
  der Normteiltabelle, und das Spiel geht immer vom eigenen Teil ab, nie auf
  die Nut auf. Das ist bis in die Vorzeichen dieselbe Aufgabe wie ein
  SKÅDIS-Zapfen, und der Baustein ist die Vorlage, an der der neue gebaut
  wird.

Der Ablauf des Kunden ist also nicht neu zu erfinden. Er ist an drei Stellen
zu vervollständigen.

---

## 4. Der Befund, der den Ablauf blockiert

**Kein rein additiver Baustein wird an einer angeklickten Fläche angeboten.**

`parts/ops.py:_applies_to` nimmt `"face"` nur auf, wenn der Baustein abträgt.
Gemessen über alle achtzehn Bausteine:

| `applies_to` | Bausteine |
|---|---|
| `['face']` bzw. `['hole','face']` | `screw_hole`, `heatset_m4`, `nut_trap`, `magnet_pocket`, `keyhole`, `cable_gland`, `dowel`, `snap_connector` — alle abtragend oder mit Richtungsparameter |
| `[]` | **`wall_mount`**, **`profile_tongue`**, `rib`, `snap_fit`, `latch`, `living_hinge` und die drei Prüfkörper — alle rein additiv |

Und `panels.py:context_menu` fällt nur dann auf die Operationen des Objekts
zurück, wenn die Merkmalsart **gar nichts** anbietet. Eine Fläche bietet
etwas an — die abtragenden Bausteine. Also erscheinen genau die, und der
Wandhalter fehlt an der Fläche, an die er gehört.

Zwei Folgerungen:

1. **Der SKÅDIS-Einhänger wäre ohne Änderung unsichtbar an der Stelle, an der
   der Kunde ihn sucht.** Setzen ließe er sich weiterhin über Menü und Dialog
   mit `at_feature` — der Weg funktioniert, die Entdeckbarkeit fehlt. Für
   Bauplan §18.5, der das Kontextmenü am Merkmal „die wichtigste
   Einzelfunktion" nennt, ist das kein Randfall.
2. **Der Befund ist älter als diese Anfrage und größer.** Er trifft den
   Wandhalter und die Nutfeder heute. Er wird deshalb als eigener Punkt
   behoben und nicht in den SKÅDIS-Baustein hineingebaut.

Der Fix ist klein: Ein additiver Baustein, der eine Fläche als Auflage
braucht, gehört an `face`. Ob das für **jeden** additiven Baustein gilt (ein
Filmscharnier will vielleicht keine), ist die einzige offene Frage — sie steht
in §13.

---

## 5. Die Maße, und warum sie zuerst kommen

**Wir kennen sie nicht.** Das ist die ehrliche Lage, und Regel 21 verlangt,
sie so zu benennen.

Was eine Suche am 24.08.2026 hergab: Lochdurchmesser 5 mm, Lochabstand 40 mm,
Plattendicke 5,2 mm. Was dieselbe Suche **nicht** hergab: ob zwischen den
40-mm-Löchern versetzte Zwischenlöcher liegen — und genau davon hängt ab, ob
ein Zapfenpaar 40 mm auseinandersteht oder ob dazwischen noch etwas ist, in
das ein zweiter Zapfen greifen kann. `dimensions.com` nennt nur die
Außenmaße und keine einzige Lochangabe; die Modellportale nennen Zahlen ohne
Herkunft, und sie widersprechen sich in der Plattendicke (3, 5 und 5,2 mm).

Der Kopf von `standards.toml` hat für genau diesen Fall schon eine Haltung:
„Wo Hersteller sich unterscheiden, steht der gebräuchlichste Wert und in
`note` woher er kommt." Das reicht hier **nicht**, denn ein Zapfen, der um
einen halben Millimeter danebenliegt, geht nicht in ein Loch, das 5 mm misst.

Also: **an einer echten Platte nachmessen, bevor eine Zeile Code entsteht.**
Gebraucht wird eine SKÅDIS-Platte und ein Messschieber; gemessen werden
Lochdurchmesser, Mittenabstand in beiden Richtungen, ein etwaiger
Reihenversatz und die Plattendicke, jedes an mehreren Stellen. Wer keine
Platte hat, kauft eine — das ist die billigste Position des ganzen Vorhabens.

Bis dahin steht dieses Vorhaben. Das ist keine Verzögerung, sondern das
Verfahren: „Test zuerst bei Geometrie" heißt hier, dass der Sollwert von der
Platte kommt und nicht aus dem Netz. Ein Baustein, dessen Maße aus einer
Suchmaschine stammen, ist ein Baustein, der beim Kunden nicht passt — und er
passt dann bei **jedem** Kunden nicht, weil die Platte überall dieselbe ist.

---

## 6. Der Entwurf

### 6.1 Die Datenschicht — das Raster als Nachschlagewert

Neue Tabellenart in `app/core/knowledge/data/standards.toml`, dazu die
Dataclass und die drei Zugriffsfunktionen in `standards.py` nach dem Muster
von `ProfileSlot`:

```toml
# --- Lochwandsysteme ------------------------------------------------------------
# hole: Lochdurchmesser · pitch_x/pitch_y: Mittenabstand · stagger: Reihenversatz
# thickness: Plattendicke · Alle Werte am 00.00.2026 an einer Platte gemessen.

[[boards]]
size = "skadis"
hole = 5.0
pitch_x = 40.0
pitch_y = 40.0
stagger = 0.0
thickness = 5.2
note = "IKEA SKÅDIS, gemessen an <Platte>; Herstellerangaben nennen die Lochung nicht"
```

`version` der Tabelle geht auf `"3"`. Die Werte oben sind **Platzhalter mit
Nullen an der Stelle des Datums**, damit niemand sie versehentlich für
gemessen hält.

Warum eine eigene Tabellenart und nicht `profiles`: Eine Lochplatte ist kein
Nutprofil, und ein gemeinsames Schema aus sechs optionalen Feldern wäre die
Sorte Abstraktion, die AGENTS.md „spekulativ" nennt. Zwei Tabellen mit je
fünf gefüllten Feldern schlagen eine mit zehn halbleeren.

### 6.2 Der Baustein

```python
@register_part(
    name="pegboard_hook",
    title=_("Lochwand-Einhänger"),
    group="mounting",
    params=PegboardHookParams,
    features=["hook_1", "plate"],
    doc=_("Zapfen mit Rastnase für eine Lochwand. Die Lochmaße kommen aus der "
          "Normteiltabelle; das Spiel geht vom Zapfen ab, nie vom Loch."),
    changes=[PEGBOARD_ADDED],
)
```

Parameter, aufgeteilt nach der Dialoggrenze aus §9:

| Feld | Vorn/Hinten | Warum |
|---|---|---|
| `system` (Enum, vorerst `skadis`) | vorn | Ein Enum mit einem Wert heute, mit dreien morgen — die Alternative wäre ein Baustein je System und damit ein Menü, das mit dem Katalog wächst |
| `count` (int, 1–6) | vorn | Die Frage des Kunden, Schritt 4 |
| `orientation` (Enum: waagerecht/senkrecht) | vorn | Ein Behälter hängt anders als ein Werkzeughalter |
| `plate` (float, Dicke der Rückplatte) | vorn | Siehe §8 — bei `count > 1` konstruktiv zwingend |
| `play` (float, Vorgabe 0) | **hinten** | Regel 7: null heißt „aus dem Materialprofil", `ops.py` füllt es |
| `lead_in` (float, Anfasung an der Zapfenspitze) | **hinten** | Erleichtert das Einhängen, interessiert niemanden beim ersten Mal |

Sechs Felder vorn plus die vier Ortsfelder aus `_PLACEMENT` — die Grenze von
acht steht auf `placement="front"` und ist damit eingehalten, aber sie ist
knapp. Ein siebtes Feld vorn gibt es nicht.

Die Geometrie folgt `profile_tongue` bis in die Vorzeichen: Zapfendurchmesser
ist `hole - play`, die Rastnase greift hinter die Platte und ist deshalb
`thickness + play` vom Ansatz entfernt, und wo zwei Körper sich sonst nur in
einer Fläche berührten, überlappen sie um `shapes.OVERLAP` (§39).

### 6.3 Die Gruppe

`group="mounting"` — **nicht** eine neue Gruppe. Die Gruppe „Befestigung" hat
heute drei Einträge, die Menügrenze liegt bei zwölf, und ein Untermenü
„Lochwand und Montagesysteme" mit einem einzigen Eintrag wäre ein Klick für
nichts. Eine eigene Gruppe wird angelegt, wenn der vierte Eintrag dieser Art
entsteht, und nicht vorher.

Das ist eine Abweichung von dem, was Robert dem Kunden geschrieben hat („eine
eigene Kategorie für Befestigungssysteme"). Die Zusage bleibt richtig — sie
beschreibt den Zustand, den §10 anpeilt. Nur beginnt er nicht mit einem
halbleeren Menü.

---

## 7. Der Bedienablauf, Klick für Klick

Nach §4 behoben und dem Baustein aus §6:

1. **Datei → Öffnen**, STL oder 3MF. Das Netz erscheint, `perceive/` hat die
   Flächen benannt.
2. **Rechtsklick auf die Rückfläche** — im Viewport oder im Objektbaum.
3. Im Kontextmenü steht **„Lochwand-Einhänger"**, weil §4 additive Bausteine
   an `face` gebracht hat.
4. Der Dialog öffnet mit `at_feature` auf die geklickte Fläche vorbelegt.
   Sechs Felder vorn: System, Anzahl, Ausrichtung, Rückplatte, dazu Ort und
   Achse aus `_PLACEMENT`. Die Achse kommt aus der Flächennormalen und muss
   nicht angefasst werden.
5. **Übernehmen.** Der Einhänger wird mit dem Körper vereinigt, ein Schritt im
   Stapel, mit einem Undo weg.
6. Verfehlt der Baustein den Körper, sagt `without_effect` es als Befund mit
   Handlungsvorschlag — das kann es nämlich, wenn jemand die Fläche
   angeklickt, den Ort aber von Hand verstellt hat.

**Sieben Klicks vom fremden STL zur SKÅDIS-Fassung.** Das ist die Zahl, an der
dieses Vorhaben gemessen wird.

---

## 8. Mehrere Haken — die Stelle, an der es technisch wird

Der Kunde will Anzahl und Position festlegen. Dafür gibt es drei Wege, und
zwei davon sind versperrt:

**Weg A: eine Musteroperation.** Es gibt keine. Von den sechsundvierzig
Operationen des Geometriekerns ist keine ein lineares oder kreisförmiges
Muster. Eine zu bauen wäre ein eigenes Vorhaben mit eigenem Nutzen — und es
ist nicht dieses.

**Weg B: den Baustein mehrfach setzen.** Funktioniert heute, verlangt aber vom
Kunden, den Rasterabstand selbst zu treffen. Genau das soll die Funktion ihm
abnehmen.

**Weg C: der Baustein baut alle Zapfen selbst.** Das ist der Weg — und er
bringt eine Bedingung mit, die nicht verhandelbar ist:

> `tests/test_parts.py:test_a_part_holds_over_its_whole_range` prüft für jede
> Ecke des Parameterbereichs `mesh.component_count == 1`.

Zwei Zapfen im Abstand von 40 mm sind zwei Komponenten. Der Baustein wäre rot,
bevor er das erste Mal läuft. **Also verbindet eine Rückplatte die Zapfen** —
nicht als Zierde, sondern weil der Bereichstest es erzwingt. Und `corners()`
fährt `count` an beiden Enden, also muss die Platte bei `count = 6` genauso
tragen wie bei `count = 1`.

Bei `count = 1` ist die Platte entbehrlich; abschaltbar wird sie trotzdem
nicht, denn ein Parameter, der bei einem Wert von `count` erlaubt und bei
allen anderen verboten ist, ist ein Fehler mit Ansage. Die Vorgabe ist eine
dünne Platte, und wer sie nicht will, setzt sie auf ihr Minimum.

Der Nebengewinn: Die Platte legt sich flächig an das Modell und verbessert
genau die Verbindung, an der ein einzeln aufgesetzter Zapfen bricht.

---

## 9. Was das an anderer Stelle kostet

| Ort | Folge |
|---|---|
| `standards.toml` | Neue Tabellenart, `version` auf `"3"` |
| `standards.py` | Dataclass `Board`, `board()`, `board_sizes()` |
| `parts/mounting.py` | Der Baustein, plus `PartChange`-Eintrag |
| `parts/registry.py` | `LIBRARY_VERSION` auf `"5"` — ein neuer Baustein verschiebt keine bestehenden Maße, aber die Bibliothek ist eine andere |
| `parts/ops.py` | Der Fix aus §4 (`_applies_to`) |
| `app/i18n/locales/` | Fünf Kataloge: `en`, `es`, `fr`, `it`, `pt`. Kein Katalog darf zurückbleiben — `tests/test_translations.py` prüft jeden gefundenen |
| Katalog und Menü | Kommen von selbst; das Vorschaubild wird gerendert, nicht gepflegt (§24.3) |
| Handbuch | Die Referenz erzeugt `manual.py` aus dem Register. Eine geschriebene Seite lohnt erst mit dem zweiten System |
| `tests/test_parts.py` | Der Bereichstest greift automatisch. Dazu drei eigene: Zapfen passt ins Lochmaß, Nase greift hinter die Platte, jedes Maß kommt aus der Tabelle — genau die drei, die `profile_tongue` schon hat |
| `ROADMAP.md` | Register plus Abschnitt; `tests/test_roadmap.py` hält beides zusammen |

**Keine neue Abhängigkeit.** Nichts hiervon braucht ein Paket, das nicht schon
da ist — die Lizenzfrage stellt sich nicht.

**Und keine Rechtsfrage am Namen.** „SKÅDIS" ist eine fremde Marke. Der
Baustein heißt deshalb `pegboard_hook` und trägt das System als
Parameterwert; im Text steht „passend für IKEA SKÅDIS", nicht „IKEA
SKÅDIS-Haken". Maßangaben als Zahlen sind frei verwendbar (§24.2) — der Name
eines Möbelhauses im Menütitel ist etwas anderes.

---

## 10. Wie weit die Verallgemeinerung trägt

Der Kunde schlägt eine Bibliothek für Befestigungssysteme vor. Die Idee ist
richtig, und sie trägt **nicht so weit, wie sie klingt**:

* **Gemeinsam ist die Datenschicht.** Jedes dieser Systeme ist ein fremdes,
  gegebenes Raster mit festen Maßen. Genau dafür ist die Normteiltabelle da,
  und jedes weitere System ist dort ein Eintrag von fünf Zeilen.
* **Gemeinsam ist die Haltung.** Das Spiel geht immer vom eigenen Teil ab, nie
  auf das fremde auf. Die Lochwand ist gegeben, die Aluminiumnut ist gegeben,
  die Gridfinity-Grundplatte ist gegeben.
* **Nicht gemeinsam ist die Geometrie.** Ein Lochwandzapfen ist ein Zylinder
  mit Nase. Ein Gridfinity-Fuß ist ein dreifach abgesetztes Profil auf einem
  42er-Raster, und er sitzt **unten** statt hinten. Eine gemeinsame
  Basisklasse für beides hätte einen einzigen gemeinsamen Satz — „hol die
  Maße aus der Tabelle" — und den erledigt ein Funktionsaufruf.

Also: **eine Gruppe, eine Tabellenart, ein Baustein je System.** Die
Reihenfolge ergibt sich aus der Verbreitung — SKÅDIS zuerst, weil danach
gefragt wurde, Gridfinity als Zweites, weil es seit der Durchsicht vom
16.08.2026 ohnehin auf der Liste steht (dort als „meistgedruckte
Funktionsteil-Kategorie" geführt). Sobald der dritte Eintrag kommt, entsteht
die eigene Gruppe aus §6.3, und dann heißt sie, was Robert dem Kunden
geschrieben hat.

---

## 11. Arbeitspakete

In dieser Reihenfolge, jedes für sich mit grüner Suite abschließbar:

* **P1 — Messen.** Eine SKÅDIS-Platte, ein Messschieber, fünf Werte, jeder an
  mehreren Stellen. Ergebnis ist ein Kommentar in `standards.toml` mit Datum
  und Herkunft. **Blockiert alles Weitere** (§5).
* **P2 — Die Tabelle.** Tabellenart `boards`, Dataclass, Zugriff, `version`
  auf `"3"`, Test „jede Tabellenart ist über ihre Art nachschlagbar" zieht von
  selbst nach.
* **P3 — Der Flächenbefund.** `_applies_to` bringt additive Bausteine an
  `face`. Eigener Commit, eigener Test, unabhängig vom Rest — er behebt
  Wandhalter und Nutfeder mit (§4).
* **P4 — Der Baustein.** `pegboard_hook` nach §6.2, mit den drei eigenen
  Tests. `LIBRARY_VERSION` auf `"5"`.
* **P5 — Die Texte.** Deutsche Quelle plus fünf Kataloge.
* **P6 — Der Durchlauf.** Ein echtes Modell von MakerWorld oder Printables
  einlesen und die sieben Klicks aus §7 fahren. Was dabei hakt, ist der
  eigentliche Befund dieses Vorhabens — nicht, was die Tests sagen.
* **P7 — Drucken.** Ein Prüfstück mit `count = 2` auf dem Centauri Carbon 2,
  einhängen, hängen lassen. Eine Passung, die nicht gedruckt wurde, ist eine
  Behauptung.
* **P8 — Gridfinity.** Eigenes Paket, eigenes Konzept, nach demselben Muster.
  Erst wenn P1 bis P7 durch sind.

---

## 12. Woran es gemessen wird

* Ein heruntergeladenes STL wird in **sieben Klicks** zur SKÅDIS-Fassung (§7).
* Der Bereichstest ist über den ganzen Parameterbereich grün, `count` an
  beiden Enden, `component_count == 1` (§8).
* Jedes Maß des Bausteins lässt sich auf eine Zeile in `standards.toml`
  zurückführen. Keine Zahl im Code, die ein Loch beschreibt.
* Ein gedrucktes Prüfstück hängt an einer echten Platte, ohne zu klemmen und
  ohne zu wackeln (P7).
* Die fünf Sprachkataloge sind vollständig.
* Der Baustein erscheint im Kontextmenü der angeklickten Fläche — nicht nur im
  Menü.

---

## 13. Was offen ist

1. **Die Maße** (§5). Blockiert alles. Braucht eine Platte.
2. **Gilt der Flächenfix aus §4 für jeden additiven Baustein oder für eine
   Auswahl?** Der Wandhalter und die Nutfeder gehören zweifellos dazu. Beim
   Filmscharnier ist es eine Frage. Vorschlag: alle, und wer nicht will, sagt
   es in seiner Deklaration — die Umkehrung würde bei jedem neuen Baustein
   vergessen.
3. **Reihenversatz ja oder nein.** Hängt an P1. Falls die Platte versetzte
   Zwischenlöcher hat, bekommt `count` eine zweite Bedeutung, und §6.2 ist
   nachzuziehen.
4. **Wann die eigene Gruppe entsteht** (§6.3) — Vorschlag: mit dem dritten
   Eintrag.

## 14. Was hier ausdrücklich nicht gebaut wird

* **Keine Musteroperation** (§8, Weg A). Sie wäre nützlich und ist ein anderes
  Vorhaben.
* **Kein Lochplatten-Generator.** Die Platte kauft man; wer sie druckt, findet
  sie fertig. Solidon passt Modelle an, es ersetzt kein Möbelhaus.
* **Kein automatisches Finden der Rückseite.** Der Kunde klickt sie an. Eine
  geratene Fläche wäre in der Hälfte der Fälle die falsche, und Regel 21 sagt,
  was dann zu tun ist: fragen, nicht raten.
