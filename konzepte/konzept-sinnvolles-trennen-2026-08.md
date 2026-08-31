# Konzeptnotiz: Sinnvolles Trennen (31.08.2026)

Anlass: Roberts Auftrag vom 31.08.2026 — „die Option zum sinnvollen Trennen,
recherchieren da auch mal." Diese Notiz ist der Rohling für seine
Entscheidung: Ist-Stand, Stand der Technik, Kriterien mit Optionen und
Aufwand. Sie empfiehlt keine Bauweise; die Wahl trifft Robert.

## Was Solidon heute kann

Drei Wege existieren, alle mit Verbindern:

| Weg | Ort | Ebene |
|---|---|---|
| Op `split_pinned` („Teilen") | `app/core/geom/prepare_ops.py` | achsparallel |
| Op `split_line` („An gezeichneter Linie trennen") | `prepare_ops.py` + `app/ui/split_bar.py` | beliebig schief, aus zwei Klicks |
| Auto Split (Menü) | `app/core/split.py` + `app/core/geom/autosplit.py` | nur achsparallel |

Auto Split ist bewusst ein **Ablauf aus `split_pinned`-Schritten** — jede
Trennebene bleibt eine änderbare Zahl im Stapel (§14, §15.1). Die Suche
tastet 33 Positionen je Achse ab und bewertet mit drei Termen: Konturzahl
(Gewicht 1,0), prismatischer Querschnitt (0,6), Mittenlage (0,25); über der
Schwelle 0,3 fragt sie die konvexe Zerlegung (V-HACD) nach der
Einschnürungsposition. Höchstens 12 Teile, der Stiftüberstand zählt zur
Bettprüfung.

Die Verbinder sind der stärkste Teil: Stifte rund/sechskant/schwalbenschwanz/
Schnapper, Durchmesser aus der Nahtgröße, **Materialtiefe je Stiftposition
per Strahlenpaar gemessen** (hohle Teile bekommen gekürzte Stifte oder einen
Befund), Spiel aus dem Materialprofil, Passungspaare automatisch (§14).
**Das kann keiner der verglichenen Slicer.**

## Stand der Technik, in vier Sätzen

PrusaSlicer 2.6 und Bambu Studio schneiden in beliebigem Winkel mit
Verbinderfamilien (Plug/Dowel/Snap/Dovetail, Bambu zusätzlich Groove) —
aber **keiner sucht die Schnittlage automatisch**; dort ist Solidon voraus.
Das Chopper-Verfahren (SIGGRAPH Asia 2012) sucht global: 129 Richtungen,
Beam Search Breite 4, sieben Bewertungs-Terme (Teilezahl, Bauraum,
Verbinder-Machbarkeit, FEM-Festigkeit, Zerbrechlichkeit, Naht-Unauffälligkeit,
Symmetrie) — stark, aber langsam (287 s für 10 Teile) und
gewichts-empfindlich. Die interaktive Weiterentwicklung (Jadoon et al. 2018)
ergänzt No-Go-Malregionen und gezeichnete Ebenen. Die Praxis-Guides nennen
immer dieselben vier Regeln: Naht auf vorhandene Kanten legen, jedes Teil
einzeln neu orientieren (Anisotropie), Klebefläche vergrößern
(Dovetail/Überlappung), flache Fügeflächen.

Quellen: Prusa KB „Cut tool", Bambu Wiki „Cut tool", Chopper
(gfx.cs.princeton.edu/pubs/Luo_2012_CPM), Jadoon et al. IEEE CG&A 2018,
Sovol-/DigiKey-Guides — vollständige Liste im Recherchebericht
(ROADMAP-Registerpunkt vom 31.08.2026).

## Was „sinnvoll" messbar heißt — und was fehlt

| # | Kriterium | Stand | Option und Aufwand |
|---|---|---|---|
| 1 | Bauraum-Passung je Teil inkl. Verbinderüberstand | vorhanden | — |
| 2 | Teilezahl minimal | teils (greedy) | Beam Search wie Chopper: M–L |
| 3 | **Nahtlage unauffällig** (Kanten, Sichtflächen) | fehlt — der `caveat` der Op delegiert es an den Nutzer | Krümmungsterm in der Bewertung: M; Sichtflächen-Malregion als harte Sperre: M (+ Malwerkzeug); Sichtbarkeitsterm: L |
| 4 | Flache/prismatische Fügefläche | vorhanden | Planarität zusätzlich: S |
| 5 | **Minimale Stützen je Teil** in seiner besten Lage | fehlt in der Bewertung — Schichtanalyse und `orient_for_print` existieren, sind nicht eingekoppelt | für die besten 3–5 Kandidaten nachrechnen: M; für alle: M–L (Budget §31) |
| 6 | Verbinderart nach Material hinter der Naht | vorhanden, stark | automatischer Formvorschlag statt Nutzerwahl: S–M |
| 7 | Festigkeit quer zur Schicht | fehlt | Einschnürungs-Heuristik („Naht nicht am Querschnittsminimum"): S; Fragilitätsterm: S–M; FEM: L + Lizenzfrage (Regel 22) |
| 8 | **Schiefe Ebenen in der automatischen Suche** — §22.3 verspricht „Höhen und Richtungen", heute sind es drei Richtungen | fehlt (manuell via `split_line` geht es längst) | Normalenfächer 13–33 Richtungen als Zweitstufe: M; voller Fächer: L |
| 9 | Symmetrie erhalten | fehlt | S–M (braucht Symmetrieerkennung) |
| 10 | Anordnen, Explosion, Passungen, Kalibrierung | vorhanden (P10) | Schaustück „zusammengebaut → Bett-Lage": S (eigener Registerpunkt) |

## Randbedingungen für jede Bauweise

Abbrechbar (§15.6, `JUDGE_BLOCK`-Muster), deterministisch (§11.3), im
Leistungsbudget (§31 — die Suche läuft heute unter einer Sekunde je Achse),
keine GPL-Abhängigkeit (Regel 15), und Auto Split bleibt ein Ablauf aus
`split_pinned`-Schritten: Jede neue Bewertung ändert nur, **wo** die Ebene
liegt, nie, **was** auf den Stapel kommt.

## Stand

**Entschieden (Robert, 31.08.2026): Vollausbau.** Wörtlich: „Qualität ist
das wichtigste — wie immer das sinnvollste und beste für den Kunden ohne
CAD-Kenntnisse. Aufwand wie immer egal." Der Maßstab ist damit: Auto Split
tut von selbst das Richtige — der Kunde wählt keine Kriterien, er bekommt
eine Zerlegung, die er auch von einem erfahrenen Kollegen bekäme; höchstens
eine einfache Geste („diese Fläche soll schön bleiben") kommt dazu. Die
Serie steht als T1–T9 im ROADMAP-Register; FEM bleibt zurückgestellt, bis
die Heuristiken gemessen nicht reichen (neue Abhängigkeit = Regel 22, eigene
Entscheidung). Die Randbedingungen oben gelten unverändert — „Aufwand egal"
kauft Rechenzeit mit Fortschritt und Abbruch, keine eingefrorene Oberfläche.
