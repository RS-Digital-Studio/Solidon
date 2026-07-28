# Formwerk

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
Modelle. Kern ist ein non-destruktiver Operationsstack über einer Szene mit
mehreren Objekten, benannten Projektparametern und Passungsbeziehungen. Ein
LLM-Agent steuert denselben Operations-API fern, den auch die Menüs benutzen.

**Geometrie rechnet Code, nie das Modell.** Ohne Netz, ohne Konto und ohne KI
bleibt alles außer dem Chat benutzbar.

Projektdateien tragen die Endung `.p3d`.

## Was Formwerk nicht ist

Damit niemand das Falsche erwartet:

* **Kein CAD-Ersatz.** Es gibt keine Skizzen, keine Zwangsbedingungen, keine
  Historie aus parametrischen Features im Sinne von Fusion oder SolidWorks.
  Formwerk arbeitet auf Netzen; Verrundungen und Fasen auf beliebigen Kanten
  bleiben deshalb hart, bis der B-Rep-Kern kommt (§30).
* **Keine Passungen aus erzeugten Meshes.** Was ein Bildmodell erzeugt, ist eine
  Oberfläche, keine Konstruktion. Bohrungen und Passungen entstehen danach als
  eigene Operationen — nicht dadurch, dass man das erzeugte Netz vermisst.
* **Kein Slicer.** Die eingebaute Schichtanalyse sucht und bewertet; die
  Druckdatei kommt weiter aus dem Slicer. Beide Zahlenwelten bleiben getrennt
  ausgewiesen (§22.5).
* **Keine Cloud.** Kein Konto, keine Telemetrie, keine Projektablage im Netz.
  Ein Sprachmodell wird nur gefragt, wenn ein Schlüssel hinterlegt ist.

**Support** läuft über einen Kanal: die Issues dieses Repositories. Ein
Fehlerbericht entsteht im Programm unter *Hilfe → Fehlerbericht erstellen* und
bleibt so lange auf dem Rechner, bis jemand ihn selbst anhängt.

---

## Die drei Wege

Beim Start liegen drei Beispielprojekte bereit — sie sind gleichzeitig
Dokumentation und Abnahmeprüfung (§37.2):

| Projekt | Weg |
|---|---|
| `weg1-halterung-anpassen.p3d` | fremdes Modell einlesen, reparieren, bohren |
| `weg2-halter-konstruieren.p3d` | aus Parametern und Bausteinen neu konstruieren |
| `weg3-generiert-aufbereiten.p3d` | erzeugtes Mesh durch die Reparaturkette |

---

## Unterlagen

| Datei | Inhalt |
|---|---|
| [3d-agent-bauplan.md](3d-agent-bauplan.md) | die Spezifikation — sagt **was** |
| [AGENTS.md](AGENTS.md) | Repository-Regeln — sagen **wie** |
| [ROADMAP.md](ROADMAP.md) | Arbeitsliste je Phase — sagt **was als Nächstes** |

