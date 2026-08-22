# Konzepte und Durchsichten

Hier liegt das **Begründungsgedächtnis** dieses Projekts: warum etwas so gebaut
wurde, was dabei gemessen und was dabei widerlegt wurde. Keines dieser
Dokumente ist eine Arbeitsliste — die steht in `ROADMAP.md`, und was verbindlich
ist, steht im Bauplan.

**Wozu das gut ist.** Wer an einer Stelle arbeitet, an der schon jemand war,
spart hier Tage: die Messwerte stehen dabei, und die zurückgenommenen
Erstannahmen stehen daneben. Gesucht wird über den Text, nicht über diese
Tabelle — die Tabelle sagt nur, **welchem** Dokument man wie weit glauben darf.

**Wie man ein Dokument liest.** Jedes trägt oben einen Kasten mit seinem Stand.
Wo der Fließtext im Präsens steht, beschreibt er seinen Stichtag und nicht
heute. Ein Messwert vom 8. August ist am 22. August nicht falsch, sondern
datiert.

**Und die Warnung, die diese Sammlung sich selbst verdient hat.** Am 22.08.2026
wurden alle Statustabellen gegen den Code nachgeprüft: Von zwölf Punkten, die
hier als offen geführt waren und in keinem Register standen, waren **sieben
längst behoben** und einer entschieden. Ein Dokument, das „offen" sagt, sagt
das über seinen Stichtag. **Offene Arbeit zählt nur, wo sie ein Kästchen im
Register von `ROADMAP.md` hat** — was hier steht, ist die Begründung, nicht der
Rückstand.

## Der Stand, Dokument für Dokument

Sortiert nach Brauchbarkeit von heute aus, nicht nach Datum: oben, was noch
gilt, unten, was nur noch erklärt.

