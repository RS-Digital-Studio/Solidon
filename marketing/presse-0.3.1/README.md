# Presseansprache Solidon3D 0.3.1

**Direkt zum Versand:** [`VERSAND.html`](VERSAND.html) enthält für jeden
Empfänger einen eigenen Link auf den vollständig ausgefüllten E-Mail-Entwurf.

Stand der Adressprüfung: 29.08.2026 für die Entwürfe 1–20, 31.08.2026 für
21–25; die Inhalte sind am 03.09.2026 auf 0.3.1 umgeschrieben. Die
fünfundzwanzig Entwürfe sind **nicht versandt**. Sie sind für den
Veröffentlichungstag der 0.3.1 bestimmt und dürfen erst hinausgehen, wenn
Download, Changelog und Bilder öffentlich erreichbar sind. 3Druck.com und
VoxelMatters haben Solidon3D bereits ausführlich vorgestellt; ihre Entwürfe
sind deshalb ausdrücklich als Folge-Update formuliert und wiederholen die
Erstvorstellung nicht. Alle anderen Texte erklären den für die jeweilige
Redaktion notwendigen Kontext aus sich heraus.

## Die Geschichte dieser Welle

**Bis 0.2.2 war es die eine änderbare Bohrung, ab 0.3.1 ist es das bearbeitbare
Merkmal.** Das ist der Unterschied, um den jeder Entwurf gebaut ist: Eine
STL-Datei speichert Dreiecke, keine Konstruktionshistorie. Solidon erkennt
darin Bohrungen, Zapfen, Senkungen und Kuppeln — und seit dieser Fassung lassen
sie sich verschieben, drehen, in der Größe ändern, verdoppeln und entfernen.

Der Punkt, der die Meldung von einer Funktionsliste unterscheidet, ist die
**Kennung**: Wer eine Bohrung verschließt und neu bohrt, erzeugt dieselbe
Geometrie, aber ein anderes Merkmal — jede Passung, die darauf zeigte, verliert
ihren Bezug. Beim Versetzen bleibt die Kennung erhalten. Dieser Satz steht in
fast jedem Entwurf, weil er den Nutzen erklärt, den ein Netzwerkzeug nicht hat.

Die zweite Ebene ist das Merkmalsfenster: gemessene Werte als änderbare Felder,
Vorschau schon beim Tippen, eine ganze Lochreihe in einem Zug mit einem
einzigen Schritt zum Zurücknehmen, die Normgröße einer Bohrung im Klartext und
der Abstand zweier markierter Merkmale.

Als drittes taucht in mehreren Entwürfen die **Schranke der Erkennung** auf:
Angezeigt wird nur, was ein Drucker herstellen kann. An einem heruntergeladenen
Schlauchhalter fallen dadurch 296 von 1130 Einträgen weg, die Messrauschen
waren. Das ist die Sorte Zahl, die eine Redaktion selbst nachmessen kann.

„Seit 0.1" bedeutet in den Anschreiben: Seit der ersten öffentlichen
0.1-Demo. Der Changelog dokumentiert seit 0.1.2 insgesamt **464 ausgewählte,
für Nutzer sichtbare Änderungen**: 8 + 11 + 20 + 17 + 75 + 49 + 83 + 115 + 86
Punkte bis einschließlich 0.3.1. Die Zahl ist kein Commit-Zähler und wird in
den Mails auch nicht so dargestellt.

**Die Zahl wandert, solange an der 0.3.1 gearbeitet wird**, und sie steht in
fünf Anschreiben (01, 02, 05, 09, 11).
`tests/test_changelog.py::test_the_press_drafts_count_the_same_changes`
hält beide Seiten zusammen — wer den Changelog ergänzt, bekommt einen roten
Lauf statt einer falschen Zahl in einer Mail an eine Redaktion. Erlaubt sind
genau zwei Werte: die Punkte dieser Fassung und die Summe über alle.

## Verteiler

