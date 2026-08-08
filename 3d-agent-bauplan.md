# 3D-Agent — Bauplan v10

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
3D-Modelle. Non-destruktiver Operationsstack über einer Szene mit mehreren
Objekten, vollwertiger Viewport, Bausteinbibliothek, Rückkopplung aus Slicer
und Drucker. Veröffentlichung als Download; online nur Website und optionaler
Generierungs-Backend.

Spezifikation zur Abarbeitung durch einen Programmier-Agenten.
Begleitdateien: `AGENTS.md` (Repository-Regeln, immer lesen) und `ROADMAP.md`
(Arbeitsliste je Phase).

> **Wenn du nur drei Kapitel liest:** §1 Leitprinzipien, §2 Bedienkonzept,
> §9 Kernverträge. Das erste sagt, wonach entschieden wird, das zweite wofür,
> das dritte womit.

---

## Inhalt

**Warum und wofür** — §1 Leitprinzipien · §2 Bedienkonzept · §3
Ausführungsmodell · §4 Glossar und Sprachregelung · §5 Verteilungsmodell ·
§6 Die drei Säulen

**Aufbau** — §7 Schichten · §8 Paketstruktur · §9 Kernverträge · §10
Operationsregister · §11 Zahlen und Determinismus

**Datenmodell** — §12 Szenenmodell · §13 Projektparameter · §14 Passungen ·
§15 Auswertung · §16 Projektdatei · §17 Eingangsstufe und Rückfallketten

**Oberfläche** — §18 Viewport · §19 Bedienung und Barrierefreiheit · §20 Farbe

**Analyse und Agent** — §21 Feature-Erkennung · §22 Schichtanalyse · §23
Steckbrief · §24 Bausteinbibliothek · §25 Operationskatalog · §26
Agentenschicht · §27 Backends

**Ausgabe** — §28 Slicer-Rückkopplung · §29 Export · §30 B-Rep-Kern

**Qualität** — §31 Leistungsbudget · §32 Sicherheit · §33 Fehler und
Protokollierung · §34 Referenzdaten · §35 Testbarkeit · §36 Lizenzen · §37
Veröffentlichung · §38 Desktop-Spezifika · §39 Regelsammlung

**Umsetzung** — §40 Phasen · §41 Ausbaustufen · §42 Grenzen · §43 Nächster
Schritt

---

## 0. Änderungen gegenüber v9

**Skizzen mit Zwangsbedingungen (§30.1, P13)** — aus dem Nebensatz in §30 wird
eine eigene Phase. Der Anlass ist eine Produktentscheidung: so wenig
Fremdprogramme wie möglich, und das fremde CAD **vor** dem Import ist der
größte verbliebene Grund, ein zweites Programm zu öffnen. Dazu kommen die
Formgebungs-Operationen auf dem B-Rep-Kern (Formschräge, exakte Schale, Sweep,
Loft, exaktes Gewinde), ein Leistungsziel für den Solver (§31) und die
Verträge in §9. Der Slicer bleibt außen (§22.5), OpenSCAD bleibt Rückfallebene
— an der Nicht-bauen-Liste ändert sich nichts.

**Die erste Veröffentlichung wartet auf P13** (Entscheidung vom 31.07.2026):
der Launch führt die Skizzen als Kernargument. Die Veröffentlichungsreste aus
P8 (Zertifikat, Vertrieb, Website, Betatest) laufen parallel weiter.

## 1. Leitprinzipien

Neun Sätze, an denen jede Entscheidung gemessen wird.

1. **Jede Operation ist manuell bedienbar.** Die KI ruft exakt dieselben
   Funktionen wie ein Menüeintrag.
2. **Non-destruktiv.** Nie Geometrie überschreiben, sondern den
   Operationsstack fortschreiben.
3. **Alles genau einmal deklariert.** Ops, Bausteine, Profile, Texte haben je
   eine Quelle; alle Oberflächen werden daraus erzeugt.
4. **Reproduzierbar.** Gleiche Datei, gleiche Bibliotheksversionen, gleiches
   Ergebnis. Zufall bekommt einen gespeicherten Startwert.
5. **Die KI erzeugt niemals Koordinaten.** Sie verweist auf erkannte Features,
   benutzt Projektparameter und setzt geprüfte Bausteine ein.
6. **Nie stillschweigend raten** — weder die Zuordnung noch der Agent. Bei
   Mehrdeutigkeit wird angehalten und gefragt.
7. **Deterministische Geometrie, probabilistische Absicht.** Das LLM
   interpretiert die Anfrage. Die Geometrie rechnet Code.
8. **Vollständig ohne Konto und ohne Netz nutzbar.** Gehostete Dienste sind
   Bequemlichkeit, nie Voraussetzung.
9. **Der Kern kennt keine Oberfläche.** Keine Qt-Einbindung unterhalb von
   `ui`. Alles Rechnende ist ohne Fenster aufrufbar.

---

## 2. Bedienkonzept

Die Anwendung ist vielseitig — genau deshalb muss die Oberfläche einfach
bleiben. Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche.

### 2.1 Das Versprechen

**Nichts ist endgültig.** Jede Handlung ist eine Op, jede Op ist rücknehmbar,
jeder Wert nachträglich änderbar. Das ist der eigentliche Gewinn des
non-destruktiven Aufbaus — und er muss spürbar sein, nicht bloß vorhanden.
Praktisch heißt das: keine Bestätigungsdialoge vor rücknehmbaren Handlungen,
kein „Möchten Sie wirklich", keine Sackgassen.

### 2.2 Drei Hauptwege

Alles Weitere ist Ausbau dieser drei. Sie müssen ohne Handbuch gehen.

**Weg 1 — Fremdes Modell anpassen** (der häufigste Fall)
Datei ziehen und ablegen → Einheitenrückfrage, falls nötig → Modell steht,
Prüfbericht sichtbar → Fläche oder Bohrung anklicken → im Chat sagen, was
werden soll, oder aus dem Kontextmenü wählen → Vorschau als
Vorher/Nachher → übernehmen → exportieren.

**Weg 2 — Neu konstruieren**
Neues Projekt → beschreiben, was gebraucht wird → Agent legt Parameter an und
setzt Bausteine → Parameterleiste zeigt die Hauptmaße → an den Zahlen drehen,
Modell folgt sofort → exportieren.

**Weg 3 — Generieren**
Text oder Bild → Mesh → Reparaturkette läuft automatisch → Prüfbericht →
gegebenenfalls teilen und verstiften → exportieren.

Diese drei Wege sind je ein Beispielprojekt (§37) und je eine
Abnahmeprüfung (§40).

### 2.3 Die ersten fünf Minuten

- **Kein leerer Startbildschirm.** Zuletzt geöffnete Projekte, die drei
  Beispielprojekte, ein großes Ablagefeld für Dateien.
- **Ziehen und Ablegen funktioniert überall** — auf das Fenster, auf den
  Viewport, auf den Objektbaum.
- **Die Erstinbetriebnahme fragt das Nötigste** (Sprache, Drucker, Material)
  und lässt alles andere auf Vorgaben stehen. Sie ist übersprings- und
  jederzeit nachholbar.
- **Ohne KI-Zugang läuft alles außer dem Chat.** Kein Nörgeln, kein
  Werbebanner — ein Hinweis an der Chatleiste, mehr nicht.

### 2.4 Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und einen aufklappbaren Bereich
„Weitere Einstellungen". Vorn stehen die zwei bis drei Werte, die man
tatsächlich ändert; hinten Toleranzen, Auflösungen, Rückfallverhalten.

Die Vorgaben kommen aus dem Drucker- und Materialprofil und sind so gewählt,
dass die Vorderseite in den meisten Fällen genügt. **Eine gute Vorgabe ist
mehr wert als eine gute Einstellmöglichkeit.**

### 2.5 Fensterschema

Sechs Bereiche wären zu viel für ein Fenster. Deshalb ein festes Schema mit
höchstens drei sichtbaren Zonen:

```
┌──────────────────────────────────────────────────────────┐
│ Werkzeugleiste                                           │
├──────────────┬───────────────────────────┬───────────────┤
│ Links        │                           │ Rechts        │
│ ┌──────────┐ │                           │ ┌───────────┐ │
│ │Objektbaum│ │        Viewport           │ │  Chat     │ │
│ ├──────────┤ │                           │ │    oder   │ │
│ │Parameter │ │                           │ │ Prüfbe-   │ │
│ ├──────────┤ │                           │ │ richt     │ │
│ │Verlauf   │ │                           │ └───────────┘ │
│ └──────────┘ │                           │               │
├──────────────┴───────────────────────────┴───────────────┤
│ Statusleiste: Maße · Auswahl · Fortschritt · Warnungen   │
└──────────────────────────────────────────────────────────┘
```

- **Links** drei einklappbare Abschnitte, nicht drei Fenster
- **Rechts** ein Bereich mit Umschaltung zwischen Chat und Prüfbericht — beide
  gleichzeitig braucht niemand, und die Umschaltung springt automatisch zum
  Bericht, wenn eine Warnung entsteht
- **Rechts ist ganz ausblendbar.** Ein Tastendruck, und der Viewport ist
  Vollbild.
- Keine Betriebsarten, keine Umschaltung zwischen „Bearbeiten" und
  „Konstruieren". Es gibt einen Zustand, und der ist die Szene.

### 2.6 Entdeckbarkeit

- **Befehlspalette** über eine Taste: alles aus dem Register per Suche
  erreichbar, mit Kürzel daneben — so lernt man die Kürzel nebenbei.
- **Kontextmenü am Feature**: Klick auf eine Bohrung bietet genau die Ops an,
  die auf Bohrungen anwendbar sind. Der kürzeste Weg vom Sehen zum Tun.
- **Bausteinkatalog mit Vorschaubildern** statt einer Namensliste. Eine
  Bibliothek, die man nicht sieht, existiert für den Nutzer nicht.
- **Der Chat ist auch ein Suchfeld.** „Wie mache ich das Loch größer?"
  beantwortet der Agent mit dem Vorschlag *und* dem Hinweis, wo die Funktion
  im Menü steht.

### 2.7 Fehler als Vorschlag

Ein Fehler endet nie mit „fehlgeschlagen". Er nennt in dieser Reihenfolge:
was nicht ging, warum, was jetzt möglich ist — mit anklickbaren
Handlungen.

> Die Differenz ist fehlgeschlagen, weil das Modell an drei Stellen offen ist.
> **[Reparieren und erneut versuchen]  [Stellen zeigen]  [Abbrechen]**

Kein Stapelabzug im Nutzerdialog. Der gehört ins Protokoll und in den
Fehlerbericht (§33).

### 2.8 Rückmeldung und Wartezeit

- Unter 0,2 s: nichts anzeigen
- Bis 2 s: Mauszeiger und Statusleiste
- Darüber: Fortschritt in der Statusleiste mit **Abbrechen**, Oberfläche
  bedienbar
- Über 10 s: zusätzlich eine Schätzung, wenn möglich

Die letzte gültige Darstellung bleibt sichtbar (§15.3) — nie ein leerer
Viewport, nie ein blockierendes Fenster.

### 2.9 Maus und Navigation

Vorgabe folgt der Slicer-Gewohnheit: linke Taste wählt, rechte oder mittlere
Taste dreht, Umschalt plus Ziehen schiebt, Rad zoomt auf den Mauszeiger. Zwei
Alternativschemata (CAD-typisch, Blender-typisch) stehen in den Einstellungen
— das kostet fast nichts und erspart Umgewöhnung.

---

## 3. Ausführungsmodell

Der Plan wird von einem Programmier-Agenten umgesetzt. Zeitaufwand ist kein
Kriterium; Eindeutigkeit und maschinelle Abnahme sind es.

- **Abnahmekriterien statt Zeitschätzungen.** Jede Phase in §40 endet mit
  Bedingungen, die grün sein müssen.
- **Tests sind die Definition von fertig.** Für jede Geometrieoperation
  existiert ein Test mit festem Eingangs-Mesh (§34) und erwarteten Kennzahlen.
- **Kleine Schritte.** Nach jedem Schritt läuft die vollständige Suite.
- **Verbote sind Prüfungen, keine Absichten.** Jede harte Regel aus
  `AGENTS.md` hat einen Test.
- **Verträge zuerst.** Bei jedem neuen Modul steht die Signatur aus §9 fest,
  bevor die Umsetzung beginnt.
- **Konsistenz vor Vollständigkeit.** Acht Ops, die überall identisch
  auftauchen, schlagen zwanzig, die auseinanderdriften.
- **Keine stillen Erweiterungen.** Neue Abhängigkeiten, Ops, Formatversionen
  und Parameterfunktionen sind an Checklisten in `AGENTS.md` gebunden.

