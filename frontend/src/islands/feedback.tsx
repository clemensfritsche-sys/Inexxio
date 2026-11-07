/**
 * ►►► Testnotizen auf der Website – dasselbe Werkzeug, kein Nachbau. ◄◄◄
 *
 * Die Website (`website/`, Astro) ist reines HTML ohne React. Damit dort trotzdem
 * dieselben Testnotizen gehen wie im ERP, wird **dieselbe Komponente** (`FeedbackPin`)
 * mit `scripts/build-islands.mjs` zu einem eigenen Skript gebündelt
 * (`public/islands/feedback.js`). Die Website lädt es nur in der Testumgebung und nur,
 * wenn jemand angemeldet ist (`website/src/layouts/Base.astro`).
 *
 * Anmeldung und Rechte prüft das Werkzeug selbst wie im ERP (Firebase-Sitzung derselben
 * Domain, Endpunkt `/api/v1/feedback`). Die Stile kommen als `<style>` mit, auf
 * `#ix-feedback` begrenzt – die Website bleibt unberührt.
 */
import { createRoot } from 'react-dom/client';
import { FeedbackPin } from '@/components/feedback/feedback-pin';
import css from 'islands:feedback.css';

const ROOT_ID = 'ix-feedback';

if (!document.getElementById(ROOT_ID)) {
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);
  const host = document.createElement('div');
  host.id = ROOT_ID;
  document.body.appendChild(host);
  createRoot(host).render(<FeedbackPin />);
}
