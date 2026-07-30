---
name: liefern
description: >
  Schließt eine Arbeitseinheit ab: vollständiges Tor laufen lassen, Änderungen in
  logische Einheiten aufteilen und mit aussagekräftigen deutschen Meldungen
  committen. Nur auf ausdrückliche Anweisung.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Liefern

## 1. Tor

Erst `/pruefen`. Ist etwas rot, wird nicht committet — dann ist die Behebung
die Aufgabe, nicht der Commit. Melde den roten Lauf und halte an.

## 2. Aufteilen

`git status` und `git diff` lesen und die Änderungen in **logische Einheiten**
schneiden: ein Thema, ein Commit. Mehrere Themen werden mehrere Commits, in
einer Reihenfolge, in der jeder für sich Sinn ergibt. Keine Mega-Commits über
alles, keine Mini-Commits je Datei.

Nicht mitcommitten: `3D Drucker/` (steht in `.gitignore`), Messdaten,
Testartefakte, `.venv`. Prüfe vor dem `git add`, was tatsächlich hineinläuft —
ein `git add .` ohne Blick ist die häufigste Ursache für versehentliche
Dateien im Repository.

## 3. Meldung

Deutsch, mit echten Umlauten, im Ton dieses Projekts: eine **Aussage**, keine
Etikettierung. So klingen die bisherigen:

> Hohle Querschnitte kamen als nichts zurück
> Ein echtes Modell als Prüfstein — vier Funde
> Angeklickte Fläche setzt die Operation an, und Operationen sind änderbar

Kein `feat:`, kein `fix:`, kein Präfix. Der Betreff sagt, was jetzt anders ist.
Wenn es einen Grund gibt, den man später sucht, steht er im Rumpf — was war,
warum es falsch war, was jetzt gilt. Am Ende:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 4. Danach

Nicht pushen, außer es wurde ausdrücklich verlangt. Melde am Ende: welche
Commits entstanden sind, was bewusst uncommittet blieb und warum — und ob
`ROADMAP.md` fortzuschreiben ist, weil ein Punkt erledigt oder ein neuer Fund
aufgetaucht ist.