---

## 4. Glossar und Sprachregelung

### 4.1 Sprachen

| Bereich | Sprache |
|---|---|
| Bezeichner im Code, Dateinamen, Modulnamen | Englisch |
| Docstrings und Kommentare | **Deutsch** |
| Schlüssel in Projektdatei und Schemata | Englisch |
| Oberflächentexte | Deutsch und Englisch über `tr()` |
| Doku für Nutzer, dieser Bauplan | Deutsch |
| Commit-Nachrichten | **Deutsch** |

Ohne diese Festlegung entsteht ein Gemisch wie `bausteinRegistry` oder
`wall_staerke`. Der Konsistenztest prüft Bezeichner stichprobenartig gegen
eine Liste deutscher Stämme.

Docstrings und Kommentare standen hier bis „Doku nachziehen" (b2e6e28) auf
Englisch. Die Zeile ist geändert, weil die Trennung nicht zwischen Code und
Prosa verläuft, sondern zwischen **Maschine und Mensch**: Bezeichner liest der
Interpreter, Kommentare liest nur Robert. `app/`, `tests/` und `tools/` sind
vollständig nachgezogen; die Prüfung bleibt auf Bezeichner beschränkt, weil nur
die eindeutig entscheidbar ist.

### 4.2 Begriffe

| Deutsch (Doku) | Code | Bedeutung |
|---|---|---|
| Operation, Op | `Operation` / `op` | eine Änderung im Stack |
| Transaktion | `Transaction` | Gruppe von Ops, gemeinsam rücknehmbar |
| Szene | `Scene` | alle Objekte plus Parameter, Passungen, Stack |
| Objekt | `SceneObject` | ein Körper in der Szene |
| Baustein | `Part` | parametrisches Fertigteil aus der Bibliothek |
| Feature | `Feature` | erkannte Bohrung, Fläche, Kante |
| Provenienz | `provenance` | Herkunft eines Features oder einer Op |
| Steckbrief | `digest` | Textbeschreibung der Szene für den Agenten |
| Prüfbericht | `report` | Befunde aus Eingangsstufe, Ops und Prüfungen |
| Rückfallkette | `solver chain` | Stufen bei gescheiterter Boolescher Op |
| Passung | `Fit` | benannte Beziehung zweier Features |
| Profil | `Profile` | Drucker- oder Materialeinstellungen |
| Regelsammlung | `rules` | Druckregeln für Agent und Prüfungen |

Diese Zuordnung ist verbindlich. Ein neuer Begriff kommt zuerst in diese
Tabelle, dann in den Code.

---

## 5. Verteilungsmodell

| | |
|---|---|
| **Produkt** | Desktop-Anwendung, als Download veröffentlicht |
| **Online** | Website mit Doku und Downloads |
| **Online, optional** | gehosteter Generierungs-Backend für Nutzer ohne GPU |
| **Ausdrücklich nicht** | Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage |

Wichtigster Nebeneffekt: **Auf dem Server läuft niemals Code, den ein LLM
erzeugt hat.** OpenSCAD läuft ausschließlich lokal; der gehostete Backend
nimmt nur Text oder Bild und gibt ein Mesh zurück.

---

## 6. Die drei Säulen

| | **A — Konstruieren** | **B — Generieren** | **C — Bearbeiten** |
|---|---|---|---|
| Eingabe | Beschreibung + Maße | Text oder Bild | STL/3MF/OBJ + Anweisung |
| Motor | LLM → Op-Liste aus Bausteinen, ersatzweise OpenSCAD | ComfyUI lokal *oder* gehostet | Feature-Erkennung + Boolesche Ops |
| Ergebnis | parametrisch, maßhaltig | organisch, texturiert | modifiziertes Mesh |
| Ausführungsort | immer lokal | lokal oder Backend | immer lokal |

Säule A hat zwei Ausgabeformen in verbindlicher Reihenfolge:

1. **Op-Liste aus Bausteinen und Primitiven** — bevorzugt. Bleibt im Kern,
   schemageprüft, im Stack sichtbar, rücknehmbar, erzeugt
   Provenienz-Features und kann Projektparameter benutzen.
2. **OpenSCAD** — Rückfallebene für Freiformen. Ergebnis wird Quelle im Stack.

---

## 7. Schichtenaufbau

```
╔══ ui ══════════════════════════════════════════════════════╗
║  PySide6 — Viewport │ Objektbaum │ Parameter │ Verlauf │    ║
║             Chat / Prüfbericht │ Statusleiste              ║
╚══════════════════════┬═════════════════════════════════════╝
                       │  einzige erlaubte Richtung ↓
╔══ core ═══════════════════════════════════════════════════════╗
║  Operationsregister (§10) — Quelle für alle Oberflächen       ║
║  Szenenmodell — Objekte, Parameter, Passungen, Op-DAG,        ║
║  Auswertung, Undo/Redo, Caching, Projektdatei                 ║
║      ┌──────────────┬──────────────────┬──────────────────┐   ║
║  ┌───▼─────────┐ ┌──▼──────────────┐ ┌─▼───────────────┐      ║
║  │Geometriekern│ │ Wahrnehmung     │ │ Wissensbasis    │      ║
║  │manifold3d   │ │ Features,       │ │ Bausteine (Py), │      ║
║  │trimesh      │ │ Steckbrief,     │ │ Normteile,      │      ║
║  │(OpenSCAD)   │ │ Analysekarten   │ │ Profile, Regeln │      ║
║  │(B-Rep §30)  │ └──┬──────────────┘ └─────────────────┘      ║
║  └─────────────┘    │ speist Viewport UND Agent               ║
║              ┌──────▼─────────────────────────────────────┐   ║
║              │ Agentenschicht — LLM, Werkzeuge, Kontext   │   ║
║              └──────┬─────────────────────────────────────┘   ║
╚═════════════════════┼═════════════════════════════════════════╝
              ┌───────▼────────────────────┐
              │ Backends (austauschbar §27)│
              │ LLM: Cloud │ lokal         │
              │ Mesh: ComfyUI │ gehostet   │
              └────────────────────────────┘
```

---

## 8. Paketstruktur und Kernabgrenzung

```
app/
  core/
    registry/    # Operationsregister, Schemata, Erzeugung der Oberflächen
    scene/       # Szene, Parameter, Passungen, Op-DAG, Auswertung,
                 # Projektdatei, Migrationen
    geom/        # Operationen, Geometriekerne, Rückfallketten
    slice/       # Schichtanalyse (§22)
    ingest/      # Eingangs-Normalisierung
    perceive/    # Feature-Erkennung, Analysekarten, Steckbrief
    knowledge/   # Bausteine, Normteile, Profile, Regelsammlung
    agent/       # LLM-Anbindung, Werkzeuge, Kontextverwaltung
    backends/    # LLM- und Mesh-Backends hinter einer Schnittstelle
    export/      # Schreiben, Slicer-Übergabe, Namensschema
    errors.py    # Ausnahmehierarchie (§33)
    types.py     # Kernverträge (§9)
  ui/            # PySide6 — darf core benutzen, nie umgekehrt
  cli/           # Kommandozeilen-Einstieg auf core
  i18n/
  tests/
    data/        # Referenzkorpus (§34)
```

**Die Regel:** `core` importiert niemals aus `ui`. Ein Test importiert `core`
ohne installiertes Qt; bricht er, ist die Trennung verletzt.

---

## 9. Kernverträge

Die Signaturen, an denen sich alle Module ausrichten. Sie stehen in
`core/types.py` und werden vor der ersten Umsetzung festgelegt.

```python
# ---- Geometrie und Objekte -------------------------------------------
@dataclass(frozen=True)
class Feature:
    id: str  # "hole_3" oder "op4.pin_1"
    kind: Literal["hole", "face", "edge_loop", "pin", "thread"]
    provenance: Literal["detected", "generated"]
    params: dict  # Durchmesser, Achse, Tiefe, Fläche …
    face_indices: tuple[int, ...]


@dataclass
class SceneObject:
    id: str
    name: str
    mesh: Mesh  # Hülle um manifold3d/trimesh
    kind: Literal["mesh", "brep"]
    features: dict[str, Feature]
    material_slots: list[MaterialSlot]
    created_by: int  # Op-Nummer
    visible: bool = True


@dataclass
class Scene:
    objects: dict[str, SceneObject]
    parameters: dict[str, Parameter]
    fits: list[Fit]
    profile: Profile
    report: Report


# ---- Operationen -----------------------------------------------------
@dataclass
class OpContext:
    scene: Scene  # nur lesend
    inputs: list[SceneObject]
    params: BaseParams  # validiertes Schema
    profile: Profile
    quality: Literal["draft", "fine"]
    seed: int | None
    progress: ProgressFn  # (fraction: float, text: str) -> None
    ask: AskFn  # (question: str, choices: list[str]) -> str
    cancelled: CancelToken


@dataclass
class OpResult:
    outputs: list[SceneObject]
    solver: SolverInfo | None  # verwendete Rückfallstufe
    findings: list[Finding]  # Warnungen und Hinweise für den Bericht


OpFn = Callable[[OpContext], OpResult]


# ---- Schichtanalyse (§22) --------------------------------------------
@dataclass(frozen=True)
class LayerInfo:
    z: float
    contours: tuple[Polygon, ...]
    area: float
    overhang_area: float
    islands: tuple[Polygon, ...]
    min_width: float


@dataclass(frozen=True)
class SliceResult:
    layers: tuple[LayerInfo, ...]
    support_volume: float
    first_layer_area: float
    source: Literal["internal", "gcode"]  # nie vermischen (§22.5)


# ---- Skizzen (§30.1) -------------------------------------------------
@dataclass(frozen=True)
class SketchElement:
    kind: Literal["line", "arc", "circle", "point"]
    points: tuple[tuple[float, float], ...]  # Bedeutung je kind


@dataclass(frozen=True)
class SketchConstraint:
    kind: Literal[
        "distance",
        "coincident",
        "horizontal",
        "vertical",
        "parallel",
        "perpendicular",
        "tangent",
        "symmetric",
        "fixed",
    ]
    targets: tuple[int, ...]  # Punktindizes über die flache Punktliste der Skizze
    value: str = ""  # Maß als Ausdruck der Grammatik (§13), kein eval


@dataclass(frozen=True)
class Sketch:
    plane: str  # "plane:xy" | "plane:xz" | "plane:yz" | "feature:<id>"
    elements: tuple[SketchElement, ...]
    constraints: tuple[SketchConstraint, ...]


def solve_sketch(sketch: Sketch, params: "ParameterValues") -> "SolvedSketch":
    """Deterministisch, ohne Zufall. Unterbestimmt meldet die Freiheitsgrade
    als Befund; überbestimmt oder widersprüchlich hält an und nennt das
    kollidierende Bedingungspaar (Regel 17)."""
```

**Vier Regeln, die aus diesen Verträgen folgen:**

1. **`OpContext.scene` ist nur lesend.** Eine Op erzeugt neue Objekte, sie
   ändert keine bestehenden. Damit ist Leitprinzip 2 in der Typebene verankert.
2. **Jede Op meldet `findings` statt zu protokollieren.** Der Kern entscheidet,
   was daraus im Bericht und im Steckbrief erscheint.
3. **`progress`, `ask` und `cancelled` sind Teil des Vertrags**, nicht Zugriffe
   auf globale Objekte — das ist die technische Absicherung der Kerntrennung.
4. **`quality` reicht durch.** Jede Op muss beide Stufen beherrschen, notfalls
   indem sie sie gleich behandelt.

Weitere feste Verträge: `PartFn` für Bausteine (§24.1), `MeshBackend` und
`LLMBackend` für Backends (§27), `Migration` für Formatwechsel (§16.2).

---

## 10. Operationsregister

Eine Operation wird genau einmal deklariert; alles Weitere wird erzeugt.

```python
@register_op(
    name="resize_hole",
    title=_("Bohrung ändern"),
    category="holes",
    params=ResizeHoleParams,
    reversible=True,
    consumes=1,
    produces=1,
    applies_to=["hole"],  # steuert das Kontextmenü am Feature
    touches_features=True,
    deterministic=True,
    shortcut="Ctrl+Shift+B",
    doc=_("Ändert den Durchmesser einer erkannten Bohrung."),
)
def resize_hole(ctx: OpContext) -> OpResult: ...
```

