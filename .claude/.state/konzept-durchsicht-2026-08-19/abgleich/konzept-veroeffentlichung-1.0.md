# Abgleich: `.claude/konzept-veroeffentlichung-1.0.md` gegen den Code vom 19.08.2026

Geprüft am 19.08.2026, Stand `b0415d6`, Arbeitsbaum sauber.
Dokumentstand laut Kopf: 06.08.2026, letzter Nachtrag 08.08.2026 — also elf
Tage alt bei einem Dokument mit Fortschrittstabelle.

**Ergebnis in einem Satz:** Von siebzehn geprüften Behauptungen hält genau
eine. Der Grund ist nicht Schlamperei, sondern eine Richtungsänderung, die
das Dokument nicht kennt: **am 12.08.2026 ist aus dem 14-Tage-Testlauf mit
Verkauf eine kostenlose öffentliche Demo bis zum 30.10.2026 geworden**
(`.claude/konzept-demo-2026-10.md`, `ROADMAP.md:4465`). Damit sind §2 A, §2 C,
§3, §4 V5–V9 und die halbe Fortschrittstabelle nicht falsch abgeschrieben,
sondern überholt. Das Dokument sagt an keiner Stelle, dass es einen Nachfolger
hat.

Zählung: **stimmt 1 · überholt 14 · falsch 1 · unprüfbar 1**

---

## Der Kopfbefund: das Nachfolgekonzept fehlt im Text

`.claude/konzept-demo-2026-10.md` (Stand 12.08.2026) sagt in seinem eigenen
Kopf: „Baut auf `.claude/konzept-veroeffentlichung-1.0.md` auf und ändert dessen
§7-Entscheidung ‚keine Beta-Fassung'". Der Kern trägt die Änderung bereits:

```
app/core/activation/store.py:50: DEMO_UNTIL: Final[date | None] = date(2026, 10, 30)
app/core/activation/store.py:144: def days_left(...)  # mit Stichtag zählt der Kalender,
                                  # ohne ihn die Frist ab dem ersten Start
```

`TRIAL_DAYS = 14` (`store.py:36`) steht noch da, ist aber der tote Zweig:
`days_left()` geht nur dann über `trial_days_left()`, wenn `DEMO_UNTIL is None`.
Die Website führt es aus (`website/index.html:376–383`): „0 € — Demo bis
30.10.2026 … Die Vollversion folgt zu 49 € statt 79 €".

**Was im Konzept stehen müsste (als Kasten direkt unter dem Datum):**
> **Überholt am 12.08.2026.** Das Zeitmodell dieses Dokuments — 14 Tage Testlauf
> ab erstem Start, danach Betrachter — ist ersetzt durch eine kostenlose,
> vollständige Demo bis zum 30.10.2026 ohne Schlüssel
> (`.claude/konzept-demo-2026-10.md`, `store.DEMO_UNTIL`). Alles unter §2 A und
> §2 C beschreibt weiterhin die **Verkaufsfassung**, die nach dem 30.10.2026
> entschieden wird; §4 V5–V9 und §9 gelten für die Demo nicht.

---

## Die fünfzehn internen Behauptungen der Arbeitsmappe

### 1. „Tor grün am 06.08.2026: 2872 Tests" bzw. „2913 Tests" — **überholt**

*Ort:* §1.1 (Tabellenzeile „Das Tor"), §9 (V3), §7 („was 2913 Tests nicht abdecken")

**Beleg:**
```
.venv/Scripts/python.exe -m pytest -q --collect-only
→ 4251 tests collected in 3.64s
ls tests/*.py | wc -l → 133
```
Die CI-Zahl aus dem letzten protokollierten Hauptblock liegt bei 3 275
(`ROADMAP.md:4582`), also ebenfalls über den Konzeptzahlen und darunter, weil
der Lauf aufgeteilt ist.

**Statt dessen:** „Das Tor: 4251 Tests in 133 Dateien (Stand 19.08.2026); die
Zahl ist ein Datum, kein Merkmal — sie wird hier nicht mehr fortgeschrieben."

---

### 2. „Acht Beispielprojekte, das achte uncommittet; README nennt sieben" — **überholt**

