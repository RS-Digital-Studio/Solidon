export const meta = {
  name: 'konzepte-recherche',
  description: 'Recherchiert je Themenfeld den heutigen Stand der Welt ausserhalb des Repositories und belegt jede Aussage mit Quelle',
  phases: [
    { title: 'Recherche', detail: 'ein Rechercheur je Themenfeld' },
  ],
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['cluster', 'facts', 'not_verifiable', 'surprises'],
  properties: {
    cluster: { type: 'string' },
    facts: {
      type: 'array',
      maxItems: 40,
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['entity', 'statement', 'as_of', 'confidence', 'sources'],
        properties: {
          entity: { type: 'string', description: 'Produkt, Firma, Paket oder Norm' },
          statement: { type: 'string', description: 'Der belegte Sachverhalt, ein Satz, mit Zahl wo es eine gibt' },
          as_of: { type: 'string', description: 'Wann das gilt bzw. Stand der Quelle, so genau wie die Quelle es hergibt' },
          confidence: { type: 'string', enum: ['belegt', 'mehrere_quellen', 'unsicher'] },
          sources: { type: 'array', maxItems: 4, items: { type: 'string', description: 'vollstaendige URL' } },
          note: { type: 'string', description: 'Einschraenkung, Widerspruch zwischen Quellen, oder warum es fuer Solidon zaehlt' },
        },
      },
    },
    not_verifiable: {
      type: 'array',
      maxItems: 15,
      items: { type: 'string', description: 'Was gesucht, aber nicht belastbar gefunden wurde — wörtlich, damit niemand es später für belegt hält' },
    },
    surprises: {
      type: 'array',
      maxItems: 10,
      items: { type: 'string', description: 'Was sich seit Anfang August 2026 geaendert hat und eine Entscheidung in Solidon beruehren koennte' },
    },
  },
}