| Ausgabe | Woraus |
|---|---|
| Menüeintrag und Dialog | `title`, `category`, Parameterschema |
| Kontextmenü am Feature | `applies_to` |
| Befehlspalette und Kürzel | `title`, `doc`, `shortcut` |
| Kommandozeilen-Befehl | `name`, Parameterschema |
| Tool-Schema für den Agenten | `name`, `doc`, JSON-Schema aus `params` |
| Doku-Abschnitt | alles zusammen |
| Prüfungen im Stack | `consumes`/`produces`, `reversible`, `deterministic` |

**Konsistenztest**: Jede Op erscheint in allen Ausgaben, besitzt Schema,
Geometrietest und übersetzte Texte; kein Kürzel doppelt; nicht-deterministische
Ops führen einen Startwert; `applies_to` nennt nur bekannte Feature-Arten.

**Parameterschema** trägt Grenzen, Einheiten, Vorgabewerte und die Zuordnung
zu Vorder- oder Rückseite des Dialogs (§2.4) — dieselbe Definition validiert
Dialog, Kommandozeile und Agentenaufruf.

---

## 11. Zahlen, Einheiten, Toleranzen, Determinismus

### 11.1 Einheiten
Der Kern rechnet **ausschließlich in Millimetern** und in doppelter
Genauigkeit. Eine andere Anzeigeeinheit ist reine Oberflächensache und
erreicht den Kern nie. Umrechnungen passieren genau zweimal: beim Import
(§17.1) und in der Anzeige.

### 11.2 Drei benannte Toleranzen

| Name | Größenordnung | Wofür |
|---|---|---|
| `EPS_GEOM` | 1e-6 mm | koinzidente Punkte, Nullflächen, Verschweißen |
| `EPS_DISPLAY` | 0,01 mm | Rundung in Bemaßung, Steckbrief, Berichten |
| `EPS_MATCH` | relativ, ~0,5 % der Modelldiagonale | Feature-Vergleich |

Merkregel: **absolut für Fertigung, relativ für Vergleiche.** Gerundet wird nur
in der Anzeige. Fließkommazahlen werden nie mit `==` verglichen.

### 11.3 Determinismus
Vier Stellen sind randomisiert: Jitter-Rückfallstufe (§17.2),
Farbquantisierung (§20), Abtastung der Orientierungssuche (§28.2) und die
konvexe Zerlegung beim Auto Split. Jede bekommt einen **Startwert, der in der
Op gespeichert wird**, ist im Register als `deterministic=False` gekennzeichnet
und liefert bei gleichem Startwert dasselbe Ergebnis. Ohne diese Regel ist
Leitprinzip 4 nicht haltbar und ein Fehlerbericht reproduziert nichts.

---

## 12. Szenenmodell

```json
{
  "format_version": 5,
  "app_version": "0.4.1",
  "libs": {"manifold3d": "3.2.1", "trimesh": "4.9.0"},
  "parts_version": "7",
  "scene": {"printer": "centauri-carbon-2", "material": "petg"},
  "parameters": {
    "breite": {"value": 84.0, "unit": "mm", "min": 40, "max": 200,
               "title": "Breite"},
    "hoehe":  {"value": 22.0, "unit": "mm", "min": 10}
  },
  "sources": {
    "src_1": {"type": "import", "path": "sources/halterung.stl",
              "sha256": "…",
              "ingest": {"unit": "mm", "scale": 1.0, "welded": true},
              "origin": {"url": "…", "license": "CC BY-NC 4.0",
                         "author": "…", "retrieved": "2026-07-20"}}
  },
  "fits": [
    {"name": "stift_1", "a": "obj_2:op5.pin_1", "b": "obj_3:op5.hole_1",
     "type": "clearance", "tolerance": "auto:petg"}
  ],
  "transactions": [
    {"id": "t1", "title": "Import und Reparatur", "origin": {"by": "user"},
     "ops": [1, 2]},
    {"id": "t2", "title": "Teilen und verstiften",
     "origin": {"by": "agent", "model": "…", "prompt_version": "3",
                "rules_version": "7", "temperature": 0.2},
     "ops": [3, 4, 5, 6]}
  ],
  "ops": [
    {"id": 1, "op": "load",        "in": [],                "out": ["obj_1"],
     "params": {"source": "src_1"}},
    {"id": 2, "op": "repair",      "in": ["obj_1"],         "out": ["obj_1"],
     "params": {"fill_holes": true}},
    {"id": 3, "op": "insert_part", "in": ["obj_1"],         "out": ["obj_1"],
     "params": {"part": "heatset_m4", "anchor": "face_1", "mode": "subtract"}},
    {"id": 4, "op": "split_plane", "in": ["obj_1"],         "out": ["obj_2","obj_3"],
     "params": {"axis": "z", "position": "=@hoehe/2"}},
    {"id": 5, "op": "add_pins",    "in": ["obj_2","obj_3"], "out": ["obj_2","obj_3"],
     "params": {"count": 3, "d": 4.0, "clearance": "auto:petg"},
     "solver": {"strategy": "direct"}, "seed": 20260727},
    {"id": 6, "op": "arrange_bed", "in": ["obj_2","obj_3"], "out": ["obj_2","obj_3"],
     "params": {"spacing": 5.0}}
  ]
}
```

Der DAG über `in`/`out` bildet Teilen (1 → 2) und Vereinigen (2 → 1) ab; der
Stack bleibt linear darstellbar. Drei Indirektionen tragen das Modell:
`"auto:petg"` für Toleranzen, `"=@hoehe/2"` für Parameter (§13), `solver` und
`seed` für Reproduzierbarkeit (§11.3, §17.2).

---

## 13. Projektparameter

Benannte Größen auf Szenenebene, auf die Ops verweisen. Damit wird aus jedem
Projekt eine Vorlage: „dieselbe Halterung, andere Maße" ist ein Zahlendialog
statt einer neuen Sitzung.

- **Verweis** `"@breite"` oder Ausdruck `"=@breite/2 - @wandstaerke"`
- **Ausdrücke sind eingeschränkt**: Zahlen, Parameter, `+ - * /`, Klammern,
  `min`, `max`, `round`, `abs`. Eigener Auswerter über eigener Grammatik —
  **kein `eval`**, auch nicht abgesichert (§32).
- **Zyklen** werden beim Setzen erkannt und abgelehnt.
- **Parameterleiste** links: Name, Wert, Einheit, Schieberegler bei
  begrenztem Bereich. Änderung rechnet nur die abhängigen Zweige neu (§15).
- **Der Agent legt Parameter an, statt Zahlen zu streuen** — verpflichtend,
  sobald ein Wert zweimal vorkommt oder erkennbar eine Hauptabmessung ist. Die
  Agenten-Suite misst es.
- **Vorlagen** ergeben sich fast von selbst: Ein Projekt ohne Quellen, nur mit
  Parametern und Bausteinen, ist eine Vorlage (§41).

---

## 14. Passungsbeziehungen

Objekte sind sonst unabhängig, und ein Fehler fällt erst beim Zusammenbau auf.

```json
{"name": "stift_1", "a": "obj_2:op5.pin_1", "b": "obj_3:op5.hole_1",
 "type": "clearance", "tolerance": "auto:petg"}
```

- **Arten**: `clearance` (Spiel), `press` (Presspassung), `thread` (Gewinde),
  `flush` (bündig, für Flächen)
- **Prüfung bei jeder Auswertung**: Entspricht die Differenz der
  Profiltoleranz im Rahmen von `EPS_GEOM`? Verletzungen erscheinen im
  Prüfbericht, im Steckbrief und als Analysekarte (§18.4), nie stillschweigend.
- **Auto Split legt die Paare automatisch an** — dort entstehen sie ohnehin.
- **Der Agent kann Paare anlegen**; die Suite prüft, ob er es tut.

---

## 15. Auswertung und Neuberechnung

### 15.1 Auswertung als reine Funktion
`Stack + Quellen + Parameter + Profile + Startwerte → Szene`. Kein versteckter
Zustand, keine Seiteneffekte. Zweimal ausgewertet ergibt zweimal dasselbe.

### 15.2 Geänderte Objektzahl
Liefert eine Op nach einer Änderung mehr oder weniger Objekte als zuvor:
gleiche Anzahl → Bindung über die Position in `out`; abweichende Anzahl →
nachfolgende Ops, die auf entfallene Objekte zeigen, gelten als
**unerfüllbar**, die Kette hält an, der Nutzer wählt zwischen neu zuordnen und
verwerfen. Kein automatisches Nachrücken.

### 15.3 Angehaltene Kette
Der Viewport zeigt **den letzten vollständig gerechneten Zustand**, nie ein
leeres Fenster, dazu einen Hinweis in der Statusleiste und die betroffenen Ops
im Verlauf markiert. Alles davor bleibt bedienbar.

### 15.4 Keine Verzweigungen
Eine Änderung nach einem Undo verwirft die abgeschnittenen Ops — mit
Rückfrage, sobald es mehr als eine ist. Verzweigungen stehen in §41.

### 15.5 Transaktionen
Mehrere Ops können als benannte Gruppe eingetragen werden. **Undo nimmt die
ganze Gruppe.** Jeder Agentenvorschlag ist genau eine Transaktion — sonst muss
der Nutzer achtmal rückgängig machen, was der Agent einmal vorgeschlagen hat.
Manuelle Operationen sind Einzeltransaktionen. Die Transaktion trägt Titel und
Herkunft (§26.4) und ist die Einheit, auf die sich Verlauf, Differenzansicht
und Chatverlauf beziehen.

### 15.6 Abbruch und Nebenläufigkeit
Eine laufende Berechnung ist jederzeit abbrechbar; der Stack bleibt auf dem
letzten vollständig gerechneten Stand — **keine halb angewandten Ops**. **Ein
Rechenlauf je Dokument**; weitere Anforderungen ersetzen die wartende
(Entprellung). Der Cache wird erst nach vollständigem Durchlauf geschrieben.

---

## 16. Projektdatei

### 16.1 Container
```
projekt.p3d           (ZIP)
  project.json        # Stack, Parameter, Passungen, Transaktionen
  sources/            # eingebettete Quell-Meshes
  report.json         # letzter Prüfbericht
  thumb.png           # Vorschaubild für Dateidialoge
```
Quellen wahlweise eingebettet oder verlinkt; **für die Weitergabe ist
Einbetten die Vorgabe**. Prüfsummen in beiden Fällen, beim Laden verifiziert.

### 16.2 Version und Reproduzierbarkeit
- **`format_version`**: gleich → laden, älter → Migrationskette, neuer →
  freundlich ablehnen statt halb zu laden
- **Migrationen** als eigene Funktionen mit Test und eingecheckter
  Beispieldatei je Altversion
- **`libs`** hält fest, womit gerechnet wurde; Abweichung ergibt einen Hinweis,
  keinen Abbruch
- **`parts_version`** hält den Stand der Bausteinbibliothek fest (§24.4).
  Beim Öffnen mit neuerem Stand nennt der Hinweis **welche benutzten Bausteine
  sich geändert haben**, nicht nur dass sich etwas geändert hat
- **Ein Fehlerbericht ist der Container** — er reproduziert den Fehler exakt,
  einschließlich Startwerten und Rückfallstufen

### 16.3 Herkunft importierter Modelle
Heruntergeladene Modelle tragen Lizenzen, oft mit Einschränkung für
kommerzielle Nutzung. Jede Quelle kann `origin` führen: URL, Titel, Urheber,
Lizenz, Abrufdatum. Beim Import anbieten, nicht erzwingen. **Beim Export ein
Hinweis**, wenn eine beteiligte Quelle eine Einschränkung trägt — einmal,
sachlich, ohne Belehrung.

---

## 17. Eingangsstufe und Rückfallketten

### 17.1 Eingangsstufe
Jede geladene Datei durchläuft dieselbe Kette; das Ergebnis steht in `sources`:

1. **Einheit bestimmen.** STL kennt keine Einheiten. Heuristik über die
   Bounding Box; bei Verdacht **nachfragen** statt annehmen.
2. **Vertices verschweißen** mit `EPS_GEOM`, skaliert an der Modellgröße.
3. **Entartete Dreiecke entfernen** (Nullfläche, Nadeln, Dubletten).
4. **Normalen vereinheitlichen**, Orientierung prüfen.
5. **Komponenten zählen**, Kleinstteile melden statt still zu löschen.
6. **Lage**: Schwerpunkt ermitteln, Aufsetzen auf das Bett anbieten — nicht
   erzwingen.

Die Eingangsstufe ist die Op `load`, damit ihre Parameter im Stack sichtbar und
änderbar bleiben.

### 17.2 Rückfallkette für Boolesche Operationen

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, Toleranz erhöhen, erneut | `welded` |
| 3 | minimale Störung der Eingangsgeometrie | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen und zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag (§2.7) | — |

