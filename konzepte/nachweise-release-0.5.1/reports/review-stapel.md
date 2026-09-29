# Review: Paket „Stapelumbau der Einpassungen“ (RM-132, RM-193, RM-209)

Stand: 28.09.2026, nur lesend im Hauptbaum. Geprüft: Zweig
`origin/rm-209-stapel`, Endstand `8e1afee29`, Basis `aa82afdff`
(`git diff aa82afdff 8e1afee29`, 7 Dateien, +1678/−150). Gelesen am Commit
(`git show`), gerechnet in einem eigenen Arbeitsbaum
`F:\3D Druck.review-051\wt-revstapel` (losgelöst auf `8e1afee29`), jeder Lauf
gebunden über `skripte/lauf-wt.sh` (`/affinity FFFFF0FF`), Protokolle in
`laeufe\rev-stapel-*.txt`. Zeilennummern gelten für `8e1afee29`.

Maßstab: `AGENTS.md`, `CLAUDE.md`, Karte `app/core/perceive/CLAUDE.md`,
Regeln `schichtanalyse.md`, `kern.md`, `tests.md`, `zwillinge.md`, Skill
`regelcheck`; SciPy-Quelltext der installierten und gepinnten Fassung 1.18.1
(`constraints.txt:86`; `.venv/Lib/site-packages/scipy/optimize/_lsq/`
`least_squares.py`, `trf.py`, `common.py`, dazu
`optimize/_differentiable_functions.py`).

Drei Stufen: **blockiert den Merge**, **vor dem Tag** (nach dem Merge, vor dem
Tag 0.5.1), **nach 0.5.1** (Register).

## Urteil

**Stand Nachtrag `3a83c04af`: mergebar ja** — B1–B4 und B6 sind behoben,
offen bleiben B5, B7, B8 (Register) und die neuen kleinen Punkte B9 (vor dem
Tag, Unterlagen), B10, B11 (nach 0.5.1); Einzelheiten im Abschnitt
„Nachtrag 3a83c04af“ am Ende. Das Folgende ist das Urteil zu `8e1afee29`.

**Mergebar: ja.** Kein Befund blockiert den Merge. Der heikle Teil hält:
`refine.solve` ist Zeile für Zeile SciPys `trf_no_bounds` und rechnete in
allen 4 992 Läufen außerhalb des Korpus, in denen beide rechnen, bitgleich
(abweichend nur SciPys Argumentprüfung, B5); der Stapel
gab an 4 700 synthetischen Aufgaben (Kegel fast wie Zylinder, dünne Ringe,
Splitter, Float32, Auffüllgrenzen) und unter Plattformrauschen kein falsches
Nein, seine Abstände verhindern dort nachweislich eines; die Korpusgleichheit
des Pakets (553 Körper) bestätigt der eigene Nachvergleich. **Vor dem Tag**
müssen B1–B4 und B6 behoben sein — B1 macht die Modelle von RM-132 und
RM-193, für die das Paket gebaut ist, durch den Stapel acht bis zehn Prozent
langsamer und ist klein zu beheben; am besten noch vor dem Merge. B5, B7, B8
gehen ins Register.

## Übersicht

| Nr. | Stufe | Kurz | Ort |
|---|---|---|---|
| — | blockiert den Merge | keiner | — |
| B1 | vor dem Tag (besser vor dem Merge) | jede Stützpunktlesung und `_rigid_key` doppelt; Freiform 200 000 △ +8–10 % CPU, Drache +9 % laut Paketmessung | `features.py:7858`, `7861`, `6853`, `7935`, `2455` |
| B2 | vor dem Tag | Suite hält weder `MIN_BATCH` im Betrieb noch Schatten/Abstände noch zwei Zweige von `solve`; 7 von 10 Gegenproben grün, zwei nur am „wird gefragt“-Fall rot | `tests/test_refine.py:121, 201–234, 263–278, 283, 352` |
| B3 | vor dem Tag | `refine` beruft sich auf „exakt nachgeprüfte Vorauswahl“ (`kern.md`), das Nein wird nicht nachgeprüft; Regel und Plattformtest decken die Klasse nicht | `refine.py:43–48`, `546–547` |
| B4 | vor dem Tag | ein Stapelblock bis rund 400 MiB (Wegfeld 149 MiB), Blockgrenze begrenzt es nicht; alle Lesungen einer Runde festgehalten | `refine.py:103–105`, `557`; `features.py:7816`, `7976`, `8335` |
| B5 | nach 0.5.1 | `solve` hängt bei `evaluations < 1`, prüft Genauigkeit nicht | `refine.py:220–272` |
| B6 | vor dem Tag (Rechtefrage, Robert) | Lizenzvermerk des übertragenen SciPy-Codes ohne Bedingungen und Ausschluss | `refine.py:55–56`, `199` |
| B7 | nach 0.5.1 | fünf Docstrings nennen `_fit_*_measured` als Formelquelle, die Formeln stehen in `_*_from_plan` | `refine.py:57–58, 129, 147, 443, 484` |
| B8 | nach 0.5.1 | Balken steht während des Stapels | `features.py:7855–7876`, `refine.py:369–370` |

## Befunde

### B1 — Jede Stützpunktlesung und jede Deckungsgleichheitskennzahl wird zweimal gerechnet (vor dem Tag, besser vor dem Merge)

**Ort:** `app/core/perceive/features.py:7858` (`_screened_fits` liest
`_surface_support` für jeden Fleck der Runde vorab), `features.py:7861`
(`_rigid_key` vorab), gegen `features.py:6853`/`6869`/`7202`
(`"support"` steht in `WHOLE_BODY_ANSWERS`, Grenze `SUPPORT_CACHE_LIMIT = 8`)
und `features.py:7935` (`_fit_cone_read` liest die Lesung in `classify`
erneut), `features.py:2455` (`classify` rechnet `_rigid_key` erneut).

**Was falsch ist:** Der Stapel liest alle Lesungen einer Runde, bevor
`classify` beginnt. Der Merker hält davon nur die letzten acht — mit Absicht,
weil eine Lesung so groß wie ihr Fleck ist (Kommentar an
`SUPPORT_CACHE_LIMIT`). `classify` findet sie deshalb nicht mehr und liest
jede ein zweites Mal. Dasselbe gilt für `_rigid_key`, das nicht gemerkt wird.

**Beleg** (Sonde E, `sonden\revstapel\test_zz_revstapel_e_overhead.py`,
gefahren im eigenen Baum, `laeufe\rev-stapel-e1.txt`/`-e2.txt`, Rohdaten
`sonden\revstapel\probe_e.jsonl`): je Netz vier `detect` im Wechsel,
„neu“ wie geliefert, „alt“ mit `_screened_fits → {}` (jeder Plan entsteht
wie vor dem Paket erst in der Einpassung), gleiche Merkmale in jedem Lauf.

| Netz | `_read_surface_support` neu / alt | `_rigid_key` neu / alt | eingesparte Löserläufe | CPU neu | CPU alt |
|---|---|---|---|---|---|
| Freiform der Leistungstests (200 000 △, `detect_freeform_200k`) | 3 896 / 1 949 | 3 894 / 1 947 | 27 von 1 264 | 12,47 / 12,02 s | 10,94 / 11,28 s |
| Beulenkugel aus `test_refine.py` (10 000 △) | 932 / 466 | 932 / 466 | 41 von 792 | 7,05 / 7,27 s | 7,31 / 7,20 s |

