/** Prüfpflicht-Check: zeigt das passende, bereits gerenderte Ergebnis. */
export function initInspectionCheck(): void {
  document.querySelectorAll<HTMLElement>('[data-pcheck]').forEach((root) => {
    root.hidden = false;
    const pick = (name: string) => root.querySelector<HTMLInputElement>(`input[name="${name}"]:checked`)?.value ?? '';
    const update = () => {
      const key = `${pick('pc-type')}|${pick('pc-age')}`;
      root.querySelectorAll<HTMLElement>('[data-pcheck-result]').forEach((r) => {
        r.hidden = r.dataset.pcheckResult !== key;
      });
    };
    root.addEventListener('change', update);
    update();
  });
}
