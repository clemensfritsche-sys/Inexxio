/* Läuft vor dem ersten Zeichnen (klassisches Skript im <head>, ~400 Byte):
   1. markiert «JavaScript ist da»;
   2. liest den Anzeige-Cache des Kontos (Schlüssel wie in scripts/account.ts, geschrieben vom
      Konto-/ERP-Frontend auf derselben Domain) und setzt html[data-account] = «user» bzw.
      «staff» – so steht von Anfang an «Anmelden» oder das Profilmenü da, nichts springt.
      Nur Anzeige: den Zugang zu /konto und /erp prüft das ERP selbst. */
(function () {
  var d = document.documentElement;
  d.classList.add('js');
  try {
    var role = localStorage.getItem('inexxio_user_role');
    // Spiegel von frontend/src/lib/record-status.ts (isStaff) – geprüft in scripts/account.test.mjs.
    if (role) d.dataset.account = role === 'admin' || role === 'employee' ? 'staff' : 'user';
  } catch (e) { /* Speicher gesperrt – es bleibt bei «Anmelden». */ }
})();
