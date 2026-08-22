# Abgleich: `.claude/konzept-demo-2026-10.md` gegen den Stand vom 19.08.2026

Geprüft wurden die fünfzehn intern prüfbaren Behauptungen der Sondierung, dazu
drei Widersprüche, die beim Lesen zusätzlich auffielen. Das Repository wurde
nur gelesen; nichts wurde geändert.

**Zählung:** stimmt 7 · überholt 7 · falsch 1 · unprüfbar 0

Ermittelte Kennzahlen zum Vergleich (heute):

| Größe | Wert | Ermittelt mit |
|---|---|---|
| Operationen | 85 | `load_operations(); len(REGISTRY.all())` |
| Hauptwege | 4 | `3d-agent-bauplan.md:101` „### 2.2 Vier Hauptwege" |
| Beispielprojekte | 9 | `len(app.core.examples.EXAMPLES)` |
| Sprachen | 6 (de + en/es/fr/it/pt) | `ls app/i18n/locales/` |
| Handbuchseiten | 40 (21 geschrieben + 4 Wissen + 15 erzeugt) | `len(manual.pages())` nach `load_operations()` |
| Abbildungen | 25 | `len(app.core.figures.FIGURES)` |
| Fassung | 0.1.0 | `app/branding.py:68`, `pyproject.toml:7` |
| Ungepushte Commits | 0 | `git rev-list --count origin/main..main` |
| Testdateien | 133 (`tests/*.py`), davon 131 `test_*.py` | `ls tests/*.py \| wc -l` |

---

## 1 — „P0–P15 durch, 77 Operationen, drei Hauptwege als Ende-zu-Ende-Tests"

*Ort:* §1 Tabelle, Zeile Anwendung

**Urteil: überholt** — in allen drei Teilen.

**Beleg:**
- Operationen: `.venv/Scripts/python.exe -c "from app.core.bootstrap import
  load_operations; from app.core.registry import REGISTRY; load_operations();
  print(len(REGISTRY.all()))"` → `85`. Der Weg dahin ist datiert:
  `96cf760` (16.08.2026) „Der Agent bietet fünfundachtzig Schemata an, nicht
  vierundachtzig", `5c8f1d0` (16.08.2026) „Der Durchgang vom 16.08. hat die
  Operationszahl nachgetragen".
- Hauptwege: `3d-agent-bauplan.md:101` heißt „### 2.2 **Vier** Hauptwege";
  `3d-agent-bauplan.md:1568` führt die Testart als „die vier Wege aus §2.2".
  `tests/test_examples.py:143-158` hält Bauplan und Beispiele zusammen und
  begründet die Drift ausdrücklich. Commit `216b397` (19.08.2026) heißt „Der
  vierte Weg war gebaut, nur die Unterlagen wussten es nicht"; `ce92dd4`
  (16.08.2026) „Weg 4 lag zwischen den Reparaturwerkzeugen".
  `EXAMPLES` trägt heute die Wege `1,2,3,4`.
- Phasen: `ROADMAP.md:4908` führt ein **P16 — Organische Modellierung**, mit
  `P16.10` als offenem Punkt (`ROADMAP.md:44` in der Kopftabelle). „P0–P15
  durch" beschreibt damit nicht mehr den Umfang, sondern einen früheren Stand.

**Satz, der stattdessen dort stehen müsste:**
„P0–P16 bis auf P16.10 durch, 85 Operationen, vier Hauptwege als
Ende-zu-Ende-Tests (Bauplan §2.2, neun Beispielprojekte)."

---

## 2 — „Vier Stellen im Datenpfad rufen `require()`"

*Ort:* §1 Tabelle, Zeile Lizenzgrenze; §2 B

**Urteil: stimmt.**

**Beleg:** `app/core/activation/integrity.py:48-53` führt genau vier
`BOUNDARY_FILES`: `core/scene/history.py`, `core/export/writer.py`,
`core/export/handover.py`, `core/agent/session.py`. Die Aufrufe stehen in
`history.py:234` (CHANGE), `writer.py:452` und `:529` (EXPORT, einmal Einzel-,
einmal Baugruppenexport), `handover.py:1019` (SLICER), `session.py:172` (CHAT)
— fünf Aufrufe in vier Dateien, vier Gattungen
(`app/core/activation/__init__.py:69-72`).
`tests/test_licence_boundary.py:93-198` prüft jede Grenze einzeln und in beide
Richtungen (`test_a_licence_opens_all_four_boundaries`).

