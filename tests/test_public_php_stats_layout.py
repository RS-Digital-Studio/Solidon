"""Die Statistikseite stellt zuerst, was der Betreiber zuerst wissen will.

Oben stehen die Warnungen, dann die letzten sieben Tage als vier gleich gebaute
Karten — Downloads, Besuche, Update-Prüfungen, Seitenaufrufe — und die
Versionen derselben Woche; darunter die Sätze, die nicht schon als Zahl in
einer Karte stehen. Jeder Teil nennt seinen Zeitraum. Lange Ranglisten zeigen
ihre ersten Zeilen und klappen den Rest auf. Die JSON-Ausgabe bleibt dabei,
wie Skripte sie lesen.

Herausgelöst aus ``test_public_php_security.py`` (Regel 6: keine neue
Definition in einer Datei über 2 000 Zeilen); Prüfserver und Zählzeilen von
dort.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.helpers import php_server
from tests.test_public_php_security import (
    display_today,
    stats_request,
    stats_row,
    stats_test_access,
    write_stats_rows,
)

API = Path(__file__).resolve().parent.parent / "website" / "api"

#: Neun Versionen, die neueste zuerst — zwei mehr, als die Tabelle „Je Version“
#: offen zeigt.
VERSIONS = ["0.5.0", "0.4.4", "0.4.3", "0.4.2", "0.4.1", "0.4.0", "0.3.3", "0.3.1", "0.2.2"]

#: Update-Prüfungen der letzten sieben Tage je Version, die neueste zuerst:
#: Tage zurück → Prüfungen an diesem Tag, zusammen 100. Eine Version liegt
#: unter drei Prozent (0.6.0 mit 2) — und ist neuer als zwei der übrigen.
WEEK_ONE_SMALL = {
    "0.6.1": {0: 30, 1: 20, 2: 10},
    "0.6.0": {3: 2},
    "0.5.1": {4: 20, 5: 14},
    "0.5.0": {5: 3, 6: 1},
}

#: Dasselbe mit zwei Versionen unter drei Prozent: 0.6.0 mit 2, 0.4.4 mit 1.
WEEK_TWO_SMALL = {
    "0.6.1": {0: 30, 1: 20, 2: 10},
    "0.6.0": {3: 2},
    "0.5.1": {4: 20, 5: 13},
    "0.5.0": {5: 3, 6: 1},
    "0.4.4": {2: 1},
}

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _rows(today: datetime) -> list[dict]:
    """Zwei Wochen Zählzeilen mit einem Trend bei Besuchen und Downloads.

    Heute fünfzehn Besuche aus fünfzehn Herkünften, drei davon laden; acht bis
    dreizehn Tage zurück je zwei Besuche ohne Herkunft und ein Download. Jeden
    Tag prüft jede der neun Versionen einmal. Was der Monat zeigt, liegt auf
    heute, damit der Fall an jedem Kalendertag gleich ausgeht.
    """
    day = timedelta(days=1)
    minute = timedelta(minutes=1)
    rows = [
        stats_row(
            today + index * minute, "p", "/", f"quelle{index:02d}.example", f"aaaa{index:04d}"
        )
        for index in range(15)
    ]
    rows += [
        stats_row(
            today + (20 + index) * minute, "d", "Solidon3D-Setup-0.5.0.exe", "", f"aaaa{index:04d}"
        )
        for index in range(3)
    ]
    for days_ago in range(8, 14):
        when = today - days_ago * day
        rows += [
            stats_row(when + visit * minute, "p", "/", "", f"bb{days_ago:02d}{visit:04d}")
            for visit in range(2)
        ]
        rows.append(
            stats_row(
                when + 5 * minute, "d", "Solidon3D-Setup-0.4.4.exe", "", f"bb{days_ago:02d}0000"
            )
        )
    for days_ago in range(14):
        when = today - days_ago * day
        rows += [
            stats_row(when + (30 + index) * minute, "u", version)
            for index, version in enumerate(VERSIONS)
        ]
    return rows


def _week_rows(today: datetime, checks: dict[str, dict[int, int]]) -> list[dict]:
    """Update-Prüfungen nach ``checks``: je Version, je Tag zurück so viele."""
    rows = []
    for version, per_day in checks.items():
        for days_ago, count in per_day.items():
            when = today - timedelta(days=days_ago)
            rows += [
                stats_row(when + index * timedelta(minutes=1), "u", version)
                for index in range(count)
            ]
    return rows


def _day_label(day: datetime) -> str:
    """Ein Tag, wie die Seite ihn schreibt: „Fr 17.10.“."""
    return f"{WEEKDAYS[day.weekday()]} {day:%d.%m.}"


def _render(
    tmp_path: Path,
    rows: list[dict] | None = None,
    *,
    month: str | None = None,
    release: str = "0.5.0",
) -> tuple[str, dict]:
    """Die Seite und ihre JSON-Ausgabe zu ``rows`` (sonst ``_rows``) im Monat
    ``month`` (sonst dem heutigen); im Download-Ordner liegt von der angebotenen
    Version nur das Windows-Paket — das ergibt eine Warnung."""
    docroot = tmp_path / "website"
    shutil.copytree(API, docroot / "api")
    (docroot / "dl").mkdir()
    (docroot / "dl" / f"Solidon3D-Setup-{release}.exe").write_bytes(b"kein echtes Paket")
    (docroot / "version.json").write_text(f'{{"version": "{release}"}}', encoding="ascii")
    today = display_today()
    stats = tmp_path / "stats"
    stats.mkdir(mode=0o700)
    write_stats_rows(stats, _rows(today) if rows is None else rows)
    environment, headers = stats_test_access(tmp_path)
    shown = month or today.strftime("%Y-%m")
    with php_server(tmp_path, environment, docroot=docroot) as base:
        status, _headers, page = stats_request(f"{base}/stats.php?m={shown}", headers=headers)
        json_status, _json_headers, body = stats_request(
            f"{base}/stats.php?m={shown}&format=json", headers=headers
        )
    assert status == json_status == 200 and "</html>" in page
    return page, json.loads(body)


def _shown(fragment: str) -> str:
    """Der sichtbare Text eines HTML-Stücks, Zwischenraum wie im Browser."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def test_stats_puts_warnings_first_and_the_week_above_the_details(tmp_path: Path) -> None:
    """Warnungen vor allem anderen, dann die Woche, erst danach die Sätze.

    Jeder Befund steht einmal auf der Seite: die Warnungen im Warnblock, der
    Satz zur aktuellen und zur ältesten Version in der Versionskarte, der Rest
    unter „Was auffällt“. Die Trendsätze der Woche stehen nicht noch einmal da —
    ihre Zahlen tragen die Karten: Wert, Veränderung und der Wert davor, die
    Einstufung als ▲ oder ▼ mit Namen und Regel, nicht allein als Farbe
    (Regel 18), und nach derselben Regel wie der Trendsatz.
    """
    page, report = _render(tmp_path)
    marks = [
        '<h2 id="befunde">',
        'class="warnungen"',
        'id="jetzt"',
        'id="woche-versionen"',
        '<h3 class="zwischen">Was auffällt</h3>',
        '<h2 id="reichweite">',
    ]
    positions = [page.index(mark) for mark in marks]
    assert positions == sorted(positions), marks

    findings = report["findings"]
    warnings = [item["text"] for item in findings if item["tone"] == "warnung"]
    assert warnings, "der Fall braucht eine Warnung, sonst prüft er den Block nicht"
    block = page.split('class="warnungen"')[1].split("</section>")[0]
    assert block.count("<li>") == len(warnings)
    for text in warnings:
        assert f'<span class="ton">Achtung</span>{html.escape(text, quote=False)}' in block

    trends = {
        item["text"].split(" ")[0]: item
        for item in findings
        if item["text"].startswith(("Besuche der letzten 7 Tage", "Downloads der letzten 7 Tage"))
    }
    assert len(trends) == 2, findings
    trend_texts = [item["text"] for item in trends.values()]
    readable = html.unescape(page)
    for item in findings:
        expected = 0 if item["text"] in trend_texts else 1
        assert readable.count(item["text"]) == expected, item["text"]

    # Die Sätze zur aktuellen und zur ältesten Version stehen in der
    # Versionskarte, nicht unter „Was auffällt“.
    version_notes = [
        item["text"]
        for item in findings
        if item["text"].startswith((f"{VERSIONS[0]} ", "Älteste Version"))
    ]
    assert len(version_notes) == 2, findings
    card = html.unescape(page.split('aria-labelledby="woche-versionen"')[1].split("</article>")[0])
    listed = html.unescape(
        page.split('<h3 class="zwischen">Was auffällt</h3>')[1].split("</section>")[0]
    )
    for text in version_notes:
        assert text in card and text not in listed, text

    # Die vier Karten in der Reihenfolge der Fragen, jede mit Wert, Veränderung
    # und dem Wert der sieben Tage davor — dieselben Zahlen wie im JSON.
    week = report["now"]["windows"][0]
    top = page.split('id="jetzt"')[1].split('id="woche-versionen"')[0]
    cards = re.findall(
        r'<h3>([^<]+)</h3>\s*<p class="wert">([\d.]+)(<span class="delta.*?)</p>'
        r'\s*<p class="notiz">[^<]*davor ([\d.]+)</p>',
        top,
    )
    assert [card[0] for card in cards] == [
        "Downloads",
        "Besuche",
        "Update-Prüfungen",
        "Seitenaufrufe",
    ]
    for (_title, value, _delta, before), key in zip(cards, ["d", "visits", "u", "p"], strict=True):
        assert (int(value.replace(".", "")), int(before.replace(".", ""))) == (
            week["now"][key],
            week["before"][key],
        ), key
    # 3 Downloads gegen 6 und 15 Besuche gegen 12 sind deutlich, ebenso 15
    # Aufrufe gegen 12; je Tag jede der neun Versionen einmal, 63 gegen 63, ist
    # es nicht. Die Einstufung steht als Zeichen vor dem Vorzeichen.
    deltas = [card[2] for card in cards]
    assert [_shown(delta) for delta in deltas] == ["▼−50 %", "▲+25 %", "±0 %", "▲+25 %"]
    assert deltas[0] == (
        '<span class="delta minus" title="Deutlich weniger als im Zeitraum davor: ab 10 % '
        'Veränderung bei mindestens 3 davor"><span class="zeichen" role="img" '
        'aria-label="deutlich weniger">▼</span>−50 %</span>'
    )
    assert deltas[1] == (
        '<span class="delta plus" title="Deutlich mehr als im Zeitraum davor: ab 10 % '
        'Veränderung bei mindestens 5 davor"><span class="zeichen" role="img" '
        'aria-label="deutlich mehr">▲</span>+25 %</span>'
    )
    assert deltas[2] == '<span class="delta">±0 %</span>', "nicht eingestuft: ohne Zeichen"
    # Trendsatz und Karte stufen nach derselben Regel ein.
    assert (trends["Downloads"]["tone"], trends["Besuche"]["tone"]) == ("minus", "plus")
    # Was die Zeichen bedeuten, steht unter den Karten.
    note = _shown(top.split('<p class="fussnote">')[1].split("</p>")[0])
    assert note.startswith(
        "▲ und ▼ markieren eine deutliche Veränderung: mindestens 10 %, wenn der Zeitraum "
        "davor genug Masse hat (Downloads 3, Besuche 5, Update-Prüfungen 5, Seitenaufrufe 5)."
    ), note

    # Die Versionskarte nennt jede Version der Woche mit Zahl und Anteil.
    versions = page.split('id="woche-versionen"')[1].split("</article>")[0]
    for version in VERSIONS:
        assert f"<b>{version}</b>" in versions, version
    assert (
        'role="img" aria-label="Anteile an den Update-Prüfungen der letzten 7 Tage: 0.5.0 11 %'
        in versions
    )


