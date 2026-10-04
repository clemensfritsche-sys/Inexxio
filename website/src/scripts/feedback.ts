/**
 * Testnotizen nachladen – dasselbe Werkzeug wie im ERP (frontend/src/islands/feedback.tsx).
 *
 * Nur wenn der Build es einschaltet (`<body data-feedback>`, allein im Dev-Deploy) und nur
 * für Angemeldete (`html[data-account]` aus dem Anzeige-Cache). Ob die Sitzung gilt und was
 * jemand sehen darf, prüft das Werkzeug selbst – hier wird bloss das Skript geholt.
 */
export function initFeedback(): void {
  if (!('feedback' in document.body.dataset) || !document.documentElement.dataset.account) return;
  const s = document.createElement('script');
  s.src = '/islands/feedback.js';
  s.async = true;
  document.body.appendChild(s);
}
