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
  'unitOptions', 'document', 'documentsOf', 'payments', 'history', 'senders', 'mailboxes',
  'newsletter', 'access', 'company', 'pins', 'talks', 'recordings', 'time', 'catalog'] as const;
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
 * Genauere zuerst. **Jede Änderung steht im Log** – darum lädt jeder Schreibvorgang auch
 * den Verlauf (`history`) nach. `=` am Anfang heisst «genau dieser Pfad», sonst ist es ein Präfix ganzer
 * Pfadteile (`erp/orders` trifft `erp/orders/…`, nicht `erp/ordersx`). `*` steht für genau einen
 * Pfadteil (eine Nummer).
 */
/**
 * **Was jede Änderung am Datensatz mitnimmt**: den Verlauf (jede Änderung steht im Log) und das
 * Angeheftete – ob sich im Umfeld etwas änderte, leitet der Server aus dem Log ab.
 */
const LOGGED: readonly Area[] = ['history', 'pins'];

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
    'article', 'stock', 'units', 'unitOptions', 'document', 'documentsOf', 'payments', ...LOGGED]],
  ['erp/instances', ['instances', 'orders', 'instance', 'units', 'stock', 'unitOptions', ...LOGGED]],
  ['erp/places', ['instances', 'instance', 'units', ...LOGGED]],
  ['erp/articles', ['articles', 'article', 'stock', 'catalog', ...LOGGED]],
  ['erp/documents', ['documents', 'todo', 'document', 'documentsOf', ...LOGGED]],
  ['erp/attachments', ['documents', 'todo', 'document', 'documentsOf', ...LOGGED]],
  // Eine Person kann dabei eine Firma anlegen (`sites.resolve`); fehlende Angaben zählen.
  // Der Zugang einer Person (Passkeys zählen in der Liste der Personen).
  ['erp/records/*/passkeys', ['people', 'access', ...LOGGED]],
  ['erp/records/*/mcp', ['access', ...LOGGED]],
  ['erp/records', ['people', 'companies', 'todo', ...LOGGED]],
  ['auth/me', ['people', 'companies', 'todo', ...LOGGED]],
  ['erp/newsletter', ['people', 'todo', 'newsletter', ...LOGGED]],
  // Ein Postfach verbinden oder trennen setzt die Kontakt-E-Mail der Gesellschaft.
  ['erp/messages/mailboxes', ['companies', 'company', 'mailboxes', 'senders', ...LOGGED]],
  // Ein unbekannter Absender wird Person; eine Nachricht von uns schliesst Offenes.
  ['erp/messages', ['people', 'todo', ...LOGGED]],
  ['erp/time', ['todo', 'time', ...LOGGED]],
  ['admin', ['companies', 'todo', 'company', 'documentsOf', ...LOGGED]],
  // Phase 5 · Der Assistent: ein Handgriff kann ALLES ändern, was das ERP kann – er lädt
  // alles nach (wie ein unbekannter Pfad). Sagen, Weglegen, eine Datei ändern nur Gespräche,
  // «zu tun», «Auf einen Blick» und die Aufnahmen (gesendet ist gesendet); das Wissen neu wählen
  // nur «Auf einen Blick».
  ['=erp/assistant/handgriffe/*/run', AREAS],
  ['=erp/assistant/handgriffe/*/done', AREAS],
  ['=erp/assistant/files', []],
  ['erp/assistant/pins', ['pins']],
  ['erp/assistant', ['talks', 'todo', 'pins', 'recordings']],
  // Phase 4 · Sprache: ein Stück (alle 30 s) ändert nichts, was eine Ansicht zeigt; «weiter
  // abschreiben» bringt den Text (er geht in die Eingabe); Start und Stopp ändern die offenen
  // Aufnahmen und «zu tun».
  ['=erp/recordings/*/chunks', []],
  ['=erp/recordings/*/advance', ['todo', 'recordings']],
  ['erp/recordings', ['todo', 'recordings']],
];

/** Trifft die Regel den Pfad? (`=` genau, sonst Präfix ganzer Pfadteile; `*` = ein Pfadteil.) */
function hits(rule: string, bare: string): boolean {
  const exact = rule.startsWith('=');
  const want = (exact ? rule.slice(1) : rule).split('/');
  const have = bare.split('/');
  if (exact ? have.length !== want.length : have.length < want.length) return false;
  return want.every((part, i) => (part === '*' ? !!have[i] : part === have[i]));
}

/** Welche Bereiche ein Schreibvorgang auf `path` ändert (unbekannt → alle). */
export function touchedBy(path: string): readonly Area[] {
  const full = path.split('?')[0];
  if (!full.startsWith(`${API}/`)) return AREAS;
  const bare = full.slice(API.length + 1).replace(/\/$/, '');
  for (const [rule, areas] of TOUCHES) if (hits(rule, bare)) return areas;
  return AREAS;
}

/** Nur die Listen des Feeds davon. */
export function feedsTouchedBy(path: string): readonly FeedList[] {
  return touchedBy(path).filter((a): a is FeedList => (FEED_LISTS as readonly string[]).includes(a));
}