*Ort:* §1.1, §1.2, §4 V0, §4 V6 („die acht Beispielprojekte sind da")

**Beleg:** `app/core/examples.py:70` führt neun Einträge, der neunte ist
`Weg 4 — eine Figur formen` (Zeile 100). Beide fraglichen Dateien sind
versioniert:
```
git ls-files | grep -i "dose-mit-deckel\|weg4"
→ app/examples/dose-mit-deckel.p3d / .svg
→ app/examples/weg4-figur-formen.p3d / .svg
```
`README.md:56` sagt „neun Beispielprojekte", `website/index.html:154` zeigt
„9". Commit `216b397` („Der vierte Weg war gebaut, nur die Unterlagen wussten
es nicht") hat die Drift geschlossen und einen Test dagegen gestellt
(`test_there_is_one_example_per_way`).

**Statt dessen:** „Beispielprojekte: **neun**, alle versioniert, je eines pro
Hauptweg (`app/core/examples.py:70`, `app/examples/`); README und beide
Startseiten sind gleichgezogen."

---

### 3. „Handbuch achtzehn Seiten" / Nachtrag „dreiunddreißig Seiten, achtundzwanzig Abbildungen" — **überholt**

*Ort:* §1.1, Nachtrag-Tabelle

**Beleg:**
```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; load_operations();
 from app.core import manual, figures;
 print(len(manual.pages()), len(manual.knowledge_pages()), len(figures.FIGURES))"
→ 40 4 25
```
Also **40 Seiten** (25 geschriebene plus die aus dem Register erzeugten
Referenzseiten) und **4 Wissensseiten**, zusammen 44; **25 Abbildungen** im
Katalog, davon sechs aufgenommene Bildschirmfotos je Sprache
(`app/images/manual/de/`, sechs Dateien, sechs Sprachordner).

Die Seitenzahl hängt am Register — mit 85 Operationen wächst die Referenzhälfte
mit. Eine feste Zahl in einem Konzeptdokument ist deshalb dauerhaft falsch.

**Statt dessen:** „Handbuch: geschriebene Seiten plus eine Referenzhälfte, die
aus dem Register entsteht — die Seitenzahl folgt der Zahl der Operationen und
wird hier nicht festgeschrieben (`app/core/manual.py`, `tools/make_manual.py`)."

---

### 4. „`constraints.txt` ist nicht im Repository — der eigentliche Blocker" — **überholt, und im Dokument widersprüchlich**

*Ort:* §1.2 (Haupttext, als Blocker), Nachtrag-Tabelle (als „erledigt"), §4 V0, §5

**Beleg:** `git ls-files constraints.txt` → `constraints.txt`. Sie führt heute
u. a. `Cython==3.2.9` (Zeile 31), also die Bauabhängigkeit aus H5.

Das ist der Fehlertyp, auf den bei diesem Dokument besonders zu achten war:
Der Nachtrag oben sagt „erledigt", §1.2 sagt zwölf Zeilen weiter unten
weiterhin „**Die CI kann in ihrer heutigen Form auf `origin/main` nicht grün
sein**", und §5 baut die ganze Reihenfolgebegründung darauf („V0 zuerst, ohne
Ausnahme — solange `constraints.txt` fehlt …"). Drei Stellen, zwei Wahrheiten.

**Statt dessen:** §1.2 ersatzlos streichen und in §5 den Satz ersetzen durch:
„V0 ist erledigt; `constraints.txt` ist versioniert und der CI-Lauf prüft
denselben Stand wie diese Maschine."

---

### 5. „Bezahlung, Testlauf, Aktivierung — es gibt nichts davon" — **überholt, und im Dokument widersprüchlich**

*Ort:* §1.3 (Überschrift und Haupttext: „keine einzige Zeile"), Nachtrag-Tabelle

**Beleg:**
```
ls app/core/activation/
→ __init__.py  ed25519.py  integrity.py  key.py  store.py
app/core/activation/store.py:36  TRIAL_DAYS: Final = 14
app/core/activation/store.py:50  DEMO_UNTIL: Final[date | None] = date(2026, 10, 30)
app/core/activation/key.py:72    PUBLIC_KEY: Final = bytes.fromhex(...)
```
Gebaut in `b5b5096`, Grenze in `c6b5eea`, Oberfläche in `7fe8cb9`, Schlüssel
gesetzt in `19fe09b` — alle vier stehen bereits in §9 des Dokuments, während
§1.3 daneben unverändert „keine einzige Zeile" behauptet.

**Statt dessen:** §1.3 auf einen Satz zusammenziehen: „Der Prüfkern steht
(`app/core/activation/`, V3–V4c). Was fehlt, ist der Verkauf selbst — und der
wartet auf die Entscheidung nach dem 30.10.2026."

---

### 6. „Kein EULA, keine AGB, keine Widerrufsbelehrung" — **überholt, und im Dokument widersprüchlich**

*Ort:* §1.3 (Haupttext), Nachtrag-Tabelle, §4 V2

**Beleg:** `EULA.md`, `AGB.md`, `WIDERRUF.md` liegen im Wurzelverzeichnis, die
Webfassungen unter `website/eula.html`, `website/agb.html`,
`website/widerruf.html`; erzeugt von `tools/make_legal.py`, gehalten von
`tests/test_legal.py` (u. a.
`test_the_generated_page_matches_its_source`,
`test_the_selling_page_links_every_legal_text`).

Auch der Nebensatz „`LICENSE` … Der Installer zeigt genau diesen Text als
Lizenzseite (`solidon3d.iss:27`)" ist erledigt:
`tools/make_installer.py:74–76` — „Bis hierher stand dort ``LICENSE`` … jetzt
``EULA.md``"; `tests/test_legal.py:66`
`test_the_installer_shows_the_agreement_and_not_the_copyright_notice`.

**Statt dessen:** „EULA, AGB und Widerrufsbelehrung stehen als Quelle im
Wurzelverzeichnis und als erzeugte Seiten auf der Website; der Installer zeigt
den EULA-Text. Offen ist allein die fachliche Prüfung (siehe unten)."

---

### 7. „Anschrift, Hoster und Zahlungsdienstleister fehlen weiterhin; drei Platzhalter mit Entwurfshinweis" — **überholt**

*Ort:* Nachtrag-Tabelle (letzte Zeile), §1.3, §4 V2, §7 Punkt 1 und 3

**Beleg:** Kein Platzhalter mehr im Bestand:
```
grep -rnoE "\[[A-ZÄÖÜ][A-ZÄÖÜ .,-]{3,}\]" website/*.html website/en/*.html EULA.md AGB.md WIDERRUF.md
→ (keine Treffer)
```
* Anschrift: `website/impressum.html:29` „96049 Bamberg", Zeile 38
  „Robert Schneider, Anschrift wie oben."
* Hoster: `website/datenschutz.html:29–35` „netcup GmbH, Emmy-Noether-Straße 10,
  76131 Karlsruhe", samt AV-Vertrag nach Art. 28 DSGVO.
* Zahlungsdienstleister: `website/datenschutz.html:39–49` „Paddle.com Market
  Limited, 30 Old Bailey, London EC4M 7AU"; laut `ROADMAP.md:521` seit dem
  08.08.2026 auch in den AGB.

Der erzwingende Test aus dem Nachtrag existiert weiter
(`tests/test_legal.py:87` `test_a_page_with_a_placeholder_says_that_it_is_a_draft`),
findet aber nichts mehr. Der verbliebene Vorbehalt hängt jetzt an einem
Schalter statt an einem Platzhalter: `tools/make_legal.py:224
REVIEW_PENDING = True`, gehalten von `tests/test_legal.py:111`
`test_an_unreviewed_contract_keeps_its_reservation`.

**Statt dessen:** „Anschrift, Hoster (netcup) und Zahlungsdienstleister
(Paddle) stehen mit echten Angaben in Impressum und Datenschutzerklärung.
Offen ist nur noch die fachliche Prüfung der Verträge — sie hängt an
`tools/make_legal.py: REVIEW_PENDING`, nicht an einem Platzhalter."

---

### 8. „13 lokale Commits nicht gepusht, `origin/main` steht auf `4700309`; unklar, ob die CI je grün lief; `gh` nicht installiert" — **überholt (mit einem Rest, der hält)**

*Ort:* §1.1 Schlussabsatz („**Das ist die erste zu klärende Unbekannte**"), §4 V1

**Beleg:**
```
git rev-list --count origin/main..main → 0
git rev-parse origin/main             → 142663931d18f36bf4caf4e57ef8d48dad65fad0
git status --porcelain                → (leer)
```
Die CI ist gelaufen: `ROADMAP.md:2073` „Der erste echte CI-Lauf … mit vier
Funden, von denen …". Der Stand ist allerdings schlechter, als der Nachtrag
klingen ließ — `ROADMAP.md:4572–4578`: „Von **34 Läufen ist genau einer grün**
— der vom 02.08., per Handstart. Jeder Push seither ist rot". Der offene Punkt
ist unverändert `ROADMAP.md:4570` `- [ ] CI grün sehen und die Artefakte holen`;
die Ursache ist heute benannt (Segmentierungsfehler in `tests/test_chat_ui.py`,
`ROADMAP.md:4583–4590`).

**Hält:** `gh` ist weiterhin nicht installiert (`Get-Command gh` → nichts,
`which gh` → nicht gefunden).

**Statt dessen:** „Der Arbeitsbaum ist sauber und mit `origin/main` gleich. Die
CI ist gelaufen — und ist es überwiegend rot: ein grüner Lauf von 34, der
letzte am 02.08.2026 per Handstart; die Ursache steht in `ROADMAP.md` unter
‚CI grün sehen und die Artefakte holen'. Ohne einen grünen Lauf gibt es keine
Artefakte, weil `package` an `suite` hängt. `gh` ist weiterhin nicht
installiert."

---

### 9. „35 geänderte Dateien, drei unversionierte im Baum" — **überholt**

*Ort:* §1.2 erster Satz

**Beleg:** `git status --porcelain` → leer. `git log --oneline -1` → `b0415d6`.

**Statt dessen:** entfällt mit §1.2 (siehe Nr. 4).

---

### 10. „`ROADMAP.md:526` ist veraltet; `ROADMAP.md:2033` gehört auf `[x]`" — **überholt (Zeilennummern und Sache)**

*Ort:* §1.1, §1.4, §4 V0 Punkt 5

**Beleg:** `ROADMAP.md` hat heute 6759 Zeilen; beide genannten Zeilen zeigen auf
etwas anderes.
* „es gibt kein Remote" steht jetzt in `ROADMAP.md:663` und `ROADMAP.md:1268` —
  und ist an der ersten Stelle bereits berichtigt: „*Überholt am 02.08.2026:
  das Repository liegt auf GitHub, die CI ist gelaufen*" (Zeilen 666–669). Die
  zweite Stelle ist ein historischer Rückblick unter „Bewusst offen, weil es
  niemand von hier aus erledigen kann".
* Der `fits`-Punkt steht jetzt als `ROADMAP.md:2335` und trägt `- [x]`: „Der
  Deckelablauf legt sie jetzt an (`core/lid_flow.py`), über ein `fits`-Feld an
  `OpResult`". `git show --stat aa48f10` bestätigt den Commit;
  `app/core/types.py:653/866/989` führt die `fits`-Felder.

**Statt dessen:** Beide Verweise streichen. „Zeilennummern in `ROADMAP.md` sind
kein Beleg — die Datei wächst täglich; verwiesen wird auf die Überschrift des
Abschnitts."

---

### 11. „P0–P12 abgeschlossen, drei Hauptwege als Ende-zu-Ende-Tests" — **überholt**

*Ort:* §1.1 (erste Tabellenzeile), §4 V6 Punkt 4 („die drei Wege durchgehen")

**Beleg:** `grep -n "^## " ROADMAP.md` findet P13 (Zeile 1278), P14 (1490),
P15 (2236) und P16 (4908). Die Hauptwege sind **vier**:
`tests/test_way_four.py` existiert, das Beispielprojekt
`app/examples/weg4-figur-formen.p3d` liegt bei, und `216b397` zieht Bauplan
§2.2 nach: „**§2.2 heißt jetzt ‚Vier Hauptwege'**". `AGENTS.md` nannte die vier
schon vorher — die Arbeitsmappe hatte hier recht.

**Statt dessen:** „Anwendung: P0–P16 durch, **vier** Hauptwege als
Ende-zu-Ende-Tests (Bauplan §2.2, `tests/test_way_four.py`)."

---

### 12. „Schichtanalyse 1,05 s statt 300 ms" — **stimmt**

*Ort:* §1.4, §3, §4 V10

**Beleg:** `tests/test_performance.py:168–186`
`test_the_layer_analysis_stays_under_the_budget`: „Dieser Körper hat 328 000
Dreiecke und braucht etwa 1,05 Sekunden — also grob 650 ms bei der Größe, die
§31 nennt, von 2,35 Sekunden am Anfang." Gleiche Zahl in `ROADMAP.md:711`
(Tabelle) und `ROADMAP.md:740`.

Die abweichende Angabe „1,7 s" in `ROADMAP.md:660` ist der ältere Stand vor der
Parallelisierung und dort auch als solcher erkennbar.

**Nichts zu ändern.**

---

### 13. „`APP_VERSION` steht auf `0.0.1` (`app/branding.py:35`), `pyproject.toml:7` ebenso; beide gehen auf `1.0.0`" — **überholt, in beiden Hälften**

*Ort:* §2 G, §4 V6 Punkt 1, §9 (V6-Zeile)

**Beleg:**
```
app/branding.py:68  APP_VERSION: Final = "0.1.0"
pyproject.toml:7    version = "0.1.0"
```
`app/branding.py:35` ist heute ein Kommentar zur Support-Adresse. Die Zahl ist
auch nicht mehr auf dem Weg zu 1.0.0: `ROADMAP.md:4525–4536` — „**Fassung
0.1.0** (am 14.08.2026 von 0.7.0 heruntergesetzt, entschieden von Robert). Die
Null vorn ist Mechanik: `key.current_major()` liest sie, also greift ein
1.x-Kaufschlüssel in der Demo nicht". Dass beide Stellen zusammenbleiben, hält
jetzt ein Test:
`test_the_version_is_the_same_in_both_places_that_carry_it`.
`website/version.json` steht passend auf `0.1.0`.

**Statt dessen:** „Version: `0.1.0` in `app/branding.py` und `pyproject.toml`,
von einem Test zusammengehalten. Die führende Null ist Absicht — sie sperrt
1.x-Kaufschlüssel in der Demo. `1.0.0` wird erst gesetzt, wenn nach dem
30.10.2026 der Verkauf beschlossen ist."

---

### 14. „`integrity.py` (H4) fehlt und `require()` hat keinen Aufrufer — die Grenze greift nicht" — **überholt, und im Dokument widersprüchlich**

*Ort:* V3-Kasten („**Gebaut am 08.08.2026**"), dort zwei Absätze, gegen §9

**Beleg:** `app/core/activation/integrity.py` existiert. Die vier Prüfstellen
rufen:
```
app/core/scene/history.py:234    activation.require(activation.CHANGE)
app/core/export/writer.py:452    activation.require(activation.EXPORT)
app/core/export/writer.py:529    activation.require(activation.EXPORT)
app/core/export/handover.py:1019 activation.require(activation.SLICER)
app/core/agent/session.py:172    activation.require(activation.CHAT)
```
Die vier Handlungen sind Konstanten (`app/core/activation/__init__.py:69–72`).
Gehalten von `tests/test_licence_boundary.py` und `tests/test_licence_build.py`
(`ROADMAP.md:3577`: „hält Spec, Werkzeug und CI zusammen"),
`tools/build_licence_module.py` und `tools/make_licence_keys.py` liegen vor.

Der Widerspruch im Dokument: Der V3-Kasten sagt „`integrity.py` (H4) **fehlt**"
und „ein abgelaufener Testlauf sperrt heute nichts", während §9 vier Zeilen
weiter unten V4, V4b und V4c als **fertig, am Paket belegt** führt.

**Eine Einschränkung, die im Konzept fehlt:** In der Entwicklung prüft das
Manifest nichts — `app/core/activation/integrity.py:41
MANIFEST_PUBLIC_KEY: bytes | None = None`, gesetzt erst beim Bau. H4 greift
also am Paket, nicht im Baum; das steht im Modulkopf, aber nicht im Konzept.

**Statt dessen:** Den V3-Kasten auf zwei Sätze kürzen: „Gebaut am 08.08.2026
(`b5b5096`), abweichend als `app/core/activation/` statt `licence/`, Test in
`tests/test_activation.py`. `integrity.py` und die vier Aufrufer kamen mit V4
(`c6b5eea`) nach; `MANIFEST_PUBLIC_KEY` ist nur im gebauten Paket gesetzt, in
der Entwicklung prüft das Manifest nichts."

---

### 15. Fortschrittstabelle §9 und der Aufwand aus §5 — **überholt**

*Ort:* §9, §5 Schlussabsatz

Zeile für Zeile gegen den heutigen Stand:

| §9 sagt | heute |
|---|---|
| V0 fertig | **stimmt** |
| V1 CI grün — offen | **stimmt**, aber der Grund ist heute benannt: 1 grüner Lauf von 34, Segfault in `tests/test_chat_ui.py` (`ROADMAP.md:4570–4590`) |
| V2 Rechtstexte — offen | **überholt**: Impressum, Datenschutz, EULA, AGB, Widerruf stehen mit echten Angaben; offen sind nur die fachliche Prüfung (`REVIEW_PENDING`) und **DMARC** für `solidon3d.de` (`ROADMAP.md:4516`, `- [ ]`) |
| V3 fertig (2913 Tests) | **fertig stimmt, die Zahl nicht** (siehe Nr. 1) |
| V4 / V4b / V4c fertig | **stimmt** (siehe Nr. 14) |
| V5 Kaufabwicklung — offen | **teilweise überholt**: der Anbieter ist entschieden und benannt (Paddle, `website/datenschutz.html:39`, AGB seit 08.08.2026). Der Verkauf selbst ist bewusst verschoben — die Demo verkauft nichts |
| V6 — „Version auf 1.0.0" | **überholt**: 0.1.0 ist die gewollte Zahl (Nr. 13). Was von V6 bleibt, ist die Installation auf einem fremden Rechner |
| V7 Website — offen | **überholt**: live auf `solidon3d.de` seit dem 08.08.2026, HTTPS über Let's Encrypt (`ROADMAP.md:498–506`), seit dem 16.08.2026 **sechssprachig** (`website/en|es|fr|it|pt`), `website/version.json` liegt auf `0.1.0`, Startseite auf Funktionen- und KI-Modell-Seiten geteilt |
| V8 Doku — offen | **überholt** in seinen Einzelpunkten: README nennt neun Beispiele und die vier Wege, `ROADMAP.md` ist fortgeschrieben |
| V9 Veröffentlichen — offen | **überholt in der Sache**: das Ziel ist nicht mehr 1.0, sondern der Demo-Start am **20.08.2026** (`ROADMAP.md:4467`) |

Auch §7 „Noch offen" ist überholt: Punkt 1 (Zahlungsanbieter) ist mit Paddle
entschieden, Punkt 3 (Webspace) mit netcup erledigt. Nur Punkt 2 (Signierung)
hält — `.github/workflows/build.yml:200–211` liefert bewusst unsigniert aus
und schreibt eine Warnung ins Protokoll; die Kommentare dort (Zeilen 206–207)
nennen Azure Trusted Signing als den Weg, falls signiert wird.

**Statt dessen:** §9 durch einen Verweis ersetzen — „Der Fortschritt der Demo
steht in `.claude/konzept-demo-2026-10.md` und in `ROADMAP.md` unter ‚Die Demo
bis 30.10.2026'. Diese Tabelle führt nur noch, was den späteren **Verkauf**
betrifft: V5 (Kaufabwicklung, Anbieter Paddle entschieden), V6 (fremder
Rechner), die Signierentscheidung aus §2 E."

---

## Zwei Behauptungen außerhalb der Arbeitsmappe, die ich mitgeprüft habe

### 16. „Das Repository ist privat und soll es bleiben" — **falsch**

*Ort:* §2 H erster Absatz („Grund: Das Repository ist privat und soll es
bleiben — ein Release-Anhang daraus wäre nicht öffentlich abrufbar"), §3
letzter Punkt („**Keine öffentliche Quelloffenlegung.** Das Repository bleibt
privat.")

**Beleg:** `ROADMAP.md:4497–4499`: „**Das Repository ist öffentlich** und hieß
bis heute `Formwerk`. Umbenannt auf `Solidon`; die Sichtbarkeit ist Roberts
Entscheidung und steht auf öffentlich." Am 14.08.2026 an der API nachgeprüft:
„`full_name: RS-Digital-Studio/Solidon`, `private: false`"
(`ROADMAP.md:4502–4504`). `git remote -v` zeigt entsprechend
`https://github.com/RS-Digital-Studio/Solidon.git`.

Das ist keine Kleinigkeit: §2 H begründet die **gesamte** Auslieferung über
eigenen Webspace damit, dass ein Release-Anhang nicht öffentlich abrufbar wäre
— und §2 I H5 (kompiliertes Prüfmodul) verliert seinen Sinn zum Teil, was die
ROADMAP an derselben Stelle auch sagt: „Damit ist H5 (kompiliertes Prüfmodul)
eine Bremse und keine Hürde — H1 hält weiter."

**Statt dessen:** „Das Repository ist seit dem 12.08.2026 **öffentlich**
(`RS-Digital-Studio/Solidon`). Die Auslieferung über `solidon3d.de` bleibt
trotzdem der Weg — wegen der Dateigröße und weil die Download-Seite den
unsignierten Bau erklären soll, nicht mehr wegen der Sichtbarkeit. Für die
Härtung heißt es: H5 ist eine Bremse, keine Hürde; H1 hält unverändert."

---

### 17. „Rund zwölf bis sechzehn Arbeitstage, realistisch drei bis fünf Wochen" — **unprüfbar**

*Ort:* §5 Schlussabsatz, Tabelle „Umfang"

Eine Schätzung lässt sich am Repository nicht falsifizieren. Prüfbar ist nur
der Kalender daneben, und der ist überholt: die Schätzung wurde am 06.08.2026
für eine 1.0 aufgestellt; seither ist elf Tage lang gearbeitet worden, das Ziel
ist ein anderes (Demo am 20.08.2026), und V0/V3/V4/V4b/V4c sind erledigt.

**Statt dessen:** Die Zeile datieren: „Schätzung vom 06.08.2026 für den Weg zur
1.0; sie gilt nicht für die Demo (siehe `.claude/konzept-demo-2026-10.md`)."

---

## Was am Dokument strukturell zu ändern ist

1. **Der Nachtragskasten oben ist zur Falle geworden.** Er sagt „erledigt", der
   Haupttext darunter sagt weiter „fehlt" — bei `constraints.txt` (Nr. 4), bei
   der Aktivierung (Nr. 5), bei den Rechtstexten (Nr. 6). Wer §1 liest und den
   Kasten überspringt, bekommt drei falsche Blocker. Die überholten Absätze
   gehören gestrichen, nicht danebengestellt; die Begründungen, die erhalten
   bleiben sollen, gehören in einen Abschnitt „Wie es dazu kam".
2. **Dasselbe im V3-Kasten** (Nr. 14): „`integrity.py` fehlt" steht vier Zeilen
   über einer Tabelle, die V4c als fertig und am Paket belegt führt.
3. **Zeilennummern als Beleg aufgeben** (Nr. 10, Nr. 13): `ROADMAP.md:526`,
   `ROADMAP.md:2033`, `branding.py:35`, `index.html:31` — vier von vier zeigen
   heute auf etwas anderes. Abschnittsüberschriften und Bezeichner halten,
   Zeilennummern nicht.
4. **Die Zählstände aus §1 herausnehmen** (Nr. 1, Nr. 2, Nr. 3): Testzahl,
   Seitenzahl, Zahl der Abbildungen und Beispiele veralten pro Arbeitstag. Wo
   die Zahl wirklich gebraucht wird, gehört das Kommando daneben, nicht das
   Ergebnis.
5. **Den Nachfolger benennen.** Ohne einen Verweis auf
   `.claude/konzept-demo-2026-10.md` liest sich §2 A/§2 C wie geltendes Recht,
   obwohl der Kern seit dem 12.08.2026 einen Stichtag statt einer Frist fährt.