Gegen einen Reihenfolgeeffekt ein zweiter Wechsel, alt zuerst, drei Paare
(`test_overhead_freeform_reversed`, `laeufe\rev-stapel-fgh.txt`): neu
11,05 / 11,69 / 11,67 s, alt 10,44 / 10,63 / 10,77 s. An der Freiform
kostet der Stapel damit acht bis zehn Prozent (gebunden, im Wechsel, gleiche
Last); die Zählungen oben sind lastunabhängig. Das erklärt, was der
Paketbericht „im Rauschen“ nennt: Drache 12,8/11,7/13,1 → 14,7/12,9/13,3 s
(Mittel +9 %), Schiff
20,2 → 20,7 s — genau die Modelle von RM-193 und RM-132, für die das Paket
gebaut ist, werden durch den Stapel langsamer; der Gewinn des Nachbaus deckt
es an der Freiform gerade zu.

**Warum es zählt:** Leistungspaket mit systematischer Mehrarbeit; §31 und die
Registerpunkte RM-132/RM-193 messen genau diese Modelle.

**Fix:** In der Runde antwortet `_surface_support` aus dem Wissen des Stapels
(die Pläne halten die Lesungen ohnehin; Schlüssel wie `remembered`: Körper
und `_patch_digest`), und `_rigid_key` wird je Fleck einmal gerechnet (im
Wissen mitgeben, `classify` liest es von dort). Danach Drache, Freiform,
Schiff im Wechsel neu messen und die Korpusgleichheit wie in `p42`
wiederholen.

### B2 — Die Suite hält weder den Produktionsweg des Stapels noch seine Schutzabstände, noch die Randzweige des Nachbaus (vor dem Tag)

**Ort:** `tests/test_refine.py:121`, `:283`, `:352` (jeder Test setzt
`MIN_BATCH = 1`), `:201–234` (SciPy-Gleichheit nur an den Läufen der
Beulenkugel), `:263–278` (Abstände nur in Richtung „unerfüllbar“).

**Beleg — Gegenproben** (im eigenen Baum, `zz_mutationen.sh`, je Mutation
`tests/test_refine.py` gebunden, danach `refine.py` aus dem Commit
zurückgeschrieben; Zusammenfassung `laeufe\rev-stapel-mut-summary.txt`,
Einzelläufe `laeufe\rev-stapel-mut-M*.txt`):

| Mutation in `refine.py` | Ergebnis `test_refine.py` |
|---|---|
| M1 `SHADOW_NOISE = 0.0` (Schatten läuft ungestört mit) | **grün**, 15 passed |
| M2 `MIN_BATCH = 10**9` (Stapel im Betrieb nie aktiv) | **grün**, 15 passed |
| M3 Zweig „nicht endlicher Probepunkt“ in `solve` gestrichen (`:237`) | **grün**, 15 passed |
| M4 Neustart von `alpha` bei Rangmangel in `_trust_region_step` gestrichen (`:300`) | **grün**, 15 passed |
| M5 Vorzeichen der Spitzenzeilen in `_cone_residual` (`:455`) | rot (Formelfall) |
| M6 `STOP_MARGIN_DECADES = -1e9` (kein Abbruchabstand) | **grün**, 15 passed |
| M7 `DECISION_MARGIN = -1.0` (kein Zweigabstand) | **grün**, 15 passed |
| M8 `rtol` der Newton-Suche im Stapel 0,01 → 0,02 (`:724`, anderer Algorithmus als SciPy) | **grün**, 15 passed |
| M9 Schattenurteil gestrichen | rot, aber nur `test_every_margin_can_refuse_on_its_own[SHADOW_AGREEMENT]` („wird gefragt“) |
| M10 M6 + M7 + M9 zusammen: Stapel ohne jeden Schutz | rot nur am selben „wird gefragt“-Fall; `test_the_batch_never_turns_away_a_run_that_answers` bleibt **grün** |

**Was falsch ist:** (a) Der Betriebsweg ist nirgends zugesichert: Mit
`MIN_BATCH = 10**9` spart die Anwendung keinen einzigen Lauf mehr, und alles
bleibt grün („Anschluss“, `AGENTS.md`, Testarten). Die Beulenkugel spart mit
dem echten `MIN_BATCH = 64` schon 41 Läufe (Sonde E), der Test könnte also
ungepatcht laufen. (b) Kein Schutzabstand ist an einem Fall belegt, an dem er
etwas verhindert — ein Stapel ohne jeden Schutz ist an der Beulenkugel
fehlerfrei; die Zahlen, die die Abstände tragen, stehen nur in den
Paketsonden (`p55`, `p59`, `p63`), nicht in der Suite. (c) Der Stapel darf
einen anderen Algorithmus rechnen als SciPy (M8), und `solve` darf in zwei
Zweigen von SciPy abweichen (M3, M4), ohne dass ein Test es merkt — genau
der Fall „SciPy wird gehoben“, den der Docstring von
`test_the_solver_computes_what_scipy_computes` abdecken will.

**Fix:** (1) `test_the_screen_keeps_every_shape_and_saves_runs[bumpy]` einmal
ohne `MIN_BATCH`-Patch mit „spart Läufe“; (2) eine kleine Zufallsgegenprobe
`solve` ↔ `least_squares` in `test_refine.py` (linear, rangdefizient,
unterbestimmt, nicht endliche Probepunkte, Budget 1–5, Start null — wie
Sonde A/A2 dieses Reviews, 318 Fälle in wenigen Sekunden, alle bitgleich;
Vorlage `sonden\revstapel\test_zz_revstapel_a_solve.py` und `…_a2_edges.py`);
(3) ein Test, der die Planzeilen von `refine._run` Auswertung für Auswertung
gegen `solve` hält (Weg bis 1e-9 relativ, wie `p55`) — das fängt M8;
(4) für den Schatten eine Richtung „wird gestört“ (mit `SHADOW_NOISE = 0`
muss `apart` überall null sein, mit dem Wert nicht) und für die Abstände ein
Fall, an dem sie etwas verhindern. Den Fall gibt es: Sonde H
(`test_zz_revstapel_h_guards.py`, `laeufe\rev-stapel-gh2.txt`) fand unter
4 700 synthetischen Aufgaben genau eine, bei der der Stapel **ohne**
Abstände „vergeblich“ sagt, der echte Lauf aber nach 97 Auswertungen mit
Status 3 (`xtol`) antwortet — Ring an einem Zylinderstück, 65 Punkte,
Aufgabe Nr. 4676; mit Abständen sagt der Stapel dort nichts. Punkte,
Achsbasis und Startwert stehen vollständig in
`sonden\revstapel\probe_h.json` und taugen unverändert als Testfall.

### B3 — `refine` beruft sich auf eine Ausnahme aus `kern.md`, die nicht passt (vor dem Tag)

**Ort:** `refine.py:43–48` („Deshalb darf er schnell rechnen (``kern.md``:
exakt nachgeprüfte Vorauswahl — hier nachgeprüft durch die Abstände)“),
`refine.py:546–547`; Regel `kern.md`, „Dieselbe Datei, dasselbe Teil — auf
jeder Maschine“.

