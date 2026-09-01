"""Legt den Zugang zur Zugriffsstatistik in ``appdata/stats-access.php`` an.

``website/api/stats.php`` zeigt, wie oft die Seiten geöffnet und die Pakete
geladen wurden. Das geht niemanden außer dem Betreiber etwas an, also liegt
die Seite hinter einer Anmeldung, und die braucht einen Passwort-Hash. Er
liegt neben dem Dokumentenstamm; selbst eine falsche Webserverregel kann ihn
damit nicht ausliefern.

Von Hand ginge das mit ``php -r`` auch, aber dort lauert eine Falle, die still
zuschlägt: Ein bcrypt-Hash beginnt mit ``$2y$`` und trägt weitere
``$``-Zeichen. Wer ihn in einer Zeichenkette mit **doppelten**
Anführungszeichen ablegt — in PHP wie in der PowerShell —, bekommt eine Datei,
in der PHP die ``$``-Teile als Variablennamen ausgewertet und durch nichts
ersetzt hat. Der Hash ist dann verstümmelt, die Anmeldung scheitert mit dem
richtigen Passwort, und nichts sagt einem, warum.

Hier passiert das nicht: Die Datei entsteht mit einfachen Anführungszeichen,
und danach wird sie wieder eingelesen und gegen das eben eingegebene Passwort
geprüft. Erst wenn das aufgeht, gilt sie als angelegt.

    .venv\\Scripts\\python.exe tools/make_stats_access.py

Das Passwort wird abgefragt, nicht als Argument übergeben — sonst stünde es in
der Befehlsgeschichte. An PHP geht es über eine Umgebungsvariable und nicht
über die Kommandozeile, denn die ist auf einem Mehrbenutzersystem für jeden
sichtbar.

Die Datei ist in ``.gitignore`` und wandert nie mit dem öffentlichen
Website-Abgleich. Der private Deploymentweg legt sie serverseitig als
``appdata/stats-access.php`` mit Rechten 0600 in einem Ordner mit 0700 ab.

"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

#: Wohin der Zugang gehört — neben, niemals unter den Dokumentenstamm.
TARGET = ROOT / "appdata" / "stats-access.php"
WEB_ROOT = ROOT / "website"

#: Wie kurz ein Passwort sein darf. Die Seite steht offen im Netz; ein
#: Passwort, das eine Wörterbuchliste in Minuten durchprobiert, ist keines.
MIN_LENGTH = 12


def find_php() -> str:
    """PHP suchen — im Pfad, sonst dort, wo winget es ablegt.

    Der winget-Alias landet erst in einer **neu geöffneten** Sitzung im Pfad.
    Wer gerade installiert hat und weiterarbeitet, findet ihn über
    ``shutil.which`` nicht, obwohl er da ist.
    """
    found = shutil.which("php")
    if found:
        return found

    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for candidate in sorted(packages.glob("PHP.PHP.*/php.exe"), reverse=True):
        return str(candidate)

    raise SystemExit(
        "PHP ist auf dieser Maschine nicht zu finden.\n"
        "  winget install --id PHP.PHP.8.4\n"
        "installiert es; danach eine neue Sitzung öffnen, sonst fehlt der Pfad."
    )


def ask_password() -> str:
    """Das Passwort, zweimal — und keines, das zu kurz ist."""
    first = getpass.getpass("Passwort für die Statistikseite: ")
    if len(first) < MIN_LENGTH:
        raise SystemExit(f"Zu kurz. Mindestens {MIN_LENGTH} Zeichen, gern mehr.")
    second = getpass.getpass("Noch einmal zur Kontrolle:       ")
    if first != second:
        raise SystemExit("Die beiden Eingaben sind nicht gleich. Nichts geändert.")
    return first


def run_php(php: str, code: str, password: str, target: Path | None = None) -> str:
    """Ein Stück PHP laufen lassen, mit dem Passwort in der Umgebung."""
    environment = dict(os.environ, SOLIDON_STATS_PASSWORD=password)
    if target is not None:
        environment["SOLIDON_STATS_FILE"] = str(target)
    done = subprocess.run(
        [php, "-r", code],
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
    )
    if done.returncode != 0:
        raise SystemExit(f"PHP kam nicht durch:\n{done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def prepare_target() -> None:
    """Prüft den privaten Zielpfad und legt seinen Elternordner geschützt an."""
    target = TARGET.resolve(strict=False)
    web_root = WEB_ROOT.resolve(strict=False)
    try:
        target.relative_to(web_root)
    except ValueError:
        pass
    else:
        raise SystemExit("Der Statistikzugang darf nicht im Dokumentenstamm liegen.")
    if TARGET.is_symlink():
        raise SystemExit("Der Statistikzugang darf kein symbolischer Verweis sein.")
    TARGET.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    TARGET.parent.chmod(0o700)


def write_private(path: Path, text: str) -> None:
    """Schreibt eine neue Datei ohne Zeitfenster mit zu weiten Rechten."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        stream.write(text)
    path.chmod(0o600)