Die erfolgreiche Stufe steht in der Op. Stufe 4 kostet Genauigkeit und wird im
Prüfbericht ausgewiesen, nicht stillschweigend verwendet. In Entwurfsqualität
(§31) endet die Kette nach Stufe 2, um Iterationen schnell zu halten.

### 17.3 Prüfbericht
Alles aus §17.1 und §17.2 landet in einem Bericht je Objekt, sichtbar im
rechten Bereich, im Steckbrief und in `report.json`. Der Agent muss wissen,
dass er auf einem voxelgeglätteten Ergebnis arbeitet.

---

## 18. Der Viewport

Kein Anzeigefenster, sondern das Prüfwerkzeug.

### 18.1 Darstellung
Massiv, Drahtgitter, Massiv+Kanten, transparent. Flache und weiche
Schattierung. Orthografisch und perspektivisch — orthografisch ist beim Messen
Pflicht. Sieben Kameravoreinstellungen. Rückseiten eingefärbt, damit
invertierte Normalen auffallen.

### 18.2 Schnittebene
Ebene an X/Y/Z oder frei, interaktiv verschiebbar, optional zweite Ebene für
eine Scheibe, Schnittkontur mit Maßangaben.

**Die Schnittfläche wird geschlossen dargestellt** (Capping). Ohne Deckel wirkt
jedes Volumen hohl und Wandstärken sind nicht beurteilbar — daran scheitern
naive Umsetzungen.

### 18.3 Messen
Punkt-zu-Punkt mit Fang auf Vertices und Kanten. **Durchmesser über
Feature-Auswahl**, nicht über drei geklickte Punkte. Winkel zwischen erkannten
Ebenen. Wandstärke am Klickpunkt. Bounding Box und Volumen der Auswahl.
Bemaßungen bleiben stehen, bis sie gelöscht werden; Anzeige gerundet auf
`EPS_DISPLAY`.

### 18.4 Analysekarten

| Karte | Zeigt | Nutzen |
|---|---|---|
| Wandstärke | Verlauf, dünn hervorgehoben | zu dünne Stellen finden |
| Überhang | Winkel gegen Z, > 45° hervorgehoben | Stützbedarf, Orientierung |
| Netzfehler | offene Kanten, Non-Manifold, Durchdringung | Reparaturbedarf |
| Krümmung | Kanten und Verrundungen | Feature-Erkennung prüfen |
| Feature-Zuordnung | jedes Feature eigen eingefärbt | verstehen, was die KI sieht |
| Passungen | verbundene Paare, Verletzungen markiert | Mehrteiliges prüfen (§14) |
| Stützbedarf | aus der Schichtanalyse (§22), fein aus dem G-Code (§28) | Orientierung beurteilen |

Immer mit Legende und Zahlenbereich, Paletten nach §19.1. Jede Karte ist auch
über den Prüfbericht erreichbar: Klick auf eine Warnung schaltet die passende
Karte ein und fährt die Kamera auf die Stelle — der kürzeste Weg von „es gibt
ein Problem" zu „hier ist es".

### 18.5 Feature-Overlay
Erkannte Bohrungen und Flächen farbig, mit Beschriftung (`hole_3 · Ø4.2`), beim
Überfahren hervorgehoben, beim Anklicken ausgewählt, als Referenz im Chat und
als Kontextmenü mit den passenden Ops (§10, `applies_to`).

Diese Brücke zwischen Maus und Sprache ist die wichtigste Einzelfunktion der
Anwendung: Der Nutzer muss keine Feature-Namen kennen, er zeigt hin.

### 18.6 Druckbett und Bauraum
Bett als Gitter im realen Maß, Bauraum als transparente Box, Objekte außerhalb
markiert, Kollisionen markiert, Schwerpunkt und Aufstandsfläche einblendbar.

### 18.7 Vorher/Nachher
Vorheriger Stand als halbtransparenter Geist. **Differenzansicht**: entferntes
und hinzugefügtes Volumen unterschieden — Farbwahl nach §19.1, zusätzlich über
Muster kodiert. Schieberegler über den Verlauf. Bezugsgröße ist die
Transaktion, nicht die Einzel-Op.

### 18.8 Objektbaum
Sichtbarkeit, Isolieren, Umbenennen, Farbe, Herkunft (aus welcher Op und
Transaktion), Kennzeichnung Mesh oder B-Rep. Bei Split-Ergebnissen eine
**Explosionsansicht**.

### 18.9 Darstellungsleistung
Für die Anzeige dezimierte Fassung ab der Schwelle aus §31; das Original bleibt
für die Berechnung unangetastet. Analysekarten verzögert im Hintergrund mit
Fortschritt. Die Dezimierung darf nie in den Geometriekern zurückfließen.

### 18.10 Schichtenvorschau
Durch die Höhe scrubben, Querschnitt und Konturen sehen, Inseln hervorgehoben
(§22.4). Ehrlich beschriftet als „Schichtanalyse", nicht als „Vorschau" — sie
zeigt Geometrie, keine Werkzeugwege.

### 18.11 Direktmanipulation
Gizmo zum Verschieben, Drehen, Skalieren. Snapping: Fläche an Fläche, Achsen
ausrichten, Bohrungsachsen zur Deckung bringen, Raster- und Winkelfang.
**Jede Manipulation erzeugt eine Op.** Zahleneingabe während des Ziehens.

---

## 19. Bedienung und Barrierefreiheit

### 19.1 Farbe trägt nie allein die Bedeutung
Die Differenzansicht ist die wichtigste Ansicht der Anwendung — ausgerechnet
sie hätte in Rot/Grün die für Farbfehlsichtigkeit schlechteste Kombination.

- **Vorgabe ist Blau/Orange.** Rot/Grün und Graustufen-mit-Schraffur stehen
  als Alternativen zur Wahl.
- Zusätzlich zur Farbe immer eine zweite Kodierung: Muster, Schraffur, Symbol
  oder Beschriftung.
- Analysekarten benutzen wahrnehmungsgleiche Paletten (Viridis-Art), keinen
  Regenbogen — der erzeugt Kanten, wo keine sind.

### 19.2 Tastatur
Jede Op kann ein Kürzel führen; der Konsistenztest lehnt Dubletten ab. Die
**Befehlspalette** ist der Universalzugang. Der Viewport ist mit der Tastatur
navigierbar (Achsansichten, Zoom, Auswahl durchblättern). Undo und Redo gelten
überall, auch im Chat.

### 19.3 Anzeige
HiDPI-tauglich, skalierbare Schriftgröße, ausreichender Kontrast in hellem und
dunklem Thema. **Anzeigeeinheit umschaltbar** zwischen Millimeter und Zoll —
der Kern bleibt bei Millimeter (§11.1).

---

## 20. Farbe und Multi-Material

**Datenmodell**: pro Objekt eine Liste von Materialslots, pro Dreieck ein
Slot-Index als Face-Attribut, optional UV und Textur aus Säule B.

**Import**: STL keine Farbe (alles Slot 0), 3MF Materialgruppen je Dreieck,
OBJ+MTL Gruppen und optional Textur, GLB/glTF ein PBR-Material mit Textur,
STEP keine Farbe aber echte Flächen (§30).

**Von der Textur zum Druck**: zurückprojizieren, auf die Anzahl geladener
Filamente quantisieren (k-Means, **mit gespeichertem Startwert**), glätten
gegen Einzeldreieck-Sprenkel, als Slots ablegen, nach 3MF exportieren. Nie so
fein wie das Rendering — klar kommunizieren.

**Attributerhalt**: Boolesche Operationen dürfen die Slot-Zuweisung nicht
verlieren. `manifold3d` kann Eigenschaften hindurchreichen; wo das nicht
greift, über Nächste-Fläche-Zuordnung übertragen. Neue Schnittflächen bekommen
einen konfigurierbaren Slot. **Nach Rückfallstufe „voxel" ist die Zuweisung
immer neu zu übertragen**, weil die Vernetzung ersetzt wurde.

**Bemalen** als Pinselwerkzeug mit Radius und Kantenerkennung: späte Phase,
aber im Datenmodell von Anfang an vorgesehen.

---

## 21. Feature-Erkennung und stabile IDs

### 21.1 Was erkannt wird
Bohrungen (Zylinderflächen clustern → Durchmesser, Achse, Tiefe, Durchgang oder
Sackloch), ebene Flächen (koplanare Cluster → Normale, Fläche, Schwerpunkt,
Randkontur), Randschleifen (offene Kanten = Defekte), Symmetrieebenen,
Dünnstellen, Zusammenhangskomponenten.

### 21.2 Das ID-Problem
**Erzeugte Features — Provenienz.** Was eine Operation selbst erzeugt, bekommt
eine abgeleitete ID: `op4.pin_1`. Keine Erkennung, keine Mehrdeutigkeit. Mit
der Bausteinbibliothek (§24) wächst dieser Anteil deutlich.

**Importierte Features — Zuordnung.** Nach jeder Op läuft die Erkennung neu.
Alt und neu werden über einen Merkmalsvektor (Typ, Durchmesser,
Achsenrichtung, Position im Objektsystem, Nachbarschaft) optimal zugeordnet —
ungarische Methode über die Kostenmatrix, Schwelle `EPS_MATCH`.

| Fall | Verhalten |
|---|---|
| eindeutig unter Schwelle | ID bleibt |
| kein Partner | verwaist |
| mehrere dichte Kandidaten | mehrdeutig |

### 21.3 Verhalten bei Verwaisung
Verweist eine spätere Op auf eine verwaiste oder mehrdeutige ID, **hält die
Auswertung dort an** (§15.3), zeigt die Kandidaten hervorgehoben und fragt über
`ctx.ask`. Der Nutzer wählt, die Op wird umgeschrieben, es läuft weiter. Beim
Öffnen einer Projektdatei werden alle Feature-Verweise einmal geprüft, bevor
gerechnet wird.

---

## 22. Schichtanalyse — der eigene Analyse-Slicer

Bewusst **kein** G-Code-Slicer. Perimeter, Nahtplatzierung, Kühlung,
Retraction, Bridging, Baumstützen und Maschinengrenzen sind fünfzehn Jahre
Arbeit anderer Leute; ein schlechteres Ergebnis kostet das Vertrauen in die
ganze Anwendung. Die Datei, die auf den Drucker geht, kommt weiterhin vom
externen Slicer (§28).

Das **Schneiden zur Analyse** ist dagegen eine überschaubare Sache und der
größere Hebel.

### 22.1 Verfahren
Ebene-Mesh-Schnitt je Höhe über eine sortierte Kantenliste, die Schnittsegmente
zu geschlossenen Polygonen verkettet. Für Flächen- und Offsetrechnungen
Clipper2 (Boost-Lizenz, unkritisch). Kein Fremdprozess, keine Installation,
Ergebnis in Millisekunden statt Sekunden.

### 22.2 Was daraus abfällt

| Größe | Bedeutung |
|---|---|
| Überhangfläche je Schicht | Differenz zur darunterliegenden Kontur |
| Stützvolumen | Summe der nicht unterstützten Flächen über die Höhe |
| Querschnittsverlauf | sprunghafte Änderungen → Verzugs- und Haftungsrisiko |
| **Inseln** | Konturen ohne Verbindung nach unten — brauchen zwingend Stütze |
| Erste Schichtfläche | Haftung und Kippstabilität |
| Brückenweiten | freitragende Strecken je Schicht |
| Kleinste Strukturbreite | gegen Düsendurchmesser prüfbar |

### 22.3 Was sich dadurch ändert
Der eigentliche Gewinn ist nicht die Ersparnis, sondern der Maßstab:

- **Orientierungssuche**: statt drei bis fünf vorgefilterte Kandidaten extern
  zu slicen, lassen sich **hunderte Rotationen** durchrechnen und nach echtem
  Stützvolumen sortieren.
- **Trennebene beim Auto Split**: dieselbe Suche über Schnitthöhen und
  -richtungen.
- **Sofortige Rückmeldung**: Überhang- und Inselwarnungen erscheinen im
  Prüfbericht, ohne dass ein Slicer installiert sein muss. Die Anwendung ist
  damit vom ersten Start an beurteilungsfähig.
- **Analysekarten** Überhang und Stützbedarf (§18.4) bekommen echte Werte
  statt einer Normalen-Heuristik.

### 22.4 Schichtenvorschau
Fällt fast gratis ab: durch die Höhe scrubben, Querschnitt und Konturen sehen,
Inseln hervorgehoben. Sie ersetzt keine Slicer-Vorschau — sie zeigt die
Geometrie, nicht die Werkzeugwege — und ist genau deshalb ehrlich zu
beschriften: „Schichtanalyse", nicht „Vorschau".