**Was falsch ist:** `kern.md` erlaubt schnelles Rechnen (einsum, BLAS,
LAPACK, `np.cos`) für Anzeige, Berichtsmessung und **exakt nachgeprüfte**
Vorauswahlen. Das Nein des Stapels wird nicht nachgeprüft — es nimmt den
echten Lauf weg. Seine Sicherheit auf einer anderen Plattform hängt allein an
den Abständen (das Urteil darf auf ARM anders ausfallen; kippt es zu „nicht
sicher“, kostet das nur Zeit, kippt es zu „sicher“, muss der Abstand es
tragen). Die Regel deckt diese Klasse nicht, `test_platform_identity.py`
fährt den Stapel nicht (`_WAYS`), und der Satz im Docstring lädt dazu ein,
„durch Abstände nachgeprüft“ künftig auch anderswo gelten zu lassen.

**Fix:** Die Klasse in der Regel benennen (ein Satz in
`schichtanalyse.md` unter „Ein Löserlauf entfällt nur mit dem Nein des
Stapels“ mit Verweis aus `kern.md`: eine Vorhersage, die nur einen Lauf
auslässt, dessen Ergebnis leer wäre, darf schnell rechnen, wenn ihr Nein
Abstände zu jedem Zweig und Abbruch hält und ein Schattenlauf es bestätigt)
und den Docstring berichtigen. Die Substanz trägt: Unter `platform_noise()`
(ein ULP auf BLAS, einsum, LAPACK und Winkelfunktionen) kippte an fünf
Beulenkugeln mit 1 484 Läufen kein einziges Urteil, und keines war falsch
(Sonde G, `test_zz_revstapel_g_platform.py`, `laeufe\rev-stapel-fgh.txt`
und `-gh2.txt`). Diese Probe gehört als Test neben die Regel.

### B4 — Speicher an großen Netzen: ein Stapelblock bis rund 400 MiB, das Wegfeld allein 149 MiB (vor dem Tag)

**Ort:** `refine.py:557` (`track = np.full((count, evaluations + 1, size),
np.nan)`), `refine.py:103–105` (`BATCH_ELEMENTS`: „Wie viele
Gleitkommazahlen ein Stapel je Feld höchstens hält“),
`features.py:7976–7995`, `8335–8346` (`_ConePlan.support`,
`_TorusPlan.support`), `features.py:7816` (`_SCREENED` hält alle Pläne der
Runde).

**Was falsch ist:** (a) Das Wegfeld hält je Zeile alle 101 Parametersätze,
nur um am Ende den größten Abstand Plan↔Schatten zu lesen. Bei Gruppen mit
16 Zeilen ist ein Block `262 144 // 19 = 13 797` Probleme groß; das Wegfeld
eines Ringblocks wiegt dann `2 × 13 797 × 101 × 7 × 8 B = 148,8 MiB` — rund
das 74-Fache dessen, was der Kommentar an `BATCH_ELEMENTS` je Feld zusagt
(2 MiB). **Gemessen** (Sonde F, `tracemalloc`, NumPy meldet seine Felder
dorthin; `laeufe\rev-stapel-fgh.txt`): 1 000 Ringaufgaben mit 16 Zeilen
Spitze 28,7 MiB (Wegfeld 10,8), 4 000 Aufgaben 114,8 MiB (Wegfeld 43,2) —
linear, also rund 400 MiB für einen vollen Block. Die Blockgrenze begrenzt
damit nicht, was sie verspricht; ein Speicherfehler kostet laut `kern.md` die
ganze Erkennung des Körpers.
(b) Das Wissen des Stapels hält jede Lesung und jeden Plan der Runde fest;
`SUPPORT_CACHE_LIMIT = 8` wurde gerade eingeführt, weil Lesungen so groß wie
ihr Fleck sind. Gemessen festgehalten (Sonde E): 1,0 MiB an der Beulenkugel
(10 000 △), 0,39 MiB an der Freiform (200 000 △); am Meshy-Murmelbrett
(1,95 Mio. △) hat das Paket keinen Speicher gemessen.

**Fix:** laufendes Maximum für `apart` und `width` statt des vollen Wegs
(Speicher `count × size`); die Blockgröße an der gemessenen Spitze je Aufgabe
ausrichten (rund 29 KiB bei 16 Zeilen, wächst mit der Zeilenzahl), nicht an
einem Feld; die Speicherspitze von `detect` am Meshy-Brett alt gegen neu in
den Bericht. Löst B1 die Doppellesung über das Wissen des Stapels, bleibt (b)
bestehen und muss dort bewusst entschieden werden.

### B5 — `refine.solve` hängt bei einem Budget unter eins (nach 0.5.1)

**Ort:** `refine.py:220–272`.

**Beleg:** Sonde A2 (`laeufe\rev-stapel-a2.txt`): `refine.solve(…,
evaluations=0)` im Unterprozess nach 60 s nicht zurück; SciPy:
`ValueError: max_nfev must be None or positive integer.` Die Schleife prüft
`nfev == evaluations` (`:223`) und `nfev < evaluations` (`:229`); bei 0 ist
beides nie wahr. Ebenso lehnt SciPy Genauigkeiten unter der
Maschinengenauigkeit ab (Sonde A, 25 Fälle mit 0,0), der Nachbau rechnet.
Heute unerreichbar (`ROUND_FIT_EVALUATIONS = 100`, `ROUND_FIT_PRECISION =
eps**0.75`), aber `solve` gibt sich als `least_squares`-Ersatz aus.

**Fix:** am Anfang `if evaluations < 1: raise ValueError(...)` wie SciPy.

### B6 — Der Nachbau trägt den Lizenzvermerk von SciPy nur halb (vor dem Tag, Rechtefrage — Robert entscheidet)

**Ort:** `refine.py:55–56`, `:199`.

**Was falsch ist:** `solve` und `_trust_region_step` sind eine Übertragung von
`trf_no_bounds` und `solve_lsq_trust_region` (SciPy, BSD-3-Clause). Klausel 1
verlangt bei Weitergabe von Quelltext den Copyright-Vermerk, die Bedingungen
und den Haftungsausschluss. Die Datei nennt Lizenz und Rechteinhaber, nicht
Bedingungen und Ausschluss; der volle Text steht nur in der erzeugten
`THIRD-PARTY-NOTICES.md` beim Abhängigkeitseintrag `scipy` (Zeile 12069 ff.).
Das Repository wird zum Release öffentlich; es ist die erste übertragene
Fremdzeile im Projekt (keine Vorlage in `app/`).

**Fix:** den SciPy-Vermerk (Copyright-Zeile, drei Bedingungen, Ausschluss)
als Kommentarblock an `refine.py` oder mindestens einen Verweis auf die
Fundstelle des vollen Texts im Repository; einmal von Robert bestätigen
lassen.

### B7 — Veraltete Verweise auf die Formelquelle (nach 0.5.1)

**Ort:** `refine.py:57–58` („dieselben Formeln wie in
``_fit_cone_measured`` und ``_fit_torus_measured`` — wer dort eine ändert,
ändert sie hier mit“), `:129`, `:147`, `:443`, `:484`.

