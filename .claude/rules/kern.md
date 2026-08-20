---
paths:
  - "app/core/**/*.py"
---

# Regeln für den Kern

Der Kern ist der Teil, der ohne Fenster funktioniert. Alles hier gilt
zusätzlich zu `AGENTS.md`.

## Grenze nach oben

- **Kein `PySide6`, kein Qt, kein `print`, kein `input`.**
  `tests/test_core_isolation.py` importiert `app.core` ohne installiertes Qt.
- Kommunikation nach außen ausschließlich über den `OpContext`:
  `ctx.progress`, `ctx.ask`, `ctx.cancelled`, `ctx.quality`, `ctx.seed`.
  Keine globalen Objekte, kein Logger, der etwas anzeigt, kein Dialog.
- **Fragen statt raten** (Regel 21): Mehrdeutigkeit geht über `ctx.ask`.
  Der Kern entscheidet nicht für den Nutzer.

## Zahlen

- Millimeter und `float` (doppelte Genauigkeit). Gerundet wird in der Anzeige,
  nie im Kern.
- Kein `==` auf Fließkomma. Toleranzen kommen aus dem Materialprofil
  (`auto:<material>`), nicht als Zahl in den Code.
- Jede randomisierte Prozedur nimmt `ctx.seed` und trägt `deterministic=False`.
  Ohne beides ist sie falsch, auch wenn sie funktioniert.

## Fehler

Jede Ausnahme erbt von `AppError` und trägt `suggestions: list[Action]` —
anklickbare Handlungen, keine Prosa. Ein Fehler endet nie mit
„fehlgeschlagen", sondern nennt: was nicht ging, warum, was jetzt möglich ist
(§2.7, §33.1).

Die Hierarchie unterscheidet Bedienfehler von Programmfehlern:
`UserError` (korrigierbar), `GeometryError` (mit Vorschlag),
`ExternalToolError` (Hinweis auf die Einstellung), `InternalError`
(Fehlerbericht). Ein Programmfehler darf nie wie ein Bedienfehler aussehen —
und umgekehrt. `tests/test_errors.py` prüft, dass jede Ausnahme einen
Vorschlag trägt.

Ins Protokoll gehen Kennzahlen, nie Geometriedaten. Das Protokoll verlässt den
Rechner nur, wenn der Nutzer es selbst anhängt (§33.2) — alles andere wäre die
verbotene Telemetrie.

**Es gibt genau einen Weg hinaus, und der heißt `support.send()`**
(`app/core/support.py`). Die Grenze zur Telemetrie liegt beim Auslöser: Der
Versand hängt an einem Knopf, vorher steht die vollständige Sendung in einer
Vorschau, und `tests/test_support.py` zählt die Aufrufer — genau einer. Ein
Zeitgeber, ein Fehlerpfad oder ein Startaufruf, der selbst sendet, ist ein
Verstoß, gleich wie freundlich er begründet wird. `app/core/report.py`
schreibt weiter nur einen Ordner und darf kein `urlopen` kennen.

## Auswertung

`OpContext.scene` ist nur lesend. Ops erzeugen Objekte, sie ändern keine.
Zweimal auswerten muss identisch sein; ändert sich die Objektzahl, hält die
Auswertung an, statt still weiterzurechnen.

## Am Dokument wird nie vorbei geschrieben

Alles, was das Dokument ändert, geht durch eine Transaktion — auch das, was
keine Operation ist. Parameter, Passungen, Drucker und Material reisen als
`DocumentChange` mit (§15.5); `History.apply(..., changes=...)` nimmt sie
entgegen, `undo` und `redo` spielen sie zurück und vor. Die Vorher-Seite baut
`change_for()` aus dem Dokument — wer sie selbst zusammensucht, vergisst einen
Fall.

Wer stattdessen `document.parameters[...] = ...` schreibt, baut den Fehler
nach, der hier zweimal steckte: die Änderung ist nicht rücknehmbar, sie gilt
nicht als Änderung, und beim Schließen ist sie weg.

Die Grenze verläuft an der Auswertung: was sie beeinflusst, gehört in die
Transaktion. Druckeinstellungen und Sichtbarkeit tun das nicht — die
Einstellungen reisen zum Slicer, die Sichtbarkeit gehört der Ansicht.

## Die Lizenzgrenze

Was das Dokument ändert oder ein Ergebnis herausgibt, ruft
`activation.require(<handlung>)` — was nur liest, nie (Konzept §2 C). Die
vier Stellen sind `History.apply` (CHANGE), `export/writer.py` (EXPORT),
`export/handover.py` (SLICER) und `agent/session.py` (CHAT); jede holt den
Zustand selbst und wirft selbst (H3). Eine **neue** Stelle, die schreibt oder
herausgibt, ohne durch eine der vier zu gehen, braucht ihren eigenen
`require`-Aufruf — und einen Fall in `tests/test_licence_boundary.py`, in
beide Richtungen: gesperrt lehnt ab, lesend läuft weiter.

Die Oberfläche graut nur vorher aus, sie ist nie die Hürde. Kein Schalter,
keine Umgebungsvariable, keine Freigabedatei — die Suite patcht
`activation._cached` über monkeypatch. Wer eine der vier Grenzdateien
umbenennt oder verschiebt, zieht `integrity.BOUNDARY_FILES` und die
PyInstaller-Spec nach (`tests/test_licence_build.py` hält beide zusammen).

## Pfade

Keine absoluten Pfade in Projektdateien. Nutzerverzeichnisse kommen aus
`app.core.paths` — die Suite biegt sie um, damit ein Testlauf nichts im Profil
des Entwicklers hinterlässt (§38).