| # | Redaktion / Kanal | Adresse | Sprache | Aufhänger | Öffentliche Quelle |
|---:|---|---|---|---|---|
| 1 | 3Druck.com | `content@3druck.com` | Deutsch | Folge-Update: aus der änderbaren Bohrung ist das bearbeitbare Merkmal geworden | [Artikel vom 23.08.2026](https://3druck.com/programme/solidon3d-desktop-software-passt-heruntergeladene-stl-dateien-ohne-cad-an-13162117/) |
| 2 | 3D-grenzenlos | `pressemitteilung@3d-grenzenlos.de` | Deutsch | Bohrungen versetzen, drehen, verdoppeln statt nur den Durchmesser ändern | [Impressum](https://www.3d-grenzenlos.de/impressum/) |
| 3 | Make Magazin | `mail@make-magazin.de` | Deutsch | Werkstattversuch: eine ganze Lochreihe in einem Zug ändern | [Tipp an die Redaktion](https://www.heise.de/make/projekt-eingabe) |
| 4 | Golem.de | `press@golem.de` | Deutsch | ein Merkmal bearbeiten, das im Dateiformat nie gespeichert war | [Impressum](https://www.golem.de/sonstiges/impressum.html) |
| 5 | t3n | `redaktion@t3n.de` | Deutsch | unabhängige Desktop-Software, Einmalkauf | [Kontakt](https://t3n.de/kontakt/) |
| 6 | Caschys Blog | `carsten.knobloch@gmail.com` | Deutsch | kurzes App-Update, Merkmale statt nur Durchmesser | [Impressum](https://stadt-bremerhaven.de/impressum/) |
| 7 | All3DP | `editors@all3dp.com` | Englisch | Fünf-Minuten-Test: Bohrung versetzen, Passung behalten | [Redaktionskontakt](https://about.all3dp.com/) |
| 8 | Fabbaloo | `info@fabbaloo.com` | Englisch | Produktmeldung: erkannte Merkmale werden bearbeitbar | [Kontakt](https://www.fabbaloo.com/contact) |
| 9 | 3D Printing Industry | `info@3dprintingindustry.com` | Englisch | Bearbeitung auf Merkmalsebene ohne Konstruktionshistorie | [Kontakt](https://3dprintingindustry.com/contact-us/) |
| 10 | 3DPrint.com | `info@3dprint.com` | Englisch | ein Merkmal bearbeiten, das die Datei nie gespeichert hat | [Kontakt](https://3dprint.com/contact-us/) |
| 11 | VoxelMatters | `info@voxelmatters.com` | Englisch | Folge-Update: nur der konkrete Zuwachs seit dem Artikel | [Artikel vom 22.08.2026](https://www.voxelmatters.com/solidon3d-turns-a-downloaded-stl-into-a-part-that-fits-without-cad/) |
| 12 | 3Dprinting.com | `service@3dprinting.com` | Englisch | gezielte Ergänzung zum Softwarevergleich 2026 | [Softwarevergleich](https://3dprinting.com/software/) |
| 13 | Hackaday | `tips@hackaday.com` | Englisch | technischer Tipp: eine Kennung, die das Versetzen überlebt | [Tipps](https://hackaday.com/submit-a-tip/) |
| 14 | Make: | `editor@make.co` | Englisch | Workshop: vier Bohrungen in einem Schritt versetzen | [Kontaktliste](https://help.make.co/hc/en-us/articles/360031219611-Contact-List) |
| 15 | TCT Magazine | `laura.griffiths@rapidnews.com` | Englisch | Datenherkunft: Merkmalskennung übersteht die Bearbeitung | [Redaktionskontakt](https://www.tctmagazine.com/talk-to-us/) |
| 16 | 3D ADEPT Media | `editor@3dadept.com` | Englisch | begrenzte KI und begrenzte Erkennung | [Kontakt](https://3dadept.com/contact-us/) |
| 17 | All Things Additive | `editorial@allthingsadditive.com` | Englisch | Merkmalsbearbeitung bis zur materialbelegten 3MF | [Redaktionskontakt](https://www.allthingsadditive.com/) |
| 18 | CNC Kitchen | `contact@cnckitchen.com` | Deutsch | bleibt eine gemessene Passung gültig, wenn die Bohrung wandert? | [Impressum](https://www.cnckitchen.com/impressum) |
| 19 | Made with Layers | `im2404@toms3d.org` | Deutsch | unabhängiger Test: vier Bohrungen in einem Zug versetzen | [Prüfrichtlinien](https://toms3d.org/review-guidelines/) |
| 20 | Maker's Muse | `sales@makersmuse.com` | Englisch | rein manueller Modelliertest; keine KI-Kampagne | [Kontakt und Ausschlüsse](https://www.makersmuse.com/contact) |
| 21 | 3Dnatives | `contact@3dnatives.com` | Englisch | vier Sprachausgaben — die App liegt in sechs Sprachen vor | [Kontaktseite mit „Press & media"](https://www.3dnatives.com/en/contact-3d-printing/) |
| 22 | Computerbase | `presse@computerbase.de` | Deutsch | Einmalkauf, offline, lokale KI — Architektur für ein Technikpublikum | [Kontaktseite, ausdrücklich für Pressemitteilungen](https://www.computerbase.de/kontakt/) |
| 23 | Drucktipps3D | `stephan@drucktipps3d.de` | Deutsch | Fünf-Minuten-Praxistest: vier Bohrungen auf einmal | [Impressum](https://www.drucktipps3d.de/impressum/) |
| 24 | OMG! Ubuntu | `contact@omgubuntu.co.uk` | Englisch | natives Linux: Flatpak und AppImage, offline, kein Konto | [Kontaktseite](https://www.omgubuntu.co.uk/contact), alternativ das [Tip-Formular](https://www.omgubuntu.co.uk/tip) |
| 25 | Italia 3D Print | `3dprint@tech-center.com` | Italienisch | vollständig italienische Oberfläche samt Handbuch | [Kontaktseite](https://www.italia3dprint.it/contatti/) |

## Geprüft, ohne eigenen Entwurf (Stand 31.08.2026)

Recherchiert und bewusst nicht aufgenommen — damit die Prüfung beim nächsten
Mal nicht von vorn beginnt:

- **Teaching Tech** — gestrichen: Die eigene Kontaktseite erklärt den Rückzug
  von YouTube und nimmt keine Anfragen mehr an.
- **Les Imprimantes 3D** (FR) — nur Kontaktformular erreichbar; ein
  französischer Pitch lässt sich bei Bedarf aus Entwurf 21 ableiten.
- **Tom's Hardware** — kein veröffentlichtes Presse-Postfach (Future-Verlag);
  ein Pitch liefe über persönliche Redaktionskontakte.
- **3D Printing Nerd** — die eigenen Seiten nennen keine E-Mail, nur Social
  und Discord; Adressen aus Drittdatenbanken genügen dem Beleg-Maßstab dieses
  Verteilers nicht.
- **Notícias3D, Impressão 3D Brasil** (PT/BR) — nur Formulare gefunden; die
  portugiesischsprachige Fachpresse ist dünn und händlerlastig.
- **Dr. Windows, 9to5Linux** — nicht abschließend geprüft (Zertifikatsfehler
  bzw. offen); OMG! Ubuntu deckt den Linux-Winkel vorerst.

## Versandhinweise

- Absender ist in jedem Entwurf `Solidon3D <marketing@solidon3d.de>`;
  `Reply-To` zeigt auf dieselbe Adresse.
- `X-Unsent: 1` kennzeichnet jede Datei als Entwurf. Keine Datei wurde an ein
  Mailprogramm oder einen Versanddienst übergeben.
- 3Druck.com und VoxelMatters werden nicht erneut mit der Produktgrundlage
  angeschrieben. Beide Nachrichten danken für den vorhandenen Artikel und
  nennen nur, was seit dem dort beschriebenen Stand hinzugekommen ist.
- Für die übrigen Empfänger ist die Mail eine eigenständige Ansprache zur
  veröffentlichten 0.3.1; sie setzt keine Erinnerung an eine frühere Nachricht
  voraus.
- 3Druck.com nennt für Inhalte inzwischen `content@3druck.com`; diese neuere
  veröffentlichte Adresse ersetzt das frühere Kontaktformular.
- Golem nennt `press@golem.de` inzwischen ausdrücklich für Pressemitteilungen;
  deshalb ersetzt sie `redaktion@golem.de` aus der ersten Welle.
- Vor dem Versand die öffentliche Downloadseite auf 0.3.1 bringen. Alle
  Entwürfe versprechen auf Anfrage ein Testpaket oder eine Prüfaufgabe, aber
  keinen noch nicht vorhandenen Vorabzugang.

## Empfohlene Reihenfolge für Reichweite

1. **Freigabe prüfen:** 0.3.1 muss auf der Downloadseite stehen; Windows,
   macOS und Linux müssen auf die genannten Dateien zeigen; deutscher und
   englischer Changelog müssen die 0.3.1 tatsächlich anzeigen.
2. **Danach alle fünfundzwanzig einzeln versenden:** zuerst die beiden belegten
   Folgekontakte 3Druck.com und VoxelMatters, anschließend die fünf Test- und
   Videokanäle All3DP, Make Magazin, CNC Kitchen, Made with Layers und Maker's
   Muse, danach die übrigen Nachrichten- und Fachredaktionen. Der Abstand dient
   nur der Kontrolle von Rückläufern, nicht einer mehrtägigen Staffelung.
3. **Genau eine Nachfrage nach vier Werktagen**, nur wenn sie etwas Neues
   mitbringt: ein gemessenes Ergebnis, ein fertiges Vergleichsbild oder der
   veröffentlichte 0.3.1-Bau. Keine zweite Nachfrage ohne neue Information.

Jede `.eml` einzeln öffnen und senden, nie alle Empfänger in eine Nachricht
setzen. Große Bilder und Pakete nicht anhängen; ein einziger, stabiler Link auf
das Pressepaket ist für Redaktionen schneller und landet seltener im Spam.
