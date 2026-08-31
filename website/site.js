/* Solidon3D — das Einzige, was diese Website ohne Skript nicht kann.
 *
 * Vier Dinge stehen hier, und alle sind Zugabe: die Sprungliste der
 * Funktionsseite markiert den Block, der gerade gelesen wird, der
 * Download-Kasten der Startseite zählt die Zeit bis zur Demo herunter, und
 * der Changelog zeigt die gewählte Version einzeln. Ganz unten meldet eine
 * Zeile dem eigenen Server, dass diese Seite geöffnet wurde. Alles
 * andere bleibt CSS: die Bewegung der Zeichnungen läuft über scroll-gesteuerte
 * Zeitachsen (`animation-timeline: view()`), und die gehören dorthin — sie
 * laufen im Compositor, ein Skript müsste bei jedem Bildlauf rechnen.
 *
 * Ohne diese Datei bleibt die Liste eine gewöhnliche Sprungliste, und der
 * Kasten nennt Tag und Uhrzeit im Klartext, wie er es ohnehin tut. Wer das
 * Skript blockt, verliert eine Markierung und einen Zähler — keine Aussage.
 */
(() => {
  "use strict";
  try {

    const list = document.querySelector("nav.toc");
    if (!list || !("IntersectionObserver" in window)) return;

    /* Zu jedem Block sein Listeneintrag. Fehlt das Ziel, fällt der Eintrag
       stillschweigend weg — eine Liste mit einem toten Link ist kein Grund,
       die übrigen nicht zu markieren. */
    const links = new Map();
    for (const link of list.querySelectorAll('a[href^="#"]')) {
      const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
      if (target) links.set(target, link);
    }
    if (links.size === 0) return;

    let marked = null;

    const mark = (link) => {
      if (link === marked) return;
      if (marked) marked.removeAttribute("aria-current");
      link.setAttribute("aria-current", "true");
      marked = link;
    };

    const watcher = new IntersectionObserver(
      (entries) => {
        /* Mehrere Blöcke können gleichzeitig im Band liegen. Genommen wird der
           oberste — sonst springt die Markierung beim Scrollen hin und her. */
        const seen = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (seen.length > 0) mark(links.get(seen[0].target));
      },
      /* Ein Block gilt als gelesen, sobald er das obere Viertel erreicht. Er
         füllt den Bildschirm nie ganz aus: die Blöcke sind höher als er. */
      { rootMargin: "-20% 0px -70% 0px" }
    );

    for (const target of links.keys()) watcher.observe(target);
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 16 ausgefallen —", problem);
  }
})();

/* Die Versionsauswahl des Changelogs.
 *
 * Der vollständige Inhalt steht schon im HTML. Das Skript blendet lediglich
 * alle Fassungen außer der gewählten aus und schreibt die Auswahl als
 * Sprungmarke in die Adresse. Ohne Skript hebt der ``noscript``-Block die
 * Ausblendung auf; dann stehen alle Versionen untereinander und nichts fehlt.
 */
(() => {
  "use strict";
  try {

    const picker = document.querySelector("[data-changelog-select]");
    const entries = [...document.querySelectorAll("[data-changelog-entry]")];
    const status = document.querySelector("[data-changelog-status]");
    if (!picker || entries.length === 0) return;

    const show = (version, remember) => {
      const selected = entries.find((entry) => entry.dataset.version === version);
      if (!selected) return;

      picker.value = version;
      for (const entry of entries) entry.hidden = entry !== selected;
      if (status) status.textContent = selected.dataset.announcement || version;

      if (remember && window.history?.replaceState) {
        history.replaceState(null, "", `#${selected.id}`);
      }
    };

    const fromHash = entries.find((entry) => entry.id === location.hash.slice(1));
    show(fromHash?.dataset.version || picker.value, false);

    picker.addEventListener("change", () => show(picker.value, true));
    window.addEventListener("hashchange", () => {
      const selected = entries.find((entry) => entry.id === location.hash.slice(1));
      if (selected) show(selected.dataset.version, false);
    });
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 65 ausgefallen —", problem);
  }
})();