def _trend_rows(today: datetime, downloads: tuple[int, int], visits: tuple[int, int]) -> list[dict]:
    """Besuche und Downloads als (davor, jetzt): davor alles am zehnten Tag zurück, jetzt
    alles heute; je Besuch ein Aufruf mit eigener Kennung, die Downloads aus denselben. Eine
    Update-Prüfung am dreizehnten Tag zurück macht den Zeitraum davor vollständig."""
    minute = timedelta(minutes=1)
    rows = [stats_row(today - timedelta(days=13), "u", "0.5.0")]
    for when, loaded, came, tag in (
        (today - timedelta(days=10), downloads[0], visits[0], "bb"),
        (today, downloads[1], visits[1], "aa"),
    ):
        assert loaded <= came, "jeder Download gehört zu einem Besuch"
        rows += [stats_row(when + i * minute, "p", "/", "", f"{tag}{i:06d}") for i in range(came)]
        rows += [
            stats_row(
                when + (100 + i) * minute, "d", "Solidon3D-Setup-0.5.0.exe", "", f"{tag}{i:06d}"
            )
            for i in range(loaded)
        ]
    return rows


@pytest.mark.parametrize(
    ("downloads", "visits", "card", "tone"),
    [
        ((10, 11), (20, 21), ("▲+10 %", "+5 %"), ("plus", "info")),
        ((2, 4), (4, 8), ("+100 %", "+100 %"), (None, None)),
    ],
    ids=["an-der-schwelle", "unter-der-masse"],
)
def test_card_and_trend_sentence_judge_alike_at_the_threshold(
    tmp_path: Path,
    downloads: tuple[int, int],
    visits: tuple[int, int],
    card: tuple[str, str],
    tone: tuple[str | None, str | None],
) -> None:
    """Karte und Trendsatz stufen nach derselben Regel ein, auch genau an ihren Grenzen.

    +10 % ist schon deutlich, +5 % nicht; unter der Masse davor (Downloads 3, Besuche 5)
    gibt es weder Zeichen noch Trendsatz. Weit über der Schwelle (−50 %, +25 %) fiele eine
    eigene Schwelle der Trendsätze zwischen 10 und 25 % nicht auf (Nachprüfung N1).
    """
    page, report = _render(tmp_path, _trend_rows(display_today(), downloads, visits))
    week = report["now"]["windows"][0]
    assert (week["before"]["d"], week["now"]["d"]) == downloads, "Voraussetzung: Downloads"
    assert (week["before"]["visits"], week["now"]["visits"]) == visits, "Voraussetzung: Besuche"

    top = page.split('id="jetzt"')[1].split('id="woche-versionen"')[0]
    shown = dict(
        re.findall(r'<h3>([^<]+)</h3>\s*<p class="wert">[\d.]+(<span class="delta.*?)</p>', top)
    )
    assert (_shown(shown["Downloads"]), _shown(shown["Besuche"])) == card

    trends = {
        item["text"].split(" ")[0]: item["tone"]
        for item in report["findings"]
        if item["text"].startswith(("Besuche der letzten 7 Tage", "Downloads der letzten 7 Tage"))
    }
    assert (trends.get("Downloads"), trends.get("Besuche")) == tone, trends


