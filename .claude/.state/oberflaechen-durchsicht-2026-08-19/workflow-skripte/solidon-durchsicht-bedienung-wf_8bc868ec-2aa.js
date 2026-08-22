export const meta = {
  name: 'solidon-durchsicht-bedienung',
  description: 'Breite Durchsicht der Solidon-Oberflaeche: Bedienbarkeit, Funktionen, Uebersicht, Design, Demo-Reife',
  phases: [
    { title: 'Durchsicht', detail: '14 Gebiete parallel, je mit Belegstellen' },
    { title: 'Gegenpruefung', detail: 'jeder Fund einzeln widerlegt oder bestaetigt' },
  ],
}

const CONTEXT = `
Projekt Solidon: Desktop-CAD in Python 3.14 mit PySide6, Arbeitsverzeichnis C:\\Users\\rober\\Documents\\Solidon.
Verbindliche Unterlagen: 3d-agent-bauplan.md (Sollverhalten, §-Nummern), AGENTS.md (22 harte Regeln),
.claude/rules/oberflaeche.md (Oberflaechenregeln, Grenzwerte), ROADMAP.md (Stand und frueheres Gefundene).
Python: .venv\\Scripts\\python.exe

WICHTIG:
- Aendere KEINE Datei. Das ist eine Durchsicht, nicht ein Umbau. Nur lesen, suchen, ggf. Python zur Messung ausfuehren.
- Jeder Fund braucht eine Belegstelle als datei.py:zeile und ein Zitat der belegenden Zeile(n).
- Rate nicht. Was du nicht am Code belegen kannst, laesst du weg.
- Vieles wurde schon geprueft (siehe ROADMAP-Ende). Trotzdem alles neu pruefen: der Auftrag lautet ausdruecklich,
  auch schon Kontrolliertes noch einmal zu pruefen. Aber ein Fund, der in ROADMAP.md als erledigt steht UND im Code
  wirklich erledigt ist, ist kein Fund.
- Kontext: Morgen (20.08.2026) soll die Demo auf der Webseite bereitstehen. Markiere jeden Fund, der einen
  ersten Nutzer der Demo trifft, mit demo_blocker=true.
- Auch kleine Funde sind gewollt: alles, was behoben werden sollte, wird gemeldet — aber belegt.
- Bewerte streng nach Nutzersicht: Bedienbarkeit, Entdeckbarkeit von Funktionen, Uebersichtlichkeit,
  modernes und schoenes Aussehen. Ein haesslicher, aber regelkonformer Zustand ist ein Fund.
`

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['area', 'findings'],
  properties: {
    area: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'where', 'evidence', 'why', 'fix', 'severity', 'demo_blocker', 'category'],
        properties: {
          title: { type: 'string', description: 'ein Satz, deutsch, sagt was nicht stimmt' },
          where: { type: 'string', description: 'datei.py:zeile (oder mehrere)' },
          evidence: { type: 'string', description: 'Zitat der belegenden Zeilen' },
          why: { type: 'string', description: 'warum das den Nutzer trifft; ggf. Regel- oder §-Nummer' },
          fix: { type: 'string', description: 'konkreter Vorschlag, keine Prosa' },
          severity: { type: 'string', enum: ['hoch', 'mittel', 'niedrig'] },
          demo_blocker: { type: 'boolean' },
          category: { type: 'string', enum: ['bedienbarkeit', 'funktion', 'uebersicht', 'design', 'text', 'demo', 'barrierefreiheit', 'fehler'] },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  additionalProperties: false,
  required: ['stands', 'reason'],
  properties: {
    stands: { type: 'boolean', description: 'true = Fund haelt der Gegenpruefung stand' },
    reason: { type: 'string', description: 'ein bis drei Saetze, mit Belegstelle' },
    correction: { type: 'string', description: 'falls der Fund halb richtig ist: was wirklich stimmt' },
  },
}

