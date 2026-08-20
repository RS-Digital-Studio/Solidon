# Oberflächendurchsicht 19./20.08.2026 — was offen ist

Auftrag war, alles gründlich durchzugehen mit Blick auf Bedienbarkeit,
Funktionen, Übersichtlichkeit und modernes Aussehen — **auch das, was schon
einmal kontrolliert wurde** — und alle Funde zu beheben, egal wie klein.
Randbedingung: die Demo soll auf der Webseite bereitstehen.

Diese Datei sammelt, was **nicht** behoben ist, und warum. Was behoben ist,
steht in den Commits und in
`.claude/.state/oberflaechen-durchsicht-2026-08-19/BEHOBEN.md` — dort mit
Vorher-Messung, Nachher-Messung und dem Ergebnis der Gegenprobe.

## Der Stand in Zahlen

| | |
|---|---|
| Rohfunde aus den Durchsichtsläufen | 233 (eindeutig nach Titel), davon 43 „hoch", 100 „mittel", 90 „niedrig" |
| als Demo-Blocker markiert | 65 |
| behoben und festgenagelt | 69 Einträge in `BEHOBEN.md`, jeder mit Test |
| davon mit Gegenprobe belegt | alle, bei denen ein Test neu entstand |
| Gebiete der Durchsicht gelaufen | 11 von 19 |

Die Rohfunde sind **ungeprüft**. Erfahrungswert aus dieser Durchsicht: etwa
jeder fünfte hält der Prüfung am Code nicht stand, und zwei davon waren meine
eigenen.

## 1. Bewusst offen — drei Entscheidungen, keine Fehler

Diese drei sind gemessen und nicht behoben, weil der naheliegende Fix
nachweislich falsch oder die Frage eine Abwägung ist. Sie stehen auch in
`ROADMAP.md`.

### 1.1 Nackte Tasten gehören dem Fokus — außer Entf, und das ist zu wenig