def main() -> int:
    php = find_php()

    if TARGET.exists():
        answer = input(f"{TARGET.name} gibt es schon. Überschreiben? [j/N] ").strip().lower()
        if answer not in ("j", "ja"):
            print("Nichts geändert.")
            return 0

    prepare_target()
    password = ask_password()

    # Erzeugen und gleich hier prüfen: Ein Hash, der sich nicht gegen sein
    # eigenes Passwort verifizieren lässt, ist auf dem Server nichts wert.
    hashed = run_php(
        php,
        "$p = getenv('SOLIDON_STATS_PASSWORD');"
        "$h = password_hash($p, PASSWORD_DEFAULT);"
        "if (!password_verify($p, $h)) {"
        "  fwrite(STDERR, 'Der Hash prueft sich selbst nicht.'); exit(1);"
        "}"
        "echo $h;",
        password,
    )
    if "'" in hashed or "\\" in hashed or not hashed.startswith("$2"):
        # bcrypt kennt weder Apostroph noch Backslash. Käme dort etwas
        # anderes an, würde es die Datei zerlegen, die wir gleich schreiben.
        raise SystemExit(f"PHP hat etwas geliefert, das kein bcrypt-Hash ist: {hashed[:20]}…")

    temporary = TARGET.with_name(f".{TARGET.name}.{os.getpid()}.tmp")
    created = False
    try:
        write_private(
            temporary,
            "<?php\n"
            "\n"
            "// Der Passwort-Hash für website/api/stats.php. Angelegt von\n"
            "// tools/make_stats_access.py; von Hand geändert wird hier nichts.\n"
            "//\n"
            "// Die einfachen Anführungszeichen sind kein Geschmack: Ein\n"
            "// bcrypt-Hash trägt $-Zeichen, und in doppelten Anführungszeichen\n"
            "// würde PHP sie als Variablen deuten und wegwerfen.\n"
            "\n"
            f"return ['hash' => '{hashed}'];\n",
        )
        created = True

        # Gegenprobe vor dem atomaren Austausch: Ein alter gültiger Zugang
        # bleibt erhalten, wenn die neue Datei sich nicht selbst bestätigt.
        check = run_php(
            php,
            "$a = include getenv('SOLIDON_STATS_FILE');"
            "$h = is_array($a) ? (string) ($a['hash'] ?? '') : '';"
            "echo password_verify(getenv('SOLIDON_STATS_PASSWORD'), $h) ? 'ja' : 'nein';",
            password,
            temporary,
        )
        if check != "ja":
            raise SystemExit(
                "Der neue Statistikzugang prüft sich nicht selbst. "
                "Die bisherige Datei bleibt unverändert."
            )
        temporary.replace(TARGET)
        TARGET.chmod(0o600)
    finally:
        if created:
            temporary.unlink(missing_ok=True)

    print(f"Angelegt: {TARGET.relative_to(ROOT)}")
    print("Sie steht in .gitignore und gehört nicht in den öffentlichen Website-Abgleich.")
    print("Der private Deploymentweg legt sie serverseitig unter appdata/stats-access.php ab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