### 22.5 Abgrenzung

| | eigener Analyse-Slicer | externer Slicer (§28) |
|---|---|---|
| Zweck | suchen, bewerten, warnen | drucken |
| Geschwindigkeit | Millisekunden | Sekunden |
| Ergebnis | Kennzahlen, Konturen | G-Code |
| Voraussetzung | keine | Installation |
| Verbindlich für | Iteration und Optimierung | die Druckdatei |

Die Kennzahlen beider Wege werden **nie vermischt**. Der Prüfbericht weist
aus, woher ein Wert stammt — ein geschätztes Stützvolumen aus der
Schichtanalyse ist etwas anderes als ein gemessenes aus dem G-Code.

---

## 23. Steckbrief für den Agenten

```
Szene: 2 Objekte, Drucker centauri-carbon-2, Material PETG (kalibriert)
Parameter: breite=84.0 mm, hoehe=22.0 mm, wandstaerke=2.4 mm
Auswahl: obj_2 · hole_3
obj_2  "halterung_oben"  84 × 40 × 11 mm, 14.1 cm³, wasserdicht, auf Bett
  face_1  planar 84×40, Normale -Z   (Aufstandsfläche)
  hole_3  Ø 5.2 mm, Achse +Z, Durchgang, auf face_1
  op3.heatset_1  Baustein heatset_m4, auf face_1
  op5.pin_1      Ø 4.0 mm, Achse +Z, Zapfen   → Passung stift_1
  hinweis Op 5 über Rückfallstufe "voxel" gelöst — Maße gerundet
  warnung Dünnstelle 0.9 mm nahe face_7
obj_3  "halterung_unten" …
Stack: t1 "Import und Reparatur" (Ops 1–2, Nutzer) ·
       t2 "Teilen und verstiften" (Ops 3–6, Agent)
```

Dazu die gerenderten Ansichten — beschriftete PNG-Bilder (schräg oben und
von oben), gerendert von der Oberfläche, denn der Kern rastert nicht. Sie
erreichen nur ein Backend, das Bilder versteht; an jedes andere entfallen
sie ersatzlos, und der Steckbrief trägt allein — Bilder sind Zugabe, nie
Voraussetzung (Leitprinzip 8). Der Agent referenziert ausschließlich diese
Namen.

---

## 24. Bausteinbibliothek und Normteile

**Der Agent setzt geprüfte Bausteine zusammen, statt Geometrie zu erfinden.**

### 24.1 Bausteine in Python
```python
@register_part(
    name="heatset_m4",
    title=_("Heat-Set-Einpressbuchse M4"),
    params=HeatsetParams,
    features=["bore", "chamfer"],
    preview="heatset_m4.png",  # für den Katalog (§2.6)
    doc=_("Bohrung für eine Einpressbuchse M4 mit Einführfase."),
)
def heatset_m4(params: HeatsetParams) -> PartResult: ...
```

Bausteine bauen gegen `manifold3d`. Damit hängt `insert_part` an keiner
externen Installation, ist testbar, schemageprüft und liefert
Provenienz-Features. **OpenSCAD wird optional** und nur für Freiformen in
Säule A gebraucht — das löst zugleich die GPL-Frage (§36). Ein `to_scad()` je
Baustein bleibt als Ausgabeformat erhalten.

**Erstbestückung**: Schraubenloch mit Senkung, Heat-Set-Einpressbuchse,
Mutternfalle (seitlich und von unten), Magnettasche, Kabeldurchführung mit
Zugentlastung, Schnappverbindung, Rastnase, Filmscharnier, Passstift und
Passbohrung, Wandhalter, Schlüsselloch-Aufhängung, Versteifungsrippe, Gewinde.

### 24.2 Normteiltabelle
Metrische Schrauben (Kern, Durchgang, Kopf, Schlüsselweite), Muttern,
Scheiben, Heat-Set-Buchsen, Magnete, Kugellager, Aluprofil-Nutmaße, Schlauch-
und Rohrmaße. „Loch für M4-Einpressmutter" muss ein Nachschlagewert sein.

Bei Veröffentlichung: Maßangaben als Zahlen sind frei verwendbar, Normtexte
und Normtabellen nicht. Werte aus frei zugänglichen Herstellerangaben
zusammentragen, keine Normblätter abschreiben.

### 24.3 Katalog und Prüfung
Der **Bausteinkatalog** zeigt Vorschaubilder, Kurzbeschreibung und die zwei
wichtigsten Parameter — eine Bibliothek, die man nicht sieht, existiert für
den Nutzer nicht. Die Vorschaubilder werden aus den Bausteinen selbst
gerendert, nicht von Hand gepflegt.

Jeder Baustein wird über seinen Parameterbereich durchgerechnet: wasserdicht,
Mindestwandstärke, keine Selbstdurchdringung an den Grenzen, Features korrekt
benannt. Ein Baustein ohne diesen Test gilt als nicht vorhanden.

### 24.4 Versionierung
Die Bibliothek ist Teil des Rechenwegs — also wird sie wie eine Abhängigkeit
behandelt. Ohne das rechnet eine spätere Korrektur an `heatset_m4` alte
Projekte still anders, und Leitprinzip 4 ist verletzt.

- **`parts_version`** in jeder Projektdatei (§16.2)
- **Änderungsverlauf je Baustein**: was, wann, warum, mit Auswirkung auf die
  Maße
- **Beim Öffnen**: Hinweis, welche *benutzten* Bausteine sich seither geändert
  haben, mit der Wahl zwischen „neu rechnen" und „alten Stand beibehalten"
- Der alte Stand bleibt aufrufbar, solange die Bibliothek ihn führt; wird er
  entfernt, verhält sich das wie eine Migration (§16.2)

### 24.5 Eigene Bausteine
Dieselbe Registrierung aus einem Nutzerverzeichnis
(`<Nutzerdaten>/parts/*.py`), beim Start eingelesen, im Katalog eigens
gekennzeichnet.

**Das ist kein Plugin-System.** Der Unterschied ist die Reichweite: Eigene
Bausteine gelten nur auf dem Rechner, auf dem sie liegen.

- Sie **reisen nie in Projektdateien mit** — sonst wäre die Regel aus §32
  umgangen, dass eine fremde Datei keinen Code ausführt
- Öffnet jemand ein Projekt, das einen unbekannten eigenen Baustein benutzt,
  hält die Auswertung an und meldet, was fehlt (§15.2)
- Sie erweitern nicht die Anwendung, sondern nur die Bibliothek — keine neuen
  Ops, keine Oberflächenänderungen, kein Zugriff auf den Op-Stack
- Dieselben Tests gelten; ohne bestandenen Parameterbereichstest erscheint ein
  Warnhinweis im Katalog

---

## 25. Operationskatalog

**Szene** — laden (§17.1), duplizieren, löschen, umbenennen, auf Bett anordnen,
Kollision prüfen, vereinigen, in Komponenten zerlegen

**Parameter** — anlegen, ändern, löschen, an eine Op binden

**Passungen** — Paar anlegen, Art ändern, lösen, prüfen

**Reparatur** — Löcher füllen, Non-Manifold entfernen, Normalen
vereinheitlichen, Selbstdurchdringungen auflösen, Kleinstkomponenten löschen,
Vertices verschmelzen

**Transformation** — verschieben, drehen, spiegeln, gleichmäßig und achsweise
skalieren, auf Bett ausrichten, druckoptimal orientieren

**Boolesch** — Vereinigung, Differenz, Schnitt (mit Rückfallkette §17.2);
Primitive einfügen; **Baustein an ein erkanntes Feature setzen** (§24);
OpenSCAD-Teil anheften (optional)

**Skizze** (§30.1, B-Rep) — Grundform anlegen (Rechteck, Langloch, Kreisbild,
Vieleck), Skizze extrudieren, rotieren, als Tasche schneiden, entlang Pfad
führen

**Formgebung** (B-Rep) — Fase, Verrundung; Formschräge, exakte Schale, Sweep,
Loft, exaktes Gewinde (§30.1)

**Bohrungen** — aufbohren, verschließen, senken, um Materialtoleranz korrigieren

**Druckvorbereitung** — aushöhlen mit Entlüftung, an Ebene schneiden,
Verstiftung setzen, Elefantenfuß kompensieren

**Import** — STL, 3MF (einzeln und als ganze Bauplatte), OBJ, GLB, STEP (§30);
SVG und DXF mit Extrusion

**Farbe** — Slot zuweisen, aus Textur ableiten, bemalen

**Beschriftung** — Text oder Logo erhaben/vertieft auf eine gewählte Fläche

**Oberfläche** — Textur auf eine gewählte Fläche prägen oder einschneiden:
Rippe, Welle, Rändel gerade und gekreuzt, Wabe, Noppen, Voronoi, Rauschen. Als
**echte Geometrie** und als exaktes Gitter, nicht als abgetastetes Höhenfeld —
sonst druckt ein Rändel gerundeten Brei statt scharfer Rauten. Vor dem Bauen
steht die Frage, ob das Muster auf dieser Maschine überhaupt entsteht: Stege
schmaler als die Düse und Prägungen flacher als eine Schicht verschwinden beim
Drucken und werden abgewiesen, nicht gerechnet.

**Netz** — dezimieren, remeshen, glätten

**Varianten** — dieselbe Op-Kette mit durchvariiertem Parameter (§28.3)

Einschränkung, solange nur der Mesh-Kern läuft: **Verrundungen und Fasen auf
beliebigen Mesh-Kanten bleiben hart.** Mit dem B-Rep-Kern (§30) fällt sie.

---

## 26. Agentenschicht

### 26.1 Was der Agent sieht
- **Steckbrief** (§23) einschließlich Projektparameter und **aktueller
  Auswahl** — sonst verpufft der Klick bei „mach das Loch größer"
- **Prüfbericht** einschließlich verwendeter Rückfallstufen
- **Verlauf in Kurzform**: Transaktionen mit Titel, Ops mit Nummer und
  Objekten — sonst kann er „nimm das zurück" nicht ausführen
- **gültige Chatbeiträge** (§26.3), nicht der rohe Verlauf
- **Regelsammlung** in der aktuellen Version (§39)

### 26.2 Werkzeuge
Alle Ops aus dem Register, dazu:

| Werkzeug | Zweck |
|---|---|
| `ask_user(frage, optionen)` | **Nachfragen statt raten** — Leitprinzip 6 |
| `undo_transaction(id)` | Transaktion zurücknehmen |
| `add_parameter` / `set_parameter` | Projektparameter statt Streuzahlen |
| `add_fit` | Passungspaar anlegen |
| `read_report` | Prüfbericht gezielt nachlesen |
| `find_part(beschreibung)` | passenden Baustein suchen, bevor gebaut wird |
| `read_digest(objekte)` | den Steckbrief mitten im Zug neu lesen — nach mehreren Ops kennt der Agent sonst die IDs nicht, die er selbst erzeugt hat |
| `read_standard(art, größe)` | Normteilmaße nachschlagen statt raten (§24.2) |
| `read_analysis(art, objekte)` | Schichtanalyse, Zeit- und Materialschätzung, Einstellungsrat, Orientierung — nur lesend, mit hartem Größendeckel, Herkunft immer ausgewiesen (§22.5) |
| `set_print_target(drucker, material)` | Projektdrucker und -material wechseln — Toleranzen bleiben Verweise (`auto:<material>`) und rechnen sich mit um |

Ein Werkzeug, das Druckeinstellungen **setzt**, gibt es mit Absicht nicht:
Einstellungen reisen nicht in Transaktionen (§15.5 zieht die Grenze an der
Auswertung), ein Undo nähme sie also nicht mit zurück — und Regel 16 gilt
auch für den Agenten. §28.2 bleibt dabei: „Übernommen wird auf Klick, nie
von allein." Der Agent liest die Vorschläge über `read_analysis`, nennt sie
samt Begründung, und der Klick bleibt im Druckdialog.

`ask_user` ist Pflicht, keine Höflichkeit: Die Agenten-Suite enthält absichtlich
mehrdeutige Anfragen und misst, ob gefragt statt geraten wird.

Diese Liste ist abschließend — was hier nicht steht, gibt es nicht. Die fünf
Werkzeuge ab `read_digest` kamen mit der Agent-Vertiefung dazu
(`konzept-agent-vertiefung.md`); sie öffnen keinen zweiten Weg ins Dokument:
die lesenden rechnen auf der Arbeitskopie, die schreibenden reisen als Teil
der einen Transaktion des Vorschlags (§26.5, Regel 16).