const AREAS = [
  {
    key: 'startbildschirm',
    prompt: `Gebiet: Startbildschirm, Erstlauf, Tour, Einrichtung.
Dateien: app/ui/start_screen.py, app/ui/first_run.py, app/ui/tour.py, app/ui/splash.py, app/ui/install_dialog.py,
app/core/tour.py, app/core/examples.py, konzept-erstnutzer-2026-08.md.
Frage: Was sieht und tut jemand in den ersten drei Minuten, der Solidon zum ersten Mal startet? Wo bleibt er haengen,
was versteht er nicht, was sieht schaebig aus? Ist der Startbildschirm ein guter erster Eindruck fuer eine Demo?
Pruefe auch: Fenstergroesse beim ersten Start, was passiert ohne Netz und ohne KI-Schluessel, was passiert bei
leerer Zuletzt-Liste, ob die neun Beispiele ohne Scrollen erfassbar sind, ob die Begriffe (Weg 1..4) einem
Erstnutzer etwas sagen.`,
  },
  {
    key: 'hauptfenster',
    prompt: `Gebiet: Hauptfenster, Aufteilung, Uebersichtlichkeit.
Dateien: app/ui/main_window.py (6000 Zeilen — arbeite mit grep, lies gezielt), app/ui/panels.py, app/ui/header.py,
app/ui/tool_strip.py.
Frage: Ist das Fenster uebersichtlich? Pruefe die drei Zonen aus .claude/rules/oberflaeche.md, die Grenzwerte
(<=9 Menues, <=12 Zeilen je Menue, <=8 Umschalter), die Statusleiste (was steht dort gleichzeitig, ist es
zuordenbar), die linke Spalte (Objekte/Parameter/Verlauf — Platzverteilung, was passiert wenn der Verlauf lang
wird, ist der Verlauf lesbar/gruppiert), die rechte Spalte. Sag, wo Leerraum verschwendet und wo gedraengt wird.`,
  },
  {
    key: 'designsystem',
    prompt: `Gebiet: Aussehen — Farben, Abstaende, Typografie, Rundungen, Symbole.
Dateien: app/ui/style.py, app/ui/theme.py, app/ui/palette.py, app/ui/icons.py, app/ui/motion.py.
Frage: Sieht das aus wie eine 2026er Anwendung? Pruefe konkret: gibt es eine Schriftgroessen-Hierarchie oder ist
alles gleich gross; gibt es ein Abstandsraster (4/8 px) oder gestreute Zahlen; Ecken-Radien; Rahmenstaerken und ob
ueberall 1px-Kaesten stehen wo ein Abstand genuegte; Zustaende hover/pressed/focus/disabled fuer jedes Element;
Fokusring sichtbar; Umschaltknoepfe; Bildlaufleisten; Reiter. Zaehle die verschiedenen verwendeten Grauwerte und
Radien und melde Streuung als Fund. Belege jede Zahl mit der Zeile im Stylesheet.`,
  },
  {
    key: 'dialoge',
    prompt: `Gebiet: Operationsdialoge und die uebrigen Dialoge.
Dateien: app/ui/op_dialog.py, app/ui/dialogs.py, app/ui/report_dialog.py, app/ui/variants_dialog.py,
app/ui/settings_dialog.py, app/ui/shortcuts_window.py.
Frage: Wie fuehlt sich ein Operationsdialog an? Pruefe: gestufte Tiefe (Vorderseite/Weitere Einstellungen),
Groesse und Leerraum (waechst der Dialog mit dem Inhalt oder steht er auf einer festen Groesse — sizeHint,
setFixedSize, setMinimumHeight suchen), Feldbreiten (ein 4-stelliges Zahlenfeld ueber 300 px breit ist ein Fund),
Tastaturbedienung (Enter, Esc, Tab-Reihenfolge, Anfangsfokus), Vorschau der Wirkung, Einheitenanzeige,
fx-Ausdrucksknopf (erklaert er sich?), Reihenfolge und Beschriftung der Knoepfe, was bei ungueltiger Eingabe
passiert. Pruefe app/ui/labels.py auf rohe Schluessel, die als Auswahlwert beim Nutzer landen (z. B. Achse "z").`,
  },
  {
    key: 'entdeckbarkeit',
    prompt: `Gebiet: Findet der Nutzer die Funktionen?
Dateien: app/ui/command_palette.py, app/ui/tool_strip.py, app/core/registry/, app/ui/main_window.py (Menuebau),
app/ui/shortcut_schemes.py, app/ui/shortcuts_window.py.
Frage: Zaehle die registrierten Operationen und pruefe je Operation, ob sie ueber Menue, Kontextmenue, Palette und
Kuerzel erreichbar ist. Nenne Operationen, die NUR ueber die Palette erreichbar sind, und ob das begruendet ist.
Pruefe die Menuetitel und Operationstitel auf Verstaendlichkeit fuer einen Nichtfachmann. Pruefe, ob die
Befehlspalette Beschreibung, Kuerzel und Grund fuer Nichtverfuegbarkeit zeigt, ob sie Tippfehler vertraegt
(Fuzzy-Suche) und ob sie auch Einstellungen/Ansichten findet, nicht nur Operationen. Nutze
.venv\\Scripts\\python.exe fuer eine Auszaehlung aus dem Register.`,
  },
  {
    key: 'texte',
    prompt: `Gebiet: Die Texte, die der Nutzer liest.
Dateien: app/core/errors.py, app/ui/labels.py, app/core/*/ (Befundtexte), app/i18n/locales/.
Frage: Pruefe eine Stichprobe von mindestens 25 Befund- und Fehlertexten auf: sagt der Text, was der Nutzer jetzt
tun kann (§2.7, Regel 17); ist er ohne Fachwort verstaendlich; steht ein roher Bezeichner oder eine Zahl ohne
Einheit darin. Pruefe, ob jede Ausnahme in errors.py wirklich irgendwo erzeugt wird (tote Ausnahmen mit
Handlungsvorschlaegen, die niemand sieht) und ob jede Ausnahme, die erzeugt wird, Vorschlaege hat. Pruefe
Vollstaendigkeit und Qualitaet der Kataloge in app/i18n/locales — fehlende Eintraege, deutsche Reste im
englischen Katalog, unuebersetzte Auswahlwerte.`,
  },
  {
    key: 'demoreife',
    prompt: `Gebiet: Demo-Reife (das ist der wichtigste Punkt — morgen soll die Demo auf der Webseite stehen).
Dateien: app/core/activation/ (store.py, keys.py), app/ui/install_dialog.py, app/branding.py, website/, packaging/,
tools/make_installer.py, ROADMAP.md (Abschnitt "Die Demo bis 30.10.2026").
Frage: Was erlebt jemand, der morgen die Demo von der Webseite laedt? Pruefe genau:
1. Die Demo-Frist: ist sie ein festes Datum (30.10.2026) oder eine Frist ab Installation? Ein festes Datum heisst,
   dass ein Nutzer im Oktober nur noch Tage hat und im November gar nichts — belege am Code und bewerte.
2. Was ist in der Demo gesperrt, wie erfaehrt der Nutzer davon, und ist die Sperre freundlich formuliert?
3. Der Text in der Statusleiste ("Demo — noch 74 Tage, bis zum 30.10.2026") — verstaendlich? Zu aufdringlich? Zu leise?
4. Die Webseite: gibt es einen Download-Kasten mit Datei, Groesse, Pruefsumme, Systemvoraussetzungen? Stimmt
   website/version.json mit app/branding.py und pyproject.toml zusammen?
5. Braucht die Demo Netz, Konto oder KI-Schluessel fuer irgendetwas, das nicht KI ist?
6. Was passiert nach Fristende — Sackgasse oder Weg zum Kauf?`,
  },
  {
    key: 'druckdialog',
    prompt: `Gebiet: Druckeinstellungen und Uebergabe an den Slicer — der groesste Dialog der Anwendung.
Dateien: app/ui/print_settings_dialog.py (2000 Zeilen — grep-gefuehrt lesen), app/core/knowledge/print_settings.py,
app/core/export/handover.py, app/core/export/slicer_keys.py.
Frage: Ist dieser Dialog uebersichtlich? Zaehle Felder, Gruppen und Reiter. Pruefe: findet ein Anfaenger die drei
Werte, die er wirklich braucht; sind die Vorgaben gut genug, dass er nichts anfassen muss; ist die Herkunft jedes
Wertes ausgewiesen (Profil, Material, Analyse — §22.5, Regel 14); was passiert, wenn kein Slicer installiert ist;
ist der Weg vom Modell zum gedruckten Teil ohne Umweg. Melde jede Stelle, an der der Dialog Fachwissen voraussetzt,
das er selbst haette liefern koennen.`,
  },
  {
    key: 'chat',
    prompt: `Gebiet: Chat und Generierung (Weg 3), also die KI-Seite an der Oberflaeche.
Dateien: app/ui/chat.py, app/ui/generate_dialog.py, app/core/agent/, app/ui/facts.py.
Frage: Wie fuehlt sich das Gespraech an? Pruefe: was steht im leeren Chat (Vorschlaege? Beispiele? oder ein leeres
Feld); wie wird ein Vorschlag des Agenten angezeigt und wie nimmt man ihn an oder zurueck (Regel 16: eine
Transaktion, ein Undo); was passiert ohne Schluessel/ohne Netz und wie erklaert die Oberflaeche das; wie lange
darf es dauern und was sieht man dabei; kann man mittendrin abbrechen; sieht man, was die KI kostet oder wie oft
sie noch darf; was passiert bei einer Rueckfrage des Agenten (ctx.ask). Pruefe den Generierungsdialog auf dieselben
Fragen und darauf, ob ein Ergebnis vor dem Uebernehmen zu sehen ist.`,
  },
  {
    key: 'skizze',
    prompt: `Gebiet: Skizzeneditor (Weg 2).
Dateien: app/ui/sketch_editor.py (2755 Zeilen — grep-gefuehrt lesen), app/core/sketch/.
Frage: Kann jemand ohne CAD-Erfahrung hier ein Rechteck mit einem Loch zeichnen und daraus einen Koerper machen?
Zaehle die Knoepfe der Leiste und pruefe ihre Beschriftung/Symbole. Pruefe: Werkzeugwechsel und Esc-Verhalten,
Rueckgaengig in der Zeichenflaeche, Sichtbarkeit von Bedingungen, was ein unterbestimmtes/ueberbestimmtes System
dem Nutzer sagt, was beim Loeser-Fehlschlag passiert, wie man aus der Skizze herauskommt und was dann entsteht,
und ob die Zahlenfelder sich erklaeren. Melde jede Stelle, die CAD-Fachsprache verlangt.`,
  },
  {
    key: 'viewport',
    prompt: `Gebiet: Die 3D-Ansicht — Aussehen und Navigation.
Dateien: app/ui/viewport.py (3900 Zeilen — grep-gefuehrt lesen), app/ui/overlay.py, app/ui/cursors.py,
app/ui/scale_widget.py, app/ui/theme.py (viewport_colours).
Frage: Sieht das Bild gut aus? Pruefe: Material und Beleuchtung des Koerpers (ein flaches Grau ist ein Fund),
Kanten, Umgebungsverdeckung, Schatten, Hintergrundverlauf, Raster und Beschriftung, Druckplatte, Orientierungswuerfel,
Auswahl-Hervorhebung, Ueberlagerungen (verdecken sie das Modell?), Navigation (Zoom auf Zeiger? Traegheit? passt
das zu Fusion/Blender-Gewohnheiten?), was beim leeren Viewport steht, was bei einem sehr grossen und einem sehr
kleinen Modell passiert. Nenne konkret, was das Bild moderner machen wuerde, mit der Zeile, an der es haengt.`,
  },
  {
    key: 'webseite',
    prompt: `Gebiet: Die Webseite, auf der die Demo morgen liegen soll.
Dateien: website/ (alle .html, .css, version.json), marketing/, README.md.
Frage: Pruefe die Seiten wie ein Besucher: sagt die Startseite in fuenf Sekunden, was das Programm ist und fuer
wen; gibt es einen sichtbaren Download-Weg; sind Preis, Demo-Bedingungen, Systemvoraussetzungen und Rechtstexte
(EULA, AGB, Widerruf, Datenschutz) verlinkt und stimmig; sind alle internen Links vorhanden (pruefe jeden href
gegen die Dateien); sind die Zahlen (Version, Fassung, Anzahl Operationen/Bausteine/Beispiele) mit dem Code
stimmig; funktioniert die Seite auf einem Telefon (pruefe die CSS-Bruchpunkte); ist das Handbuch verlinkt und
aktuell erzeugt. Sieht die Seite modern aus? Belege am CSS.`,
  },
  {
    key: 'barrierefreiheit',
    prompt: `Gebiet: Barrierefreiheit und Bedienung ohne Maus.
Dateien: app/ui/style.py, app/ui/palette.py, app/ui/panels.py, app/ui/main_window.py, tests/test_accessibility.py,
tests/test_style.py.
Frage: Pruefe Regel 18 (keine Bedeutung allein ueber Farbe) an JEDER Stelle, die faerbt — Pruefbericht, Analysekarten,
Differenzansicht, Objektbaum, Verlauf, Statusleiste, Chat, Skizze, Druckdialog: gibt es ueberall eine zweite
Kodierung? Rechne die Kontraste der Textrollen beider Themen mit theme.contrast_ratio nach (nutze
.venv\\Scripts\\python.exe) und melde alles unter 4,5 fuer Text und unter 3,0 fuer Bedeutungsflaechen. Pruefe
Tastaturbedienung: erreicht Tab jedes Bedienelement, ist der Fokus sichtbar, gibt es Tastenfallen, funktioniert
alles ohne Maus. Pruefe Screenreader-Namen (setAccessibleName/Description) an den Ansichten.`,
  },
  {
    key: 'wartezeit',
    prompt: `Gebiet: Start, Wartezeit, Stabilitaet unter Bedienung.
Dateien: app/ui/app.py, app/ui/splash.py, app/ui/loading.py, app/ui/leash.py, app/ui/session.py,
app/ui/main_window.py (Arbeiter, waiting()).
Frage: Pruefe die Wartezeit-Tabelle aus .claude/rules/oberflaeche.md an jedem Ort, der rechnet: unter 0,2 s nichts,
bis 2 s Zeiger und Statusleiste, darueber Fortschritt MIT Abbrechen und bedienbarer Oberflaeche, ueber 10 s
Schaetzung. Suche jede Stelle, die im Qt-Hauptthread rechnet oder eine Datei liest, ohne das anzuzeigen (grep nach
read_bytes, open(, evaluate, subprocess, requests). Messe die Importzeit von app.ui.main_window und melde, was
davon vermeidbar ist. Pruefe, ob jeder gestartete Arbeiter festgehalten wird (Halteleine) und ob Abbrechen
ueberall wirkt.`,
  },
]

