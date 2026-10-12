# Nachweise: Suche und Befehlspalette (0.6.1, Oktober 2026)

Belege zu [RM-734](../../ROADMAP.md#rm-734) und [RM-735](../../ROADMAP.md#rm-735), Konzept
[`konzept-suche-und-palette-2026-10.md`](../konzept-suche-und-palette-2026-10.md). Zahlen und
Zeilenangaben gelten für ihren Stichtag.

| Datei | Inhalt |
|---|---|
| `inventur.md` | Was am Stand `ee6b810fe` nur über die Befehlspalette erreichbar war: 273 Zeilen, je Zeile ihr Ort ohne Palette, Panelsuche gegen Palette, Tests am fallenden Code |
| `bedienlogik-suche-und-hinweis.md` | Soll-Ablauf von `bedienlogik`: Befunde F1–F5 am Ist, Entscheidungen A1–A8 (Hinweis zu den Booleschen), B1–B6 (Suchfeld statt Palette), C1–C4, Abnahmekriterien. Code und Regeln zitieren diese Kennungen |
| `oberflaechentexte-kundenwoerter.md` | Kundenwörter der drei Booleschen in sechs Sprachen, gemessene Kollisionen, Handbuchquote, der Hinweissatz je Sprache |
| `leistung-tastendruck.md` | Messung C4: Tastendruck in Palette (vorher) und Suchfeld (nachher), zwei Funde daraus, der frühe Ausstieg in `_filter` |
| `sonden/` | Die Sonden der Messung: `sonde_tastendruck.py`, `sonde_filter.py`, `taste_auswerten.py` (Aufruf im Kopf jeder Datei) |

Skripte und Rohdaten der Inventur lagen örtlich unter `F:\tmp-agenten\palette-inventur\` und
sind nicht erhalten; die Tabellen in `inventur.md` sind ihr Ergebnis, der Messweg steht dort.