### 26.3 Chat und Verlauf
**Jeder Chatbeitrag verweist auf die Transaktion, die er erzeugt hat.** Wird
sie zurückgenommen, gilt der Beitrag als **verworfen** und geht beim nächsten
Kontextaufbau höchstens als „wurde verworfen" mit; Redo stellt ihn wieder her.
In der Oberfläche werden verworfene Beiträge ausgegraut, nicht gelöscht.

Ohne diese Kopplung argumentiert der Agent nach jedem Undo mit einem Zustand,
den es nicht mehr gibt.

### 26.4 Herkunft
Jede Transaktion trägt `origin`: Urheber, bei Agenten zusätzlich Modell,
Version des Systemprompts, Version der Regelsammlung und Temperatur. Da die
Projektdatei als Fehlerbericht dient, ist das der einzige Weg, später zu
verstehen, unter welchen Bedingungen eine Op entstanden ist.

### 26.5 Ablauf
Vorschlag → Berechnung in Entwurfsqualität → Differenzansicht → Übernahme oder
Verwerfen. Ein Vorschlag ist genau eine Transaktion. Bei eindeutig umkehrbaren
Ops kann die Übernahme automatisch laufen. Iterationslimit und Kostendeckel
sind hart. Nach jeder Op läuft die Prüfung (wasserdicht, Volumen plausibel,
keine unerwarteten Komponenten, keine verwaisten Referenzen, keine verletzten
Passungen); der Befund geht zurück in den Kontext.

**Bausteine vor Primitiven, Op-Liste vor OpenSCAD, Parameter vor Zahlen,
Fragen vor Raten** — alle vier im Systemprompt verankert und in der Suite
gemessen.

### 26.6 Fernsteuerung über MCP
Ein zweites Programm auf demselben Rechner ruft dieselben Operationen auf wie
die Menüs — über JSON-RPC nach dem Model-Context-Protocol. Die Werkzeuge kommen
aus derselben Liste wie die des Chats; es gibt keine zweite und keinen zweiten
Weg ins Dokument.

Vier Auflagen, jede mit Test:

1. **Standardmäßig aus**, Schalter in den Einstellungen.
2. **Nur `127.0.0.1`** — geprüft an der Bindung *und* an jeder Anfrage.
3. **Kein ausführbarer Quelltext, kein Dateipfad**, abgewiesen vor der
   Rechnung. Der Pfad wird am Wert erkannt, nicht am Parameternamen.
4. **Jeder Aufruf eine Transaktion** mit Herkunftsvermerk (§26.4), rücknehmbar
   wie jede andere.

---

## 27. Backends

**LLM** — Standard ist der eigene Schlüssel des Nutzers im
System-Schlüsselbund. Alternative: lokal über Ollama; zuverlässiges
Tool-Calling braucht ein ausreichend großes Modell, kleine scheitern
reproduzierbar. Empfehlungsliste in die Doku. Ohne Schlüssel sind
Agentenfunktionen ausgegraut, die Anwendung bleibt voll nutzbar.

**Mesh-Generierung** — lokal über ComfyUI oder gehostet gegen denselben Aufruf.
Die Schnittstelle kennt nur `text_to_mesh` und `image_to_mesh`: kein
Nutzercode, keine Dateipfade, kein Zustand.

**Der gehostete Dienst, falls er kommt**, bleibt klein: nimmt Text oder Bild,
gibt ein Mesh zurück, sonst nichts. Keine Projektablage, keine Historie.
Eingaben nach Auslieferung löschen, nicht für Training verwenden, und das auch
so hinschreiben. Abrechnung über Guthaben, Warteschlange mit Zeitlimit,
Serverstandort in der EU.

---

## 28. Rückkopplung aus Slicer und Drucker

Die Schichtanalyse (§22) sucht und bewertet, der externe Slicer liefert die
Wahrheit für die Druckdatei. Beide Wege bleiben getrennt ausgewiesen.

### 28.1 G-Code zurücklesen
Druckzeit, Materialverbrauch, **gemessenes Stützmaterialvolumen**, Schichtzahl,
Warnungen — als Gegenprobe zur internen Schätzung und als Grundlage der
Kostenschätzung.

### 28.2 Was das ändert
Die Suche selbst läuft intern über §22 — hunderte Kandidaten statt einer
Handvoll. Der externe Lauf dient nur noch der **Bestätigung der Siegerlösung**
und der Kostenschätzung. Das kehrt das Verhältnis um: früher war der Slicer der
Flaschenhals der Suche, jetzt ist er die Endabnahme.

Weicht die Gegenprobe deutlich von der internen Schätzung ab, ist das ein
Befund im Prüfbericht — und ein Hinweis, dass die Schichtanalyse nachgebessert
werden muss.

### 28.3 Selbstkalibrierung
1. Toleranz-Testkörper erzeugen (Zapfen und Bohrungen mit gestaffeltem Spiel,
   Wandstärkenleiter, Überhangfächer)
2. Drucken, nachmessen, Werte eintragen
3. Werte landen im **Materialprofil**, nicht in einem Modell

Weil Toleranzen im Stack Verweise sind (§12), rechnen alle bestehenden
Projekte danach mit den kalibrierten Werten neu.

Dazu der **Varianten-Generator**: dieselbe Op-Kette mit gestaffeltem Parameter
in einem Durchlauf — vier Ausführungen mit 0,10 / 0,15 / 0,20 / 0,25 mm Spiel,
beschriftet, angeordnet. Ein Druck, danach steht der Wert. Mit
Projektparametern ist das ein Aufruf, keine Sonderfunktion.

---

## 29. Export und Slicer-Übergabe

**Umfang**: einzelnes Objekt, aktuelle Auswahl oder ganze Szene.

**Formate**: STL binär, **3MF mit Objektnamen, Anordnung und Farbgruppen**,
OBJ, STEP (bei B-Rep-Objekten).

**Namensschema** bei mehreren Teilen, konfigurierbar, Vorgabe
`<projekt>_<objekt>_1von3.stl`. Objektnamen werden dateisystemtauglich
gemacht, ohne unkenntlich zu werden.

**Übergabe an den Slicer**: direkt per Kommandozeile aufrufen oder die
exportierte Datei öffnen. Ordner, Format und Übergabeart werden je Projekt
gemerkt.

**Exportprüfung vor dem Schreiben**, als Bericht, nicht als Blockade:
wasserdicht, innerhalb des Bauraums, keine verletzten Passungen, keine
Dünnstellen unter der Mindestwandstärke, Lizenzhinweis beteiligter Quellen
(§16.3). Wer trotzdem exportieren will, kann das — er weiß dann nur, was er tut.

---

## 30. Zweiter Konstruktionskern (B-Rep)

Späte, aber geplante Stufe (build123d oder CadQuery, OpenCascade darunter):
echte Kanten und damit **echte Fasen und Verrundungen**, **STEP-Import und
-Export**, Skizzen mit Zwangsbedingungen, präzise Booleans ohne
Vernetzungsartefakte.

Als zweiter Kern **neben** dem Mesh-Kern, nicht als Ersatz. Objekte tragen die
Kennzeichnung `kind` (§9). Der Übergang B-Rep → Mesh ist jederzeit möglich, der
Rückweg nicht — im Objektbaum sichtbar machen.

Für die Feature-Erkennung ein Sprung: Bei B-Rep-Objekten entfallen Clustern und
ID-Problem weitgehend, weil Flächen und Kanten benannte Entitäten sind.

### 30.1 Skizzen mit Zwangsbedingungen

Der Grund für diese Stufe ist eine Produktentscheidung: **so wenig
Fremdprogramme wie möglich.** Das fremde CAD vor dem Import ist der größte
verbliebene Anlass, Solidon zu verlassen — mit Skizzen entsteht ein
Druckteil von der ersten Linie bis zum Export im selben Programm.

- **Eine Skizze ist ein Datenmodell im Kern** (Verträge in §9): Ebene aus
  einer Hauptebene oder einer angeklickten planaren Fläche, Elemente (Linie,
  Bogen, Kreis, Punkt), Bedingungen (Maß, Koinzidenz, horizontal, vertikal,
  parallel, senkrecht, tangential, symmetrisch, fest). Kein Qt darunter.
- **Die Skizze lebt als Parameterwert der Operation, die sie verbraucht**
  (`sketch_extrude`, `sketch_pocket`, `sketch_revolve`, `sketch_sweep`).
  Bearbeiten heißt `change_params` auf dem Schritt im Verlauf — dieselbe
  Regel wie für jede andere Zahl (§15). Es entsteht kein zweiter
  Dokumentbegriff neben dem Stack.
- **Maßbedingungen sind Ausdrücke der Parametergrammatik (§13).** Ein
  Skizzenmaß darf einen Projektparameter benutzen; eine Parameteränderung
  rechnet die Skizze und den Zweig darunter neu. Kein `eval` (Regel 10).
- **Der Solver ist ein eigener numerischer 2D-Solver auf scipy**:
  deterministisch, ohne Zufall. Unterbestimmt meldet die verbleibenden
  Freiheitsgrade als Befund; überbestimmt oder widersprüchlich hält an und
  nennt das kollidierende Bedingungspaar — nie nur „fehlgeschlagen"
  (Regel 17). SolveSpace und py-slvs sind GPL und ausgeschlossen (Regel 15);
  CadQuery oder build123d kommen nur in Frage, wenn die Lizenzprüfung ihrer
  Solver-Abhängigkeiten besteht, und dann als Ersatz des eigenen Solvers,
  nie als zweiter daneben.
- **Der Agent erzeugt Skizzen ausschließlich über benannte Grundformen**
  (Rechteck, Langloch, Kreisbild, Vieleck) und Maße — nie über rohe
  Punktlisten (Leitprinzip 5).
- **Zwei Ausgabestufen.** Stufe eins: die Grundformen über Dialog, CLI und
  Agent — voll parametrisch, ohne Grafikeditor. Stufe zwei: der grafische
  Editor im Viewport (Ebene anklicken, zeichnen, Bedingungen über
  Werkzeugleiste und Kontextmenü), offscreen testbar. Stufe eins ist für
  sich vollständig und abnahmefähig.
- **Die Skizzen-Ops rechnen gegen den B-Rep-Kern.** Ohne installiertes
  `brep` sagen sie das in einem Satz; alles andere bleibt benutzbar
  (bestehendes Muster aus P12).

---

## 31. Leistungsbudget

Gemessen auf dem Referenzkorpus (§34), als Teil der Suite protokolliert.

| Vorgang | Zielwert |
|---|---|
| Viewport-Navigation | flüssig bei 1 Mio. Dreiecken |
| Anzeige-Dezimierung greift ab | 500 000 Dreiecken |
| Boolesche Op, 200 000 Dreiecke | unter 2 s |
| Feature-Erkennung, 200 000 Dreiecke | unter 1 s |
| Analysekarte Wandstärke | unter 3 s, im Hintergrund |
| Projekt öffnen aus Plattencache | unter 1 s |
| Parameteränderung → sichtbares Ergebnis | unter 2 s, nur betroffene Zweige |
| Schichtanalyse, 200 000 Dreiecke, 0,2 mm | unter 300 ms |
| Skizzen-Solver, 200 Bedingungen | unter 100 ms |
| Orientierungssuche, 200 Kandidaten | unter 20 s, abbrechbar |
| Anwendungsstart bis bedienbar | unter 3 s |

**Zwei Qualitätsstufen**, im `OpContext` durchgereicht: **Entwurf** beim
Iterieren und in der Vorschau (gröbere Auflösung, Rückfallkette endet nach
Stufe 2, genäherte Analysekarten), **Fein** beim Export und im finalen
Prüfbericht. Der Agent arbeitet in Entwurfsqualität und schaltet erst beim
Abschluss um.

**Regressionsprüfung**: Messwerte je Lauf festhalten; Verschlechterung um mehr
als ein Viertel gilt als Fehler, nicht als Rauschen.

---

## 32. Sicherheit lokaler Ausführung

Weil Projektdateien als Fehlerbericht weitergegeben werden, wandern sie
zwischen Leuten. Eine fremde Datei darf nichts ausführen.

- **Keine absoluten Pfade** in Projektdateien
- **Parameterausdrücke** über eigenen Auswerter mit beschränkter Grammatik —
  **kein `eval`**, auch nicht abgesichert
- **OpenSCAD-Quelltext wird vor dem Lauf geprüft**: `import`, `include`, `use`
  und `surface` nur mit relativen Pfaden unterhalb des Arbeitsordners. Gilt für
  Quelltext aus Projektdateien **und** aus dem LLM.
- **Fester Arbeitsordner** je Lauf, Zeit- und Speicherlimit für den
  Unterprozess, kein Netzzugriff
- **Warnhinweis beim Öffnen** einer fremden Datei mit Quelltext oder externen
  Verweisen
