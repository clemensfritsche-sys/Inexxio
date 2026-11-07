// @ts-check
/**
 * ►►► Die Sicherheitsrichtlinie (CSP) hat EINE Quelle: `firebase.json`. ◄◄◄
 *
 * Die Hosting-Site liefert Website und Konto/ERP aus und setzt für beide denselben
 * Content-Security-Policy-Header. Die Website legt eine strengere Richtlinie darüber (keine
 * Fremd-Skripte, keine Rahmen) – zwei Richtlinien gelten im Browser GLEICHZEITIG. Stand dort
 * eine eigene, engere Liste der Bild-Quellen, blockierte sie das Profilbild von Google im
 * gemeinsamen Kopf: im ERP erschien es, auf der Website nur die Initialen (Testnotiz #1139).
 * Darum übernimmt die Website die Bild-Quellen wörtlich aus dem Hosting-Header.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/** @returns {Record<string, string>} Direktive → Wert des globalen Hosting-Headers */
export function hostingCsp() {
  const file = resolve(process.cwd(), '../firebase.json');
  const config = JSON.parse(readFileSync(file, 'utf8'));
  /** @type {{ source: string, headers: { key: string, value: string }[] }[]} */
  const blocks = config.hosting.headers ?? [];
  const value = blocks
    .filter((b) => b.source === '**')
    .flatMap((b) => b.headers)
    .find((h) => h.key === 'Content-Security-Policy')?.value;
  if (!value) throw new Error('firebase.json: kein globaler Content-Security-Policy-Header (source «**»).');
  return Object.fromEntries(
    value.split(';').map((d) => d.trim()).filter(Boolean).map((d) => {
      const [name, ...rest] = d.split(/\s+/);
      return [name, rest.join(' ')];
    }),
  );
}