**Satz:** unverändert richtig.

---

## 3 — „Prüfmodul mit Cython kompiliert, signiertes Manifest über vier Grenzdateien, am Paket belegt"

*Ort:* §1 Tabelle, Zeile Härtung; §2 C

**Urteil: stimmt.**

**Beleg:** `.github/workflows/build.yml:188` „Prüfmodul kompilieren und Manifest
signieren". `app/core/activation/integrity.py:41-53` (`MANIFEST_PUBLIC_KEY`,
`MANIFEST_FILE`, `BOUNDARY_FILES`).
`tests/test_licence_boundary.py:251-290`: ohne Manifest wird nichts geprüft,
ein intaktes ändert nichts, ein geänderter Grenzdatei-Inhalt sperrt die
schreibende Seite, ein fremd signiertes sperrt.

**Satz:** unverändert richtig.

---

## 4 — „Handbuch: 33 Seiten, 28 Abbildungen"

*Ort:* §1 Tabelle, Zeile Handbuch

**Urteil: falsch** — die Abbildungszahl war schon am 12.08.2026 nicht richtig.

**Beleg:**
- Heute: `len(manual.pages())` = **40** (nach `load_operations()`; ohne
  geladenes Register nur 25, das erklärt eine zu kleine Zahl im Konzept),
  `len(FIGURES)` = **25**.
- Damals: `git show $(git rev-list -1 --before=2026-08-13 main):app/core/figures.py`
  enthält im `FIGURES`-Block ebenfalls **25** `Figure(`-Einträge. Die 28 stand
  also nie im Code. Die geschriebenen Seiten waren damals 25 `Page(`-Einträge
  gegen 26 heute — die Gesamtzahl lag auch am 12.08. bei rund 40, nicht bei 33.
- Die Bilder liegen sechssprachig: `app/images/manual/{de,en,es,fr,it,pt}` mit
  je 6 Bildschirmfotos.

**Satz:** „Handbuch: 40 Seiten (21 geschrieben, 4 Wissensseiten, 15 aus dem
Register erzeugt), 25 Abbildungen, **sechs** Sprachen, als PDF im
Releases-Ordner."

---

## 5 — „`store.TRIAL_DAYS = 14`, kein Stichtag vorhanden; `Licence` trägt kein `expires_on`"

*Ort:* §1.1 Punkt 1

**Urteil: überholt** im ersten Teil, **stimmt** im zweiten.

**Beleg:** `app/core/activation/store.py:36` `TRIAL_DAYS: Final = 14` steht
weiter, aber `store.py:50` trägt `DEMO_UNTIL: Final[date | None] = date(2026,
10, 30)`, und `days_left()` (`store.py:152-157`) rechnet gegen den Stichtag,
solange er gesetzt ist. Commit `f8ac8c1` (12.08.2026) „Vierzehn Tage ab dem
ersten Start sind keine Demo, die am 30.10. endet".
`Licence` (`app/core/activation/key.py:89-101`) trägt weiterhin nur `major`,
`purchased_on`, `order`, `holder` — **kein** `expires_on`; dieser Halbsatz
stimmt unverändert.