**Was falsch ist:** Seit `53813ec61` stehen Residuen und Ableitungen in
`_cone_from_plan`/`_torus_from_plan` (`features.py:8108–8143`,
`8414–8445`); `_fit_cone_measured` ist nur noch der Verteiler. Der Hinweis
für den Zwilling zeigt damit ins Leere; die Regel in `schichtanalyse.md`
nennt die richtigen Namen.

**Fix:** Namen in den fünf Docstrings nachziehen.

### B8 — Der Balken steht während des Stapels (nach 0.5.1)

**Ort:** `features.py:7855–7876` (Planschleife ohne Fortschritt: Lesung,
Kegelplan, Ringplan, Kennzahl je Fleck), `refine.py:369–370` (Fortschritt
nur je Block, nicht je Runde).

**Was falsch ist:** Die Lesungen, die vorher in der `classify`-Schleife mit
Fortschritt je Fleck lagen, liegen jetzt vor ihr; der Anteil des Stapels
(`SCREEN_SHARE = 0.2`) bewegt sich erst, wenn ein ganzer Block fertig ist.
§2.8 bleibt erfüllt (die Uhr läuft sekündlich weiter), der Balken steht aber
sichtbar still.

**Fix:** Planschleife meldet je Fleck in der ersten Hälfte des Anteils,
`_run` je Runde.

## Was geprüft wurde und hält

### Der Nachbau von `least_squares` (`refine.solve`, `refine.py:178–315`)

**Zeile für Zeile gegen SciPy 1.18.1 gelesen.** Weg im Original:
`least_squares` mit `method='trf'` (Vorgabe) → `check_x_scale(None)` gibt für
`trf` 1.0, als Einsenfeld aufgebläht → `make_strictly_feasible` lässt `x0` bei
unendlichen Schranken unverändert → `VectorFunction` wertet am Start erst
`fun`, dann `jac` aus (Nachbau `:204–205`, gleiche Folge) → `trf` →
`trf_no_bounds` (beide Schranken unendlich) mit `tr_solver='exact'` (dichte
Ableitung). Nicht `lm`, nicht `dogbox`, keine `loss`, kein `x_scale='jac'`.

| Schritt | SciPy | Nachbau |
|---|---|---|
| Maßstab `d = 1`: `J*d`, `d*g`, `d*step_h`, `norm(x0*scale_inv)` | `trf.py:437–445, 477–482, 512` | entfällt, Werte identisch (Multiplikation mit 1,0 ist exakt; `J*d` behält die Speicherordnung) |
| `Delta == 0 → 1.0` | `trf.py:443–445` | `:215–217` |
| `gtol` am Schleifenkopf, dann Budget | `trf.py:466–475` | `:221–224` |
| Zerlegung `scipy.linalg.svd`, `uf = U.T f` | `trf.py:482–484` | `:225–227` |
| innere Schleife `actual_reduction <= 0 and nfev < max_nfev` | `trf.py:502–503` | `:228–229` |
| Vertrauensbereich (`rtol=0.01`, `max_iter=10`, Rang über `EPS*m*s[0]`, Neustart bei Rangmangel) | `common.py:57–168` | `:278–315` |
| vorhergesagte Abnahme | `evaluate_quadratic`, `common.py:325–360` | `:231–232` |
| nicht endlicher Probepunkt: `Delta = 0.25*|step|`, `continue` | `trf.py:519–521` | `:237–239` |
| Radius und Güte | `update_tr_radius`, `common.py:222–245` | `:243–253` |
| Abbruch `ftol`/`xtol` → 2/3/4 | `check_termination`, `common.py:705–717` | `:254–263` |
| `alpha *= Delta/Delta_new` | `trf.py:540–541` | `:264–265` |
| Annahme, neue Ableitung, Gradient | `trf.py:543–558` | `:266–272` |
| Status 0 bei ausgeschöpftem Budget, Rückgabe `x`, `fun`=`f_true`, `jac`, `nfev`, `status`, `success = status > 0` | `trf.py:580–587`, `least_squares.py:1035–1036` | `:273–275`, `Solution` |

`_refined_fit` liest genau `success`, `x`, `fun`, `nfev`, `jac`
(`features.py:7789–7805`); `cost`, `grad`, `optimality`, `njev` fehlen und
würden von mypy gemeldet. Nicht nachgebaut: Schranken, `loss`, `lsmr`,
Rückruf, Argumentprüfung (siehe B5) — kein Aufrufer braucht sie.

**Gerechnet, bitgleich in `x`, `fun`, `jac`, `nfev`, `status`:**

- Sonde A (`laeufe\rev-stapel-a1.txt`): 258 Zufalls- und Randfälle — linear
  voll und rangdefizient (doppelte oder leere Spalte), Start null,
  Exponentialanpassung, Rosenbrock, unterbestimmt (m < n), Nullresiduum am
  Start, skalarer und ganzzahliger Start, Budgets 1/2/3/5/10/100,
  Genauigkeiten `eps**0.75`, 1e-8, 1e-3, 1e-15. Alle numerischen Ausgänge
  gleich (Status 0, 1, 2, 3 vertreten). Abweichend nur die Argumentprüfung:
  Genauigkeit 0,0 (SciPy lehnt ab, 25 Fälle) und NaN-Start (beide
  `ValueError`, anderer Text).
- Sonde A2 (`laeufe\rev-stapel-a2b.txt`): 60 Läufe mit 2 966 nicht endlichen
  Probepunkten — gleich.
- Sonde B (`laeufe\rev-stapel-b1.txt`): 4 700 Kegel- und Ringläufe mit den
  Residuen und Ableitungen der Anwendung (über `_cone_from_plan`/
  `_torus_from_plan`) — 0 Abweichungen.

Die Fassung in `constraints.txt` ist 1.18.1; `pyproject.toml` erlaubt ab
1.13. Den Weg `trf_no_bounds` hält im Tor nur
`test_the_solver_computes_what_scipy_computes` fest, und zwar nur an den
Zweigen, die die Beulenkugel berührt (B2). Kein Zufall, keine Startwerte
(Regel 9); deterministisch wie SciPy, mit denselben BLAS-/LAPACK-Aufrufen wie
vorher.

### Der Stapel (`refine.exhausted`, `features._screened_fits`)

**Was ausgelassen wird:** nur Kegel- und Ringläufe mit Ableitung, und nur,
wenn der vorhergesagte Lauf ohne Abbruch am Budget endet, mit Abstand zu
jedem Zweig (`DECISION_MARGIN`), zu jedem Abbruch (`STOP_MARGIN_DECADES`) und
bestätigt durch den Schatten. Genau diese Läufe liefern im alten Weg `None`
(`_refined_fit`, `features.py:7789`: `not result.success`). Kugel, Zylinder,
Bögen, Nahtstücke, `_cylinder_beside_a_torus` und die örtlichen Zwillinge
(`_near_surfaces`, `features.py:9402`; `features.py:5959`) rechnen wie vorher
— dort gilt die `kern.md`-Regel „örtlich = ganz“ weiter, weil der Stapel kein
Ergebnis ändert.

