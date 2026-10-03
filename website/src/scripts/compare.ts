/** Vorher/Nachher: der Regler setzt die Trennlinie (nur eine CSS-Variable). */
export function initBeforeAfter(): void {
  document.querySelectorAll<HTMLElement>('[data-ba]').forEach((root) => {
    const stage = root.querySelector<HTMLElement>('[data-ba-stage]');
    const range = root.querySelector<HTMLInputElement>('[data-ba-range]');
    if (!stage || !range) return;
    const set = () => stage.style.setProperty('--pos', `${range.value}%`);
    range.addEventListener('input', set);
    set();
  });
}
