/** Ankündigungsleiste: Schliessen-Knopf zeigen und die Entscheidung merken. */
const KEY = 'ix-announce';

export function initAnnouncement(): void {
  const bar = document.querySelector<HTMLElement>('[data-announce-bar]');
  const close = bar?.querySelector<HTMLButtonElement>('[data-announce-close]');
  if (!bar || !close) return;
  const id = document.documentElement.dataset.announce ?? '';
  close.hidden = false;
  close.addEventListener('click', () => {
    document.documentElement.classList.add('announce-off');
    try {
      localStorage.setItem(KEY, id);
    } catch {
      /* Speicher gesperrt (privates Fenster) – dann bleibt sie eben beim nächsten Mal. */
    }
  });
}
