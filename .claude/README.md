# Die `.claude/`-Ebene — was hier liegt und was davon mitreist

**Welche Datei welche Frage beantwortet**, steht in `CLAUDE.md` unter „Die
Unterlagen-Pyramide"; die Hausordnung steht in `AGENTS.md`. Hier steht nur,
was dieser Ordner enthält, **wer die Quelle ist**, wo dieselbe Sache zweimal
liegt, und **was davon im Repository landet**. Nichts davon wird hier
wiederholt — wo etwas anderswo steht, steht hier der Verweis.

## Was hier liegt

| Pfad | Enthält | Quelle oder Spiegel |
|---|---|---|
| `rules/` | Die Regeln je Gebiet. Laden über `paths:` im Frontmatter, sobald eine passende Datei angefasst wird; `description:` sagt, worum es geht, ohne die Datei zu öffnen | Quelle |
| `agents/` | Die Fachagenten als Markdown mit Frontmatter | **Quelle.** `.codex/agents/*.toml` entsteht daraus über `tools/sync_agents.py`; `tests/test_agent_mirror.py` fährt `--check` |
| `skills/` | Die Befehle (`/pruefen`, `/liefern`, …) | **Quelle.** `.agents/skills/` entsteht aus derselben Datei, ebenfalls über `tools/sync_agents.py` |
| `memory/` | Die Erfahrungen dieses Projekts, eine Datei je Thema, dazu `MEMORY.md` als Index | Quelle, **nur auf der Maschine** (`.gitignore`). Den Index schreibt `tools/memory_index.py`, die Verknüpfung aus dem Nutzerprofil `tools/link_memory.py` |
| `hooks/` | `solidon3d_hooks.py` — ein Skript für beide Editoren | Quelle. Die Einstiege stehen in `settings.json` und `.codex/hooks.json` |
| `scripts/` | `suite-getrennt.sh` — das Entwicklungstor: Kernsammlung im Standardlauf, Fensterdateien nur beim Release mit `--release`; der gesamte Prüfweg steht in `/pruefen` | Quelle |
| `.state/` | Ein Ordner je Durchsicht: Messskripte, Rohfunde, Auftragstexte, ohne festes Format. Nennt ihn nur noch `ROADMAP-ARCHIV.md`, wird er entfernt — der Stand bleibt in der Git-Historie. Ein Skript, das eine Regel, ein Werkzeug oder ein Test dauerhaft braucht, gehört nach `tools/`; bis es umgezogen ist, bleibt sein Ordner (`git grep -l .claude/.state -- tests .github` nennt die Leser). Eine Sonde, die ein Workflow auf Zeit für einen offenen Punkt fährt, bleibt bei ihrer Durchsicht, bis der Punkt schließt (`mac-netz.yml`, RM-187) | Quelle |
| `settings.json` | Rechte, Hooks, Umgebung, Plugins. Kein Eintrag fragt oder sperrt vor einem Befehl (Entscheidung Robert). Hooks, Plugins und Umgebung stehen in `.codex/hooks.json` und `.codex/config.toml` gleich; `tests/test_agent_mirror.py` hält beide Seiten gleich | Quelle |
| `launch.json` | Startprofil für das Vorschaufenster | Quelle |
| `worktrees/` | Arbeitsbäume von Prüfläufen und Agenten, ohne eigene `.venv` — die Git-Hooks suchen sie am Hauptklon | örtlich, siehe unten |
| `bedienkonzept-ueberblick.md`, `bedienkonzept-funktionen.md` | Wie die Sitzung selbst bedienbar sein soll. **Entwurf** — umgesetzt ist davon nichts; den Stand nennt je eine eigene Tabelle, nicht die letzte der Datei | Quelle |

**Wo eine Datei zweimal existiert, wird nur die Quelle bearbeitet.** Die
erzeugte Seite unter `.codex/` und `.agents/` wird nie von Hand angefasst; nach
einer Änderung läuft `tools/sync_agents.py`, sonst wird `test_agent_mirror`
rot.

## Was ins Repository gehört

**Fast alles — und das ist eine Entscheidung, keine Nachlässigkeit.** An
diesem Projekt wird auf drei Maschinen gearbeitet, und eine Durchsicht, deren
Messskripte und Rohfunde nur auf einer davon liegen, ist auf den anderen
zweien nicht fortsetzbar. Die Begründung steht ausführlich in `.gitignore`
über dem Abschnitt „Claude Code".

Ausgenommen ist, was wirklich **dieser** Maschine gehört:

| Pfad | Warum nicht |
|---|---|
| `.state/sitzungsstart-*`, `.state/letzter-testlauf*`, `.state/letzte-erinnerung*` | Marken, die die Hooks bei jedem Lauf neu schreiben — getrackt wären sie auf jeder Maschine eine andere Änderung im Baum |
| `settings.local.json` | Rechte, die jemand für seine Maschine erteilt hat |
| `memory/` | Das Repository wird zu jedem Release öffentlich, und die Erinnerungen nennen Zugangswege, Schlüsselablagen, Kundennamen und Verkaufszahlen. `tests/test_directory_docs.py` hält fest, dass keine Datei darunter versioniert ist |
| `.state/release-*/` | Protokolle eines Release-Laufs. Die Sondenordner daneben bleiben eingecheckt: Ihre Skripte kann jemand wieder fahren — ein Protokoll von sechs Megabyte trägt das nicht |
| `worktrees/` | Arbeitsbäume von Prüfläufen und Agenten. Ausgeschlossen nur über die örtliche `.git/info/exclude`, nicht über `.gitignore` |

**Im Zweifel `git ls-files .claude` fahren statt raten.**

## Was hier nicht hingehört

Vier Sorten Inhalt haben ihren Ort woanders, und jede wandert von hier weg,
wenn sie auftaucht:

| Inhalt | Wohin |
|---|---|
| Offene Arbeit, Rückstand, „noch zu tun" | `ROADMAP.md` — **und nirgends sonst.** Ein „offen" in einer Regel altert still |
| Warum etwas so gebaut wurde, Messwerte, widerlegte Annahmen | `konzepte/` mit dem Index in `konzepte/README.md` |
| Was wo liegt | Die Karte des Verzeichnisses (`<verzeichnis>/CLAUDE.md`) |
| Phasenberichte, Verifikationsstände, Datums-Marker | `ROADMAP-ARCHIV.md` und die Git-History |

Eine Regel sagt, **was einzuhalten ist**. Sobald sie anfängt zu erzählen, was
neulich gemessen wurde, gehört dieser Teil in ein Konzept — mit Datum, damit
man ihm ansieht, wie alt er ist.
