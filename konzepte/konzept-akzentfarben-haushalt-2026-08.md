# Der Akzentfarben-Haushalt

**Konzeptnotiz zu G6 (Befunde B6, B16, B22 der Design-Durchsicht), 30.08.2026.**
Nicht gebaut — die Entscheidung steht vor der Umsetzung, und die Umsetzung
liegt in `style.py`, die eine Hand hat.

---

## Die Frage in einem Satz

Bernstein bedeutet heute mindestens neun Dinge, und ein Kunde ohne
CAD-Erfahrung kann aus der Farbe deshalb nichts ablesen. Wo darf sie stehen,
und was bekommt eine leisere Form?

---

## Bestand: wo Bernstein heute steht

Gezählt am Code, nicht geschätzt. `highlight` steht 52-mal in `app/ui/`,
davon 21-mal in `style.py`. Die Bedeutungen dahinter:

| # | Bedeutung | Fundort | flüchtig oder dauerhaft? |
|---|---|---|---|
| 1 | **Hauptknopf** eines Dialogs | `style.py:316` (`QPushButton:default`) | dauerhaft |
| 2 | **Aktives Werkzeug** | `style.py:351` (`QToolButton:checked`) | dauerhaft |
| 3 | **Gewählte Zeile** in Baum, Liste, Tabelle | `style.py:490` | flüchtig |
| 4 | **Gewählte Kachel** (nur als Rahmen) | `style.py:507` | flüchtig |
| 5 | **Markierter Text** in Feldern | `style.py:418`, `476` | flüchtig |
| 6 | **Menüeintrag unter dem Zeiger** | `style.py:656` | flüchtig |
| 7 | **Fortschritt** | `style.py:689`, `loading.py:374` | flüchtig |
| 8 | **Kartenkante** (Umfragekarte, Startkachel) | `survey.py:330`, `start_screen.py:164` | dauerhaft |
| 9 | **Wichtige Zahl** (Ablaufdatum, Version) | B6 der Durchsicht | dauerhaft |

Dazu B16: Der Prüfbericht färbt **den ganzen Befundsatz** in der Rollenfarbe,
obwohl das Symbol daneben dieselbe Aussage schon trägt — und die dringlichste
Stufe hat dabei den niedrigsten Kontrast (4,52).

Und B22: Der Hauptknopf bedeutet nicht überall dasselbe. Im Kürzelfenster trägt
**„Schließen"** den Akzent; fünf Dialoge haben gar keinen akzentuierten Knopf,
weil ihr Hauptknopf anfangs gesperrt ist.

**Die Zahl aus B6 ist die wichtigste:** Ohne dass der Kunde irgendetwas
ausgewählt hat, tragen vier Elemente gleichzeitig die Akzentkante.

---

## Die Trennlinie, die der Bestand selbst zeigt

Die Tabelle sortiert sich von allein in zwei Gruppen, und die Grenze ist
**nicht** „Auswahl gegen Zustand", sondern **flüchtig gegen dauerhaft**.

Die flüchtigen (3–7) sind unproblematisch, obwohl es fünf sind: Sie erscheinen
als Antwort auf eine Handlung und verschwinden wieder. Eine markierte Textstelle
und eine gewählte Baumzeile bestehen selten nebeneinander, und wenn doch,
bedeuten sie dasselbe — „hier bist du gerade".

Die dauerhaften (1, 2, 8, 9) sind das Problem. Sie leuchten, **bevor** der Kunde
etwas tut, sie leuchten alle gleichzeitig, und sie meinen Verschiedenes:
„drück mich", „du bist im Bewegen-Modus", „das hier ist eine Karte", „diese
Zahl läuft ab". **Vier Dauerleuchten machen aus einem Signal eine Tapete** —
und dann fällt das fünfte, das wirklich etwas will, nicht mehr auf.

---

## Vorschlag

**Der Akzent gehört dem Flüchtigen und genau einem Dauerhaften.**

1. **Behalten, flüchtig (3–7):** gewählte Zeile, gewählte Kachel, markierter
   Text, Menüeintrag unter dem Zeiger, Fortschritt. Sie sind die Antwort auf
   eine Handlung des Kunden und verschwinden mit ihr.

2. **Behalten, dauerhaft — aber nur einmal je Fenster: der Hauptknopf (1).**
   Er ist die einzige dauerhafte Aussage, die eine Handlung *verlangt*. Dazu
   gehört die Behebung von B22: Wo der Hauptknopf gesperrt startet, trägt er
   den Akzent trotzdem und sieht gesperrt aus — ein Dialog ohne akzentuierten
   Knopf lässt den Kunden suchen, welcher Weg der gemeinte ist. Und
   **„Schließen" ist nie ein Hauptknopf**: Ein Fenster zu verlassen ist keine
   Handlung, die man empfiehlt.