def test_stats_names_the_period_of_each_part_at_a_glance(tmp_path: Path) -> None:
    """„Auf einen Blick“ mischt zwei Zeiträume, und jeder Teil nennt seinen.

    Die Karten rechnen rollend über die letzten sieben Tage, gleich welcher
    Monat gewählt ist; die Sätze unter „Was auffällt“ rechnen über den
    gewählten Monat. Eine Zeile über dem ganzen Abschnitt sagte für die Sätze
    das Falsche: Unter „Besuche 15“ der Woche stand „3,7 % aller Besuche“ des
    Monats. Geprüft am Vormonat, dessen Sätze anders lauten als die des
    laufenden, während die Karten gleich bleiben.
    """
    today = display_today()
    current = today.strftime("%Y-%m")
    # Zwanzig Tage vor dem Ersten: sicher im Vormonat und vor beiden Wochen.
    earlier = today.replace(day=1) - timedelta(days=20)
    previous = earlier.strftime("%Y-%m")
    rows = _rows(today) + [
        stats_row(
            earlier + index * timedelta(minutes=1), "p", "/", "vormonat.example", f"cccc{index:04d}"
        )
        for index in range(3)
    ]
    pages = {}
    for month in (current, previous):
        place = tmp_path / month
        place.mkdir()
        pages[month] = _render(place, rows, month=month)

    def cards(page: str) -> str:
        return page.split('id="jetzt"')[1].split('id="woche-versionen"')[0]

    def glance(page: str) -> str:
        return page.split('<h2 id="befunde">')[1].split('<h2 id="reichweite">')[0]

    (now_page, now_report), (page, report) = pages[current], pages[previous]
    assert report["now"] == now_report["now"], "die Karten hängen nicht am gewählten Monat"
    assert cards(page) == cards(now_page)

    for month, (shown, _report) in pages.items():
        part = glance(shown)
        # Der Zeitraum der Karten steht einmal, direkt über ihnen.
        assert part.count("unabhängig vom gewählten Monat") == 1, month
        line = part.split('id="jetzt"')[0].rsplit('<p class="sub zeitraum">', 1)[1]
        assert _shown(line.split("</p>")[0]) == (
            "Die letzten 7 Tage bis heute gegen die 7 davor, dazu heute und 30 Tage — rollend "
            "über die Monatsgrenze, unabhängig vom gewählten Monat."
        ), month
        # Und „Was auffällt“ nennt den Monat, aus dem seine Sätze stammen.
        assert re.search(
            r'<h3 class="zwischen">Was auffällt</h3>\s*<p class="sub zeitraum">Im Monat '
            + re.escape(month)
            + r", wo ein Satz keinen anderen Zeitraum nennt\.</p>",
            part,
        ), month

    listed = page.split('<h3 class="zwischen">Was auffällt</h3>')[1]
    assert "Wichtigste Herkunft: vormonat.example mit 3 Besuchen (" in listed
    assert "vormonat.example" not in now_page.split('<h3 class="zwischen">Was auffällt</h3>')[1]