/* Der Zähler bis zur Demo im Download-Kasten der Startseite.
 *
 * Der Zielzeitpunkt steht im Markup, nicht hier: sechs Sprachversionen
 * tragen ihn, und eine Zahl in einem gemeinsamen Skript wäre die siebte
 * Stelle, an der er sich ändern müsste. Der Rahmensatz kommt aus demselben
 * Grund von dort (`data-template`) — er ist übersetzt.
 *
 * Gelesen wird er aus `data-release` am `<body>`, derselben Angabe, aus der
 * die Umschaltung von Warten auf Laden ihren Zeitpunkt nimmt. Bis zum
 * 20.08.2026 stand er zweimal je Seite, am Zähler und am Körper, und ein
 * Test hielt beide zusammen — zwölf Stellen für einen Termin. Wer eine
 * verschob und die andere vergaß, bekam eine Seite, die den Download
 * freigibt, während daneben noch etwas herunterzählt.
 *
 * Die Einheiten formatiert `Intl`. Damit heißt es „1 Stunde" und nicht
 * „1 Stunden", und zwar in jeder Sprache, ohne dass hier eine Liste von
 * Pluralformen läge. Kann ein Browser das nicht, bleibt der Kasten so, wie
 * er ohne Skript aussieht.
 */
(() => {
  "use strict";
  try {

    const box = document.querySelector("[data-countdown]");
    if (!box) return;

    const target = Date.parse(document.body.dataset.release || "");
    if (Number.isNaN(target) || !box.dataset.template) return;

    const language = document.documentElement.lang || "de";
    let unit;
    let join;
    try {
      unit = (value, name) =>
        new Intl.NumberFormat(language, {
          style: "unit",
          unit: name,
          unitDisplay: "long",
        }).format(value);
      join = new Intl.ListFormat(language, { style: "short", type: "unit" });
      unit(1, "hour");
    } catch {
      return;
    }

    /* Wer ruhige Seiten eingestellt hat, bekommt keine Sekunden: eine Ziffer,
       die im Blickfeld einmal je Sekunde springt, ist genau die Bewegung, die
       diese Einstellung meint. Die Minute genügt — bis zum Termin sind es
       Stunden. */
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* Der Wecker steht vor `tick`, nicht dahinter: Wird die Seite **nach** dem
       Termin geladen, räumt der erste Schlag ihn sofort wieder ab — und griffe
       dabei auf eine Bindung zu, die erst zwei Zeilen später entsteht. Das ist
       kein theoretischer Fall, sondern der Normalfall ab dem Zieltag. */
    let timer = null;

    const tick = () => {
      const raw = target - Date.now();
      /* Ruhige Seiten zählen in Minuten, und zwar aufgerundet: abgerundet
         stünde die letzte Minute lang „noch 0 Minuten" da, was zugleich falsch
         aussieht und falsch ist — es ist ja noch etwas übrig. */
      const rest = calm ? Math.ceil(raw / 60000) * 60 : Math.floor(raw / 1000);
      if (raw <= 0) {
        /* Vorbei heißt weg. Was dann gilt, sagt der Kasten selbst — ein
           Zähler, der auf null stehen bleibt, behauptete etwas über einen
           Download, den er nicht kennt. */
        box.hidden = true;
        clearInterval(timer);
        return;
      }
      const days = Math.floor(rest / 86400);
      const hours = Math.floor(rest / 3600) % 24;
      const minutes = Math.floor(rest / 60) % 60;
      const seconds = rest % 60;
      const parts = [];
      if (days > 0) {
        parts.push(unit(days, "day"));
        if (hours > 0) parts.push(unit(hours, "hour"));
      } else {
        if (hours > 0) parts.push(unit(hours, "hour"));
        /* Unter einer Minute bleiben die Sekunden allein stehen. */
        if (hours > 0 || minutes > 0) parts.push(unit(minutes, "minute"));
        if (!calm) parts.push(unit(seconds, "second"));
      }
      box.textContent = box.dataset.template.replace("{rest}", join.format(parts));
      box.hidden = false;
    };

    tick();
    if (!box.hidden) timer = setInterval(tick, calm ? 30000 : 1000);
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 115 ausgefallen —", problem);
  }
})();

