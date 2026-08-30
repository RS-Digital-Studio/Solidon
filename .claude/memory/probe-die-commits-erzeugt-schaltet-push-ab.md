---
name: probe-die-commits-erzeugt-schaltet-push-ab
description: Der post-commit-Hook ist committet und läuft auch in einem Probe-Worktree — eine Messung mit echten Commits schiebt sonst Müll nach origin.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-30T18:55:49.635Z
---

Eine Probe, die **echte Commits** erzeugt, setzt `SOLIDON_KEIN_PUSH=1` — in
jedem Git-Aufruf, nicht nur im vermeintlich riskanten.

Am 30.08.2026 lief eine Hook-Probe in einem eigenen Worktree, auf einem
eigenen Zweig, mit sauberer Rückstellung. Trotzdem landeten zwei
Probe-Commits als Zweig `g17-probe` auf origin: `.githooks/post-commit` ist
**committet** und läuft deshalb in jedem Worktree, unabhängig davon, was man
dort gerade prüft. Entfernt mit `git push origin --delete g17-probe`; `main`
war nie betroffen.

**Why:** Der Worktree isoliert den *Arbeitsbaum*, nicht die *Hooks*. Wer eine
Probe für Commit-Verhalten baut, denkt an den Hook, den er prüft — und
übersieht den, der ohnehin läuft.

**How to apply:** Im Probe-Skript die Umgebung an einer Stelle setzen, nicht
je Aufruf entscheiden:

```python
subprocess.run(args, env={**os.environ, "SOLIDON_KEIN_PUSH": "1", **extra})
```

Und die Gegenprobe danach: `git ls-remote --heads origin <zweig>` muss leer
sein. Verwandt mit [[sonde-im-geteilten-baum]] (dort verändert die Messung den
Bestand, hier verlässt sie die Maschine) und
[[worktrees-enden-auf-main]] — ein Probe-Zweig auf der Gegenstelle ist
dasselbe wie ein liegengebliebener Worktree, nur sichtbar für alle drei
Maschinen.
