/* Solidon3D — das Einzige, was diese Website ohne Skript nicht kann.
 *
 * Die Sprungliste der Funktionsseite markiert den Block, der gerade gelesen
 * wird. Alles andere bleibt CSS: die Bewegung der Zeichnungen läuft über
 * scroll-gesteuerte Zeitachsen (`animation-timeline: view()`), und die
 * gehören dorthin — sie laufen im Compositor, ein Skript müsste bei jedem
 * Bildlauf rechnen.
 *
 * Ohne diese Datei bleibt die Liste eine gewöhnliche Sprungliste: jeder Link
 * springt, nichts fehlt, nichts ist unsichtbar. Wer sie blockt, verliert eine
 * Markierung und sonst nichts.
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