Das Konzept weiß das in §10 selbst („D0 fertig"), lässt §1.1 aber im Präsens
stehen. Wer §1 liest und §10 nicht, hält den Stichtag für ungebaut.

**Satz:** „Der Stichtag steht seit dem 12.08.2026 in `store.DEMO_UNTIL`
(`store.py:50`); `TRIAL_DAYS` bleibt für die Verkaufsfassung daneben stehen.
Der Lizenzschlüssel kennt weiterhin kein Ablaufdatum — das bleibt so."

---

## 6 — „Es ist nie ein Paket auf einem fremden Rechner gelaufen"

*Ort:* §1.1 Punkt 2; §3 D8; §10

**Urteil: stimmt** — und ist am heutigen Tag der kritische Punkt.

**Beleg:** `ROADMAP.md:36` (Kopftabelle) „Auf einem fremden Rechner installieren
… wartet auf: eine gebaute Datei — hängt an der CI" und `ROADMAP.md:4658`
`- [ ] **Auf einem fremden Rechner installieren**`. Keine Gegenanzeige im
Repository.

**Satz:** unverändert richtig — aber der Terminplan darum herum ist es nicht
(siehe Zusatzfund Z1).

---

## 7 — „Kein Menüeintrag zum Suchen nach neuen Fassungen; `updates.check()` schweigt in zwei von drei Fällen (`main_window.py:4202` und `:4222`)"

*Ort:* §1.1 Punkt 3; §2 G

**Urteil: überholt.**

**Beleg:** `app/ui/main_window.py:1720` legt den Eintrag „Nach einer neuen
Fassung sehen" an, `:1712` daneben „Rückmeldung schreiben …".
`main_window.py:5586-5602` (`_update_answered`) beantwortet **alle drei** Fälle:
neuere Fassung mit Nummer und Adresse, „Sie haben die aktuelle Fassung
({version})", „Die Seite war nicht erreichbar — später noch einmal versuchen.";
`action_check_updates` (`:5603-5612`) setzt dafür `_asked_for_update`.
Commit `1c50fab` (12.08.2026). Die Zeilennummern 4202/4222 zeigen in der heute
6029 Zeilen langen Datei auf nichts Verwandtes mehr.

**Satz:** „Der Menüeintrag ‚Nach einer neuen Fassung sehen' steht unter Hilfe
und antwortet in allen drei Fällen (`main_window.py:1720`, `_update_answered`);
die Abfrage beim Start bleibt abgeschaltet."

---

## 8 — „205 Commits sind nicht gepusht, `origin/main` steht auf dem 06.08., letzter grüner CI-Lauf 02.08., Segmentierungsfehler in `panels.py::show_document` aus `tests/test_operation_ui.py`"

*Ort:* §1.2 c; §3 D7

**Urteil: überholt** — und das ist der Fund mit der größten Wirkung auf eine
Entscheidung.

**Beleg:**
- `git rev-list --count origin/main..main` → `0`.
  `git log origin/main -1` → `b0415d6 2026-08-19 Vier Stellen versprachen es,
  der Kern antwortete mit einer Fehlermeldung`. Es ist also alles gepusht, und
  `origin/main` steht auf **heute**, nicht auf dem 06.08.
- Der Absturzbefund ist überholt: `ROADMAP.md:5899` „**Der Ort des Absturzes ist
  zufällig — er kumuliert.** Vier Läufe fielen nach 228, 480, 3698 und 3907
  Tests" (abgehakt, Commit `c1ff696`, 18.08.2026). Die Kopftabelle
  (`ROADMAP.md:35`) nennt als Rest den Segfault in **`test_chat_ui.py`**, nicht
  in `test_operation_ui.py`; der Aufrufweg steht in `ROADMAP.md:4586-4592`.
- Der Push ist damit nicht mehr das Nadelöhr; „CI grün sehen und die Artefakte
  holen" ist es (`ROADMAP.md:4570`).
- Die Zusatzbedingung „vorher Fund a) entscheiden" (D7 Punkt 1) ist entfallen:
  `git remote -v` → `https://github.com/RS-Digital-Studio/Solidon.git`,
  öffentlich, umbenannt (`ROADMAP.md:4498-4517`).

**Satz:** „Alles ist gepusht; `origin/main` steht auf dem Tagesstand. Offen ist
ein grüner CI-Lauf: der Hauptblock ist grün, `tests/test_chat_ui.py` stirbt auf
den Linux-Runnern an einem kumulierenden Segmentierungsfehler, dessen Ort
zufällig ist (`ROADMAP.md:5899`). Ohne grüne Suite kein Artefakt."

---

## 9 — „`package` hängt an `needs: suite`"

*Ort:* §1.2 c

**Urteil: stimmt.**

**Beleg:** `.github/workflows/build.yml:142` `needs: suite`; der Kopf der Datei
(`build.yml:3-7`) begründet es: „zuerst läuft die Suite … und nur was grün ist,
wird paketiert."

**Satz:** unverändert richtig.

---

## 10 — „Setup-Bau war kaputt (`dist/Solidon` gegen `dist/Solidon3D`), Handbuchbilder fehlten im Paket — beides am 12.08. behoben"