`_BARE_KEYS` in `app/ui/main_window.py` kennt genau `Del`. Die Begründung
daneben („Entf war fensterweit gebunden und löschte den Körper, auch wenn der
Fokus im Verlauf lag") gilt wörtlich auch für `Pos1`: Gemessen mit Fokus im
Objektbaum und in der Verlaufsliste feuert Pos1 beide Male den Fensterbefehl
„Alles einpassen"; der Sprung zur ersten Zeile, den jede Liste unter dieser
Taste kennt, findet nicht statt.

**Der naheliegende Fix ist der falsche.** „Jede Sequenz ohne Zusatztaste wird
widget-gebunden" nähme den Ziffern 1 bis 6 ihre Wirkung, sobald der Fokus in
einer Liste steht — und das ist der Normalfall. An den Viewport zu binden geht
gar nicht: er hat `NoFocus` (nachgemessen), ein widget-gebundenes Kürzel würde
dort nie feuern. Was bleibt, ist eine Entscheidung je Taste.

Der zweite Teil desselben Funds **ist** behoben: im Skizzenmodus war Pos1
doppelt belegt und feuerte deshalb gar nicht (`3bf12fd`).

### 1.2 Der Startbildschirm braucht ein Höhenbudget

Drei Kachelspalten statt zwei und schmalere Außenränder haben den Rollweg auf
1920x1080 von 198 auf 16 Pixel gebracht (`571422e`). Auf 1600x900 bleiben 156.
Damit passt der Startbildschirm nicht überall ohne Rollen, und weiter kommt man
nicht durch Umschichten: Es fehlt eine Entscheidung darüber, **was kleiner
wird**. Kandidaten, gemessen: die Kachelhöhe (122 Pixel, davon 96
Vorschaubild), die Ablagefläche (140) und „Zuletzt geöffnet" mit seiner
Leerzeile. Jede einzelne kostet etwas — die Vorschau ist der Grund, aus dem die
Kacheln erkennbar sind.

### 1.3 Der Trennen-Bereich braucht die echte Plattform

Der Fund nennt 130 Punkte Totraum. Offscreen gemessen kommt das Gegenteil
heraus — die Leiste wünscht 146 Pixel und bekommt 24 —, weil Qt ohne
Schriftfamilien andere Metriken rechnet. Aus dem Offscreen-Lauf ist dieser Fund
nicht zu entscheiden; er braucht die echte Plattform, so wie die Abbildungen
sie brauchen.

## 2. Was ein Mensch entscheiden muss — die Demo

Keiner dieser Punkte liegt an der Oberfläche, und keiner lässt sich ohne
Entscheidung erledigen.

* **Die Webseite hat in keiner der sechs Sprachen einen Download.** Jeder
  Demo-Knopf ist eine Vorankündigung: 20 mailto-Stellen (`website/index.html`
  fünfmal, je dreimal in `en es fr it pt`).
* **Es gibt keine gebaute Datei.** Lokal fehlen PyInstaller (in keinem Extra
  von `pyproject.toml`), Inno Setup 6 und `packaging/build` mit dem
  kompilierten Prüfmodul.
* **Der CI-Paketjob hat `needs: suite`** und kommt hinter einer roten
  Linux-Suite nicht heran.
* **Kein Wort zur SmartScreen-Warnung**, obwohl der Bau sie selbst ankündigt.
  Eine unsignierte Setup-Datei bekommt sie; wer nichts davon weiß, hält sie für
  eine Warnung vor Schadsoftware.
* **In der Demo ist der Hauptknopf „Eintragen" für etwas, das es nicht gibt** —
  die Demo läuft ohne Schlüssel. „Solidon kaufen" ist dort der einzige Knopf
  mit Sinn.

Zu entscheiden: PyInstaller und Inno Setup installieren, einen Tag setzen,
unsigniert veröffentlichen — oder die Vorankündigung stehen lassen.

## 3. Zwei Beispielprojekte begrüßen mit Warnungen

Heute nachgemessen, beide stehen noch:

* **`weg3-generiert-aufbereiten`**: zehn Befunde, davon drei Warnungen —
  „Es gibt sehr kleine Einzelteile. Gelöscht wurde nichts.", „Das Modell ist
  nicht geschlossen." und „Kleinstteile wurden gelöscht." Die erste und die
  dritte widersprechen sich für den, der die Herkunft nicht liest; dass der
  Tooltip inzwischen den Schritt nennt, mildert es und behebt es nicht. Weg 3
  ist einer der vier Einstiege.
* **`dose-mit-deckel`**: „Die Passung sitzt loser als vorgesehen." Das
  Vorzeigebeispiel für Passungen zeigt eine verletzte Passung.

Beides sind Entscheidungen über **Beispielinhalte** (andere Ausgangsdatei,
andere Parameter), nicht über Code. Wer sie ändert, ändert `tools/make_examples.py`
und muss `tests/test_tour.py` mitziehen — die Erkennungswerte der Touren hängen
daran.

## 4. Ein Kürzelschema nennt falsche Tasten

Im Schema „Wie Fusion und Onshape" zeigt die Palette Tasten, die dort nicht
gelten: gemessen `translate_object` Menü „M" / Palette „Strg+T",
`drill_hole` „H" / „Strg+B", und für sechs weitere Operationen nennt sie keine,
obwohl das Menü eine zeigt. Grund: `palette_entries()` setzt das rohe
Registerkürzel, während der Menüeintrag es durch `shortcut_for(...)` schickt.

**Behoben ist nur die Schreibweise** („Del" → „Entf", `91f504a`), nicht die
Zuordnung. Der Fix ist klein, aber er berührt `palette_entries` und damit den
Kern: das Schema ist eine Einstellung der Oberfläche, und der Kern kennt sie
nicht. Wo die Umrechnung hingehört, ist eine Entwurfsfrage.

## 5. Acht Gebiete sind nie gelaufen

Von den 19 Gebieten der Durchsicht liegen elf als Rohfunde vor. Nie gelaufen:

`druckdialog` · `chat` · `skizze` · `viewport` · `webseite` ·
`barrierefreiheit` · `wartezeit` · `handbuch`

Die Workflow-Skripte liegen in
`.claude/.state/oberflaechen-durchsicht-2026-08-19/workflow-skripte/` und sind
ohne Prüfstufe gebaut; die Gebietsliste `AREAS` auf die acht kürzen und
starten. Der fertige Auftragstext für eine zweite Sitzung steht in
`AUFTRAG-ZWEITE-SITZUNG.md` daneben.

## 6. Wie man mit den 233 Rohfunden arbeitet

Zwei Messfallen haben in dieser Durchsicht je einen Fehlalarm erzeugt, und
beide kosten eine Stunde, wenn man sie nicht kennt:

* **`load_operations()` vor `build_application()`.** Sonst ist das Register
  leer, jedes Menü sieht kaputt aus, und man meldet ein fehlendes Menü.
* **`QScreen.grabWindow(window.winId())` statt `QWidget.grab()`.** OpenGL wird
  von `grab()` nicht erfasst; der Viewport ist im Bild schwarz, und man meldet
  eine leere Ansicht.

Dazu die Regel, die in dieser Durchsicht mehr gefunden hat als jede andere
Gewohnheit und jetzt in `.claude/rules/tests.md` steht: **jeder neue Test wird
einmal ohne den Fix gefahren.** Sie hat an einem Tag fünf Tests verworfen, die
überzeugend aussahen, und zweimal den Fix statt des Tests.

## 7. Zwei Fund-Hälften, die nicht stimmen

Damit sie niemand ein zweites Mal „behebt":

* **Die Beispielkachel springt beim Durchtabben nicht.** Der Fund schloss das
  aus dem Stilblatt (fehlende `padding`-Ausgleichsregel). Nachgemessen mit
  gesetztem Fokus: die drei Beschriftungen stehen auf denselben Koordinaten,
  null Verschiebung. Die Ränder der Kachel kommen aus ihrem **Layout**
  (`ROOMY`), nicht aus dem `padding` — der Rahmen wächst nach außen.
* **`setStretchLastSection(False)` allein macht den Objektbaum schlechter.**
  Der Fund schlug es als Fix vor. Gemessen: danach nimmt die *Maßspalte* 186
  von 258 Pixeln und der Name 70 — schlechter als die 128/128 vorher. Beide
  Spalten wollen Platz; die Frage ist das Verhältnis (`c6046d1`).

## 8. Die Messgrenze: der große Stapel hängt

`pytest tests/` ohne die fünf üblichen Fensterdateien bleibt reproduzierbar bei
88 Prozent stehen, an derselben Stelle:
`tests/test_style.py::test_an_icon_takes_its_colour_when_it_is_drawn`. Der Test
**allein** läuft in 0,16 s; jede Zweierkombination läuft durch
(`test_pose_session`+`test_style` 102 s, `test_operation_ui`+`test_style` 160 s,
`test_split_tool`+`test_style` 100 s). Erst die Häufung reißt.

Das ist die Grenze, die `suite-getrennt.sh` und der CI-Workflow seit dem
12.08.2026 beschreiben: zu viele VTK-Fenster in einem Prozess. Seit dem 19.08.
sind Fensterdateien dazugekommen. **Gemessen wird ab jetzt getrennt**, je
Fensterdatei ein Prozess — so wie die CI es tut.

## 9. Zwei Sitzungen, ein Arbeitsbaum

Am 19./20.08. haben zwei Sitzungen gleichzeitig am selben Arbeitsbaum
gearbeitet. Dreimal hat dabei eine die Änderungen der anderen in ihren Commit
gezogen (`051c4cb`, `34a6b34`, `b85364d`). Verloren ging nichts, aber die
Historie erzählt an drei Stellen etwas anderes als das, was passiert ist, und
zweimal war der Baum für Minuten fremd-rot (ein Syntaxfehler, ein fehlender
Import) — was jede eigene Messung in dieser Zeit unbrauchbar macht.

Pfadbeschränktes Committen (`git commit -F msg -- <pfade>`) schützt nur in eine
Richtung. Wer parallel arbeiten will, braucht `git worktree`.