@pytest.mark.parametrize(
    ("checks", "bar", "legend", "rest"),
    [
        pytest.param(
            WEEK_ONE_SMALL,
            [
                ("0.6.1", 60, "0.6.1 60 %"),
                ("0.6.0", 2, "0.6.0 2 %"),
                ("0.5.1", 34, "0.5.1 34 %"),
                ("0.5.0", 4, "0.5.0 4 %"),
            ],
            ["0.6.1", "0.6.0", "0.5.1", "0.5.0"],
            "",
            id="eine-kleine-an-ihrem-platz",
        ),
        pytest.param(
            WEEK_TWO_SMALL,
            [
                ("0.6.1", 60, "0.6.1 60 %"),
                ("0.5.1", 33, "0.5.1 33 %"),
                ("0.5.0", 4, "0.5.0 4 %"),
                ("2 übrige Versionen", 3, "übrige 3 %"),
            ],
            ["0.6.1", "0.5.1", "0.5.0", "2 übrige Versionen"],
            "0.6.0: 2 Prüfungen, 2,0 % · 0.4.4: 1 Prüfung, 1,0 %",
            id="zwei-kleine-als-gruppe",
        ),
    ],
)
def test_stats_week_bar_keeps_small_versions_in_place_and_whole(
    tmp_path: Path,
    checks: dict[str, dict[int, int]],
    bar: list[tuple[str, int, str]],
    legend: list[str],
    rest: str,
) -> None:
    """Der Wochenbalken zeigt jede Prüfung der Woche, die neueste Version links.

    Versionen unter drei Prozent fasst er zu „übrige“ zusammen, rechts, mit Zahl
    und Anteil, und der Aufklapper nennt jede einzeln mit Zahl und Anteil. Ist
    es nur eine, steht sie für sich — an ihrem Platz in der Reihenfolge, nicht
    hinten angehängt. In beiden Fällen ergeben die Abschnitte zusammen alle
    Prüfungen der Woche.
    """
    today = display_today()
    page, report = _render(tmp_path, _week_rows(today, checks), release="0.6.1")
    card = page.split('aria-labelledby="woche-versionen"')[1].split("</article>")[0]

    found = re.search(r'<div class="anteil" role="img" aria-label="([^"]*)">(.*?)</div>', card)
    assert found, card
    label, inner = html.unescape(found[1]), found[2]
    sections = re.findall(
        r'<span class="v[\dx]" style="flex-grow:(\d+)" title="([^"]*)"></span>', inner
    )
    # Je Abschnitt der Name aus dem Tooltip und die Breite, von links nach rechts.
    assert [(html.unescape(title).split(":")[0], int(grow)) for grow, title in sections] == [
        (name, count) for name, count, _part in bar
    ]
    assert label == "Anteile an den Update-Prüfungen der letzten 7 Tage: " + ", ".join(
        part for _name, _count, part in bar
    )
    week_total = sum(life["last_7_days"] for life in report["usage"]["lifecycle"])
    assert sum(int(grow) for grow, _title in sections) == week_total == 100

    entries = re.findall(r"<li><span class=\"farbe v[\dx]\"></span><b>([^<]+)</b>", card)
    assert entries == legend
    if rest:
        group = card.split("<b>2 übrige Versionen</b>")[1].split("</li>")[0]
        assert '<span class="zahlwerte">3 Prüfungen · 3 %</span>' in group
        details = card.split("<details><summary>Die übrigen Versionen einzeln</summary>")[1]
        assert f'<p class="sub">{rest}</p>' in details.split("</details>")[0]
    else:
        assert "übrige" not in _shown(card)