- **Prüfsummen** aller Quellen beim Laden verifizieren
- **Grenzen beim Import**: Dreieckszahl und Dateigröße gedeckelt, mit klarer
  Meldung statt Speicherüberlauf
- **Eigene Bausteine (§24.5) reisen nie mit.** Ein Projekt verweist auf sie
  nur namentlich; fehlt der Baustein, hält die Auswertung an. Ausführbarer
  Code kommt ausschließlich aus der Installation und dem Nutzerverzeichnis,
  nie aus einer geöffneten Datei.

---

## 33. Fehler und Protokollierung

### 33.1 Ausnahmehierarchie
```python
AppError                     # Basis, trägt Titel, Ursache, Handlungsvorschläge
├── UserError                # Eingabe war unzulässig — korrigierbar
│   ├── ValidationError      # Schema verletzt
│   ├── AmbiguityError       # mehrdeutig, braucht eine Entscheidung
│   └── UnitUnknownError     # Einheit nicht bestimmbar
├── GeometryError            # Geometrie ließ es nicht zu — mit Vorschlag
│   ├── NotManifoldError
│   ├── BooleanFailedError   # trägt die versuchten Rückfallstufen
│   └── OutOfBuildVolume
├── ExternalToolError        # OpenSCAD, Slicer, ComfyUI, LLM
└── InternalError            # Programmfehler — Fehlerbericht anbieten
```

**Die Regel:** Ein Programmfehler darf nie wie ein Bedienfehler aussehen — und
umgekehrt. `UserError` und `GeometryError` erscheinen als Vorschlag nach §2.7,
`InternalError` als Fehlerdialog mit Berichtsangebot, `ExternalToolError` mit
Hinweis auf die Einstellung, in der das Programm konfiguriert wird.

Jede Ausnahme trägt `suggestions: list[Action]` — anklickbare Handlungen, keine
Prosa. Eine Ausnahme ohne Vorschlag ist unfertig.

### 33.2 Protokoll
Rotierende Datei im Nutzerverzeichnis, rein lokal. Format: Zeitstempel, Ebene,
Modul, Nachricht, Op-Nummer wo zutreffend. Kein Versand — die Abgrenzung zur
verbotenen Telemetrie ist: Das Protokoll verlässt den Rechner nur, wenn der
Nutzer es selbst anhängt.

Ebenen: `debug` nur bei gesetztem Schalter, `info` für Op-Läufe und
Dateizugriffe, `warning` für Rückfallstufen und Befunde, `error` für
Ausnahmen. Keine Geometriedaten ins Protokoll, nur Kennzahlen.

---

## 34. Referenzdaten und Testkorpus

Ohne festen Datensatz sind die Abnahmekriterien nicht prüfbar. Der Korpus liegt
unter `tests/data/` und ist Teil des Repositorys.

| Datei | Zweck |
|---|---|
| `cube_clean.stl` | Grundfall: wasserdicht, 12 Dreiecke |
| `plate_holes.stl` | vier Bohrungen bekannter Größe — Feature-Erkennung, Messen |
| `plate_holes_twin.stl` | zwei identische Bohrungen dicht beieinander — Mehrdeutigkeit |
| `bracket_inch.stl` | in Zoll gespeichert — Einheitenerkennung |
| `broken_open.stl` | drei offene Stellen — Reparatur, Rückfallkette |
| `broken_selfint.stl` | Selbstdurchdringung — Rückfallstufen 3 und 4 |
| `degenerate.stl` | Nadeln und Nullflächen — Eingangsstufe |
| `oversized.stl` | größer als jeder Bauraum — Auto Split |
| `island_tower.stl` | Bereich ohne Verbindung nach unten — Inselerkennung (§22) |
| `dense_1m.stl` | ~1 Mio. Dreiecke — Leistungsmessung |
| `colored.3mf` | Materialgruppen — Attributerhalt |
| `assembly_fit.p3d` | zwei Teile mit Passung — Passungsprüfung |
| `legacy_v1.p3d` … | je eine Datei pro Altformat — Migrationen |

**Regeln für den Korpus:** ausschließlich selbst erzeugte Geometrie oder
eindeutig frei lizenzierte Modelle — der Korpus wird mit veröffentlicht.
Jede Datei hat eine Zeile in `tests/data/README.md`: was sie enthält, welche
Kennzahlen erwartet werden, welcher Test sie benutzt. Neue Fehlerbilder aus der
Praxis werden als Datei aufgenommen, nicht als Sonderfall im Code.

---

## 35. Testbarkeit

| Art | Prüft |
|---|---|
| Kerntrennung | `core` ohne Qt importierbar |
| Registerkonsistenz | jede Op vollständig, Kürzel eindeutig, Startwert wo nötig |
| Sprachregelung | keine deutschen Stämme in Bezeichnern |
| Auswertung | zweimal ausgewertet = identisch; Objektzahländerung hält an |
| Geometrie | Kennzahlen je Operation gegen den Korpus |
| Rückfallkette | jede Stufe einmal erzwungen |
| Determinismus | gleicher Startwert → gleiches Ergebnis, alle vier Stellen |
| Bausteine | Parameterbereich vollständig, Vorschaubild erzeugbar |
| Bausteinversion | geänderter Baustein wird beim Öffnen gemeldet |
| Schichtanalyse | Fläche und Volumen gegen analytisch bekannte Körper; `island_tower` erkannt |
| Parameter | Grammatik, Zyklen, Ablehnung von allem Übrigen |
| Passungen | Verletzung wird erkannt und gemeldet |
| Migrationen | alte Beispieldateien öffnen |
| Zuordnung | ID-Stabilität, Mehrdeutigkeitserkennung |
| Fehler | jede Ausnahme trägt mindestens einen Handlungsvorschlag |
| Barrierefreiheit | keine Bedeutung allein über Farbe |
| Leistung | Zielwerte §31, Regressionsschwelle 25 % |
| Lizenzen | installierte Abhängigkeiten gegen Freigabeliste |
| Hauptwege | die drei Wege aus §2.2 laufen als Ende-zu-Ende-Test |
| Agenten-Suite | 39 Referenzanfragen — 21 zu Säule C (sechs seit der Agent-Vertiefung: nachsehen statt raten, Druckziel, Menüort), 18 zu Säule A |

Die Agenten-Suite misst zusätzlich: Wird ein vorhandener Baustein statt eigener
Geometrie benutzt? Werden Hauptabmessungen zu Parametern? Wird bei
Mehrdeutigkeit gefragt?

---

## 36. Abhängigkeiten und Lizenzen

| Baustein | Lizenz | Folge |
|---|---|---|
| trimesh | MIT | unkritisch |
| manifold3d | Apache-2.0 | unkritisch, Kern der Bausteine |
| numpy, scipy | BSD | unkritisch |
| PyVista / VTK | MIT / BSD | unkritisch |
| PySide6 | LGPL | geschlossene Weitergabe möglich, wenn dynamisch gebunden. **PyQt wäre GPL — nicht verwenden.** |
| **pymeshlab** | **GPL** | **nicht verwenden** |
| open3d | MIT | Ersatz für Reparatur und Remeshing |
| OpenSCAD | GPL | nur extern installiert aufrufen, nicht mitliefern |
| Slicer (Orca/Prusa) | GPL/AGPL | ebenso extern |
| build123d / CadQuery | Apache-2.0 | unkritisch |
| OpenCascade | LGPL mit Ausnahme | brauchbar |
| CoACD | prüfen | vor Einsatz klären |
| Generative Modelle | uneinheitlich, teils regional eingeschränkt | einzeln prüfen |

**Eigene Lizenz vor der ersten Veröffentlichung festlegen** — rückwirkend
ändern geht nur mit Zustimmung aller Beitragenden. Vier Wege: GPL, Apache/MIT,
quelloffen-mit-Einschränkung, geschlossen.

**Die Bausteinbibliothek separat und freizügig lizenzieren** (MIT oder CC0) —
ihr Code landet in der Geometrie der Nutzer. Für den Testkorpus gilt dasselbe.

**Lizenzhinweise** im Über-Dialog. Eine Prüfung vergleicht die installierten
Abhängigkeiten gegen die Freigabeliste.

---

## 37. Veröffentlichung

### 37.1 Name
Wird für Paketnamen, Domain, Dateiendung, Übersetzungen und Signierung
gebraucht — früh entscheiden. Kriterien: als Paketname und Domain frei, keine
Markenkollision, in beiden Sprachen aussprechbar. Der Name steht an **einer**
Stelle im Code (`app/branding.py`), damit ein Wechsel eine Ein-Zeilen-Änderung
bleibt.

**Entschieden: „Solidon3D".** Der volle Name steht auf Fenstertitel, Website,
Installer und Lizenzschlüssel; im Fließtext und in Docstrings heißt es kurz
„Solidon". Die Begründung führt `.claude/namensentscheidung-solidon.md`.

Hier stand bis zum 08.08.2026 zusätzlich „kein ‚3D' im Namen". Das Kriterium
war gegen einen beschreibenden Namen gerichtet und hat sich gegen zwei Dinge
nicht gehalten. Erstens die Marke: der Vorgänger „Formwerk" fiel, weil eine
Wort-/Bildmarke „3D FORMWERK" für „Entwurf von 3D-Modellen für den 3D-Druck"
bestandskräftig wurde — geprägt hat dabei *Formwerk*, das „3D" trat als
beschreibend zurück. Genau diese Beschreibungsschwäche macht das Kürzel als
Zusatz zu einem eigenen, kennzeichnungskräftigen Wortstamm unbedenklich.
Zweitens die Domain: `solidon3d.de` war frei, und Website, Support-Postfach,
Update-Datei und Fenstertitel sollen denselben Namen tragen — wer eine
Setup-Datei von der einen Adresse lädt und im Programm eine andere findet, hat
zwei Namen vor sich und keinen Grund zu glauben, dass sie zusammengehören.

Das Muster ist nicht neu: Shapr3D und Simplify3D führen dasselbe Kürzel. Es
kostet nichts, solange der Stamm allein trägt — und „Solidon baut keinen
G-Code-Slicer" liest sich besser als die Langfassung.

### 37.2 Auslieferung
- **Signierung.** Windows zuerst, Linux als AppImage oder Flatpak, macOS
  später (Beglaubigung nötig).
- **Automatische Bauläufe** über eine CI für alle Zielplattformen.
- **Update-Hinweis statt Auto-Update**: Versionsdatei abfragen, auf die
  Download-Seite verweisen.
- **Übersetzbarkeit von Anfang an**; eine Prüfung schlägt bei unübersetzten
  Texten an.
- **Fehlerberichte.** Keine Telemetrie. Ein Dialog legt Fehlertext,
  Versionsangaben und auf Wunsch den Projektcontainer bereit — mit Hinweis,
  dass Geometrie enthalten ist.
- **Doku und Beispielprojekte**: genau die drei Hauptwege aus §2.2. Sie sind
  gleichzeitig Doku, Abnahmeprüfung und Startbildschirm-Inhalt.
- **Erwartungsmanagement.** Klar hinschreiben, was die Anwendung nicht ist —
  kein CAD-Ersatz, keine Passungen aus generierten Meshes.
- **Ein einziger Supportkanal.**

---

## 38. Desktop-Spezifika

- **Erstinbetriebnahme** beim ersten Start: Sprache, Druckerprofil, Material,
  Pfade zu externen Programmen prüfen, LLM-Backend optional. Überspringbar und
  nachholbar.
- **Nebenläufigkeit.** Alles Rechnende im Worker-Thread mit Fortschritt und
  Abbrechen (§15.6).
- **Absturzwiederherstellung.** Der Autosave-Container liegt neben dem Projekt
  und wird beim nächsten Start angeboten.
- **Speicher und Cache.** Obergrenze im RAM, darunter ein Plattencache über den
  Op-Hash.
- **Zugangsdaten** im System-Schlüsselbund.
- **Profile**: Bauraum, Düse, Schichthöhe, Materialtoleranzen — nie fest im
  Code. **Ein Startsatz gängiger Druckerprofile wird mitgeliefert**, damit
  beim ersten Start niemand Bauraummaße abtippt; eigene Profile werden davon
  abgeleitet. Der Startsatz ist eine Datentabelle wie die Normteile (§24.2)
  und wird genauso gepflegt.
- **Paketierung.** PyInstaller. ComfyUI, Ollama, OpenSCAD und Slicer werden
  nicht mitgeliefert, sondern konfiguriert — mit Prüfung beim Start und klarer
  Meldung, wenn eines fehlt.

---

## 39. Die Regelsammlung