/* Der Wechsel vom Warten zum Laden.
 *
 * Um achtzehn Uhr blendete sich bisher nur der Zähler aus — die Überschrift
 * nannte weiter einen Termin, der vorbei war, und der Knopf bot an, Bescheid
 * zu geben, wenn da längst etwas zu laden war. Wer fünf Minuten nach dem
 * Termin kam, fand keinen Download.
 *
 * Termin und Datei stehen am `<body>`, nicht hier: sechs Sprachversionen
 * tragen beides, und eine Adresse in einem gemeinsamen Skript wäre die
 * siebte Stelle, an der sie sich ändern müsste.
 *
 * **Ohne Adresse geschieht nichts.** Das ist keine Vorsicht, sondern der
 * Zweck: Eine Seite, die um Punkt achtzehn Uhr auf eine Datei zeigt, die noch
 * nicht liegt, ist schlechter als eine, die weiter um Nachricht bittet. Wer
 * die Datei erst zehn vor sechs hochlädt, trägt die Adresse ein, und der
 * nächste Seitenaufruf schaltet um.
 */
(() => {
  "use strict";
  try {

    const page = document.body;
    const moment = Date.parse(page.dataset.release || "");
    if (Number.isNaN(moment)) return;

    /* Ob es etwas zu laden gibt, steht nicht in einem Schalter, sondern im
       Kasten selbst: Wenn dort ein Verweis auf eine Datei liegt, gibt es sie.
       Ein Schalter wäre eine zweite Wahrheit neben der ersten, und die beiden
       liefen irgendwann auseinander. Gefüllt wird der Kasten von
       tools/make_download.py. */
    const shelf = document.querySelector("[data-files]");
    const ready = Boolean(shelf && shelf.querySelector("a[href]"));

    const arrive = () => {
      /* Zwei Bedingungen, und sie sind nicht dieselbe.
       *
       * Ein Satz wie „die Demo erscheint am 20. August" wird am 21. falsch,
       * ganz gleich ob eine Datei liegt — der Termin vergeht von selbst. Ein
       * Knopf, der „Demo laden" heißt, wird dagegen erst richtig, wenn es
       * etwas zu laden gibt. Wer beides an dieselbe Bedingung hängt, bekommt
       * entweder einen toten Knopf oder einen Satz, der auf die Datei wartet.
       */
      for (const node of document.querySelectorAll("[data-past-text]")) {
        node.textContent = node.dataset.pastText;
      }
      page.dataset.past = "true";

      if (!ready) return;

      /* Erst die Verweise, dann die Texte: Ein Knopf, der schon „Demo laden"
         heißt, aber noch auf das Postfach zeigt, ist für den Bruchteil einer
         Sekunde eine Lüge. Wohin er zeigt, sagt die erste Datei im Kasten —
         auf einer Seite mit mehreren Paketen ist das die für Windows. */
      const first = shelf.querySelector("a[href]");
      for (const link of document.querySelectorAll("[data-release-href]")) {
        link.href = first.getAttribute("href");
        /* Den Dateinamen mitnehmen, nicht nur das leere Attribut: Der Verweis
           zeigt auf den Zählpunkt und wird von dort weitergeleitet, und ein
           `download` ohne Namen überließe es dem Browser, sich einen aus der
           Adresse zu bauen — die dann `count.php` heißt. */
        if (link.hasAttribute("data-release-download")) {
          link.setAttribute("download", first.getAttribute("download") || "");
        }
      }
      for (const node of document.querySelectorAll("[data-release-text]")) {
        node.textContent = node.dataset.releaseText;
      }
      for (const node of document.querySelectorAll("[data-release-hide]")) node.hidden = true;
      for (const node of document.querySelectorAll("[data-release-show]")) node.hidden = false;
      page.dataset.released = "true";
    };

    const rest = moment - Date.now();
    if (rest <= 0) {
      arrive();
      return;
    }
    /* Wer die Seite vorher offen hat, soll sie nicht neu laden müssen. Über
       dem Bereich, den ein Zeitgeber sicher trägt (gut 24 Tage), wird nicht
       gewartet — dann ist der Termin ohnehin keine Sitzung entfernt. */
    if (rest < 2 ** 31 - 1) setTimeout(arrive, rest);
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 205 ausgefallen —", problem);
  }
})();