**`_run` gegen SciPy gelesen:** Reihenfolge äußere Prüfung → Zerlegung →
innerer Schritt → Güte → Abbruch → Radius/`alpha` → Annahme wie
`trf_no_bounds`; ein nicht endlicher Punkt macht die Zeile „nicht sicher“
(strenger als SciPy, nie gefährlich); NaN in einer Entscheidungsgröße endet
als `final_decision = NaN` und damit nicht sicher; ungesunde Zeilen verlassen
den Stapel vor der Zerlegung.

**Kann ein Merkmal verloren gehen?** Nur über ein falsches Nein. Belege:

- Paket: 553 Körper bitgleich. Eigener Nachvergleich der Rohdaten
  (`sonden\stapel\p42_alt.jsonl` gegen `p42_wt2.jsonl`, eigenes Skript
  `sonden\revstapel\vergleich_p42.py`): 553/553, kein Fehler, 0 Abweichungen
  über 37 596 Merkmale (Abdruck, Arten, Freiformauskunft, Dreieckszahl).
  Nicht neu gerechnet — das war nicht in der Zeit.
- Sonde B, außerhalb des Korpus, `MIN_BATCH = 1`: neun Familien — Kegel echt
  (1–75°), fast wie Zylinder (Anfangswinkel 0,5–5° an einem Zylinder),
  kleiner Winkel (0,5–2°), gekrümmte Splitter (Kugelfleck als Kegel), mit
  belegter Spitze; Ringe mit dünner (0,2–5 %) und dicker Röhre, Ring an Kugel
  und an Zylinder; Rauschen 0 bis 1 %, halb Float32, Punktzahlen gezielt an
  16/17, 32/33, 64/65, 128/129. 4 700 Aufgaben, 1 235 echte Läufe
  vergeblich, 993 davon erkannt, **0 falsche Neins**; Reihenfolge gemischt
  und jede Familie allein: 0 geänderte Urteile.
- Sonde H: dieselben Aufgaben ohne jeden Abstand — 1 falsches Nein (siehe
  B2); mit Abständen 0. Die Abstände tragen.
- Sonde G: unter Plattformrauschen 0 gekippte, 0 falsche Urteile an
  1 484 Läufen (B3).
- Gruppengrenze: unter `MIN_BATCH` sagt der Stapel nichts; ein Block rechnet
  jedes Problem für sich (Zerlegung je Matrix, Summen je Zeile), daher kein
  Einfluss der Nachbarn (Sonde B bestätigt).

**Abbruch:** `check_cancelled` je Fleck in der Planschleife und je Runde in
`_run` (`refine.py:588–589`); `test_a_cancel_stops_the_batch`; der
`ContextVar` wird im `finally` zurückgesetzt, ein Abbruch in
`_screened_fits` setzt ihn gar nicht erst. **Fortschritt:** monoton, aber
grob (B8). **Merker:** Treffer nur bei bitgleicher Lesung und Toleranz
(`support.digest`, dieselbe Formel wie `_fit_cone_read`); `_by_geometry`
merkt sich das Ergebnis mit Stapel wie ohne. Sonde E: an 13 Netzen (CAD-Teile
aus `tests/data/meshes`, Beulenkugel, Freiform, Lochplatte 204 000 △) in
jedem Lauf dieselben Merkmale mit und ohne Stapel.

### Regeln (Durchgang `regelcheck`)

- **1** `refine.py` importiert NumPy, SciPy (träge) und `app.core.units`; kein
  Qt. **2–5, 8, 10–16, 18–20, 22** nicht berührt (keine Op, keine
  Oberfläche, keine Datei, kein Netz, keine neue Abhängigkeit).
- **6** Gleitkomma-`==` an `refine.py:216, 245, 300, 575, 655, 751` — es sind
  SciPys eigene exakte Proben (`Delta == 0`, `predicted == reduction == 0`,
  `alpha == 0`); `is_zero` bräche die Bitgleichheit. Begründet; ein Satz im
  Code, dass sie absichtlich exakt sind, schützt sie vor einem gut gemeinten
  Umbau.
- **7** Die neuen Zahlen sind Rechen- und Sicherheitsabstände mit Herkunft im
  Kommentar, keine Fertigungstoleranzen.
- **9** Der Schatten ist ein festes Muster, kein Zufall.
- **17** `solve` wirft `ValueError` wie SciPy an derselben Stelle; das
  Verhalten nach außen ist unverändert (vorher warf SciPy dieselbe
  Ausnahme). Kein neuer Kundenweg.
- **21** Der Stapel rät nicht zwischen Deutungen; er lässt nur einen Lauf
  aus, dessen Ergebnis leer wäre.
- `kern.md`, Plattformgleichheit: siehe B3. `zwillinge.md`: Die Residuen
  stehen zweimal (Einpassung und Stapel) — gewollter Zwilling mit Test
  (`test_the_batch_computes_the_residuals_of_the_fit`, Gegenprobe M5 rot);
  der Algorithmus steht zweimal (`solve` und `_run`) ohne Test, der beide
  aneinander hält (B2, M8).

### Unterlagen

Regel `schichtanalyse.md` („Ein Löserlauf entfällt nur mit dem Nein des
Stapels“) knapp und ohne Messwerte; die Zahlen stehen in der Begründung unter
derselben Überschrift; die Karte nennt Modul und Weg, ohne die Regel zu
wiederholen. Offen: B3 (Ausnahme falsch zitiert) und B7 (veraltete Namen).
Register (`ROADMAP.md`) zieht das Paket nicht selbst nach; der Registertext
steht im Schlussbericht — das ist Sache der Koordination.

### Merge

`git merge-tree --write-tree --name-only main 8e1afee29` → Exit 0, keine
Konflikte. `main` hat seit `aa82afdff` an `features.py` nur
`_vertex_faces_index`/`_candidates_at` geändert (Kerben), nichts an den
berührten Wegen.

## Kundensicht

Vorher und nachher dieselben Merkmale mit denselben Namen und Maßen (Paket:
553 Körper; hier: 13 Netze, dazu 4 700 synthetische Aufgaben ohne falsches
Nein). Schneller wird die Erkennung an Gittern und erzeugten Netzen
(Paketmessung Kumiko −34 %, Meshy −22 % CPU). An Figuren und Freiformen
kostet der Stapel dagegen acht bis zehn Prozent (B1), was der Nachbau gerade
auffängt; nach B1 würden auch sie schneller. Neue Texte gibt es keine. Der
Balken steht während des Stapels kurz still (B8); die Uhr läuft weiter.
Der Changelog-Satz des Pakets („an Gittermodellen und erzeugten Netzen
deutlich schneller, bei denselben Ergebnissen“) stimmt so.

## Läufe dieses Reviews

