---
name: neues-druckteil
description: >
  Legt ein neues Druckteil im Ordner „3D Drucker“ an: Maße mit Quelle klären,
  parametrisches Skript mit trimesh/manifold3d, Netzprüfung mit Zahlen,
  STL-Export, Bauteil-Spezifikation und Druckhinweise für den Elegoo Centauri
  Carbon 2. Für Roberts eigene Druckprojekte, nicht für Solidons
  Bausteinbibliothek (/neuer-baustein). Abgeschlossen delegieren oder ein
  bestehendes Teil ändern: Agent druckteil-konstrukteur; Druckfragen:
  druck-berater.
argument-hint: "[was gebraucht wird]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neues Druckteil: $ARGUMENTS

Ein Teil, das gedruckt und benutzt wird; Material und Zeit sind echt. Werkstatt,
Ablage und Haltung regeln `.claude/rules/druckteile.md` und
`3D Drucker/CLAUDE.md`. Der Ordner ist ein eigenes Repository und fehlt auf
manchem Rechner — einen fehlenden Bestand nicht als leeren behandeln, sondern
sagen, dass er fehlt.

## 1. Maße klären, bevor irgendetwas entsteht

Die wichtigste Phase. Für jedes maßgebliche Maß steht fest, **woher es
kommt**: gemessen, Herstellerangabe, Ersatzteil — oder geschätzt, und dann als
geschätzt markiert. Ein geschätztes Passmaß heißt: erst ein **Prüfstück**, das
nur diese Passung enthält, dann das ganze Teil.

Frag nach, was du nicht wissen kannst: Spaltmaße, Blechdicken,
Rohrdurchmesser, Gewindegrößen, Anflugrichtungen. Raten ist hier teurer als
jede Rückfrage.

Gerät, Düse, Material und nutzbarer Bauraum kommen aus `3D Drucker/CLAUDE.md`;
fehlt der Ordner, ist `app/core/knowledge/data/printers.toml` ein Einstieg.
Passt das Teil nicht, eine Orientierung oder Teilung vorschlagen —
Funktionsmaße werden nicht gekürzt.

## 2. Konstruieren

Ablage nach dem Bestand des Ordners und `druckteile.md`: ein nummerierter
Projektordner, der aktuelle Stand im Projekt-Root, frühere Iterationen in
`Versuch N/`. Ein parametrisches Python-Skript mit `trimesh`/`manifold3d` in
einer vorhandenen Umgebung; keine Installation voraussetzen.

Aufbau nach dem Vorbild bestehender Skripte: benannte Maßkonstanten oben mit
Einheit und Quelle im Kommentar, ein `PART`-Schalter für Varianten und
Prüfstücke, Export am Ende. Spiel und Wandstärke sind **eigene Parameter**.
Die Konstruktionsrichtwerte — Wand und Orientierung, Spiel, Verbindung und
Festigkeit, Dichtheit — stehen in `references/fdm-konstruktion.md`.

## 3. Prüfen

Vor dem Export, und das Ergebnis wird gezeigt, nicht behauptet:

- `is_watertight` — topologisch geschlossen, kein Nachweis für
  Flüssigkeitsdichtheit
- Anzahl Komponenten — eine, wenn es eine sein soll
- Volumen und Bounding Box plausibel, passt auf die Platte
- keine Selbstdurchdringung, Normalen einheitlich
- dünnste Stelle über der Mindestwandstärke, mit Messverfahren und bei
  Stichproben deren Grenzen

Was nicht gemessen wurde, bleibt ausdrücklich offen.

## 4. Dokumentieren

Zu jedem Teil eine `*_Bauteil-Spezifikation.md` im Projektordner:

- Zweck und Einbausituation
- Maßtabelle **mit Quelle je Maß** und den offenen Messungen
- Materialwahl mit Begründung aus dem Bestand
- Druckhinweise: Orientierung, Stützen, Perimeter, Schichthöhe, Besonderheiten
- was vor dem Druck des ganzen Teils noch zu prüfen ist

Das Projekt bekommt seinen Eintrag in `3D Drucker/CLAUDE.md`. Eine STL, die
das Skript wiederherstellt, wird nicht eingecheckt — das Skript ist die Quelle
(`druckteile.md`).

## Haltung

Bei tragenden oder sicherheitsrelevanten Teilen Lastfall, Umgebung und
Versagensfolge klären. Geometrieprüfungen ersetzen keinen Belastungsversuch;
eine Schutzwirkung oder zulässige Last ohne passenden Nachweis nicht zusagen.
Ein berechnetes Modell ist noch kein erprobter Druck.
