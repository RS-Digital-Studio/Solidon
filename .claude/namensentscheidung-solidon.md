# Namensentscheidung: Formwerk wird Solidon

Stand 07.08.2026. Ergänzt `konzept-veroeffentlichung-1.0.md` — dort ist der
Produktname an vielen Stellen noch „Formwerk". Diese Datei sagt, warum er geht
und was an seine Stelle tritt. Sie wird hinfällig, sobald die Umbenennung
durch ist und das Konzept nachgezogen wurde.

---

## §1 Warum Formwerk nicht bleiben kann

Der Name wurde am 27.07.2026 gewählt (`app/branding.py:11`). Eine Recherche im
DPMAregister am 07.08.2026 hat zehn Treffer zu „Formwerk" ergeben, davon vier
eingetragene Marken. Drei davon sind branchenfern und ohne Belang:

| Registernummer | Inhaber | Klassen | Gegenstand |
|---|---|---|---|
| 302014063859 | Achim Rampf, Erbach | 6, 7, 19, 35, 37, 42 | Beton-Formen; Klasse 42 ausdrücklich auf Beton begrenzt |
| 302025004409 | Benjamin Jeck, Recklinghausen | 10, 20, 35 | orthopädische Kissen |
| 302026220462 | Leonard Balzer, Berlin | 7, 21, 35 | Töpferscheiben, Töpferwaren |

**Der vierte ist der Grund für diese Entscheidung:**

```
Registernummer    302025257965
Darstellung       "3D" in quadratischer Einfassung + FORMWERK mit Unterstrich
Markenform        Wort-/Bildmarke, blau/schwarz
Inhaber           Christian Kaule, 83112 Frasdorf
Eingetragen       02.03.2026
Bestandskräftig   03.08.2026 (ohne Widerspruch)
Benutzungsschonfrist bis 02.07.2031

Klasse 07   3D-Drucker; Maschinen und Werkzeugmaschinen
Klasse 40   3D-Druckarbeiten; Anfertigung von 3D-Drucken
Klasse 42   Entwurf von 3D-Modellen für den 3D-Druck; Designdienstleistungen
```

Klasse 42 lautet wörtlich „Entwurf von 3D-Modellen für den 3D-Druck". Das
Produkt ist eine „Desktop-Anwendung zum Konstruieren, Generieren und Bearbeiten
druckbarer 3D-Modelle" (`AGENTS.md`). Das ist dieselbe Sache.