3. **Leiser werden (2, 8):**
   - Das **aktive Werkzeug** bekommt eine gedämpfte Fläche statt der vollen
     Akzentfarbe — es sagt „du bist hier" und nicht „tu das". Ein Rahmen in
     Akzentfarbe wäre die zweitbeste Lösung; die gedämpfte Fläche ist besser,
     weil Rahmen bei kleinen Knöpfen mit der Auswahl kollidieren.
   - **Kartenkanten** verlieren den Akzent vollständig und bekommen die
     Linienfarbe. Eine Karte ist eine Fläche, keine Aussage; dass sie eine
     Karte ist, sagt ihre Kante auch in Grau.

4. **Eigene Farbe bekommen (9 und die Bedeutungsfarben):**
   - „Diese Zahl läuft ab" ist eine **Warnung** und gehört in die Warnfarbe,
     nicht in den Akzent. Der Unterschied ist der Kern: Der Akzent lädt ein,
     die Warnung hält an.
   - „Nimmt Material weg" im Katalog ist eine **Sachaussage über die
     Operation** und gehört zu den Rollenfarben, nie zum Akzent.

5. **B16 gesondert:** Der Prüfbericht soll den Satz **nicht** einfärben. Das
   Symbol trägt die Rolle bereits (Regel 18 ist damit erfüllt), und ein voll
   eingefärbter Satz ist schlechter lesbar als ein schwarzer neben einem
   farbigen Symbol. Die Farbe bleibt am Symbol, der Text wird Fließtext.

---

## Woran sich das messen lässt

Ein Wächter, der zählt, wie viele Elemente im **Ruhezustand** eines Fensters
die Akzentfarbe tragen — ohne Auswahl, ohne Zeiger auf einem Element. Die
Zusage: **höchstens eines** (der Hauptknopf). Heute sind es vier.

Das ist am Stylesheet allein nicht zu prüfen; es braucht das echte Fenster und
die gerenderte Palette je Widget. Der Aufwand lohnt: Ohne diese Zahl wandert
der Akzent binnen eines halben Jahres an die nächste Stelle zurück, und
niemand merkt es, weil jede einzelne Entscheidung für sich plausibel ist.

---

## Was diese Notiz **nicht** entscheidet

- **Welcher Ton** die gedämpfte Fläche des aktiven Werkzeugs bekommt. Das ist
  eine Frage an `style.py` und an die Hand, die sie hält.
- **Ob der Kontrast von 4,52** (B16) durch eine andere Rollenfarbe oder durch
  den Wegfall der Textfärbung gelöst wird. Fällt die Färbung weg, erledigt
  sich der Kontrast von selbst — dann ist B16 keine Farbfrage mehr.
- **Die Reihenfolge der Umsetzung.** Der Kartenkanten-Teil ist der billigste
  und sichtbarste; der Hauptknopf-Teil (B22) berührt fünf Dialoge und braucht
  je eine eigene Entscheidung, welcher Knopf der gemeinte ist.

---

## Eine Reibung an der Vorab-Haltung

Die Vorgabe lautete: „Der Akzent gehört der Auswahl und dem einen Hauptknopf —
Zustände wie ‚aktiv' und Karten brauchen eine leisere Form, und
Bedeutungsfarben wie ‚nimmt Material weg' eine eigene, nie den Akzent."

**Im Ergebnis stimmt das, in der Begründung nicht ganz.** „Auswahl gegen
Zustand" trennt nicht sauber: Der Fortschrittsbalken ist keine Auswahl und darf
den Akzent trotzdem tragen; das aktive Werkzeug ist beinahe eine Auswahl und
darf ihn nicht. Was wirklich trennt, ist **flüchtig gegen dauerhaft** — und
diese Linie erklärt beide Fälle ohne Ausnahme.

Der praktische Unterschied ist klein, aber er zeigt sich beim nächsten neuen
Element: Wer nach „ist das eine Auswahl?" fragt, muss bei jedem Grenzfall neu
raten. Wer fragt „steht das auch da, wenn der Kunde nichts tut?", bekommt jedes
Mal dieselbe Antwort.

---

## Präzisierung nach der B22-Messung (30.08.2026, Freigabe-Entscheid)

Die Zusage „genau ein Hauptknopf je Fenster" gilt für Fenster, die eine
**Handlung** anbieten. Ein reines Anzeigefenster (Kürzel, Über, Änderungen)
hat folgerichtig **keinen** akzentuierten Knopf: Der Akzent lädt zur
Handlung ein, „Schließen" ist keine empfohlene Handlung, und ein
akzentuiertes „Schließen" wäre die Einladung, das Fenster zu verlassen,
bevor man gelesen hat. Suchen entsteht dort nicht — es gibt nur den einen
Knopf.

Und der Bestandsbefund, der die Messung nötig machte: **Qt vergibt den
Default von selbst** — beim ersten `show()` wird der erste
autoDefault-Knopf zum Default und trägt die Akzentfarbe, aber nicht die
halbfette Zweitkodierung aus `make_primary`. Neun Dialoge trugen so einen
stillen, halben Hauptknopf; der Quelltext-Wächter gegen `setDefault(True)`
war strukturell blind dafür, denn den ruft niemand. Gemessen wird am
gebauten **und angezeigten** Fenster (`isDefault()` meldet vor dem `show()`
überall False).