def test_stats_names_active_days_and_strongest_day_per_version(tmp_path: Path) -> None:
    """„Je Version“ nennt den stärksten Tag und an wie vielen Tagen eine
    Version sich gemeldet hat — beides stand vor dem Umbau in eigenen Spalten
    und steht weiter auf der Seite, nicht nur im JSON."""
    today = display_today()
    page, _report = _render(tmp_path, _week_rows(today, WEEK_TWO_SMALL), release="0.6.1")
    table = page.split('<h3 id="versionen">Je Version</h3>')[1].split("</article>")[0]
    cells = {}
    for row in re.findall(r"<tr>(.*?)</tr>", table):
        values = re.findall(r"<td[^>]*>(.*?)</td>", row)
        if values:
            cells[_shown(values[0]).removesuffix("aktuell")] = values[-2:]
    assert set(cells) == set(WEEK_TWO_SMALL)
    for version, per_day in WEEK_TWO_SMALL.items():
        # Der stärkste Tag ist der mit den meisten Prüfungen, zuletzt der
        # jüngste mit einer; die Daten sind so gebaut, dass beides eindeutig ist.
        strongest = max(per_day, key=lambda days_ago: per_day[days_ago])
        last = min(per_day)
        days = len(per_day)
        expected_last = "heute" if last == 0 else _day_label(today - timedelta(days=last))
        assert cells[version] == [
            f'{_day_label(today - timedelta(days=strongest))} <span class="leer">'
            f"({per_day[strongest]})</span>",
            f"{expected_last}<small>an {days} {'Tag' if days == 1 else 'Tagen'}</small>",
        ], version