Laut Plan das eigentliche Produkt — also wird sie wie eines behandelt: eigene
Dateien unter `core/knowledge/rules/`, mit Version und Änderungsverlauf. Jede
Änderung mit Datum, Anlass und Suite-Ergebnis vorher/nachher. Verschlechtert
sich die Quote, wird die Regel zurückgenommen oder umformuliert. Der
Systemprompt referenziert die Version; jede Transaktion hält sie fest (§26.4).

Was sich als Baustein fassen lässt, wandert aus der Sammlung in die Bibliothek.
Eine eingehaltene Regel ist besser als eine beschriebene.

Aktueller Stand:

- Mindestwandstärke = 2 × Extrusionsbreite, nie darunter
- Fasen statt Überhängen über 45°
- Passungstoleranzen aus dem kalibrierten Materialprofil, nie als feste Zahl
- Hauptabmessungen als Projektparameter, nicht als Streuzahlen
- Bei Booleschen Ops immer 0,01 mm Überlappung, nie koinzidente Flächen
- Löcher größer als Nennmaß, weil FDM enger druckt — Wert aus der Kalibrierung
- Erste Schicht: Elefantenfuß einkalkulieren
- Bei OpenSCAD: `$fn` zentral, sonst explodieren die Renderzeiten

---

## 40. Phasen mit Abnahmekriterien

Die Arbeitsliste je Phase steht in `ROADMAP.md`. Hier stehen Umfang,
Zielmodule und Abnahme.

### P0 — Skelett
*Module:* `core/types`, `core/errors`, `core/units`, `core/registry`,
`core/scene`, `core/ingest`, `core/knowledge/profiles`, `cli`, `ui`
(Grundfenster, Viewport, Objektbaum, Parameterleiste, Verlauf), `tests/data`

*Fertig, wenn:* `core` ohne Qt importierbar · Sprachregelungstest grün · zwei
Ops im Register, sichtbar in Menü, Palette, Kontextmenü, CLI und Tool-Schema ·
Projekt speichern und laden erhält den Stack bitgleich · zweimalige Auswertung
liefert identische Geometrie · Undo/Redo über zehn Transaktionen · Import in
mm, Zoll und cm mit Einheitenrückfrage · Parameteränderung rechnet nur den
betroffenen Zweig · Ausdrucksauswerter lehnt alles außerhalb der Grammatik ab ·
Startbildschirm mit Ablagefeld · Startsatz Druckerprofile vorhanden und
auswählbar · Lizenzprüfung grün.

### P1 — Sehen und Messen
*Module:* `ui/viewport` (Modi, Schnittebene, Messen, Gizmo, Snapping),
`ui/theme`

*Fertig, wenn:* Schnittfläche erscheint geschlossen (Bildvergleich) ·
gemessener Durchmesser weicht unter 0,01 mm ab · jede Gizmo-Manipulation
erzeugt genau eine Op · keine Bedeutung allein über Farbe · Navigation in allen
drei Schemata · Leistungsziele Viewport erreicht.

### P2 — Operationen manuell
*Module:* `core/geom` (Reparatur, Transformation, Boolesch mit Rückfallkette,
Bohrungen, Schneiden, Anordnen), `core/export`

Die druckoptimale Orientierung bleibt hier eine Heuristik über
Flächennormalen; sie wird in P3 durch die Schichtanalyse ersetzt.

*Fertig, wenn:* jede Op hat einen Geometrietest gegen den Korpus · die
Rückfallkette löst `broken_open` und `broken_selfint` vollständig · verwendete
Stufe und Startwert stehen in der Op · gleicher Startwert liefert gleiches
Ergebnis · 3MF-Export öffnet im Slicer mit korrekten Objektnamen · **Weg 1 aus
§2.2 läuft als Ende-zu-Ende-Test** · Zielwerte §31 erreicht.

### P3 — Wahrnehmung und Schichtanalyse
*Module:* `core/perceive`, `core/slice`, `ui/overlay`, `ui/report`,
`ui/layerview`

*Fertig, wenn:* `plate_holes` vollständig erkannt · IDs bleiben über zehn Ops
stabil · `plate_holes_twin` wird als mehrdeutig gemeldet statt geraten · Klick
liefert die korrekte Feature-ID und das passende Kontextmenü · Klick auf eine
Warnung schaltet die Karte ein und fährt die Kamera hin · verletzte Passung
erscheint im Bericht · **Schichtanalyse**: Fläche und Stützvolumen stimmen bei
analytisch bekannten Körpern auf 1 % · `island_tower.stl` wird erkannt ·
Orientierungssuche über 200 Kandidaten liefert weniger Stützvolumen als die
Heuristik aus P2 · Schichtenvorschau scrubbt flüssig · Zielwerte §31 für die
Schichtanalyse erreicht.

### P4 — Agent auf Säule C
*Module:* `core/agent`, `core/backends/llm`, `ui/chat`

*Fertig, wenn:* Agenten-Suite zu Säule C besteht die Zielquote · bei
mehrdeutigen Anfragen wird `ask_user` benutzt · ein Vorschlag ist genau eine
Transaktion und wird mit einem Undo vollständig zurückgenommen · nach einem
Undo verweist kein Kontext mehr auf die verworfene Transaktion · jede Op ist
schemagültig, bevor gerechnet wird.

### P5 — Bausteinbibliothek
*Module:* `core/knowledge/parts`, `core/knowledge/standards`, `ui/catalog`

*Fertig, wenn:* dreizehn Bausteine über ihren Parameterbereich wasserdicht und
wandstärkenkonform · Features als Provenienz-IDs im Steckbrief · Vorschaubilder
automatisch gerendert · `to_scad()` erzeugt gültigen Quelltext · kein Kernpfad
benötigt OpenSCAD · `parts_version` in der Projektdatei, geänderter Baustein
wird beim Öffnen namentlich gemeldet · eigene Bausteine aus dem Nutzerordner
werden geladen und reisen nachweislich nicht mit der Projektdatei.

### P6 — Säule A
*Fertig, wenn:* Agenten-Suite zu Säule A besteht · Bausteine werden messbar vor
eigener Geometrie bevorzugt · Hauptabmessungen landen messbar als Parameter ·
**Weg 2 aus §2.2 läuft als Ende-zu-Ende-Test** · abgewiesener
OpenSCAD-Quelltext mit `include` wird nachweislich nicht ausgeführt.

### P7 — Slicer-Rückkopplung und Kalibrierung
*Fertig, wenn:* die G-Code-Gegenprobe weicht auf dem Korpus um weniger als
15 % von der internen Schätzung ab, größere Abweichung erscheint als Befund ·
Herkunft jeder Kennzahl im Bericht ausgewiesen (intern oder G-Code) ·
geänderte Profilwerte schlagen auf bestehende Projekte durch, ohne sie zu
ändern · Suche bei gleichem Startwert reproduzierbar.

### P8 — Erste Veröffentlichung
*Fertig, wenn:* Name entschieden · Installationsdateien aus der CI für alle
Zielplattformen · alle Texte übersetzt · die drei Beispielprojekte öffnen und
rechnen fehlerfrei · Erstinbetriebnahme führt bis zum ersten Import ·
Lizenzhinweise vollständig.

Bewusst **vor** Säule B: Der Editor mit Agent ist für sich vollständig, und
frühe Rückmeldungen sind mehr wert als ein weiteres Feature.

### P9 — Säule B und Farbe
*Fertig, wenn:* generiertes Mesh durchläuft die Reparaturkette zu einem
wasserdichten Ergebnis · Slot-Zuweisung überlebt Boolesche Ops einschließlich
Stufe „voxel" · Quantisierung bei gleichem Startwert reproduzierbar · `3MF`
öffnet im Slicer mit korrekten Farbgruppen · **Weg 3 aus §2.2 als
Ende-zu-Ende-Test**.

### P10 — Auto Split mit Verstiftung
*Fertig, wenn:* jedes Teil einzeln wasserdicht · Passungspaare automatisch
angelegt und geprüft · `oversized.stl` wird ohne Eingriff druckbar zerlegt.

### P11 — Gehosteter Generierungs-Backend, falls Nachfrage besteht.

### P12 — B-Rep-Kern
*Fertig, wenn:* Verrundung an einer Referenzkante geometrisch exakt · STEP
rundreisefähig · Kennzeichnung Mesh/B-Rep korrekt.

### P13 — Skizzen und tiefere Konstruktion
*Module:* `core/sketch` (Datenmodell, Solver), `core/brep`
(Formgebungs-Ops), `ui/sketch` (Editor)

*Fertig, wenn:* der Solver bei gleichem Modell die gleiche Lösung liefert ·
widersprüchliche Bedingungen nennen das kollidierende Paar statt
„fehlgeschlagen" · ein Skizzenmaß rechnet mit einem Projektparameter und die
Änderung schlägt durch · die Grundformen sind über Dialog, CLI und Agent ohne
Grafikeditor benutzbar · der Agent erzeugt nachweislich keine rohen
Punktlisten · ein Referenzteil (Gehäuse mit passendem Deckel) entsteht von
leerer Szene bis Export ohne Fremd-CAD, als Ende-zu-Ende-Test · Formschräge,
exakte Schale, Sweep, Loft und exaktes Gewinde mit Geometrietest gegen den
Korpus · Skizzen-Solver im Leistungsziel (§31) · ohne `brep` bleibt alles
andere benutzbar.

Die erste Veröffentlichung wartet auf diese Phase (Entscheidung vom
31.07.2026): der Launch führt die Skizzen als Kernargument. Die
Veröffentlichungsreste aus P8 laufen parallel.

---

## 41. Ausbaustufen

**Vorlagenbibliothek.** Projekte ohne Quellen, nur mit Parametern und
Bausteinen, sind bereits Vorlagen (§13) — es fehlt nur die Verwaltung.

**Verzweigungen im Stack.** Mehrere Varianten nebeneinander statt Verwerfen.

**Fallbibliothek.** Erfolgreiche Paare aus Anfrage und Transaktion speichern
und bei ähnlichen Anfragen mitgeben. **Die Anfragen der Testsuite dürfen nie
hineinwandern**, sonst misst man nur das eigene Gedächtnis. Strikt lokal.

**Stapelverarbeitung** über den Kommandozeilen-Einstieg.

**Modell-Vergleich.** Zwei Fassungen überlagern, Unterschiede zeigen.

**Druckerhistorie.** Was wurde wann mit welchen Einstellungen gedruckt, mit
Ergebnisnotiz. Speist die Regelsammlung.

**Bewusst nicht:** Web-Anwendung im Browser, Mehrbenutzerbetrieb, Cloud-Ablage
von Projekten, Plugin-System, Telemetrie, eigener G-Code-Slicer.

Zur Abgrenzung: Eigene Bausteine (§24.5) sind **kein** Plugin-System. Sie
erweitern die Bibliothek, nicht die Anwendung, gelten nur lokal und reisen nie
mit einer Projektdatei.

---

## 42. Grenzen, die bleiben

- Generierte Meshes sind maßlich unpräzise; für Passungen taugen sie nicht
- Strukturen unter etwa 1 mm Wandstärke bleiben fragil
- Ein importiertes Mesh hat keine Konstruktionshistorie — was aus einem STL
  nicht erkennbar ist, kann auch die beste Feature-Erkennung nicht
  rekonstruieren (bei STEP anders, §30)
- Rückfallstufe „voxel" rettet die Operation, kostet aber Genauigkeit
- Reproduzierbarkeit gilt nur bei gleichen Bibliotheksversionen
- Farbquantisierung aus Texturen bleibt gröber als das Rendering
- Verrundungen auf Mesh-Kanten bleiben ein Kompromiss bis zum B-Rep-Kern
- Baugruppen mit echten Funktionstoleranzen bleiben Handarbeit; der Agent
  liefert den Entwurf, nicht das Endergebnis

---

## 43. Nächster Schritt

**P0, in dieser Reihenfolge:**

1. Paketstruktur mit Importtest
2. `core/types.py` — die Verträge aus §9, bevor irgendetwas sie benutzt
3. `core/errors.py` — die Hierarchie aus §33.1
4. Zahlen- und Toleranzkonventionen (§11) — `core/units.py`
5. Operationsregister mit einer Beispiel-Op
6. Szene, Parameter, Op-DAG, Auswertung, Transaktionen
7. Projektcontainer mit Version und Migrationsgerüst
8. Eingangsstufe
9. Testkorpus anlegen (§34)
10. Oberfläche: Grundfenster nach §2.5, Viewport, Objektbaum, Parameterleiste
11. Kommandozeilen-Einstieg

Regeln in `AGENTS.md`, Arbeitsliste in `ROADMAP.md`.