/* Der Zählruf.
 *
 * Ohne ihn weiß niemand, ob diese Seiten gelesen werden — und die Frage ist
 * berechtigt, auch wenn die Antwort darauf sonst über Google Analytics
 * gegeben wird. Hier geht eine Zeile an den eigenen Server, mehr nicht:
 * welcher Pfad geöffnet wurde. Kein Cookie, kein Kennzeichen im Browser,
 * kein fremder Server, keine gespeicherte IP-Adresse. Was daraus wird, steht
 * in `api/count.php`.
 *
 * `sendBeacon` und nicht `fetch`: Der Ruf muss auch dann noch hinausgehen,
 * wenn der Besucher im selben Moment weiterklickt — ein gewöhnlicher Abruf
 * würde beim Seitenwechsel abgebrochen.
 *
 * Wer im Browser „nicht verfolgen" eingestellt hat, wird nicht gezählt. Das
 * kostet ein paar Prozent der Zahl und ist es wert: Eine Website, die
 * Datensparsamkeit verspricht, hält sich an eine Einstellung, die genau das
 * verlangt — auch wenn niemand es nachprüfen würde.
 *
 * Downloads zählt diese Datei nicht. Sie laufen über `api/count.php` selbst
 * und werden dort gezählt, wo sie ankommen — ein Skript, das der Besucher
 * blockt, hätte sonst die eine Zahl verschluckt, auf die es ankommt.
 */
(() => {
  "use strict";
  try {

    if (navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl) return;

    /* **Der Verweis muss mitgeschickt werden, er steht nicht im Header.**
       `sendBeacon` sendet als `Referer` die Seite, von der aus es ruft — also
       immer solidon3d.de selbst. `count.php` erkennt die eigene Adresse und
       verwirft sie, korrekterweise: Ein Sprung von Seite zu Seite ist kein
       Verweis von außen. Damit kam nie ein Verweis an, und die Liste „Woher"
       blieb leer, ohne dass etwas kaputt war. Woher der Besucher wirklich kommt,
       weiß nur `document.referrer`. */
    const body = new URLSearchParams({ p: location.pathname || "/" });
    if (document.referrer) body.append("r", document.referrer);
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/count.php", body);
    } else if (window.fetch) {
      /* Der Rückfall für alles, was `sendBeacon` nicht kennt. `keepalive`
         versucht dasselbe zu erreichen; klappt es nicht, fehlt ein Aufruf in
         der Statistik und sonst nichts. */
      fetch("/api/count.php", { method: "POST", body, keepalive: true }).catch(() => {});
    }
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 292 ausgefallen —", problem);
  }
})();

/* Ein Knopf je Plattform, und wo es mehrere Pakete gibt, führt er hierher.
 *
 * Acht Ladeknöpfe untereinander waren nicht mehr zu lesen, und sieben davon
 * gehen den Leser nichts an: Wer auf einem Mac sitzt, entscheidet nicht
 * zwischen Flatpak und AppImage. Also fragt der Dialog genau das, was offen
 * ist — und nur, wenn etwas offen ist. Windows hat ein Paket und bleibt ein
 * Knopf.
 *
 * Der Kasten kommt aus tools/make_download.py; hier steht nur das Aufmachen.
 */
/* Das Teil zum Drehen — und der Regler, der sein Maß ändert.
 *
 * **Die Drehung geschieht nur auf Geste.** Bis zum 31.08.2026 drehte sich das
 * Teil zusätzlich an der Bildlaufposition; Robert hat das zweimal abgelehnt,
 * und beim zweiten Mal ist es gestorben. Was bleibt, ist dieser Block: Ziehen
 * und Pfeiltasten — eine Antwort auf eine Absicht statt auf eine
 * Nebenwirkung.
 *
 * **Die Bilder liegen als ein Sprite übereinander**, und dieser Grund ist
 * älter als die Scroll-Drehung und überlebt sie: Ein Sheet statt
 * sechsunddreißig Dateien heißt eine Anfrage statt sechsunddreißig. Beim
 * Ziehen darf nichts nachgeladen werden, sonst stockt genau die Bewegung,
 * die der Geste folgen soll. Verschoben wird über `background-position-y`.
 *
 * **Warum keine 3D-Bibliothek.** Ein echtes Modell im Browser bräuchte
 * three.js oder model-viewer, also drei- bis sechshundert Kilobyte fremden
 * Code auf einer Seite, die genau ein eigenes Skript lädt. Eine Bilderreihe
 * sieht für den Betrachter genauso aus — er dreht ein Teil und sieht es von
 * allen Seiten —, kostet 0,25 MB und braucht diese Zeilen hier.
 *
 * **Ohne dieses Skript steht das Teil still.** Bis zum 31.08.2026 drehte es
 * sich auch beim Scrollen, über eine Zeitachse im Stylesheet; wer das Skript
 * blockte, sah immerhin das. Seit dem Ausbau ist die Geste der einzige Weg —
 * das Standbild ist der Ruhezustand, und der Hinweis unter der Bühne sagt es.
 *
 * **Der Regler ändert ein Maß, keinen Winkel**, und das ist der Unterschied
 * zwischen einem Ansichtsspielzeug und der Aussage des Produkts: Die
 * vierundzwanzig Bilder sind einzeln **gerechnet**, nicht skaliert. Man sieht
 * es an den Laufachsen — eine gedehnte Aufnahme hätte hier Ellipsen.
 *
 * **`prefers-reduced-motion` schaltet die Scroll-Drehung ab, nicht die
 * Bedienung.** Die Einstellung zielt auf das, was ohne Zutun läuft; ein
 * Regler, den jemand zieht, ist die Funktion der Seite und kein Effekt. Bis
 * zum 31.08.2026 stieg dieses Skript dort vollständig aus — gemessen mit
 * `--force-prefers-reduced-motion` blieb die Zahl am Regler stehen und das
 * Bild wechselte nicht.
 */
