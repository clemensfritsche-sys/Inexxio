/**
 * **Was man gerade bearbeitet, bleibt, wo es war** (Chrome-Test: «die Seite springt»).
 *
 * Eine Handlung kann Inhalt *über* der Stelle wachsen lassen, an der man klickte (der Partner
 * erscheint im Kopf, eine Zeile kommt dazu) – dann rutscht die Stelle nach unten, und der
 * nächste Klick trifft daneben. `holdPlace(el)` merkt sich, wo `el` auf dem Schirm steht;
 * die zurückgegebene Funktion scrollt nach dem Neuzeichnen um genau die Verschiebung zurück.
 * Ist `el` nicht mehr da, tut sie nichts.
 */
export function holdPlace(el: Element | null): () => void {
  if (!el) return () => {};
  const before = el.getBoundingClientRect().top;
  return () => {
    if (!el.isConnected) return;
    const dy = el.getBoundingClientRect().top - before;
    if (Math.abs(dy) < 1) return;
    const box = scroller(el);
    if (box) box.scrollTop += dy;
    else window.scrollBy(0, dy);
  };
}

/** Zwei Bilder warten – erst dann steht das neue Layout. */
export function afterPaint(): Promise<void> {
  return new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done())));
}

/** Der nächste Vorfahr, der selbst senkrecht scrollt – sonst das Fenster (`null`). */
function scroller(el: Element): HTMLElement | null {
  for (let n = el.parentElement; n; n = n.parentElement) {
    const y = getComputedStyle(n).overflowY;
    if ((y === 'auto' || y === 'scroll') && n.scrollHeight > n.clientHeight) return n;
  }
  return null;
}
