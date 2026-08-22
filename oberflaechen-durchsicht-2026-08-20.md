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

## 1. Bewusst offen — eine Entscheidung, kein Fehler

Hier standen am Vormittag drei Punkte; zwei davon sind noch am selben Tag
erledigt worden und stehen unten nur zur Klarstellung. Der übrige ist gemessen
und nicht behoben, weil er eine Abwägung verlangt und keinen Griff. Er steht
auch in `ROADMAP.md`.

### 1.1 Der Startbildschirm braucht ein Höhenbudget

Drei Kachelspalten statt zwei und schmalere Außenränder haben den Rollweg auf
1920x1080 von 198 auf 16 Pixel gebracht (`571422e`). Auf 1600x900 bleiben 156.
Damit passt der Startbildschirm nicht überall ohne Rollen, und weiter kommt man
nicht durch Umschichten: Es fehlt eine Entscheidung darüber, **was kleiner
wird**. Kandidaten, gemessen: die Kachelhöhe (122 Pixel, davon 96
Vorschaubild), die Ablagefläche (140) und „Zuletzt geöffnet" mit seiner
Leerzeile. Jede einzelne kostet etwas — die Vorschau ist der Grund, aus dem die
Kacheln erkennbar sind.

### Zwei Punkte, die hier standen und noch am selben Tag erledigt wurden

Sie stehen hier nur, damit niemand sie in einer alten Version dieser Datei für
offen hält:

* **Nackte Tasten** — entschieden je Taste, so wie der Punkt es verlangte: Pos1,
  Ende, Bild auf und Bild ab gehören dem Bedienelement mit dem Fokus, die
  Ziffern der Darstellungsarten bleiben Fensterbefehle (`23cc1ea`). Der Filter
  nimmt dafür das `ShortcutOverride`, das Qt vor jedem Kürzel an die Fokuskette
  schickt.
* **Der Trennen-Bereich** — auf der echten Plattform gemessen, wie der Punkt es
  verlangte: 109 Punkte Totraum, und die Zustandszeile bekam in ihrer Zeile
  **null** Bildpunkte, weil ihre waagerechte Politik `Ignored` war (`b66987b`).

## 2. Was ein Mensch entscheiden muss — die Demo

Stand nach dem Merge von `origin/main` am Abend des 20.08. nachgeprüft, Zeile
für Zeile. Drei der fünf Punkte, die hier standen, sind erledigt; **es fehlt
genau eine Sache, und die ist keine Codearbeit.**

**Was fehlt: ein gebautes Paket.** Lokal ist PyInstaller in keinem Extra von
`pyproject.toml` und nicht in `constraints.txt`; `packaging/build` mit dem
kompilierten Prüfmodul gibt es nicht. Ohne Paket bleibt die Webseite auf der
Warteliste stehen — gezählt: vier `mailto`-Verweise je `index.html`, in allen
sechs Sprachen.

**Was inzwischen bereitsteht:**

* `tools/make_download.py` nimmt die fertigen Pakete, kopiert sie nach
  `website/dl/`, rechnet Größe und SHA-256 daraus und schreibt beides in alle
  sechs `index.html`. Die Seite schaltet damit von der Warteliste auf den
  Download um, sobald es etwas zu laden gibt — und ohne Argumente räumt das
  Skript den Kasten wieder leer, wenn ein Paket zurückgezogen werden muss.
* Der Hinweis zur unsignierten Anwendung steht auf der Seite, versteckt bis zum
  Termin (`data-release-show`): für Windows der blaue Hinweis mit *Weitere
  Informationen → Trotzdem ausführen*, für macOS Gatekeeper und der Weg über
  die rechte Maustaste.
* Der Freischaltdialog verspricht in der Demo nichts mehr: „Eintragen" ist
  gesperrt, solange kein Schlüssel im Feld steht, und sagt im Tooltip warum —
  in der Demo also immer.

**Was offen bleibt und eine Entscheidung ist:** Der CI-Paketjob hat weiter
`needs: suite` (`.github/workflows/build.yml:161`) und kommt hinter einer roten
Linux-Suite nicht heran. Und jemand muss PyInstaller und Inno Setup 6
installieren, einen Tag setzen und unsigniert veröffentlichen — oder die
Warteliste stehen lassen.

## 3. Zwei Beispielprojekte begrüßten mit Warnungen — erledigt

Der Verdacht war, es handle sich um Entscheidungen über **Beispielinhalte**
(andere Ausgangsdatei, andere Parameter). Er war falsch: Hinter beiden stand
ein Fehler im Code, und beide sind behoben (`b5bd8d3`).

* **`dose-mit-deckel`** meldete „Die Passung sitzt loser als vorgesehen",
  gemessen 0,90 mm gegen 0,25 mm erwartet. `clearance` ist im ganzen Haus ein
  **Durchmessermaß** — ein Passstift bekommt seine Bohrung als
  `diameter + play`, die Passungsprüfung rechnet
  `hole_diameter - pin_diameter`. Nur der Deckelkragen wurde damit *radial*
  eingezogen und bekam so das Doppelte. Dazu kam `COLLAR_RELIEF = 0.2`, eine
  Zahlenkonstante für eine Toleranz — Regel 7 verbietet genau das, und sie
  untergrub die Kalibrierung (§28.3): Wer sein Material misst und 0,15 mm
  einträgt, bekam trotzdem 0,55 mm je Seite. Dass ein Kragen nicht klemmt, ist
  die Aufgabe des Gleitspiels aus dem Profil.
