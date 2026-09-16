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

* **Die Ähnlichkeitsrecherche ist am 16.09.2026 in TMview gefahren** (Anlass:
  Roberts Frage nach der Firma Solido3D). Geprüft: Wortlaut `solido`,
  `solido3d`, `solidon`, alle Ämter, dazu DE/EUIPO/WIPO in den Klassen
  7, 9, 40, 42. Die juristische Beurteilung steht weiter aus — sie gehört in
  denselben Termin wie EULA, AGB und die Kleinunternehmerfrage.

  | Fund | Amt, Nummer | Klassen | Einschätzung |
  |---|---|---|---|
  | `Solidon` | DPMA, EUIPO, WIPO | — | **keine Treffer**, unverändert seit dem 07.08.2026. Außerhalb der EU: USPTO 73062437 (Essex Solutions, Kl. 9, Wickeldraht, seit 1975), Japan, Indien — für DE/EU ohne Belang |
  | `SOLIDO3D` | Italien UIBM 2015000038456, Wortmarke, angemeldet 27.07.2015, eingetragen 01.04.2019, Inhaber „Solido3d" (IT) | 1, 2, 3, 6, **7**, 8, **9**, 10, 14, 16, 17, 20, 25, 26, 27, 28, 35, **40**, 41, **42** — jeweils die ganze Klassenüberschrift | Nur Italien. Zehnjahresfrist ab Anmeldung lief am 27.07.2025 ab; TMview zeigt keine Verlängerung, führt sie aber noch als eingetragen. **Am UIBM-Register nachprüfen** (`dati.uibm.gov.it`, aus der Sitzung nicht erreichbar). Keine deutsche, keine Unions-, keine internationale Marke dieses Namens |
  | `SOLIDO` | WIPO 1538075 (+ 1538075A), Siemens Industry Software Inc., 27.05.2020–27.05.2030, US-Priorität 06.12.2019 | 9: „Electronic Design Automation (EDA) software" | Das zeichenähnlichste eingetragene Recht: `Solidon` enthält `Solido` vollständig. Ware ist Chipdesign-Software, nicht 3D-Modellierung — Warenähnlichkeit ist die Frage für den Anwalt. Benannte Vertragsparteien (EU? DE?) in TMview nicht sichtbar, im Madrid Monitor nachsehen |
  | `Solido` | EUIPO 005014741, UWT GmbH, 2006 | 9, 37 | Füllstandsensorik — fern |
  | `Solido Concept Store` | EUIPO 018777731, 2022 | 2, 9, 12, 19, 20, 24, 27 | Einrichtung — fern |
  | `Solidoro` | DPMA 3020262307353, Dennis Jakobi, Massing, **angemeldet 05.06.2026**, noch nicht eingetragen | 9, 42 | Waren noch nicht sichtbar. Liegt zeitlich **vor** der Benutzungsaufnahme von Solidon (August 2026) — beobachten, Verzeichnis lesen, sobald veröffentlicht |
  | `SOLIDOR` | WIPO 1920662, Solidor AG, 06.03.2026 | 36, 42, 45 | Verzeichnis lesen |
  | `SOLIDOODLE` | WIPO 1215959, 2014 | 9, 17, 35, 40, 42 | abgelaufen |

  **Zur Firma Solido3D selbst:** Solido Ltd., Israel, gegründet 2000, Drucker
  SD300 (Plastic Sheet Lamination). Insolvenzverwaltung 2014
  (3dprintingindustry.com, 28.03.2014), 2015 von Fabbaloo als „Zombie"
  beschrieben; `solido3d.com` steht 2026 noch mit Copyright-Zeile, ohne datierte
  Neuigkeit, ohne Impressum, mit der Angabe „USA, China, Italien". Ein
  deutsches Unternehmenskennzeichen (§ 5 Abs. 2 MarkenG) entstünde nur durch
  Benutzung im Inland und erlischt mit ihrem Ende — bei dieser Lage schwach.
  Nächster Berührungspunkt ist nicht der Produktname, sondern die Domain:
  `solidon3d.de` gegen `solido3d.com` unterscheidet ein Buchstabe.
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

**Entschieden am 08.08.2026: sie zieht mit.** Die Domain heißt mit dem Namen
`solidon3d.de`, die Adresse `support@solidon3d.de`; `rs-digital.org` bleibt
Firmendomain und trägt die Geschäftspost. Damit stehen `SUPPORT_ADDRESS` und
`WEBSITE_URL` wieder auf demselben Namen, und zwar auf dem, der auch auf dem
Fenstertitel steht. Die Anleitung in `website/README.md` ist entsprechend neu
geschrieben — sie wird dabei kürzer, nicht länger: eine eigene Domain beim
Webspace-Anbieter braucht weder Verifizierung noch einen Eintrag in fremder
Zone.
