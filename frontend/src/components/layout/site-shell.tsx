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

/** Kopf und Fuss je weiterer Sprache (`website/scripts/export-shell.mjs`). */
type ShellLangs = Record<string, { locale: string; header: string; footer: string }>;

/**
 * ►►► **Konto und Anmeldung sprechen die Sprache der Seite, von der man kommt.** ◄◄◄
 *
 * Das ERP ist bewusst deutsch; Konto und Anmeldung sieht auch der Kunde. Welche Sprache, steht in
 * der Adresse – EINE Regel, nur hier: `?lang=fr` (so verlinkt die Website in jeder Sprache), sonst
 * die Sprache des Ziels `?from=/fr/…` bzw. `?from=/konto?lang=fr` (die Anmeldung), sonst Deutsch.
 *
 * Scheitert das Skript (ein unlesbares `from`), bleibt alles deutsch – nie halb.
 *
 * Ein kleines Skript im ausgelieferten HTML, gleich nach dem Kopf: es setzt `html[data-lang]`
 * (gelesen von `lib/lang.useT`) und `lang`, tauscht den Kopf, bevor er gezeichnet wird, und den
 * Fuss, sobald er gelesen ist. Nur in den Layouts von Konto und Anmeldung – das ERP trägt es nicht.
 */
export function ShellLanguage() {
  const langs = (shell as { langs?: ShellLangs }).langs ?? {};
  if (!Object.keys(langs).length) return null;
  const data = JSON.stringify(langs).replace(/</g, '\\u003c');
  const js = `(function(){var L=${data};`
    + 'function pick(s){var u=new URL(s,location.origin),c=u.searchParams.get("lang");if(L[c])return c;'
    + 'var m=/^\\/([a-z]{2})(?:\\/|$)/.exec(u.pathname);return m&&L[m[1]]?m[1]:null}'
    + 'var c=pick(location.href);if(!c){var f=new URLSearchParams(location.search).get("from");if(f)c=pick(f)}'
    + 'if(!c)return;var d=document.documentElement;d.setAttribute("data-lang",c);d.lang=L[c].locale;'
    + 'var s=document.querySelectorAll(".ix-shell");if(s[0])s[0].innerHTML=L[c].header;'
    + 'document.addEventListener("DOMContentLoaded",function(){var a=document.querySelectorAll(".ix-shell");'
    + 'if(a.length>1)a[a.length-1].innerHTML=L[c].footer})})()';
  return <script dangerouslySetInnerHTML={{ __html: js }} />;
}
