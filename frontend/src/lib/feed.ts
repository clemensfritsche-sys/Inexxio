/**
 * ►►► **Was das ERP von React Query hält – und was ein Schreibvorgang daran ändert.** ◄◄◄
 *
 * Der Feed (`app/(erp)/erp/page.tsx`) hält jede Liste unter `['feed', <Liste>]` (Instanzen
 * und Dokumente dazu mit der Suche), die Detailansichten ihre Daten unter `[<Bereich>, …]`
 * (`lib/queries.ts` baut die Schlüssel). `lib/api.ts` meldet jede erfolgreiche Anfrage, die
 * kein GET ist, mit ihrem Pfad (`DATA_CHANGED`); `lib/use-feed.ts` invalidiert dann genau
 * die Bereiche, die `touchedBy` nennt – die EINE Stelle der Invalidierung.
 *
 * Kennt die Tabelle einen Pfad nicht, sind es **alle** Bereiche – ein neuer Endpunkt lässt
 * nichts stehen, er lädt nur mehr als nötig. Eine leere Liste ist eine Aussage: dieser Aufruf
 * ändert nichts (eine Prüfung, eine Vorschau, ein Lesen der KI).
 *
 * Ohne Imports, damit `scripts/feed.test.mjs` die Tabelle gegen die echte Quelle prüft.
 */

/** Das Ereignis, mit dem `lib/api.ts` einen Schreibvorgang meldet (`detail.path`). */
export const DATA_CHANGED = 'inexxio:data-changed';
/** Neue oder verschickte Nachrichten (Abgleich, Senden) – Verlauf, «zu tun», Personen. */
export const MESSAGES_CHANGED = 'inexxio:messages';

export const FEED_LISTS = ['people', 'companies', 'articles', 'orders', 'instances', 'documents', 'todo'] as const;
type FeedList = (typeof FEED_LISTS)[number];

/** Die Bereiche der Detailansichten – je einer ist das erste Glied ihrer Schlüssel. */
export const DETAILS = ['order', 'instance', 'article', 'articleProcess', 'stock', 'units',
  'unitOptions', 'document', 'documentsOf', 'payments', 'messages', 'senders', 'mailboxes',
  'newsletter', 'company'] as const;
export type Detail = (typeof DETAILS)[number];
type Area = FeedList | Detail;
const AREAS: readonly Area[] = [...FEED_LISTS, ...DETAILS];

/** Der Schlüssel einer Liste – zugleich das Präfix, über das sie invalidiert wird. */
export const feedKey = (list: FeedList) => ['feed', list] as const;

/** Das Präfix eines Bereichs: eine Liste des Feeds oder ein Bereich der Detailansichten. */
export function areaKey(area: Area): readonly string[] {
  return (FEED_LISTS as readonly string[]).includes(area) ? ['feed', area] : [area];
}

/** Alle Pfade der API beginnen hier; die Tabelle nennt, was danach kommt. */
const API = '/api/v1';

/**
 * Pfad (hinter `API`) → betroffene Bereiche; **der erste passende Eintrag gilt**, also das
 * Genauere zuerst. `=` am Anfang heisst «genau dieser Pfad», sonst ist es ein Präfix ganzer
 * Pfadteile (`erp/orders` trifft `erp/orders/…`, nicht `erp/ordersx`).
 */
const TOUCHES: ReadonlyArray<readonly [string, readonly Area[]]> = [
  // Prüfen, Vorschau, Lesen und Verfassen der KI legen nichts an.
  ['=erp/articles/validate', []],
  ['=erp/orders/validate', []],
  ['=erp/documents/read', []],
  ['=erp/documents/compose', []],
  ['=auth/me/email-check', []],
  // Der Abgleich der Postfächer läuft jede Minute; was er Neues bringt, meldet der Feed
  // selbst (`MESSAGES_CHANGED` → Personen und «zu tun»), ein leerer Lauf ändert nichts.
  ['=erp/messages/sync', []],
  ['auth/passkeys', []],
  ['public', []],
  // Ein Auftrag bewegt Stücke, meldet die Stückliste am Artikel, legt Papiere als
  // Dokumente an und macht Papiere fällig.
  ['erp/orders', ['orders', 'instances', 'articles', 'documents', 'todo', 'order', 'instance',
    'article', 'stock', 'units', 'unitOptions', 'document', 'documentsOf', 'payments']],
  ['erp/instances', ['instances', 'orders', 'instance', 'units', 'stock', 'unitOptions']],
  ['erp/places', ['instances', 'instance', 'units']],
  ['erp/articles', ['articles', 'article', 'stock']],
  ['erp/documents', ['documents', 'todo', 'document', 'documentsOf']],
  ['erp/attachments', ['documents', 'todo', 'document', 'documentsOf']],
  // Eine Person kann dabei eine Firma anlegen (`sites.resolve`); fehlende Angaben zählen.
  ['erp/records', ['people', 'companies', 'todo']],
  ['auth/me', ['people', 'companies', 'todo']],
  ['erp/newsletter', ['people', 'todo', 'newsletter', 'messages']],
  // Ein Postfach verbinden oder trennen setzt die Kontakt-E-Mail der Gesellschaft.
  ['erp/messages/mailboxes', ['companies', 'company', 'mailboxes', 'senders']],
  // Ein unbekannter Absender wird Person; eine Nachricht von uns schliesst Offenes.
  ['erp/messages', ['people', 'todo', 'messages']],
  ['erp/time', ['todo']],
  ['admin', ['companies', 'todo', 'company', 'documentsOf']],
];

/** Welche Bereiche ein Schreibvorgang auf `path` ändert (unbekannt → alle). */
export function touchedBy(path: string): readonly Area[] {
  const full = path.split('?')[0];
  if (!full.startsWith(`${API}/`)) return AREAS;
  const bare = full.slice(API.length + 1).replace(/\/$/, '');
  for (const [rule, areas] of TOUCHES) {
    const hit = rule.startsWith('=') ? bare === rule.slice(1)
      : bare === rule || bare.startsWith(`${rule}/`);
    if (hit) return areas;
  }
  return AREAS;
}

/** Nur die Listen des Feeds davon. */
export function feedsTouchedBy(path: string): readonly FeedList[] {
  return touchedBy(path).filter((a): a is FeedList => (FEED_LISTS as readonly string[]).includes(a));
}