| Dokument | Stand | Thema | Wie es dasteht |
|---|---|---|---|
| [konzept-demo-2026-10.md](konzept-demo-2026-10.md) | 12.08. | Öffentliche Demo bis 30.10.2026 | **gültig** — fachliche SSOT der Demo-Phase. Offen: CI-Artefakt, Signierung, CRA-Meldepflicht ab 11.09.2026 |
| [konzept-versionspflege-2026-08.md](konzept-versionspflege-2026-08.md) | 14.08. | Abhängigkeiten aktuell halten | **gültig** als Verfahren; §0 und §3 beschreiben den Vormittag des 14.08. und waren am Abend überholt. Offen: P5 zwischen 3.13 und 3.14. Der Nebenbefund über `trimesh<5` in `CLAUDE.md` ist erledigt |
| [konzept-slicer-uebergabe.md](konzept-slicer-uebergabe.md) | 07.08. | Druckeinstellungen setzen, bevor der Slicer sie bekommt | **gültig** — Abnahme §7 Punkt 1 und 2 erfüllt, Punkt 3 (Gewürzset als Referenz) offen |
| [oberflaechen-durchsicht-2026-08-20.md](oberflaechen-durchsicht-2026-08-20.md) | 19./20.08. | 233 Rohfunde, und was davon nicht behoben ist | **sammelt bewusst das Offene.** §5 (acht von 19 Gebieten nie gelaufen) steht seit dem 22.08. im Register |
| [konzept-organische-modellierung-2026-08.md](konzept-organische-modellierung-2026-08.md) | 13.08. | Organische Modellierung, und Regel 2 | entschieden und in P16 überführt; P16.10 offen |
| [konzept-wettbewerb-2026-08.md](konzept-wettbewerb-2026-08.md) | 11.08. | Alle Bereiche gegen das Wettbewerbsfeld | abgearbeitet; offen bleiben Sichtbarkeit und macOS, beides keine Entwicklungsaufgabe |
| [konzept-erstnutzer-2026-08.md](konzept-erstnutzer-2026-08.md) | 13./14.08. | Mit den Augen eines Anfängers | überwiegend behoben. Nach der Prüfung vom 22.08. offen: 3.1 (Verteilermenüs) und 5.9 (zwei modale Fehlerfenster), beide jetzt im Register; 4.1 ist ein Messauftrag, kein Befund |
| [konzept-agent-vertiefung.md](konzept-agent-vertiefung.md) | 08.08. | Der Agent wird Teil der Anwendung | umgesetzt und abgenommen (08./09.08.). Der Haupttext steht im Futur, weil er beim Planen so geschrieben wurde |
| [konzept-erzeugen-agent-oberflaeche-2026-08.md](konzept-erzeugen-agent-oberflaeche-2026-08.md) | 12.08. | Erzeugen, Agent, Oberfläche — gemessen statt abgeleitet | abgearbeitet. B1 (gehosteter Erzeugungsdienst) am 20.08. **entschieden: nein** |
| [konzept-meshy-hyper3d-2026-08.md](konzept-meshy-hyper3d-2026-08.md) | 12.08. | Gegen Meshy und Hyper3D Rodin | Befunde abgearbeitet, siehe Teil 10 |
| [konzept-kundensicht-2026-08.md](konzept-kundensicht-2026-08.md) | 08.08. | Zehn Bedienläufe aus Kundensicht | vollständig behoben — 2.7 (Tastenkürzel) seit der Prüfung vom 22.08. auch |
| [konzept-durchsicht-2026-08-14.md](konzept-durchsicht-2026-08-14.md) | 14.08. | Funktionen, Wörter, der kürzeste Weg zum geteilten Teil | abgearbeitet. Zwei Befunde stammen aus dem Ansehen und wären am Quelltext nie aufgefallen |
| [durchsicht-2026-08-16.md](durchsicht-2026-08-16.md) | 16.08. | Sechs Durchgänge: Code, Oberfläche, Wettbewerb | Befund, nicht Fix — bei dieser Durchsicht wurde nichts geändert |
| [konzept-live-durchsicht-2026-08.md](konzept-live-durchsicht-2026-08.md) | 05.08. | Gegen Fusion 2704 und ElegooSlicer 1.5.3.4 | abgearbeitet in vier Paketen, kein Punkt offen |
| [konzept-p15-konstruieren-und-zeigen.md](konzept-p15-konstruieren-und-zeigen.md) | 03.08. | P15 — Konstruieren und Zeigen | erledigt am 08.08.; von 22 Lücken vier begründet abgelehnt |
| [konzept-sindricad.md](konzept-sindricad.md) | 04.08. | SindriCAD als Maßstab | Konzeptvorlage; vier Bausteine daraus beschlossen und gebaut |
| [konzept-veroeffentlichung-1.0.md](konzept-veroeffentlichung-1.0.md) | 06.08. | Erste Veröffentlichung 1.0 | **überholt** durch `konzept-demo-2026-10.md`. Von 17 geprüften Aussagen über den eigenen Stand hält eine. Bleibt als Begründung der Entscheidungen lesbar |
| [konzept-bedienung.md](konzept-bedienung.md) | 04./05.08. | Bedienung, Gestaltung, Zeichnen | **überholt.** Von 15 nachgeprüften Aussagen über den Code hält eine. Wer den Zustand der Anwendung sucht, findet ihn hier nicht |
| [namensentscheidung-solidon.md](namensentscheidung-solidon.md) | 07.08. | Warum Formwerk zu Solidon wurde | erledigt, die Umbenennung ist durch. `app/branding.py` verweist hierher |

## Was hier nicht liegt

* **`../.claude/bedienkonzept-ueberblick.md` und `../.claude/bedienkonzept-funktionen.md`**
  handeln nicht von Solidon, sondern von Claude Code — davon, wie eine Sitzung
  an diesem Projekt bedienbar sein soll. Sie stehen bei den Regeln, nicht bei
  den Konzepten.
* **Die Rohfunde und Sitzungszustände** der Durchsichten liegen unter
  `.claude/.state/`. Was aus einer Durchsicht bleiben soll, steht in einem
  Dokument hier oder in `ROADMAP.md`.
* **Die Geschichte der Arbeitsliste** steht in `ROADMAP-ARCHIV.md` — dieselbe
  Gattung, aber chronologisch statt thematisch, und mit den Funden statt der
  Begründungen.