Alle im eigenen Baum, gebunden, Protokolle unter `laeufe\`; Sonden und
Rohdaten gesichert unter `sonden\revstapel\`.

| Protokoll | Inhalt | Ergebnis |
|---|---|---|
| `rev-stapel-1.txt` | `tests/test_refine.py` am Endstand | 15 passed, EXIT 0 |
| `rev-stapel-a1.txt` | Sonde A, 258 Fälle `solve` ↔ `least_squares` | numerisch 0 Abweichungen; 26 Argumentprüfungen (B5) |
| `rev-stapel-a2.txt`, `-a2b.txt` | Sonde A2: Budget 0; nicht endliche Probepunkte | hängt > 60 s (B5); 60 Läufe gleich |
| `rev-stapel-b1.txt` | Sonde B, 4 700 synthetische Aufgaben | 0 falsche Neins, 0 Reihenfolgeeffekte, 0 Abweichungen zu SciPy, EXIT 0 |
| `rev-stapel-e1.txt`, `-e2.txt`, `-fgh.txt` | Sonde E, Mehrarbeit an 13 Netzen, zwei Wechsel an der Freiform | B1 |
| `rev-stapel-mut-*.txt`, `-mut-summary.txt` | zehn Gegenproben an `test_refine.py` | B2; `refine.py` danach wie im Commit |
| `rev-stapel-fgh.txt` | Sonde F (Speicher), H (Abstände), G (Rauschen, erster Satz) | B4, B2, B3 |
| `rev-stapel-gh2.txt` | Sonde G (vier Beulenkugeln), H mit Fallausgabe | 0 gekippt, 0 falsch; 1 Fall ohne Abstände |
| `rev-stapel-kern1.txt` | `test_round_surface_measurements.py`, `test_fit_stability.py`, `test_cone_fit_quality.py`, `test_local_detection.py`, `test_refine.py` (ohne Fenster/Leistung) | 227 passed, keiner abgewählt, EXIT 0 |

Nicht gefahren: das ganze Entwicklungstor (das Paket meldet 17 921 grün,
`laeufe\stapel-tor2.txt`), keine Fenster- und Leistungstests (Release-Sache).

Aufgeräumt: Der Arbeitsbaum `wt-revstapel` ist entfernt
(`git worktree remove --force`); die Sonden (`test_zz_revstapel_*.py`,
`zz_mutationen.sh`, `vergleich_p42.py`) und ihre Rohdaten liegen unter
`sonden\revstapel\`. Im Hauptbaum wurde nichts geändert.

## Nachtrag 3a83c04af

Geprüft: Zweig `origin/rm-209-stapel-nachtrag`, Endcommit `3a83c04af`,
darunter der Merge `acac17e73` (Paket `8e1afee29` über `1dc916bd2`); Diff der
Befundbehebung `git diff acac17e73 3a83c04af` (9 Dateien, +869/−40). Der
Merge ist sauber: `git merge-tree --write-tree 1dc916bd2 8e1afee29` ergibt
denselben Baum wie `acac17e73` (`91cda365f`), es steckt also keine Änderung
im Merge selbst. Gerechnet in zwei eigenen Arbeitsbäumen (`wt-revstapel2`
für die Gegenproben, `wt-revstapel3` für die Sonden), gebunden, Protokolle
`laeufe\rev-stapel2-*.txt`, Sonden und Rohdaten
`sonden\revstapel\nachtrag\`. Zeilennummern gelten für `3a83c04af`.

### Urteil Nachtrag

**Mergebar: ja.** B1, B2, B3, B4 und B6 sind behoben, jeder mit eigenem Beleg
unten. Offen bleiben die vereinbarten Registerpunkte B5, B7, B8 und drei
kleine neue Punkte: B9 (Unterlagen, vor dem Tag), B10 und B11 (nach 0.5.1).
Keiner blockiert den Merge.

| Nr. | Stand am Nachtrag |
|---|---|
| B1 | **behoben** — Lesungen und Kennzahlen je einmal, Merkmale gleich |
| B2 | **behoben** — alle zehn Gegenproben rot, dazu eine neue (M11) |
| B3 | **behoben** — Regel nennt die Klasse, Docstring berichtigt, Rauschprobe als Test |
| B4 | **behoben** — Wegfeld durch laufendes Maximum ersetzt, volle Blöcke 47,6–58,0 MiB, einer 65,2 MiB (vorher bis rund 400); Rest siehe B10 |
| B5 | offen (Register): `solve` hängt bei `evaluations < 1` (`refine.py:272`, `278`) |
| B6 | **behoben** — Vermerk wortgleich zu SciPys `LICENSE.txt` 1.18.1 |
| B7 | offen (Register): `refine.py:63–64`, `178`, `196`, `491`, `532` nennen noch `_fit_*_measured` |
| B8 | offen (Register): Balken im Stapel (`features.py:7908` ff., `refine.py:418`) |
| B9 | neu, vor dem Tag: Speicherbegründung ohne Zahl und in der Sache ungenau |
| B10 | neu, nach 0.5.1: `BATCH_PEAK_FACTOR` ohne Reserve, Blockgrenze ohne Test |
| B11 | neu, nach 0.5.1: `test_the_shadow_is_disturbed` ohne Zusicherung „nicht leer“ |

### B1 — behoben

`_surface_support` (`features.py:7423–7426`) und `_rigid_key`
(`features.py:329–333`) antworten in der Runde aus `_Screened`, geschlüsselt
über `_patch_key` (`features.py:7860`: blake2b über die int64-Bytes der
Dreiecksliste, also nur für dieselbe Liste in derselben Folge) und nur für
denselben Körper (`screened.body is body`). Im Wissen liegt genau das Objekt,
das `remembered("support", …)` vorher lieferte; `None` als Kennzahl ist über
`_UNKNOWN` von „nicht im Wissen“ getrennt.

Sonde N3 (`test_zz_revstapel2_knowledge.py`, `laeufe\rev-stapel2-n3.txt`),
je Netz vier `detect` im Wechsel, „alt“ mit leerem Wissen
(`_Screened(body, {}, {}, {})`, also jede Lesung wie vor dem Paket in der
Einpassung):

| Netz | `_read_surface_support` neu / alt | `_rigid_key_read` neu / alt | CPU neu | CPU alt |
|---|---|---|---|---|
| Freiform 200 000 △ | 1 949 / 1 949 | 1 947 / 1 947 | 4,55 / 4,06 s | 4,23 / 4,28 s |
| Kumiko-Schale 94 990 △ | 2 075 / 2 075 | 1 987 / 1 987 | 8,73 / 8,41 s | 11,38 / 11,25 s |
| Beulenkugel 10 000 △ | 466 / 466 | 466 / 466 | 2,19 / 2,17 s | 2,38 / 2,42 s |

Dazu vier CAD-Netze aus `tests/data/meshes`; in allen sieben Netzen und jedem
Lauf dieselben Merkmale. Die Mehrarbeit an der Freiform ist weg (vorher +8 bis
+10 %), die Kumiko-Schale spart 24 %. Gegenprobe M14 (`_patch_key` liefert
für jeden Fleck denselben Schlüssel): 88 Fälle rot in `test_refine.py`,
`test_round_surface_measurements.py`, `test_features.py` — ein kaputtes
Wissen fällt im Tor auf.

Korpus: Die Rohdaten des Pakets habe ich selbst nachverglichen
(`vergleich_p42b.py`): `p42_wt3.jsonl` (Endstand) gegen `p42_vor.jsonl`
(`acac17e73`) und `p42_basis.jsonl` (`1dc916bd2`) je 553/553, 0 Abweichungen
über 37 598 Merkmale; die 34 Abweichungen gegen `aa82afdff` stehen schon
zwischen `1dc916bd2` und `aa82afdff`, kommen also aus den übrigen Merges.
Die Bäume `vor` und `basis` sind inzwischen gelöscht; dass `wt-stapel` beim
Lauf den Endstand trug, zeigen die Dateien: `features.py` und `refine.py`
sind gleich `3a83c04af` und älter als der Lauf (05:11/05:15 gegen 06:02).

### B2 — behoben

Dieselben zehn Gegenproben am Nachtrag (`zz_mutationen2.sh`,
`laeufe\rev-stapel2-mut-summary.txt`), dazu vier neue:

| Mutation | Ergebnis `test_refine.py` (29 Fälle) |
|---|---|
| M1 `SHADOW_NOISE = 0.0` | rot: `test_the_shadow_is_disturbed`, `…guard_case[SHADOW_AGREEMENT]` |
| M2 `MIN_BATCH = 10**9` | rot: `test_the_shipped_batch_size_takes_runs_away` |
| M3 Zweig „nicht endlich“ in `solve` gestrichen | rot: `test_the_solver_follows_scipy_on_its_edges[100]` |
| M4 Neustart bei Rangmangel gestrichen | rot: `…on_its_edges[2]`, `[3]`, `[5]`, `[100]` |
| M5 Vorzeichen der Spitzenzeilen | rot: `test_the_batch_computes_the_residuals_of_the_fit` |
| M6 kein Abbruchabstand | rot: `…guard_case[STOP_MARGIN_DECADES]` |
| M7 kein Zweigabstand | rot: `…guard_case[DECISION_MARGIN]` |
| M8 `rtol` im Stapel 0,02 | rot: `test_the_batch_walks_the_path_of_the_solver` und zwei Wächterfälle |
| M9 Schattenurteil gestrichen | rot: zwei Fälle |
| M10 Stapel ohne jeden Schutz | rot: vier Fälle |
| M11 (neu) `follow()` vergleicht den Plan mit sich selbst | rot: `test_the_shadow_is_disturbed`, `…guard_case[SHADOW_AGREEMENT]` |
| M12 (neu) Blockformel ohne `BATCH_PEAK_FACTOR` (Blöcke zehnmal größer) | **grün** → B10 |
| M13 (neu) Wissen ohne Körperprüfung (`features.py:7423`) | grün — die Prüfung schützt kopierte Kontexte fremder Fäden; heute fährt keine Probe diesen Weg (Hinweis, kein Befund) |
| M14 (neu) `_patch_key` konstant | rot, siehe B1 |

Unmutiert: 29 passed (`laeufe\rev-stapel2-basis.txt`); nach der Serie
stehen `refine.py` und `features.py` wieder wie im Commit. Der Wächterfall
`tests/data/refine_guard_case.json` ist Zahl für Zahl der Fall aus Sonde H
(`waechterfall_vergleich.py`: Punkte, Achsbasis, Start gleich), mit
Zeile in `tests/data/README.md`.

### B3 — behoben

`schichtanalyse.md` benennt die Klasse („sein Nein nur einen leeren Lauf
auslässt und Abstand zu jedem Zweig und Abbruch hält, bestätigt vom Schatten
— keine nachgeprüfte Vorauswahl“), `kern.md` verweist darauf, jede Aussage
einmal; der Docstring (`refine.py:45–52`) beruft sich nicht mehr auf die
nachgeprüfte Vorauswahl. `test_no_verdict_turns_under_platform_noise` fährt
den Stapel unter `platform_noise()` und fordert gleiche Urteile und kein
falsches Nein.

### B4 — behoben

`follow()` (`refine.py:627–636`) ersetzt das Wegfeld. Geprüft gegen die alte
Rechnung: Plan und Schatten gehen im Gleichschritt, `follow()` läuft an
denselben Stellen, an denen vorher `track` beschrieben wurde (vor der
Schleife und am Ende jeder Runde), und vergleicht nur Paare, deren beide
Hälften noch im Stapel sind — das entspricht dem `nanmax` über gleiche
Auswertungsnummern. Einziger Unterschied: ein NaN in den Parametern macht
`apart` jetzt NaN und das Urteil damit „nicht sicher“ (strenger als vorher,
nie gefährlicher). Die späte Bindung von `ids` und `x` in der Closure ist
richtig.

- Sonde N1 (`test_zz_revstapel2_verdicts.py`, `laeufe\rev-stapel2-n1n2.txt`):
  dieselben 4 700 synthetischen Aufgaben wie Sonde B, Nachtrag gegen
  `8e1afee29` Problem für Problem — mit `MIN_BATCH = 1` 993 = 993, mit der
  ausgelieferten Grenze 986 = 986 Neins, 0 abweichende Urteile, 0 falsche.
- Sonde N2 (`test_zz_revstapel2_memory.py`): je Art und Zeilenzahl ein voller
  Block, Spitze über `tracemalloc`:

| Zeilen | Kegel (Probleme, Spitze) | Ring (Probleme, Spitze) |
|---|---|---|
| 16 | 3 679, **65,2 MiB** (Faktor 10,2) | 3 153, 56,9 MiB |
| 64 | 1 043, 56,9 MiB | 894, 58,0 MiB |
| 256 | 269, 51,6 MiB | 231, 57,3 MiB |
| 1 024 | 68, 52,5 MiB | 58, 54,8 MiB |
| 4 096 | 17, 47,6 MiB | 14, 51,9 MiB |

Vorher bis rund 400 MiB je Block (Sonde F). Neun von zehn Blöcken bleiben
unter `BATCH_BYTES = 64 MiB`, der kleinste Kegelblock liegt 1,9 % darüber
(B10).

### B6 — behoben

Der Kommentarblock unter dem Moduldocstring (`refine.py:73–102`) ist mit den
ersten 30 Zeilen von
`.venv\Lib\site-packages\scipy-1.18.1.dist-info\LICENSE.txt` Zeichen für
Zeichen gleich (`lizenz_vergleich.py`: nur das führende `# ` entfernt,
Zeilenenden angeglichen): Copyright-Zeile, drei Bedingungen,
Haftungsausschluss. Davor nennt ein Satz die übertragenen Funktionen
(`trf_no_bounds`, `solve_lsq_trust_region`, `update_tr_radius`,
`check_termination`) und die Fassung 1.18.1 — dieselbe wie in
`constraints.txt`. Für die Weitergabe als Programm führt
`THIRD-PARTY-NOTICES.md` SciPy 1.18.1 mit vollem Lizenztext. Ob das so
genügt, bleibt Roberts Entscheidung; formal ist Klausel 1 jetzt erfüllt.