def test_stats_folds_long_tables_behind_their_first_rows(tmp_path: Path) -> None:
    """Lange Tabellen zeigen ihre ersten Zeilen und klappen den Rest auf.

    Sechzehn Herkünfte (fünfzehn Hosts und „direkt“) zeigen zehn, neun
    Versionen die sieben farbigen; die Tabelle der Versionen Tag für Tag ist
    Rohstoff und steht ganz hinter einem geschlossenen Aufklapper. Gezählt
    wird an den Zeilen, damit eine offene zweite Tabelle nicht durchrutscht.
    """
    page, _report = _render(tmp_path)

    sources = page.split("<h3>Woher</h3>")[1].split("</article>")[0]
    shown, folded = sources.split("<details>")
    assert shown.count("<tr>") == 1 + 10, "Kopf und zehn Zeilen"
    assert "<summary>6 weitere Herkünfte</summary>" in folded
    assert folded.count("<tr>") == 6, "der Rest ohne zweiten Kopf"

    lifecycle = page.split('<h3 id="versionen">Je Version</h3>')[1].split("</article>")[0]
    shown, folded, _meaning = lifecycle.split("<details>")
    assert shown.count("<tr>") == 1 + 7
    assert "<summary>2 ältere Versionen</summary>" in folded and folded.count("<tr>") == 2

    daily = page.split("<h3>Versionen Tag für Tag</h3>")[1].split("</article>")[0]
    assert "<details>" in daily and "<details open" not in daily