*Ort:* §1.2 d und e

**Urteil: stimmt.**

**Beleg:** `tests/test_packaging.py:68`
`test_every_data_directory_travels_with_the_package`, `:80`
`test_the_spec_names_the_application_from_branding`, `:95`
`test_the_installer_finds_what_the_spec_builds`, `:107`
`test_the_workflow_carries_no_second_copy_of_the_name`.
`ROADMAP.md:4479-4489` führt beide Funde abgehakt.

**Satz:** unverändert richtig.

---

## 11 — Die zeilengenauen Fundstellen der Testlauf-Texte

*Ort:* §1.2 „Was heute falsch auf der Seite steht"

**Urteil: überholt** — die Arbeit ist getan, die Zeilennummern zeigen ins Leere.

**Beleg:**
- `website/index.html` hat heute **605** Zeilen; die genannte Zeile 670
  existiert nicht. Zeile 84 ist `</div>`. Die Seite führt die Demo:
  `index.html:101` „Demo ab 20. August 2026 — kostenlos", `:379` „Demo bis
  30.10.2026", `:474` „Die Demo lässt sich ab dem 31. Oktober nicht mehr
  starten."
- `website/en/index.html`: 603 Zeilen, dieselbe Verschiebung.
- `website/eula.html:40` trägt jetzt `<h2>4a. Demo-Fassung</h2>` — der Abschnitt
  aus D3, nicht mehr der Testlauf-Abschnitt.
- `website/agb.html` (82 Zeilen) und `website/widerruf.html` (76 Zeilen) tragen
  weiter die Kauftexte, jetzt aber ausdrücklich als „gilt ab dem Verkaufsstart"
  (Commit `57d1d7b`, 12.08.2026).
- `app/ui/first_run.py:113-121` sagt heute: „Diese Demo läuft vollständig und
  ohne Schlüssel bis zum {date}; danach lässt sie sich nicht mehr starten."
- `app/core/activation/store.py:35` ist der Kommentar, `TRIAL_DAYS` steht auf
  Zeile 36 und ist bewusst stehen geblieben (Verkaufsfassung).

**Satz:** Der ganze Kasten gehört gestrichen und durch einen Satz ersetzt:
„Erledigt am 12.08.2026 (`9a88bfa`, `57d1d7b`, `1c50fab`). Offen an der Seite
bleibt allein der Download-Kasten: `grep -rn 'SHA-256\|SmartScreen\|Prüfsumme'
website/` findet **nichts**, und statt einer Datei steht dreimal ein
`mailto:`-Knopf (`website/index.html:106`, `:384`, `:573`)."

---

## 12 — „D1 schreibt Fassung `0.9.0` vor" gegen §10 „`0.1.0` an sieben Stellen"

*Ort:* §3 D1 gegen §10 Schlussabschnitt

**Urteil: Widerspruch im Dokument; der Code sagt 0.1.0** (überholt ist D1).

**Beleg:** `app/branding.py:68` `APP_VERSION: Final = "0.1.0"`,
`pyproject.toml:7` `version = "0.1.0"`, `website/version.json` `"version":
"0.1.0"`, `README.md:13` „## Fassung 0.1 — die öffentliche Demo",
`EULA.md:13`/`:60` „Zur Demo-Fassung 0.1" / „## 4a. Demo-Fassung".
`tests/test_toolchain.py:108`
`test_the_version_is_the_same_in_both_places_that_carry_it` hält die beiden
Handstellen zusammen. `ROADMAP.md:4526` „**Fassung 0.1.0** (am 14.08.2026 von
0.7.0 heruntergesetzt, entschieden von Robert)".

