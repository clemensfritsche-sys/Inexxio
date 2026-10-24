/** Saison-Aktion nach dem HEUTIGEN Datum des Geräts zeigen (der Build kann Wochen alt sein). */
export function initSeasons(): void {
  const now = new Date();
  const md = `${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  document.querySelectorAll<HTMLElement>('[data-season]').forEach((el) => {
    const from = el.dataset.from ?? '';
    const to = el.dataset.to ?? '';
    const on = from <= to ? md >= from && md <= to : md >= from || md <= to;
    el.hidden = !on;
  });
}
