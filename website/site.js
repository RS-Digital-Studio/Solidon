/* Solidon3D — das Einzige, was diese Website ohne Skript nicht kann.
 *
 * Zwei Dinge stehen hier, und beide sind Zugabe: die Sprungliste der
 * Funktionsseite markiert den Block, der gerade gelesen wird, und der
 * Download-Kasten der Startseite zählt die Zeit bis zur Demo herunter. Alles
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
})();

/* Der Zähler bis zur Demo im Download-Kasten der Startseite.
 *
 * Der Zielzeitpunkt steht im Markup (`data-countdown`), nicht hier: sechs
 * Sprachfassungen tragen ihn, und eine Zahl in einem gemeinsamen Skript
 * wäre die siebte Stelle, an der er sich ändern müsste. Der Rahmensatz
 * kommt aus demselben Grund von dort (`data-template`) — er ist übersetzt.
 *
 * Die Einheiten formatiert `Intl`. Damit heißt es „1 Stunde" und nicht
 * „1 Stunden", und zwar in jeder Sprache, ohne dass hier eine Liste von
 * Pluralformen läge. Kann ein Browser das nicht, bleibt der Kasten so, wie
 * er ohne Skript aussieht.
 */
(() => {
  "use strict";

  const box = document.querySelector("[data-countdown]");
  if (!box) return;

  const target = Date.parse(box.dataset.countdown);
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
})();

/* Der Wechsel vom Warten zum Laden.
 *
 * Um achtzehn Uhr blendete sich bisher nur der Zähler aus — die Überschrift
 * nannte weiter einen Termin, der vorbei war, und der Knopf bot an, Bescheid
 * zu geben, wenn da längst etwas zu laden war. Wer fünf Minuten nach dem
 * Termin kam, fand keinen Download.
 *
 * Termin und Datei stehen am `<body>`, nicht hier: sechs Sprachfassungen
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

  const page = document.body;
  const moment = Date.parse(page.dataset.release || "");
  const file = (page.dataset.download || "").trim();
  if (Number.isNaN(moment) || !file) return;

  const arrive = () => {
    /* Erst der Knopf, dann die Texte: Ein Knopf, der schon „Demo laden"
       heißt, aber noch auf das Postfach zeigt, ist für den Bruchteil einer
       Sekunde eine Lüge. */
    for (const link of document.querySelectorAll("[data-release-href]")) {
      link.href = file;
      if (link.hasAttribute("data-release-download")) link.setAttribute("download", "");
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
})();
