---
name: neues-druckteil
description: >
  Legt ein neues Druckteil im Ordner „3D Drucker" an: Maße klären, parametrisches
  Skript mit trimesh/manifold3d, Netzprüfung, STL-Export, Bauteil-Spezifikation und
  Druckhinweise für den Elegoo Centauri Carbon 2.
argument-hint: "[was gebraucht wird]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neues Druckteil: $ARGUMENTS

Ein Teil, das gedruckt und benutzt wird. Material und Zeit sind echt.

## 1. Maße klären, bevor irgendetwas entsteht

Die wichtigste Phase. Für jedes maßgebliche Maß muss feststehen, **woher es
kommt**: gemessen, aus einer Herstellerangabe, aus einem Ersatzteil, oder
geschätzt. Geschätzte Maße werden als solche markiert — und ein geschätztes
Passmaß bedeutet: erst ein **Prüfstück**, das nur diese Passung enthält, dann
das ganze Teil.

Frag nach, was du nicht wissen kannst: Spaltmaße, Blechdicken, Rohrdurchmesser,
Gewindegrößen, Anflugrichtungen. Raten ist hier teurer als jede Rückfrage.

Prüfe das aktuell verwendete Gerät und Profil einschließlich Bauraum,
Düse, Material und verfügbarer Bauhöhe; benutze vorhandene Angaben, bevor
du erneut fragst. `app/core/knowledge/data/printers.toml` ist ein Einstieg,
die tatsächliche Konfiguration entscheidet. Passt das Teil nicht, eine
geeignete Orientierung oder Teilung vorschlagen; Funktionsmaße nicht kürzen.

## 2. Konstruieren

Den beauftragten Druckteilordner zuerst lokalisieren; `3D Drucker/` ist nicht
in jedem Klon vorhanden. Einen fehlenden Bestand nicht als leeren Bestand
behandeln. Neue Dateinamen englisch, nach vorhandener Nummerierung, etwa
`NN_part-name/`. Parametrisches Skript in Python mit `trimesh`/`manifold3d`;
passende vorhandene Umgebung prüfen, keine Installation voraussetzen.

Aufbau nach dem Vorbild bestehender Skripte: benannte Maßkonstanten oben mit
Einheit und Quelle im Kommentar, `PART`-Schalter für Varianten und Prüfstücke,
Export am Ende. Spiel und Wandstärke sind **eigene Parameter**.

Die Konstruktionsrichtwerte für FDM stehen in
`references/fdm-konstruktion.md` — Überhänge, Wandstärken, Passungen,
Gewinde, Verschraubungen.

## 3. Prüfen

Vor dem Export, und das Ergebnis wird gezeigt, nicht behauptet:

- `is_watertight` — topologisch geschlossen, kein Nachweis für Flüssigkeitsdichtheit
- Anzahl Komponenten (eine, wenn es eine sein soll)
- Volumen und Bounding Box plausibel, passt auf die Platte
- keine Selbstdurchdringung, Normalen einheitlich
- dünnste Stelle über der Mindestwandstärke; Messverfahren und bei
  Stichproben deren Grenzen nennen. Nicht gemessene Eigenschaften offen lassen.

## 4. Dokumentieren

`NN_part-name/part-specification.md` (deutscher Inhalt):

- Zweck und Einbausituation
- Maßtabelle **mit Quelle je Maß** und den offenen Messungen
- Materialwahl mit Begründung aus dem aktuell bestätigten Bestand
- Druckhinweise: Orientierung, Stützen ja/nein, Perimeter, Schichthöhe,
  Besonderheiten
- Was noch zu prüfen ist, bevor das ganze Teil gedruckt wird

Neue Iterationsordner heißen etwa `iteration-02/`; bestehende Ablagekonventionen
nicht rückwirkend umbenennen. Den tatsächlich vorhandenen Projektindex
ergänzen, ohne eine nicht vorhandene `CLAUDE.md` vorauszusetzen.

## Haltung

Bei tragenden oder sicherheitsrelevanten Teilen Lastfall, Umgebung und
Versagensfolge klären. Geometrieprüfungen ersetzen keinen Belastungsversuch;
eine Schutzwirkung oder zulässige Last ohne passenden Nachweis nicht zusagen.
Ein erfolgreich berechnetes Modell ist noch kein erfolgreich erprobter Druck.