(() => {
  "use strict";
  try {

    const stage = document.querySelector(".turntable");
    if (!stage) return;
    const count = Number(stage.dataset.frames || 0);
    if (count < 2) return;

    /* **Hier wird nicht mehr ausgestiegen.** Bis zum 31.08.2026 stand an dieser
       Stelle ein `return` für `prefers-reduced-motion`, mit der Begründung „wer
       Bewegung abbestellt hat, bekommt keine, auch nicht auf seine Geste hin".
       Das klingt konsequent und ist falsch: Die Einstellung meint das, was
       **ohne Zutun** läuft. Gemessen kostete sie den Regler vollständig — die
       Zahl blieb stehen, das Bild wechselte nicht, der Knopf antwortete auf
       keinen Klick. Die Scroll-Drehung bleibt abgeschaltet, aber sie wird im
       Stylesheet abgeschaltet und nicht hier. */

    let frame = 0;
    let dragging = false;
    let last = 0;
    let carry = 0;

    const show = (index) => {
      frame = ((index % count) + count) % count;
      /* Die Scroll-Animation übersteuern, sobald jemand selbst dreht — sonst
         zieht die Zeitachse das Bild beim nächsten Bildlauf zurück, und die
         Geste wäre folgenlos. */
      /* `animation: none` stand hier, solange die Scroll-Zeitachse die Position
         bei jedem Bildlauf zurückzog. Seit sie draußen ist, gibt es nichts mehr
         zu übersteuern — die Zeile bleibt trotzdem, denn sie kostet nichts und
         macht die Geste unabhängig davon, was ein Stylesheet später wieder
         einführt. */
      stage.style.animation = "none";
      /* **Und das Sprite wiederherstellen, falls der Regler ein Einzelbild
         gesetzt hat.** Sonst verschiebt die nächste Zeile die Ansicht eines
         Bildes, das nur eine Kachel hoch ist — bei 88 % ist davon nichts mehr
         im Rahmen, und die Bühne steht leer da. Gefunden am gerenderten
         Aufmacher: erst am Regler gezogen, dann gedreht, und das Teil war weg.
         Ein leerer Inline-Wert lässt die Regel aus dem Stylesheet wieder
         gelten; der Dateiname steht deshalb hier nicht noch einmal. */
      stage.style.background = "";
      stage.style.backgroundPositionY = (frame / (count - 1)) * 100 + "%";
    };

    /* Wie weit man ziehen muss, damit sich das Teil um ein Bild dreht.
       Zwölf Bildpunkte: eine ganze Umdrehung passt damit in eine Bewegung von
       gut vierhundert Punkten, und das ist ungefähr die Breite, die eine Hand
       auf einem Trackpad bequem zurücklegt. */
    const STEP = 12;

    stage.addEventListener("pointerdown", (event) => {
      dragging = true;
      last = event.clientX;
      carry = 0;
      stage.classList.add("is-turning");
      /* Der Zeiger gehört ab jetzt dieser Fläche: Ohne das endet die Drehung,
         sobald die Maus den Rand überquert — und genau das tut sie beim
         Ziehen. */
      if (stage.setPointerCapture) stage.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    stage.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      carry += event.clientX - last;
      last = event.clientX;
      const steps = Math.trunc(carry / STEP);
      if (steps === 0) return;
      carry -= steps * STEP;
      show(frame - steps);
    });
    const end = () => {
      dragging = false;
      stage.classList.remove("is-turning");
    };
    stage.addEventListener("pointerup", end);
    stage.addEventListener("pointercancel", end);

    /* Und für die Tastatur, weil eine Geste, die nur die Maus kennt, die
       Hälfte der Besucher ausschließt. Die Fläche ist im Markup fokussierbar
       (`tabindex="0"`), hier kommt nur die Bewegung dazu. */
    stage.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      show(frame + (event.key === "ArrowRight" ? 1 : -1));
      event.preventDefault();
    });

    /* Der Regler. Seine Spanne steht im Markup und nicht hier — sie gehört zum
       Teil, das gerade gezeigt wird, und ein zweites Teil wäre sonst eine
       Änderung an zwei Dateien. */
    const dial = document.querySelector("[data-dial]");
    const readout = document.querySelector("[data-dial-value]");
    if (!dial || !readout) return;

    const from = Number(dial.dataset.from || 0);
    const to = Number(dial.dataset.to || 0);
    const stops = Number(dial.dataset.stops || 0);
    const pattern = dial.dataset.dial || "";
    if (!pattern || stops < 2 || to <= from) return;

    const picture = (index) => pattern.replace("{n}", String(index).padStart(2, "0"));

    /* Vorgeladen wird beim ersten Anfassen, nicht beim Laden der Seite: Wer die
       Seite nur überfliegt, soll die vierundzwanzig Bilder nicht bezahlen. */
    let ready = false;
    const preload = () => {
      if (ready) return;
      ready = true;
      for (let index = 0; index < stops; index += 1) {
        new Image().src = picture(index);
      }
    };
    dial.addEventListener("pointerdown", preload, { once: true });
    dial.addEventListener("focus", preload, { once: true });

    /* Der Hinweis nennt bei abgeschalteter Scroll-Drehung nur noch, was wirklich
       geht. Vorher war er ganz ausgeblendet, und damit erfuhr niemand, dass
       Ziehen überhaupt möglich ist. */
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const hint = document.querySelector(".turn-hint");
      if (hint && hint.dataset.calm) hint.textContent = hint.dataset.calm;
    }

    dial.addEventListener("input", () => {
      const index = Number(dial.value);
      stage.style.animation = "none";
      stage.style.background =
        'url("' + picture(index) + '") center / cover no-repeat';
      const value = from + (to - from) * (index / (stops - 1));
      /* **Das Trennzeichen kommt aus der Sprache der Seite, nicht aus einem
         festen Tausch.** `replace(".", ",")` schrieb in jeder Fassung ein
         Komma — im englischen Aufmacher stand damit „55.0 mm" als Startwert
         und „90,0 mm", sobald jemand den Regler anfasste. Zwei Schreibweisen
         in einem Feld, und die zweite war die falsche. Dieselbe Regel wie in
         der Anwendung: eine Zahl, eine Schreibweise, und sie folgt der
         Sprache. */
      readout.textContent =
        value.toLocaleString(document.documentElement.lang || "de", {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        }) + " mm";
    });
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 364 ausgefallen —", problem);
  }
})();