const CLUSTERS = [
  {
    key: 'ki-3d-generatoren',
    prompt: `Themenfeld: **gehostete KI-3D-Generatoren**.

Recherchiere den heutigen Stand (August 2026) zu: Meshy AI, Hyper3D Rodin, Tripo AI (Tripo3D), Sloyd, CSM (Common Sense Machines), Luma AI Genie, Alpha3D, Kaedim.

Für jeden, soweit auffindbar:
- aktuelle Modellgeneration/Fassung und wann sie erschien
- Preismodell heute: Stufen, Monatspreis, Guthaben/Credits, was eine Generierung kostet, kostenlose Stufe
- API: gibt es eine, was kostet sie, welche Formate kommen heraus (STL, OBJ, GLB, USDZ, FBX), gibt es Quad-Topologie/Remesh, PBR-Texturen
- Rechte an den Ergebnissen: kommerzielle Nutzung, Unterschiede je Stufe
- ob es Funktionen gibt, die auf CAD/3D-Druck zielen (Maßhaltigkeit, Hohlkörper, Druckvorbereitung)

Besonders wichtig: **Meshy** und **Hyper3D Rodin**, weil Solidon sich mit beiden vergleicht.`,
  },
  {
    key: 'cad-wettbewerb',
    prompt: `Themenfeld: **CAD- und Modellierprogramme, gegen die Solidon antritt**.

Recherchiere den heutigen Stand (August 2026) zu: Autodesk Fusion (aktuelle Fassung, Preis gewerblich, Preis für Privatnutzung/Personal, was die kostenlose Fassung 2026 noch darf), FreeCAD (Fassung 1.x, Stand), SindriCAD (die Beta vom 02.08.2026 — was ist seither passiert, Fassung, Lizenz AGPL, Funktionsumfang, Snapmaker-Anbindung), Onshape (Free/Standard Preis), Plasticity (Preis, Fassung), Shapr3D, Alibre, SolidWorks for Makers (Preis), Tinkercad, OpenSCAD (Fassung), Blender (Fassung), nTop, Zoo/KittyCAD Text-to-CAD, Autodesk Fusion mit KI-Funktionen, sowie neue KI-gestützte CAD-Werkzeuge, die 2026 dazugekommen sind (auch Text-zu-CAD und parametrische KI-Assistenten).

Für jedes: Fassung, Preis heute in Euro oder Dollar, Lizenz, und was es beim 3D-Druck ausdrücklich kann.

Besonders wichtig: Belege den **Preis** so genau wie möglich, mit Stand und Quelle — Solidon begründet seinen eigenen Preis von 49 € daran.`,
  },
  {
    key: 'slicer',
    prompt: `Themenfeld: **Slicer und die Übergabe an sie**.

Recherchiere den heutigen Stand (August 2026) zu: OrcaSlicer (aktuelle Fassung, Änderungen 2026), ElegooSlicer (aktuelle Fassung, Herkunft, Verhältnis zu OrcaSlicer), PrusaSlicer, Bambu Studio, Ultimaker Cura (Fassung), Creality Print.

Für jeden:
- aktuelle Fassungsnummer und Erscheinungsdatum
- Kommandozeilenschnittstelle: welche Argumente nimmt er, kann man ein Projekt mit Einstellungen übergeben
- Projekt- und Profilformate: 3MF-Konventionen, welche Metadaten ein Slicer beim Öffnen liest, Profil-Dateiformate (.ini, .json), Namen der Einstellungsschlüssel
- ob und wie ein fremdes Programm Druckeinstellungen mitgeben kann, ohne die Oberfläche zu bedienen

Dazu: der Stand von **3MF** als Format (Fassung der Spezifikation, Erweiterungen: production, slice, beamlattice) und wie Bambu/Orca/Elegoo davon abweichen.

Und: **Elegoo Centauri Carbon 2** — Drucker, Bauraum, Fassung der Firmware, Besonderheiten, welcher Slicer mitgeliefert wird.`,
  },
  {
    key: 'lokale-3d-modelle',
    prompt: `Themenfeld: **lokal laufende Bild-zu-3D- und Text-zu-3D-Modelle und ihre Lizenzen**.

Solidon ruft ComfyUI über dessen HTTP-API auf und liefert Graphen mit, die an bestimmten Knotensammlungen und Gewichten hängen. Recherchiere den heutigen Stand (August 2026) zu:
- **ComfyUI** selbst: aktuelle Fassung, API-Stabilität, Änderungen 2026
- **Hunyuan3D** (2.0, 2.1 und Nachfolger): aktuelle Fassung, und vor allem die **Tencent Community License** — schließt sie weiterhin EU, Vereinigtes Königreich und Südkorea aus? Wortlaut und Quelle.
- **Step1X-3D** (Lizenz Apache-2.0?), **TripoSG** (MIT?), **TRELLIS** (Microsoft), **Stable Fast 3D / SF3D** (Stability), **Hi3DGen**, **PartCrafter**, und was 2026 sonst als offenes Bild-zu-3D dazugekommen ist
- **RMBG-2.0** (CC BY-NC?) und **INSPYRENET** (MIT?) fürs Freistellen
- Knotensammlung **ComfyUI-Hunyuan3d-2-1** und **ComfyUI-RMBG**: gibt es sie noch, aktuelle Fassung

Für jedes Modell: Lizenz wörtlich benannt, ob kommerzielle Nutzung erlaubt ist, ob Gebietsausschlüsse bestehen, Hardwarebedarf (VRAM).

Das ist rechtlich heikel — belege die Lizenzaussagen mit der Lizenzdatei oder Modellkarte selbst, nicht mit einem Blogbeitrag.`,
  },
  {
    key: 'llm-backends',
    prompt: `Themenfeld: **LLM-Backends für die Agentenschicht**.

Solidon spricht drei Wege an: ein gehostetes Modell (Anthropic), ein lokales über Ollama, und ein eigenes. Recherchiere den heutigen Stand (August 2026):

- **Ollama**: aktuelle Fassung, Werkzeugaufrufe (tool calling) — welche Modelle können es zuverlässig, wie wird das Kontextfenster gesetzt (num_ctx), Änderungen 2026 an der API
- **Lokale Modelle mit Werkzeugaufrufen**: Stand von qwen3, llama3.x, mistral, devstral, gpt-oss und was 2026 dazugekommen ist — welche Größen laufen auf 16 GB oder 24 GB VRAM und rufen Werkzeuge zuverlässig auf
- **OpenAI-kompatible lokale Server**: llama.cpp, LM Studio, vLLM — Stand der Werkzeugunterstützung
- **Preise gehosteter Modelle** je Million Token, Stand heute, für die Anbieter, die für eine Desktop-Anwendung mit Schlüssel des Nutzers in Frage kommen

Nicht recherchieren musst du die Anthropic-Modell-IDs und -Preise — die liegen mir bereits vor. Prüfe stattdessen, **ob claude-sonnet-4-5 heute noch ein gültiger Modellname bei Anthropic ist** oder ob er abgekündigt/eingestellt wurde, und ab wann.`,
  },
  {
    key: 'python-fassungen',
    prompt: `Themenfeld: **Fassungsstand der Python-Abhängigkeiten**.

Im Repository liegt \`constraints.txt\` mit festgeschriebenen Fassungen. Lies die Datei (Arbeitsverzeichnis ist die Repository-Wurzel), und recherchiere für die **wichtigen** Pakete darin, welche Fassung heute (August 2026) auf PyPI die neueste ist und ob dazwischen etwas Bemerkenswertes passiert ist (Bruch, Sicherheitslücke, Abkündigung).

Wichtig sind: PySide6, numpy, scipy, trimesh, manifold3d, shapely, vtk, pyvista, pyvistaqt, scikit-image, matplotlib, pillow, networkx, rtree, mypy, ruff, pytest, cadquery-ocp (OCP/OpenCASCADE), fast_simplification, vhacdx, lxml, requests, setuptools, Cython.

Dazu:
- **Python selbst**: welche Fassung ist aktuell, welche ist die neueste stabile, Stand des Freigabeplans (3.14, 3.15), und welche Fassungen sind noch im Sicherheitsdienst
- **trimesh**: das Projekt hält \`trimesh<5\` als Grenze wegen einer aufgeschobenen Migration — was hat sich in trimesh 5 geändert, gibt es einen Migrationsleitfaden, und gibt es schon eine 6er-Reihe
- **PyInstaller** und **Inno Setup**: aktuelle Fassungen, Änderungen, die eine Windows-Auslieferung betreffen (SmartScreen, Signierung)

Gib je Paket: heutige neueste Fassung mit Datum, und ob der Sprung von der festgeschriebenen Fassung ein bekanntes Risiko trägt.`,
  },
  {
    key: 'recht-und-vertrieb',
    prompt: `Themenfeld: **Verkauf einer Desktop-Anwendung aus Deutschland an Verbraucher in der EU**.

Solidon soll als Kaufsoftware mit Freischaltschlüssel verkauft werden (geplant 49 €, Demo bis 30.10.2026). Recherchiere den heutigen Stand (August 2026):

- **Widerrufsrecht bei digitalen Inhalten** in Deutschland/EU: was muss vor dem Download eingeholt werden, wie lautet die verlangte Zustimmung, was hat sich 2025/2026 geändert
- **Cyber Resilience Act (CRA)**: Zeitplan der Pflichten — ab wann gelten Meldepflichten, ab wann die vollen Anforderungen, und was bedeutet das für einen Einzelentwickler, der Software gegen Geld vertreibt
- **EU Produktsicherheitsverordnung GPSR**: gilt sie für Software, welche Angaben verlangt sie
- **EU AI Act**: welche Fristen sind 2026 in Kraft, betrifft Transparenzpflicht (Art. 50) eine Anwendung, die ein fremdes LLM einbindet, und was ist mit KI-erzeugten 3D-Modellen und Kennzeichnung
- **Barrierefreiheitsstärkungsgesetz (BFSG) / European Accessibility Act**: seit Juni 2025 in Kraft — betrifft es verkaufte Desktop-Software, gibt es eine Kleinstunternehmer-Ausnahme
- **Zahlungsabwicklung für Einzelentwickler**: Stand und Gebühren von Paddle, Lemon Squeezy (Betrieb nach der Übernahme durch Stripe — läuft es noch?), Stripe, Gumroad, FastSpring, Polar.sh — wer übernimmt die Umsatzsteuer als Merchant of Record, Gebührensätze heute
- **Code Signing für Windows**: Stand der Anforderungen (EV-Zertifikate, Hardware-Token, Azure Trusted Signing — Preis und Zugangsvoraussetzungen), und wie SmartScreen heute unsignierte Anwendungen behandelt

Das ist Rechtsrecherche: gib Quelle und Stand an, und schreibe ausdrücklich dazu, wo die Quellenlage unklar ist. Keine Rechtsberatung, nur Fundstellen.`,
  },
  {
    key: 'organische-modellierung',
    prompt: `Themenfeld: **organische Modellierung, Sculpting und Skelett-Posing**.

Solidon plant/baut Sculpting-Pinsel, Subdivision, Symmetrie, Displacement und Posing über ein Skelett, alles innerhalb einer Operation im Stapel. Recherchiere den heutigen Stand (August 2026):

- **Sculpting-Programme**: Blender (Fassung, Sculpt-Mode, Remesh), ZBrush (Maxon, Preis, Fassung), Nomad Sculpt, Plasticity, 3D-Coat, Womp — was können sie, was kosten sie
- **Bibliotheken** für dieselbe Aufgabe in Python/C++: OpenVDB (VDB-Remesh), libigl, PyMeshLab (Lizenz beachten — GPL?), Instant Meshes, quadriflow, geogram, CGAL — Lizenzen und ob sie für ein kommerzielles Produkt ohne GPL benutzbar sind
- **Rigging/Posing automatisch**: Mixamo (Stand, gibt es den Dienst noch), Rignet, UniRig, Anything World, und was 2026 an automatischer Skelettierung dazugekommen ist
- **KI-Sculpting**: gibt es 2026 Werkzeuge, die per Text eine organische Form ändern statt neu zu erzeugen
- **Für den 3D-Druck relevant**: Wandstärke bei organischen Formen, Hohlkörper, Stützstrukturen — gibt es dafür etablierte Verfahren oder Werkzeuge

Achte besonders auf **Lizenzen**: Solidon darf keine GPL-Abhängigkeit einziehen. Nenne für jede Bibliothek die Lizenz wörtlich und die Quelle.`,
  },
]

