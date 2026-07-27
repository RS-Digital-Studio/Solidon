# Formwerk

Desktop-Anwendung zum **Konstruieren, Generieren und Bearbeiten** druckbarer
Modelle. Kern ist ein non-destruktiver Operationsstack über einer Szene mit
mehreren Objekten, benannten Projektparametern und Passungsbeziehungen. Ein
LLM-Agent steuert denselben Operations-API fern, den auch die Menüs benutzen.

**Geometrie rechnet Code, nie das Modell.** Ohne Netz, ohne Konto und ohne KI
bleibt alles außer dem Chat benutzbar.

Projektdateien tragen die Endung `.p3d`.

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

Ohne funktionierendes OpenGL startet die Anwendung ohne 3D-Ansicht; erzwingen
lässt sich das mit `FORMWERK_NO_VIEWPORT=1`.

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