* **`weg3-generiert-aufbereiten`** zeigte drei Warnungen, zwei davon drei
  Schritte später behoben. `SETTLED_BY` (`scene/evaluate.py`) streicht einen
  Befund, sobald einer aus seiner Menge an einem **späteren** Schritt und am
  **selben Körper** steht. Gestrichen und nicht herabgestuft: „Das Modell ist
  nicht geschlossen" steht im Präsens und beschreibt einen Zustand, den es
  nicht mehr gibt. Übrig bleibt eine Warnung, und die stimmt: Kleinstteile
  wurden gelöscht.

`tools/make_examples.py` und `tests/test_tour.py` mussten dafür nicht angefasst
werden — die Beispieldateien tragen Operationen, keine Geometrie.
`test_no_example_greets_with_a_contradiction` hält alle neun gegen die drei
Befundcodes.

## 4. Ein Kürzelschema nannte falsche Tasten — erledigt

Im Schema „Wie Fusion und Onshape" zeigte die Palette Tasten, die dort nicht
gelten: **drei** Operationen nannten eine falsche — `translate_object` „Strg+T"
statt „M", `rotate_object` „Strg+R" statt „R", `drill_hole` „Strg+B" statt „H" —
und **sieben** nannten keine, obwohl das Schema ihnen eine gibt: `chamfer_edges`
„C", `fillet_edges` „F", `mirror_object` „Strg+M", `pattern` „P", `push_face`
„Q", `shell_exact` „S", `sketch_extrude` „E". Grund: `palette_entries()` setzt
das rohe Registerkürzel, während der Menüeintrag es durch `shortcut_for(...)`
schickt.

**Die Entwurfsfrage hat sich an der Kerntrennung entschieden.** Sie lautete, wo
die Umrechnung hingehört; die Antwort steht in Regel 1. Das Schema ist eine
Einstellung der Oberfläche, der Kern kennt sie nicht und darf sie nicht kennen —
also bleibt `palette_entries()` unberührt und liefert weiter das Register, und
die Umrechnung steht dort, wo auch das Menü sie hat: im Fenster, das die
Einstellung führt. Der Aufbau der Palettenzeilen ist dafür aus
`action_command_palette` in `MainWindow.palette_rows()` herausgezogen — hinter
dem modalen Dialog sieht keine Prüfung mehr etwas, und genau so ist der Fund
entstanden. `test_the_palette_teaches_the_keys_of_the_active_scheme` misst jetzt
alle zehn Tasten gegen die Belegung; ohne den Fix nennt er sie beim Namen.

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

## 8. Wie gemessen wird — und eine Fehldiagnose von mir

`pytest tests/` ohne die fünf üblichen Fensterdateien blieb am Nachmittag
zweimal reproduzierbar bei 88 Prozent stehen, an derselben Stelle:
`tests/test_style.py::test_an_icon_takes_its_colour_when_it_is_drawn`. Der Test
**allein** läuft in 0,16 s; jede Zweierkombination lief durch
(`test_pose_session`+`test_style` 102 s, `test_operation_ui`+`test_style` 160 s,
`test_split_tool`+`test_style` 100 s). Ich habe daraus die VTK-Grenze gelesen,
die `suite-getrennt.sh` seit dem 12.08.2026 beschreibt.

**Das war falsch.** Die Ursache lag in Arbeit, die zur Messzeit unfertig im Baum
lag: ein Ereignisfilter, der **je Fenster** installiert wurde, sodass die
Filterkette mit jedem gebauten Fenster wuchs — dieselbe Sitzung hat es später
selbst gemessen (`tests/test_ui.py` blieb bei 97 % stehen, zweimal, mit einem
Filter dann 223 Tests in 3:16) und behoben. Nach dieser Behebung läuft derselbe
Stapel bei mir über die 88 Prozent hinaus.

Was daraus bleibt, ist keine Grenze, sondern eine Regel: **Ein Hänger im
fremden Baum ist keine Aussage über den eigenen Code.** Wer messen will, prüft
zuerst, ob der Baum in sich stimmt (`ruff`, `mypy`, `git status`) — an diesem Tag
war er dreimal fremd-rot. Und für das Tor gilt weiter, was die CI tut: je
Fensterdatei ein Prozess (`suite-getrennt.sh`). So ist auch dieser Stand geprüft:
„Läufe mit Fehler: 0".

## 9. Zwei Sitzungen, ein Arbeitsbaum

Am 19./20.08. haben zwei Sitzungen gleichzeitig am selben Arbeitsbaum
gearbeitet. Dreimal hat dabei eine die Änderungen der anderen in ihren Commit
gezogen (`051c4cb`, `34a6b34`, `b85364d`). Verloren ging nichts, aber die
Historie erzählt an drei Stellen etwas anderes als das, was passiert ist, und
zweimal war der Baum für Minuten fremd-rot (ein Syntaxfehler, ein fehlender
Import) — was jede eigene Messung in dieser Zeit unbrauchbar macht.

Pfadbeschränktes Committen (`git commit -F msg -- <pfade>`) schützt nur in eine
Richtung. Wer parallel arbeiten will, braucht `git worktree`.