Derselbe Widerspruch steht ein zweites Mal in **§9 Punkt 1**, wo die
Fassungsnummer noch als offene Entscheidung geführt wird („Bis zum Widerspruch
wird `0.9.0` gebaut") — entschieden am 14.08.2026.

**Satz:** D1 muss lauten „`app/branding.py` und `pyproject.toml` auf `0.1.0`",
die Abnahme „eine erzeugte Projektdatei trägt `app_version: 0.1.0`", und §9
Punkt 1 gehört unter „Entschieden am 14.08.2026". Ebenso zu streichen sind die
`0.9.x`-Nennungen in §3 D6 („in 0.9.1 nachziehen"), §5 („0.9.1, 0.9.2") und §6
(„0.9.5") — nach der Zählregel aus §2 D ist der nächste Bau `0.1.1`.

---

## 13 — „`settings.check_for_updates` steht per Vorgabe auf `False`"

*Ort:* §2 G

**Urteil: stimmt.**

**Beleg:** `app/ui/settings.py:77` `check_for_updates: bool = False`.
Gelesen wird sie nur beim Start (`main_window.py:5461-5462`); der Menüweg geht
daran vorbei.

**Satz:** unverändert richtig.

---

## 14 — Fortschrittstabelle §10 (D0–D5 fertig, D6 halb, D7/D8 offen, D9 halb; `kern.md` ohne Stichtag)

*Ort:* §10 Tabelle

**Urteil: stimmt** — mit einer Einschränkung bei D4/D6.

**Beleg:**
- Die fünf genannten Commits existieren und tragen die zugeschriebene Arbeit:
  `f8ac8c1` (12.08., Stichtag), `7c2e6d6` (12.08., Fassung), `1c50fab` (12.08.,
  Texte und die zwei Menüeinträge), `57d1d7b` (12.08., Rechtstexte), `9a88bfa`
  (12.08., Website).
- D6 „halb": `build.yml:199-211` „Ohne Signatur bauen (Windows)" mit
  `::warning::Unsigniert gebaut`. Die fehlende Abnahme ist belegt: auf der
  Website steht kein Wort zu SmartScreen und keine Prüfsumme (siehe Nr. 11).
- D7/D8 offen: `ROADMAP.md:35-36` und `:4570`, `:4658`.
- D9 „halb": `.claude/rules/kern.md` enthält weder `DEMO_UNTIL` noch „Stichtag"
  noch „30.10" (`grep -n "DEMO_UNTIL\|Stichtag\|30.10" .claude/rules/kern.md`
  → keine Treffer). Der Punkt ist unverändert offen.
- Einschränkung: D4 ist als „fertig" geführt, aber Punkt 1 („Download-Kasten:
  echte Dateien, SHA-256 daneben") und Punkt 2 („der ‚Früher
  hineinschauen'-Mailto verschwindet") sind es nicht — der `mailto:` steht
  dreimal auf der Startseite (`website/index.html:106`, `:384`, `:573`).
  Der Schlussabsatz von §10 sagt das zwar, die Tabelle sagt es nicht.

**Satz:** In der Tabelle bei D4 ergänzen: „**fast fertig** — es fehlt der
Download-Kasten mit Datei und Prüfsumme; bis dahin steht dort der
`mailto:`-Platzhalter aus D4 Punkt 2." Der Rest bleibt.

---

## 15 — „Vier ROADMAP-Punkte offen: ES/FR/IT/PT fehlen, Skizzen-Restpunkte, Plattenvorschlag in der Oberfläche; Paketierung sah OCP und V-HACD zuletzt nicht (`ROADMAP.md:515`)"

*Ort:* §5; §3 D8 Abnahme; §8 letzter Punkt

**Urteil: überholt** — alle vier Teile.

**Beleg:**
- Sprachen: `ls app/i18n/locales/` → `en.json es.json fr.json it.json pt.json`,
  dazu Deutsch als Quelle. `ROADMAP.md:4451-4459` nennt sechs Kataloge mit je
  2 426 Einträgen, keiner leer, und `available_languages()` zählt das
  Verzeichnis. Die Website ist seit dem 16.08. sechssprachig und seit dem
  18.08. hochgeladen (`ROADMAP.md:506-512`, Commits `6a08c84`, `ae72a05`,
  `db9cf98`).
- Skizzen: `ROADMAP.md:4460-4463` „**Skizze bedienerisch fertig** (B1) … die
  übrigen Punkte aus `konzept-bedienung.md` Teil 4 sind seither nachgekommen —
  … im Code nachgeprüft am 13.08."
- Plattenvorschlag: `ROADMAP.md:413` `- [x] Plattenvorschlag angeboten —
  `arrange_bed` trägt jetzt den Umschalter *Nach Filament trennen*".
- OCP/V-HACD: `packaging/solidon3d.spec:97-109` listet die zwölf
  `OCP.*`-Module und `vhacdx` unter `hiddenimports`. Der Fund selbst steht
  heute auf `ROADMAP.md:654`, nicht auf `:515` (dort steht inzwischen der
  Website-/Let's-Encrypt-Absatz), und er ist als behoben verbucht.

**Satz:** §5 vierter Punkt und §8 letzter Punkt gehören gestrichen; §3 D8
Abnahme muss lauten „die Paketierung nimmt OCP und V-HACD über
`hiddenimports` mit (`packaging/solidon3d.spec:97-109`) — am gebauten Paket
noch zu belegen." §5 bleibt damit ohne die „verbleibenden vier
ROADMAP-Punkte"; was tatsächlich offen ist, steht in `ROADMAP.md:27-45`.

---

## Zusatzfunde beim Lesen (nicht in der Sondierungsliste)

### Z1 — Der Terminplan in §4 ist heute abgelaufen

§4 legt für den **19.08.** „D8 fremder Rechner, D9 Doku" fest und für den
**20.08.** den Start. Heute ist der 19.08., und D7 wie D8 stehen unverändert
auf offen (`ROADMAP.md:35-36`). §4 nennt zugleich die Bedingung: „Was am 19.08.
fertig sein muss, sonst startet nichts: ein Paket, das auf einem fremden
Windows installiert …". Ein Paket gibt es nicht, weil es keinen grünen CI-Lauf
gibt. Wer den Plan als Stand liest, hält den Start für gesichert.

**Satz:** „Der Start am 20.08. steht nicht: D7 und D8 sind offen, weil die
Suite auf den Linux-Runnern an `tests/test_chat_ui.py` stirbt und `package` an
`needs: suite` hängt. Der Rückfallweg aus D7 Punkt 4 — lokal bauen und von Hand
hochladen — ist damit der einzige Weg zu einem Start am 20.08.; sonst
verschiebt sich der Start, nicht der Stichtag (§4 Schlussabsatz)."

### Z2 — §9 Punkte 0 und 0b sind entschieden und erledigt

§9 führt „Bleibt das Repository öffentlich?" als offene, den Push blockierende
Entscheidung und „Zieht das Repository auf den Produktnamen um?" als offen.
Beides ist erledigt: `git remote -v` zeigt auf
`https://github.com/RS-Digital-Studio/Solidon.git`; `ROADMAP.md:4498-4517`
hält fest, dass die Umbenennung durch ist, der alte Name mit 301 antwortet, die
Sichtbarkeit auf öffentlich entschieden wurde und die Begründung der
CI-Matrix am 14.08. nachgezogen wurde (`build.yml:21-28`).

**Satz:** §9 Punkte 0, 0b und 1 gehören in den Absatz „Entschieden" mit Datum
14.08.2026; offen bleibt allein Punkt 2 (Rechtsprüfung).

### Z3 — §8 „Kein macOS" gegen die Paketierung

§8 führt „Kein macOS, kein AppImage, kein Flatpak" als ausdrückliche
Nicht-Zugehörigkeit. Der Paketierschritt für macOS existiert inzwischen:
`packaging/solidon3d.icns`, `tests/test_packaging.py:155`
`test_the_specification_builds_a_bundle_on_macos`, `:194`
`test_the_workflow_keeps_the_two_mac_packages_apart`, und `build.yml:50` nimmt
`macos-latest` bei Tag und Handstart in die Matrix. Die *Auslieferung* bleibt
offen (`ROADMAP.md:32`: „wartet auf Apple-Zertifikat und Notarisierung; der
Paketierschritt steht").

**Satz:** „Kein macOS-Download — der Paketierschritt steht und läuft in der
Matrix mit, ausgeliefert wird er nicht, weil Zertifikat und Notarisierung
fehlen."

### Z4 — §3 D8 „die acht Beispielprojekte"

`len(app.core.examples.EXAMPLES)` → **9**. Die Verwechslung ist im Projekt
bekannt und an anderer Stelle schon behoben (`ROADMAP.md:4557`: „acht gegen
neun Beispielprojekte" als einer von vier Selbstwidersprüchen der Startseite).

**Satz:** „die neun Beispielprojekte sind da und rechnen".
