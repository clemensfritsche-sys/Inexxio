/**
 * ►►► **Die Listen des ERP-Feeds und was ein Schreibvorgang an ihnen ändert.** ◄◄◄
 *
 * Der Feed (`app/(erp)/erp/page.tsx`) hält jede Liste als Query von React Query unter
 * `['feed', <Liste>]` (Instanzen und Dokumente dazu mit der Suche). `lib/api.ts` meldet
 * jede erfolgreiche Anfrage, die kein GET ist, mit ihrem Pfad (`DATA_CHANGED`);
 * `lib/use-feed.ts` invalidiert dann genau die Listen, die `feedsTouchedBy` nennt.
 *
 * Kennt die Tabelle einen Pfad nicht, sind es **alle** Listen – ein neuer Endpunkt lässt den
 * Feed damit nie stehen, er lädt nur mehr als nötig. Eine leere Liste ist eine Aussage:
 * dieser Aufruf ändert keine Liste des Feeds (eine Prüfung, eine Vorschau, ein Lesen der KI).
 *
 * Ohne Imports, damit `scripts/feed.test.mjs` die Tabelle gegen die echte Quelle prüft.
 */

/** Das Ereignis, mit dem `lib/api.ts` einen Schreibvorgang meldet (`detail.path`). */
export const DATA_CHANGED = 'inexxio:data-changed';

export const FEED_LISTS = ['people', 'companies', 'articles', 'orders', 'instances', 'documents', 'todo'] as const;
type FeedList = (typeof FEED_LISTS)[number];

/** Der Schlüssel einer Liste – zugleich das Präfix, über das sie invalidiert wird. */
export const feedKey = (list: FeedList) => ['feed', list] as const;

/** Alle Pfade der API beginnen hier; die Tabelle nennt, was danach kommt. */
const API = '/api/v1';

/**
 * Pfad (hinter `API`) → betroffene Listen; **der erste passende Eintrag gilt**, also das
 * Genauere zuerst. `=` am Anfang heisst «genau dieser Pfad», sonst ist es ein Präfix ganzer
 * Pfadteile (`erp/orders` trifft `erp/orders/…`, nicht `erp/ordersx`).
 */
const TOUCHES: ReadonlyArray<readonly [string, readonly FeedList[]]> = [
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
  ['erp/orders', ['orders', 'instances', 'articles', 'documents', 'todo']],
  ['erp/instances', ['instances', 'orders']],
  ['erp/places', ['instances']],
  ['erp/articles', ['articles']],
  ['erp/documents', ['documents', 'todo']],
  ['erp/attachments', ['documents', 'todo']],
  // Eine Person kann dabei eine Firma anlegen (`sites.resolve`); fehlende Angaben zählen.
  ['erp/records', ['people', 'companies', 'todo']],
  ['auth/me', ['people', 'companies', 'todo']],
  ['erp/newsletter', ['people']],
  // Ein unbekannter Absender wird Person; eine Nachricht von uns schliesst Offenes.
  ['erp/messages', ['people', 'todo']],
  ['erp/time', ['todo']],
  ['admin', ['companies', 'todo']],
];

/** Welche Listen ein Schreibvorgang auf `path` ändert (unbekannt → alle). */
export function feedsTouchedBy(path: string): readonly FeedList[] {
  const full = path.split('?')[0];
  if (!full.startsWith(`${API}/`)) return FEED_LISTS;
  const bare = full.slice(API.length + 1).replace(/\/$/, '');
  for (const [rule, lists] of TOUCHES) {
    const hit = rule.startsWith('=') ? bare === rule.slice(1)
      : bare === rule || bare.startsWith(`${rule}/`);
    if (hit) return lists;
  }
  return FEED_LISTS;
}