**Was für Entwarnung spräche:** Es ist eine Wort-/*Bild*marke, der Schutzumfang
ist damit enger als bei einer reinen Wortmarke. Klasse 9 — Software als Ware —
ist nicht eingetragen.

**Was dagegen spricht:** Warenähnlichkeit wird wirtschaftlich beurteilt, nicht
nach Klassennummern; eine Software zum Entwerfen von Druckmodellen liegt nah an
der Dienstleistung „Entwurf von 3D-Modellen für den 3D-Druck". Der Zusatz „3D"
ist beschreibend und tritt beim Zeichenvergleich zurück — prägend bleibt
FORMWERK. Und die Benutzungsschonfrist bis 2031 heißt: Der Inhaber muss bis
dahin keine Benutzung nachweisen, um die Marke durchzusetzen.

Dazu kommt die Lage außerhalb des Registers: `formwerk.de` gehört einem
Berliner Architektur- und Ladenbaubüro (seit 1996, Savignyplatz), `.com` und
`.eu` sind ebenfalls vergeben, und mindestens drei weitere GmbHs führen den
Namen. Eine eigene Domain war unter diesem Namen nicht zu bekommen.

**Der Zeitpunkt ist der günstigste, den es geben wird.** Nach V5 tragen
Lizenzschlüssel (`SOLIDON-1-…`), Rechnungen, EULA und Kundenbeziehungen den
Namen. Heute kostet der Wechsel einen halben Tag, weil Bauplan §37.1 alles
Namensbezogene in `app/branding.py` gebündelt hat.

---

## §2 Warum Solidon

Von lateinisch *solidum* — der feste, massive Körper.

**Solid Modeling** ist der Fachbegriff für genau das, was der Kern tut: echte
Volumenkörper rechnen statt Mesh-Hüllen zu schieben. `manifold3d` und der
OpenCASCADE-B-Rep-Kern arbeiten beide auf Solids. Der Name benennt damit die
Kerntechnologie und nicht eine Stimmung.

Klanglich sitzt er im Register der Programme, gegen die gemessen wird — Cura,
Creo, Solidon. Drei Silben, in beiden Sprachen identisch aussprechbar, keine
Umlaute, keine Stolperstelle beim Diktieren.

**Prüfstand am 07.08.2026:**

| | |
|---|---|
| DPMAregister, Wortlaut `Solidon` | **keine Treffer** — nationale Marken, Unionsmarken, internationale Marken |
| `solidon.de` | frei — und in den drei Inklusivdomains des netcup-Pakets enthalten |
| `solidon.io`, `.app`, `.studio` | frei |
| Softwareprodukt dieses Namens | keines auffindbar |

---

## §3 Was noch offen ist

* **Die Ähnlichkeitsrecherche fehlt.** Geprüft wurde der Wortlaut, nicht das
  Umfeld: Marken wie „Solido", „Solidan" oder „Solidum" könnten in den Klassen
  7, 9, 40 oder 42 existieren und relevant sein. Diese Beurteilung gehört in
  denselben Termin wie EULA, AGB und die Kleinunternehmerfrage — nach dem Fund
  bei Formwerk diesmal **vorher**, nicht nachher.
* **Eine eigene Markenanmeldung** ist erwägenswert: 290 € beim DPMA für bis zu
  drei Klassen. Bei einem Produkt, das verkauft wird, ist das keine große
  Summe gegen das Risiko, denselben Vorgang ein zweites Mal zu erleben.

---

## §4 Umfang der Umbenennung

Gemessen am 07.08.2026: 608 Vorkommen in rund 131 Dateien. Der weit
überwiegende Teil ist Prosa in Docstrings und Doku und funktional folgenlos.

| Was | Umfang |
|---|---|
| `app/branding.py` | 5 Zeilen — `APP_NAME`, `DISTRIBUTION_NAME`, `APP_ID`, `ENVIRONMENT_PREFIX`, `WEBSITE_URL` |
| `app/i18n/locales/*.json` | Suchen/Ersetzen, beide Sprachen |
| `app/core/manual.py` | Handbuchtexte |
| `app/core/activation/key.py` | Schlüsselpräfix `FORMWERK-` → `SOLIDON-` |
| `website/` und `website/en/` | 106 Stellen — fällt mit V7 zusammen, die Seiten werden ohnehin überarbeitet |
| Dateinamen | 15 Dateien: Agents, Hooks, Icon, `packaging/*`, `tools/start-formwerk.cmd` |
| Werkzeugläufe | `make_icon.py`, `make_figures.py`, `make_manual.py` — die Bilder tragen den Namen im Fenstertitel |
| Docstrings und Doku | nach und nach, kein Blocker |

Das Icon ist rein geometrisch und enthält keinen Schriftzug — es braucht keine
Gestaltungsarbeit, nur einen neuen Dateinamen.

**Voraussetzung:** `app/branding.py` muss frei sein. Am 07.08.2026 lag die
Datei in einer parallel laufenden Sitzung geändert im Baum; die Umbenennung
beginnt erst, wenn sie committet ist.

---

## §5 Folge für die Domainplanung

Die Produktseite läuft künftig unter `solidon.de`, nicht als Subdomain von
`rs-digital.org`. Das ändert nichts an der laufenden Einrichtung:
`rs-digital.org` bleibt Firmendomain und trägt die Post; der Webspace bei
netcup trägt beide. Die Anleitung in `website/README.md` gilt unverändert, nur
der Hostname wechselt.

`SUPPORT_ADDRESS` und `WEBSITE_URL` liegen damit erstmals auf verschiedenen
Domains — was `app/branding.py:35` ausdrücklich vermeiden wollte. Vor der
Umbenennung ist zu entscheiden, ob die Support-Adresse mitzieht
(`support@solidon.de`) oder ob die Firmenadresse bleibt. Beide Postfächer sind
im netcup-Paket enthalten.
