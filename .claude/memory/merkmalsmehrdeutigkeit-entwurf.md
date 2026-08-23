---
name: merkmalsmehrdeutigkeit-entwurf
description: "ERLEDIGT am 23.08.2026 (eb77658) — die Antwort auf eine mehrdeutige Merkmalszuordnung steht im Stapel (§15.7 zweiter Teil)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0545ae7f-0dd2-436b-aa74-3a2e2040e3ae
  modified: 2026-08-22T16:09:16.172Z
---

**ERLEDIGT.** Gebaut am 23.08.2026 als `eb77658` („Neunundneunzig Fenster für
sieben Entscheidungen, und keine davon blieb"). Nachgemessen am 24.08.2026:

    app/core/scene/history.py:378   def record_matches(...)
    app/core/scene/history.py:412   ops[index] = replace(entry, matches=merged)
    app/ui/session.py:1388          matched = self.history.record_matches(result.matches)
    tests/test_evaluation.py        deckt es ab

Der Anschluss ist geprüft, nicht nur die Existenz — genau die Frage, an der
heute drei andere Sachen hingen ([[eine-kette-endet-am-letzten-glied]]).

**Der Rest dieses Dokuments ist der Entwurf von damals** und bleibt als Beleg
stehen, wie entschieden wurde. Er beschreibt keinen offenen Punkt mehr.

**Und die Lehre über den Auftrag hinaus:** Diese Datei führte den Auftrag zwei
Tage länger als offen, als er es war. `CLAUDE.md` warnt genau davor — „Wer
‚offen' in einem Konzept liest, prüft es am Code, bevor er es glaubt." Das gilt
für die eigenen Erinnerungen genauso. **Eine Notiz altert, der Code nicht.**

## Das Problem

`_with_features` in `app/core/scene/evaluate.py` fragt bei einer mehrdeutigen
Zuordnung „Welches Merkmal entspricht `pin_1`?" (§21.3). Die Antwort steht in
`MatchResult.mapping`, gilt für diesen Lauf und ist danach vergessen. Gemessen
(`ROADMAP.md`, „Neun heruntergeladene Modelle"): ALL+PLATES stellt **99 Fenster
für 7 verschiedene Entscheidungen**. Abnahme ist: 99 wird 7, beim zweiten
Auswerten 0.

Der erste Teil von §15.7 ist gebaut (`311134a`): `OpResult.answered` →
`EvaluationResult.answers` → `History.record_answers` schreibt in die
**Parameter**. Für die Einheitenfrage reicht das, weil `unit` ein Parameter ist.

## Der Entwurf

**Gespeichert wird ein geometrischer Fingerabdruck, nicht ein Bezeichner.**
`old_id → new_id` wäre fragil: Die Erkennung nummeriert beim nächsten Lauf
womöglich anders, und dann zeigt die gespeicherte Antwort auf ein fremdes
Merkmal — aus „fragt zu oft" würde „nimmt stillschweigend das falsche".
`feature_vector` in `app/core/perceive/matching.py` rechnet den Abdruck schon
(Lage relativ zum Körper, Achse, Durchmesser), `cost()` vergleicht ihn.

**Ort: ein Beiwagenfeld an `Operation`**, etwa `matches: dict[str, dict]`, mit
lesbarem JSON (`kind`, `centre`, `axis`, `diameter`). Nicht in `params` —
`validate` wiese einen unbekannten Schlüssel ab, und es ist keine Eingabe der
Operation. **`seed` ist der Präzedenzfall:** ein Wert auf Operationsebene, der
eine nicht selbst reproduzierbare Prozedur reproduzierbar macht. Eine
festgehaltene Antwort tut dasselbe für eine Rückfrage.

**Zweiter Kanal** neben `answers`: `EvaluationResult.matches` und
`History.record_matches`. `_with_features` gibt heute nur ein `SceneObject`
zurück und muss etwas nach oben melden können.

**Formatänderung 8 → 9**, Checkliste in `AGENTS.md`. Billig: Das Feld ist leer,
wenn es fehlt, `example_v8.p3d` liegt als Beispieldatei da, `MIGRATIONS` ist
eine Liste.

## Drei Punkte von solidon-55, die den Entwurf tragen

1. **`matches` gehört nicht in den Op-Hash.** `_with_features` läuft in beiden
   Zweigen, auch nach einem Cache-Treffer, und die Zuordnung passiert *nach*
   dem Cache. Die Antwort ändert also kein gecachtes Ergebnis, und nach dem
   Antworten rechnet nichts neu — anders als bei der Einheit. Das gehört in den
   Docstring, sonst trägt es später jemand „zur Sicherheit" in den Hash ein.
2. **Der Rückfall braucht einen Abstand, nicht „am nächsten".** Die Kandidaten
   waren mehrdeutig, *weil* sie sich gleichen; „der nächstliegende gewinnt"
   entscheidet dann über einen Abstand, der kleiner ist als der zwischen den
   Kandidaten. Zu nehmen ist die **Rivalenlogik aus `match()`** mit dem
   gespeicherten Abdruck als Referenz: Gewinnt der Beste nicht mit Abstand,
   wird wieder gefragt. `MATCH_THRESHOLD` und die Rivalenspanne stehen da.
3. **Der Bezugsrahmen kann den Abdruck verderben.** `feature_vector` normiert
   auf Körpermitte und Diagonale, und beide ändern sich, sobald die Operation
   Material dazutut. `_with_features` hat dafür schon die zwei Fälle
   „verschoben" gegen „umgebaut". Entweder absolut speichern (Rahmen verrottet
   nicht, Drehung reist nicht mit) oder normiert **und mit derselben Wahl von
   `old_centre` auflösen**, die `_with_features` trifft. Nicht entschieden.

## Wegmarken im Code (von solidon-55, `311134a`)

- `OpResult.answered` in `types.py` — das Muster für das zweite Feld, mit
  Begründung im Docstring.
- `EvaluationResult.answers` neben `solvers` in `evaluate.py` — dort gehört
  `matches` daneben.
- Die Sammelstelle für Antworten ist **bei `result = CachedResult(...)`** und
  nicht weiter unten: `produced` ist das `OpResult`, danach ist es ein
  `CachedResult` und kennt `answered` nicht (22 `AttributeError`, wenn man es
  unten liest). `_with_features` sitzt noch tiefer, braucht also einen eigenen
  Weg nach oben — ein zusätzlicher Rückgabewert oder eine hineingegebene Liste.
- `History.record_answers` in `history.py` — die Form für `record_matches`,
  samt Begründung, warum es keine Transaktion ist.
- Die Anbindung in `session.py`, `_on_finished`, hinter `record_solvers`. Dort
  steht auch, warum **kein** `evaluate_async()` folgt. Ohne `_dirty = True` ist
  es die halbe Arbeit: Die Antwort stünde im Stapel, der Titel zeigte kein `*`,
  `closeEvent` sichert nur ein geändertes Dokument — beim Schließen weg.

## Die Prüfung

Nicht „die Antwort steht in den Parametern", sondern: **keine Operation gibt
mehr `to_disk=False` zurück.** `_WatchedAsk` wickelt beide Fragesteller ein —
Operation und Zuordnung; wird `used` für die Zuordnung nie mehr wahr, ist keine
Antwort mehr unaufgeschrieben. Dazu die Zahl: ALL+PLATES zweimal auswerten,
sieben Fragen und dann null.

## Gebiete

Freigegeben: `scene/evaluate.py`, `types.py`, `scene/history.py`,
`perceive/matching.py`, `tests/test_matching.py`, `tests/test_evaluation.py`,
`scene/serialise.py`, die Migrationen, `tests/data/projects/`,
`tests/test_migrations.py`. Bei `solidon-55`: `perceive/features.py`,
`app/core/geom/**`, `tests/test_features.py` und die Unterlagen — **sie schreibt
§15.7, §21.3 und das Register nach**, also die Entscheidung melden.
`ROADMAP.md`-Kästchen nicht ohne Absprache abhaken, `tests/test_roadmap.py`
zählt gegen.
