/**
 * ►►► Kopf und Fuss des Konto-/ERP-Bereichs SIND die der Website. ◄◄◄
 *
 * Rückmeldung 04.10.2026: «Ein Header für beides. Eine globale Funktion, Logik, Design.»
 * Bis dahin gab es einen React-Nachbau (navbar.tsx, footer.tsx) neben `Header.astro` – zwei
 * Fassungen, die auseinanderliefen (das Profilbild erschien nur an einer, #1139). Jetzt
 * übernimmt `scripts/site-shell.mjs` beim Bauen, was der Website-Build daraus gemacht hat:
 * HTML, Stylesheet (auf `.ix-shell` beschränkt) und Skript (WEBSITE_PLAN Entscheid 60). Hier
 * wird es nur eingesetzt – kein eigenes Wort, kein eigener Stil, keine eigene Logik.
 *
 * Gesetzt im Wurzel-Layout (Server-Komponente): das HTML landet im ausgelieferten Dokument,
 * nicht im JavaScript. Was das Frontend dazugibt, ist allein der Anzeige-Cache
 * (`account-sync.tsx`).
 */
import shell from '@/generated/site-shell.json';

/** Der Kopf der Website. */
export function SiteHeader() {
  return <Fragment html={shell.header} />;
}

/** Der Fuss der Website. */
export function SiteFooter() {
  return <Fragment html={shell.footer} />;
}

/**
 * Die Hülle: `display: contents` (aus dem Stylesheet) – sonst klebte der Kopf an ihr statt
 * an der Seite. `data-contact` trägt die Vorgabe des Website-Builds; das Skript tauscht sie
 * gegen die Angaben aus dem ERP (dieselbe Stelle wie auf der Website).
 */
function Fragment({ html }: { html: string }) {
  if (!html) return null;
  return <div className="ix-shell" data-contact={shell.contact || undefined} dangerouslySetInnerHTML={{ __html: html }} />;
}

/** Stylesheet und Skripte von Kopf und Fuss – im <head> des Wurzel-Layouts. */
export function SiteShellHead() {
  if (!shell.css) return null;
  return (
    <>
      <link rel="stylesheet" href={shell.css} />
      {/* Klassisch und früh wie auf der Website: setzt html[data-account] vor dem Zeichnen. */}
      {/* eslint-disable-next-line @next/next/no-sync-scripts */}
      <script src={shell.early} />
      {/* Modul-Skripte laufen ohnehin nach dem Lesen der Seite (wie defer). */}
      {/* eslint-disable-next-line @next/next/no-sync-scripts */}
      <script type="module" src={shell.module} />
    </>
  );
}
