// Holt beim Build Telefon und E-Mail des Betreibers aus dem ERP (Testnotiz #1094).
//
// Mit `SITE_API` (z. B. https://inexxio-dev.web.app) fragt das Skript
// `GET /api/v1/public/contact?country=` und legt die Antwort in src/config/erp-contact.json
// ab – site.mjs liest sie als Vorgabe für das HTML (Suchmaschinen, ohne JavaScript). Ohne
// `SITE_API` (lokal, CI-Prüfung) wird eine alte Datei entfernt: dann gelten die Vorgaben in
// site.mjs. Ist das ERP nicht erreichbar, bricht der Build NICHT ab – zur Laufzeit tauscht
// src/scripts/contact.ts die Angaben ohnehin aus.
import { rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const OUT = resolve(process.cwd(), 'src/config/erp-contact.json');
const api = (process.env.SITE_API ?? '').replace(/\/+$/, '');

rmSync(OUT, { force: true });
if (!api) {
  console.log('erp-contact: ohne SITE_API – Vorgaben aus site.mjs.');
  process.exit(0);
}
try {
  const res = await fetch(`${api}/api/v1/public/contact?country=`, { signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const c = await res.json();
  const data = { phone: c.phone ?? null, phone_e164: c.phone_e164 ?? null, email: c.email ?? null };
  writeFileSync(OUT, `${JSON.stringify(data, null, 2)}\n`);
  console.log(`erp-contact: ${c.name || 'Betreiber'} – ${data.phone ?? 'ohne Telefon'} · ${data.email ?? 'ohne E-Mail'}`);
} catch (e) {
  console.warn(`erp-contact: ERP nicht erreichbar (${e.message}) – Vorgaben aus site.mjs.`);
}