## Entwickeln

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,geom,ui]"
```

| Befehl | Zweck |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | vollständige Suite |
| `.venv/Scripts/python.exe -m ruff check .` | Stil und Fehlerbilder |
| `.venv/Scripts/python.exe -m mypy` | Typprüfung (strict) |
| `.venv/Scripts/python.exe -m app.ui.app` | Anwendung starten |
| `.venv/Scripts/python.exe -m app.cli.main ops` | Operationen auflisten |
| `.venv/Scripts/python.exe -m app.i18n.extract` | Übersetzungskataloge abgleichen |
| `.venv/Scripts/python.exe tests/data/make_corpus.py` | Referenzkorpus erzeugen |
| `.venv/Scripts/python.exe tools/make_examples.py` | Beispielprojekte erzeugen |
| `.venv/Scripts/python.exe tools/run_agent_suite.py` | Agenten-Suite gegen ein echtes Modell |

Zum Starten per Doppelklick liegt unter `tools/start-formwerk.cmd` eine
Verknüpfung.

## Paketieren

```
.venv/Scripts/python.exe -m pip install pyinstaller
.venv/Scripts/pyinstaller.exe packaging/formwerk.spec --noconfirm
```

Ergebnis ist ein Ordner unter `dist/Formwerk`. Die Bauläufe für Windows und
Linux stehen in `.github/workflows/build.yml`; sie laufen erst, wenn die Suite
auf allen drei Plattformen grün ist. Die Windows-Signierung braucht ein
Zertifikat als Repository-Secret — ohne das entsteht ein unsigniertes Paket
statt eines Fehlers.

OpenSCAD, Slicer, Ollama und ComfyUI werden **nicht** mitgeliefert, sondern
konfiguriert (§36, §38). Beim ersten Start zeigt die Anwendung, welche davon
gefunden wurden; Pflicht ist keines.

Ohne funktionierendes OpenGL startet die Anwendung ohne 3D-Ansicht; erzwingen
lässt sich das mit `FORMWERK_NO_VIEWPORT=1`.

## Sprachmodell für den Chat

Der Chat braucht ein Modell; alles andere in Formwerk kommt ohne aus. Der
Schlüssel wird über **Bearbeiten → Zugang zum Sprachmodell** im Schlüsselbund
des Systems abgelegt und reist nie mit der Projektdatei mit. Auf einem
Bauserver geht auch die Umgebungsvariable `FORMWERK_LLM_KEY`.

| Weg | Voraussetzung | Anmerkung |
|---|---|---|
| Eigener Schlüssel | Zugang beim Anbieter | Vorgabe, beste Werkzeugtreue |
| Lokal über Ollama | `ollama serve` auf Port 11434 | kein Schlüssel nötig |

Für den lokalen Weg braucht es ein Modell, das Werkzeugaufrufe zuverlässig
beherrscht — kleine Modelle scheitern daran reproduzierbar (§27). Bewährt haben
sich `qwen2.5-coder:14b` und größer; alles unter 7B ist für die Op-Aufrufe
erfahrungsgemäß zu wenig.

Wie gut ein Modell mit den Referenzanfragen zurechtkommt, misst

```
.venv/Scripts/python.exe tools/run_agent_suite.py --backend ollama
```

## Modelle erzeugen (Weg 3)

**Datei → Modell erzeugen** spricht lokal mit einem laufenden ComfyUI auf Port
8188. Läuft keines, bleibt der Eintrag ausgegraut und sagt warum; alles andere
in Formwerk funktioniert weiter.

Was zurückkommt, wird als Quelle ins Projekt eingebettet und danach im Stack
geladen und repariert — zwei Schritte, beide sichtbar, beide zurücknehmbar.
Prompt und Startwert stehen in der Quelle, damit die Datei sagt, woher die
Geometrie stammt.

Welche Knoten benutzt werden, steht in `app/core/backends/data/text_to_mesh.json`
und `image_to_mesh.json`. Die mitgelieferten Abläufe gehen von Hunyuan3D aus;
mit einem anderen Generator wird die Datei ersetzt, nicht der Quelltext.

## Zu groß für das Bett (Auto Split)

**Bearbeiten → Automatisch teilen** schneidet ein Objekt, bis jedes Stück auf
die Platte passt. Die Trennebene wird gesucht, nicht geraten: über dieselbe
Schichtanalyse wie die Orientierungssuche, und bewertet wird eine Kontur statt
mehrerer dünner Brücken, ein prismatischer Verlauf und die Ausgewogenheit.

In jede Schnittfläche kommen zwei Passstifte — Durchmesser aus der Fläche, Spiel
aus dem kalibrierten Materialprofil — und zu jedem Stift entsteht ein
Passungspaar, das bei jeder Auswertung geprüft wird. Jeder Schnitt ist eine
eigene Operation: die Position bleibt eine Zahl, die man nachträglich ändern
kann, und ein Undo nimmt einen Schnitt zurück.

Der Schieberegler **Explosionsansicht** unter der Ansicht zieht die Teile zum
Ansehen auseinander. Er verschiebt nichts — Stack und Export bleiben, wie sie
sind.

## Farbe und Materialslots

Jedes Dreieck trägt einen Slot, jedes Objekt eine Liste von Materialslots (§20).
Zugewiesen wird über **Farbe → Slot zuweisen**, oder aus der Textur eines
erzeugten Modells über **Farbe → Farben in Slots umrechnen** — k-Means auf die
Anzahl eingelegter Filamente, mit gespeichertem Startwert, damit dieselbe Datei
dasselbe Ergebnis liefert. Das ist nie so fein wie die Bildschirmdarstellung.

Die Zuweisung überlebt Boolesche Operationen einschließlich der Voxelstufe. Beim
Export nach `3MF` wird daraus je Slot eine Materialgruppe; `STL` kennt keine
Farbe und verliert sie folgerichtig.

## Lizenz

Formwerk ist proprietär — Copyright (c) 2026 RS Digital, alle Rechte
vorbehalten. Der vollständige Text steht in [LICENSE](LICENSE).

Zwei Teile stehen bewusst unter MIT, weil ihr Inhalt in den Ergebnissen der
Nutzer landet:

* die Bausteinbibliothek `app/core/knowledge/parts/`
* der Referenzkorpus `tests/data/`

Fremdbibliotheken behalten ihre eigenen Lizenzen; die Übersicht führt
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Geprüft wird das automatisch
gegen die Freigabeliste in `app/core/knowledge/data/licences.toml`.