(() => {
  "use strict";
  try {

    for (const button of document.querySelectorAll("[data-choice]")) {
      button.addEventListener("click", () => {
        const box = document.getElementById("wahl-" + button.dataset.choice);
        if (!box) return;
        /* `showModal` und nicht `show`: Der Dialog soll den Rest der Seite
           sperren, damit Esc ihn schließt und der Fokus nicht dahinter
           entwischt. */
        if (typeof box.showModal === "function") box.showModal();
        else box.setAttribute("open", "");
      });
    }

    /* Ein Klick neben den Dialog schließt ihn. Das Ereignis trägt dann den
       Dialog selbst als Ziel — sein Inhalt liegt in Kindknoten, und die
       melden sich selbst. */
    for (const box of document.querySelectorAll("dialog.auswahl")) {
      box.addEventListener("click", (event) => {
        if (event.target === box) box.close();
      });
      /* Nach dem Klick auf ein Paket bleibt sonst ein Dialog über einer Seite
         stehen, auf der gerade ein Download läuft. */
      for (const link of box.querySelectorAll("a[href]")) {
        link.addEventListener("click", () => box.close());
      }
    }
  } catch (problem) {
    /* Ein Fehler hier darf die folgenden Bloecke nicht mitnehmen. */
    console.warn("site.js: Block ab Zeile 507 ausgefallen —", problem);
  }
})();