def test_stats_json_keeps_every_key_scripts_read(tmp_path: Path) -> None:
    """Die Umgestaltung ändert die Seite, nicht die JSON-Ausgabe.

    Skripte lesen ``?format=json``; jeder Schlüssel, den die Ausgabe vor dem
    Umbau trug, steht weiter darin. Neue Schlüssel dürfen dazukommen, auch an
    einem Befund — er trägt mindestens Ton und Text.
    """
    _page, report = _render(tmp_path)
    counts = {"p", "d", "u", "visits", "home", "switched"}
    contract = {
        "": (
            report,
            {
                "month",
                "zone",
                "today",
                "complete",
                "months_available",
                "findings",
                "now",
                "reach",
                "conversion",
                "usage",
            },
        ),
        "now": (report["now"], {"complete", "coverage_from", "today", "windows"}),
        "now.today": (report["now"]["today"], counts),
        "window": (report["now"]["windows"][0], {"days", "from", "to", "now", "before"}),
        "window.now": (report["now"]["windows"][0]["now"], counts),
        "reach": (
            report["reach"],
            {
                "pages",
                "visits",
                "pages_per_visit",
                "median_duration_seconds",
                "per_day",
                "months",
                "direct",
                "sources",
                "languages",
                "language_switches",
                "without_page",
                "paths",
                "unread",
                "entry_pages",
                "exit_pages",
                "depth",
                "duration",
                "by_hour",
                "by_weekday",
            },
        ),
        "reach.direct": (report["reach"]["direct"], {"visits", "pages", "downloaded", "downloads"}),
        "reach.language_switches": (
            report["reach"]["language_switches"],
            {"home_visits", "stayed", "languages"},
        ),
        "reach.paths[]": (report["reach"]["paths"][0], {"name", "count"}),
        "conversion": (
            report["conversion"],
            {
                "downloads",
                "visits_with_download",
                "visits_with_download_percent",
                "downloads_without_page",
                "platforms",
                "matrix",
                "platform_totals",
                "page_before_download",
                "files",
            },
        ),
        "conversion.matrix[]": (report["conversion"]["matrix"][0], {"version", "cells", "total"}),
        "conversion.files[]": (report["conversion"]["files"][0], {"name", "count", "bytes"}),
        "usage": (
            report["usage"],
            {
                "from",
                "to",
                "complete",
                "updates",
                "updates_per_day",
                "release",
                "release_share_percent",
                "release_share_last_7_days_percent",
                "versions",
                "version_columns",
                "versions_per_day",
                "lifecycle",
            },
        ),
        "usage.versions_per_day[]": (
            report["usage"]["versions_per_day"][0],
            {"day", "cells", "total", "new", "release_share_percent"},
        ),
        "usage.lifecycle[]": (
            report["usage"]["lifecycle"][0],
            {
                "version",
                "current",
                "published_on",
                "release_covered",
                "first_seen",
                "numbered",
                "since_data_start",
                "last_seen",
                "active_days",
                "checks",
                "share_percent",
                "last_7_days",
                "last_7_days_share_percent",
                "peak_day",
                "peak",
                "majority_from",
                "days_to_majority",
                "first_week_share_percent",
            },
        ),
    }
    for place, (value, keys) in contract.items():
        assert keys <= set(value), f"{place or 'oben'}: es fehlen {sorted(keys - set(value))}"
    assert report["findings"], "ohne Befund prüfte die letzte Zeile nichts"
    assert all({"tone", "text"} <= set(item) for item in report["findings"])