### B9 — Die 90 MiB sind vertretbar, aber nicht so belegt und begründet, wie gemeldet (vor dem Tag, Unterlagen)

**Ort:** `konzepte/begruendungen/regel-schichtanalyse.md`, Abschnitt „Ein
Löserlauf entfällt nur mit dem Nein des Stapels“, Absatz „Was der Stapel
festhält“; Paketbericht `reports\stapel.md`, Nachtrag, B4.

**Was nicht stimmt:** (a) In der Begründungsdatei steht keine Zahl — weder die
rund 90 MiB noch die Spitzen am Meshy-Brett; sie stehen nur im Paketbericht.
(b) Die Begründung „jeder Plan trug die seine ohnehin“ trifft nur einen Teil:
Sonde N3 hat gezählt, was das Wissen je Runde festhält
(`laeufe\rev-stapel2-n3-meshy.txt`, `probe_n3.jsonl`):

| Meshy-Brett, Runde | Pläne | Lesungen (davon ohne Plan) | eigene Felder der Pläne | Lesungen mit Plan | Lesungen ohne Plan | Kennzahlen | Summe |
|---|---|---|---|---|---|---|---|
| Mantelnachweis | 1 | 1 (0) | 0,1 MiB | 194,7 MiB | 0 | 0 | 194,8 MiB |
| ganze Flecken | 2 352 | 3 122 (893) | 42,3 MiB | 135,4 MiB | 11,2 MiB | 3,5 MiB | 192,3 MiB |
| Stücke | 18 652 | 26 036 (12 354) | 40,4 MiB | 118,2 MiB | 12,9 MiB | **54,3 MiB** | 225,8 MiB |