phase('Recherche')

const results = await parallel(CLUSTERS.map((c) => () =>
  agent(
    `Du recherchierst für das Projekt Solidon online den heutigen Stand eines Themenfelds. Heute ist der 19. August 2026.

**Werkzeuge:** Lade zuerst die Suchwerkzeuge mit einem einzigen Aufruf:
ToolSearch mit query "select:WebSearch,WebFetch"
Dann suche. Nutze WebSearch zum Finden und WebFetch, um die gefundene Seite wirklich zu lesen — eine Suchergebnis-Zusammenfassung allein ist kein Beleg für eine Zahl. Bei Preisen und Lizenzen: hole die Seite des Anbieters selbst.

${c.prompt}

**Wie du arbeitest — das ist der wichtigste Teil:**

- Jede Faktenkarte trägt mindestens eine vollständige URL. Ohne Quelle keine Karte.
- Zahlen (Preise, Fassungen, Fristen) nur aus einer Seite, die du wirklich geholt hast.
- Dein Trainingswissen reicht bis Mai 2026 und ist damit **zu alt für dieses Themenfeld**. Was du zu wissen glaubst, prüfst du nach oder lässt es weg.
- Wenn du etwas nicht findest, schreibst du es in \`not_verifiable\` — wörtlich und mit dem, was du gesucht hast. **Nichts erfinden, nichts plausibel ergänzen.** Eine ehrliche Lücke ist wertvoll, eine erfundene Zahl ist Schaden.
- Widersprechen sich zwei Quellen, nimm die des Anbieters und notiere den Widerspruch im Feld \`note\`.
- \`surprises\`: was hat sich seit Anfang August 2026 geändert, das eine Entscheidung in Solidon berühren könnte.

Suche gründlich — mehrere Anfragen je Gegenstand, verschiedene Formulierungen, auch auf Deutsch und Englisch. Deutsch schreiben, echte Umlaute.`,
    { label: `recherche:${c.key}`, phase: 'Recherche', schema: SCHEMA, effort: 'high' }
  )
))

return results.filter(Boolean)
