/* Läuft vor dem ersten Zeichnen (klassisches Skript im <head>, gehasht, ~300 Byte):
   markiert «JavaScript ist da» und blendet eine bereits geschlossene Ankündigung aus,
   bevor sie sichtbar würde – sonst spränge der Inhalt nach oben. */
(function () {
  var d = document.documentElement;
  d.classList.add('js');
  try {
    if (d.dataset.announce && localStorage.getItem('ix-announce') === d.dataset.announce) {
      d.classList.add('announce-off');
    }
  } catch (e) { /* Speicher gesperrt – Leiste bleibt sichtbar. */ }
})();