Knapp die Hälfte der gehaltenen Lesungen gehört zu Flecken ohne Plan, und die
Kennzahlen (`_rigid_key`, bis 36 KB je Fleck) sind gar keine Lesungen — in
der Stückrunde 54 MiB, die erst der Nachtrag festhält. An der Kumiko-Schale
dasselbe Bild (1 120 von 1 412 Lesungen ohne Plan, 3,5 MiB Kennzahlen).
(c) Die Zuordnung „die rund 90 MiB über dem Stand vor dem Paket sind die
Lesungen der Runde“ misst gegen `aa82afdff`; zwischen `aa82afdff` und dem
Merge-Stand `1dc916bd2` liegen die übrigen Merges (dieselben, die 34
Korpuskörper ändern). Belegt ist der Schritt `acac17e73` → `3a83c04af`:
2 440 → 2 481 MiB Arbeitssatz, 3 975 → 4 017 MiB Zusage
(`sonden\stapel\spitze_meshy.txt`, je ein Lauf unter Last) — das passt zu den
15 bis 67 MiB, die der Nachtrag je Runde zusätzlich hält.

**Vertretbar:** ja. Gegen `aa82afdff` +93 MiB Arbeitssatz (+3,9 %) und
+140 MiB Zusage (+3,6 %) an einem Netz mit 1,95 Mio. Dreiecken, für rund ein
Viertel weniger Rechenzeit dort; ein Speicherfehler kostet nach `kern.md` nur
die Erkennung, nicht den Schritt.

**Fix:** Den Absatz in der Begründung berichtigen und mit Zahlen versehen
(was das Wissen je Runde hält, dass es auch Lesungen ohne Plan und die
Kennzahlen sind, die Spitzen gegen `1dc916bd2` oder ehrlich gegen
`aa82afdff` mit dem Hinweis auf die übrigen Merges). Billige Entlastung für
später (nach 0.5.1): `_rigid_key` gibt einen 16-Byte-Abdruck seines Tupels
statt der vollen Abstandsliste zurück — die Kennzahl dient nur dem
Gleichheitsvergleich (`no_cone_here`, `seen`), das nähme die 54 MiB aus der
Stückrunde und aus `no_cone_here`.

**Hinweis für das Register, kein Befund des Pakets:**
`local.RECOGNITION_BYTES_PER_TRIANGLE = 1 800` (Anzeige vor der bestätigten
Vollerkennung). Am Meshy-Brett liegt die Zusage schon vor dem Paket bei
2 085 B/△ (3 877 MiB), mit Paket bei 2 160 B/△ (4 017 MiB) — die Anzeige
„4 GB“ liegt dort beide Male zu tief.

### B10 — Blockgrenze ohne Reserve und ohne Test (nach 0.5.1)

**Ort:** `refine.py:148–154` (`BATCH_BYTES`, `BATCH_PEAK_FACTOR = 10`,
„Gemessen … 4,1 bis 9,9“), `refine.py:401`.

**Beleg:** Sonde N2: der volle 16-Zeilen-Kegelblock erreicht Faktor 10,2 und
65,2 MiB. M12 (Blockformel ohne Faktor, also zehnmal größere Blöcke) lässt
`test_refine.py` grün.

**Fix:** Faktor mit Reserve (12) oder die Grenze als „rund“ benennen; ein
Test, der einen vollen Block unter `tracemalloc` fährt und `peak <=
BATCH_BYTES` fordert (Vorlage `test_zz_revstapel2_memory.py`, eine
Zeilenzahl genügt, wenige Sekunden).

### B11 — Schattenprobe ohne „nicht leer“ (nach 0.5.1)

**Ort:** `tests/test_refine.py:528–539`.

**Was fehlt:** `problems` wird aus den Läufen erhoben (nur die vergeblichen).
Wäre die Menge leer, bestünden beide Zusicherungen (`(apart > 0).sum() >=
0`, `not quiet.any()`) ohne Prüfung (`tests.md`, „Ein Verbotstest über eine
leere Menge ist immer grün“). Die Voraussetzung steht in einem anderen Test
(`test_the_body_brings_runs_that_answer_and_runs_that_do_not`), nicht hier.

**Fix:** `assert len(problems) >= 10` vor der ersten Zusicherung.

### Weitere Prüfungen am Nachtrag

- `ruff check` und `ruff format --check` über `refine.py`, `features.py`,
  `test_refine.py`: sauber. mypy nicht selbst gefahren; der Befund
  `app/ui/leash.py:130` unter `--platform linux`/`darwin` gehört laut
  Koordination zu `1dc916bd2` und ist auf main mit `f1cfff619` behoben.
- Unterlagen: Karte `app/core/perceive/CLAUDE.md` nennt das Wissen mit Lesung
  und Kennzahl; Regel und Begründung stehen unter derselben Überschrift; die
  neue Korpusdatei hat ihre Zeile in `tests/data/README.md`.
- Zeiten: Die CPU-Zahlen aus N3 stammen aus einem Lauf mit weniger Fremdlast
  als der erste Durchgang (Freiform jetzt 4 s statt 11 s); verglichen wird nur
  innerhalb desselben Laufs im Wechsel.

### Läufe des Nachtrags

| Protokoll | Inhalt | Ergebnis |
|---|---|---|
| `rev-stapel2-basis.txt` | `tests/test_refine.py` am Nachtrag | 29 passed, EXIT 0 |
| `rev-stapel2-mut-summary.txt`, `rev-stapel2-mut-M*.txt` | 14 Gegenproben | M1–M11 und M14 rot, M12 und M13 grün |
| `rev-stapel2-n1n2.txt` | N1 Urteile neu gegen alt, N2 Blockspeicher | 0 abweichende Urteile; 9 von 10 Blöcken unter 64 MiB |
| `rev-stapel2-n3.txt` | N3 Lesungen, Kennzahlen, Zeit, gehaltener Speicher an sieben Netzen | gleiche Zählung wie vor dem Paket, gleiche Merkmale |
| `rev-stapel2-n3-meshy.txt` | N3 am Meshy-Brett, ein Lauf | 192–226 MiB Wissen je Runde (B9) |

Aufgeräumt: `wt-revstapel2` und `wt-revstapel3` sind entfernt; Sonden und
Rohdaten des Nachtrags liegen unter `sonden\revstapel\nachtrag\`. Im
Hauptbaum wurde nichts geändert.