phase('Durchsicht')
log(`${AREAS.length} Gebiete gehen parallel durch die Durchsicht`)

const results = await pipeline(
  AREAS,
  (a) => agent(`${CONTEXT}\n\n${a.prompt}\n\nGib deine Funde ueber das strukturierte Schema zurueck. Sortiere sie selbst nach Schwere. Weniger, belegte Funde sind besser als viele geratene.`,
    { label: `durchsicht:${a.key}`, phase: 'Durchsicht', schema: SCHEMA }),
  (res, a) => {
    if (!res || !res.findings || !res.findings.length) return { area: a.key, findings: [] }
    const top = res.findings.slice(0, 8)
    return parallel(top.map((f) => () =>
      agent(`${CONTEXT}

Gegenpruefung eines gemeldeten Funds. Versuche ihn zu WIDERLEGEN. Standard ist stands=false, wenn du unsicher bist.

Gebiet: ${a.key}
Behauptung: ${f.title}
Stelle: ${f.where}
Beleg: ${f.evidence}
Begruendung: ${f.why}

Lies die genannte Stelle und ihre Umgebung selbst. Pruefe auch, ob ROADMAP.md, .claude/rules/oberflaeche.md oder
ein Test die Sache schon anders regelt, und ob es an anderer Stelle im Code doch geloest ist (grep!).
Ein Fund ueber Aussehen ("sieht altbacken aus") ist kein Fund, wenn der Code das Gegenteil belegt;
er haelt aber stand, wenn der Code ihn belegt — auch wenn kein Test ihn verbietet.`,
        { label: `gegen:${a.key}`, phase: 'Gegenpruefung', schema: VERDICT })
        .then((v) => ({ ...f, area: a.key, verdict: v }))
    ))
  }
)

const all = results.flat().filter(Boolean).filter((f) => f && f.verdict)
const stands = all.filter((f) => f.verdict.stands)
const fell = all.filter((f) => !f.verdict.stands)
log(`${stands.length} Funde halten stand, ${fell.length} sind an der Gegenpruefung gestorben`)

return {
  bestaetigt: stands.map((f) => ({
    gebiet: f.area, titel: f.title, stelle: f.where, beleg: f.evidence, warum: f.why, fix: f.fix,
    schwere: f.severity, demo: f.demo_blocker, art: f.category, gegenpruefung: f.verdict.reason,
    korrektur: f.verdict.correction || '',
  })),
  gefallen: fell.map((f) => ({ gebiet: f.area, titel: f.title, grund: f.verdict.reason })),
}
