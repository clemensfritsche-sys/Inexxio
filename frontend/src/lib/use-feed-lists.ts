'use client';

import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { feedKey } from '@/lib/feed';
import { TYPE_META } from '@/lib/erp-record';
import { articleName, orderName, organizationName, userName } from '@/lib/record-name';
import { articleStatus, isStaff, orderStatus, organizationStatus, userStatus } from '@/lib/record-status';
import { statusCfg } from '@/lib/process-status';
import { userDisplayName } from '@/lib/utils';
import type { ScanCandidate } from '@/lib/scan';
import type { StatusCfg } from '@/lib/status-tone';
import type {
  Article, CompanySettings, DocumentSummary, InstanceSummary, OrderSummary, Todo, UserProfile,
} from '@/types';

/**
 * ►►► **Die Listen des ERP-Feeds – als Queries, zusammengeführt zu EINER Zeilenfolge.** ◄◄◄
 *
 * Jede Liste ist eine Query (`lib/feed.ts`, `lib/use-feed.ts`): EINE Datenquelle je Liste,
 * nachgeladen nur, was ein Schreibvorgang betrifft, und beim Zurückkommen nach einer Pause.
 * Ein Fehler meldet sich über `meta.what` (`lib/notice`). Name, Zustand und Suchtext einer
 * Zeile kommen aus den EINEN Ableitungen (`lib/record-name`, `lib/record-status`).
 */

/** Seitengrösse des server-paginierten Instanz-Feeds. */
const INSTANCE_PAGE = 100;

/** «zu tun» je Objektnummer – die Zahl am Symbol. */
const todoByObject = (rows: Todo[]) => new Map(rows.map((r) => [r.object_id, r]));

/** Eine Seite kann sich mit der nächsten überschneiden, wenn dazwischen etwas dazukam. */
function dedupeById(rows: InstanceSummary[]): InstanceSummary[] {
  const seen = new Set<number>();
  return rows.filter((r) => (seen.has(r.id) ? false : (seen.add(r.id), true)));
}

export type Row =
  | { type: 'user'; key: string; objectId: number | null; data: UserProfile }
  | { type: 'article'; key: string; objectId: number | null; data: Article }
  | { type: 'order'; key: string; objectId: number | null; data: OrderSummary }
  | { type: 'instance'; key: string; objectId: number | null; data: InstanceSummary }
  | { type: 'organization'; key: string; objectId: number | null; data: CompanySettings }
  | { type: 'document'; key: string; objectId: number | null; data: DocumentSummary };

// Der Name eines Datensatzes kommt aus der EINEN Ableitung (`lib/record-name`) – nie steht
// hier der Typ (den sagt das Symbol). `null` = noch ohne Namen.
export function rowTitle(row: Row): string | null {
  if (row.type === 'user') return userName(row.data);
  if (row.type === 'order') return orderName(row.data);
  if (row.type === 'instance') return row.data.article_name?.trim() || null;
  if (row.type === 'organization') return organizationName(row.data);
  if (row.type === 'document') return `${row.data.art} · ${row.data.name}`;
  return articleName(row.data);
}

// Der Zustand kommt aus der EINEN Ableitung (`lib/record-status`) – genau wie der Name.
// Hier wird nur verteilt, nie gebaut: sonst läuft der Feed vom Detail weg.
export function rowStatus(row: Row): StatusCfg | null {
  if (row.type === 'user') return userStatus(row.data);
  if (row.type === 'order') return orderStatus(row.data);
  // Die Instanz ist eine Gruppe und trägt keinen Zustand – ein Wort hier wäre bei einer
  // Charge mit gemischten Stücken eine Behauptung.
  if (row.type === 'instance') return null;
  if (row.type === 'organization') return organizationStatus(row.data);
  if (row.type === 'document') return statusCfg(row.data.status);
  return articleStatus(row.data);
}

// Gesucht wird über Name + Typ-Wort + Objektnummer: «auftrag» bleibt als Suchwort nützlich,
// obwohl es nicht mehr als Bezeichnung angezeigt wird.
function rowSearchText(row: Row): string {
  const parts = [rowTitle(row) ?? '', TYPE_META[row.type].label, String(row.objectId ?? '')];
  if (row.type === 'user') parts.push(row.data.email);
  if (row.type === 'article') parts.push(row.data.size ?? '');
  return parts.join(' ').toLowerCase();
}

/**
 * **Die EINE Suchregel des Feeds.** Sie gilt für die Liste **und** für die Vorschläge im
 * Scanner – derselbe Aufruf, sonst fände die eine Suche etwas, das die andere nicht kennt.
 * `needle` kommt bereits in Kleinschreibung.
 */
export function feedMatch(row: Row, needle: string): boolean {
  return rowSearchText(row).includes(needle);
}

/** Ein Datensatz als Scanner-Vorschlag: Nummer + «Typ · Name». */
export function toCandidate(row: Row): ScanCandidate {
  const label = TYPE_META[row.type].label;
  const title = rowTitle(row);
  return { objectId: row.objectId as number, label: title ? `${label} · ${title}` : label };
}

/** Alle Zeilen, höchste Objektnummer zuerst (Zeilen ohne Nummer stabil ans Ende). */
function toRows(l: {
  companies: CompanySettings[]; users: UserProfile[]; articles: Article[]; orders: OrderSummary[];
  instances: InstanceSummary[]; documents: DocumentSummary[];
}): Row[] {
  return [
    // Jede **Firma** ist ein nummerierter ERP-Datensatz – eigene wie fremde.
    ...l.companies.map((s): Row => ({
      type: 'organization', key: `org${s.object_id}`, objectId: s.object_id ?? null, data: s,
    })),
    ...l.users.map((u): Row => ({ type: 'user', key: `u${u.id}`, objectId: u.object_id, data: u })),
    ...l.articles.map((a): Row => ({ type: 'article', key: `a${a.id}`, objectId: a.object_id, data: a })),
    ...l.orders.map((o): Row => ({ type: 'order', key: `o${o.id}`, objectId: o.object_id, data: o })),
    ...l.instances.map((i): Row => ({ type: 'instance', key: `i${i.id}`, objectId: i.object_id, data: i })),
    ...l.documents.map((d): Row => ({ type: 'document', key: `d${d.object_id}`, objectId: d.object_id, data: d })),
  ].sort((x, y) => (y.objectId ?? 0) - (x.objectId ?? 0));
}

/**
 * Die Listen für die Suche `query` (Instanzen und Dokumente sucht der Server). Firmen,
 * Dokumente und «zu tun» fragen erst, wenn die Rolle feststeht (Personal-Endpunkte).
 */
export function useFeedLists(query: string) {
  const qc = useQueryClient();
  const profile = useQuery({ queryKey: ['me'], queryFn: () => api.getMe(), staleTime: Infinity, meta: { what: 'Profil' } }).data;
  // Ins ERP kommt ohnehin nur Personal (`AuthGate staffOnly`) – `staff` sagt, dass die
  // Antwort da ist.
  const staff = !!profile && isStaff(profile.role);
  const users = useQuery({ queryKey: feedKey('people'), queryFn: () => api.getErpRecords(), meta: { what: 'Personen' } });
  const articles = useQuery({ queryKey: feedKey('articles'), queryFn: () => api.getArticles(), meta: { what: 'Artikel' } });
  const orders = useQuery({ queryKey: feedKey('orders'), queryFn: () => api.getOrders(), meta: { what: 'Aufträge' } });
  const companies = useQuery({
    queryKey: feedKey('companies'), queryFn: () => api.getCompanies(), enabled: staff, meta: { what: 'Firmen' },
  });
  const todo = useQuery({
    queryKey: feedKey('todo'), queryFn: () => api.todo(), enabled: staff, meta: { what: 'Zu tun' },
    select: todoByObject,
  });
  // Instanzen (höchste Kardinalität): seitenweise und auf dem Server durchsucht. Die letzte
  // Seite war nicht voll → es gibt nichts mehr nachzuladen (der Server nennt keine Gesamtzahl).
  const instances = useInfiniteQuery({
    queryKey: [...feedKey('instances'), query],
    queryFn: ({ pageParam }) => api.getInstances(INSTANCE_PAGE, pageParam, query),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length < INSTANCE_PAGE ? undefined : pages.reduce((n, p) => n + p.length, 0)),
    meta: { what: 'Instanzen' },
  });
  const documents = useQuery({
    queryKey: [...feedKey('documents'), query], queryFn: () => api.getDocuments(query, 200),
    enabled: staff, meta: { what: 'Dokumente' },
  });
  const instanceRows = dedupeById(instances.data?.pages.flat() ?? []);

  /** Eine Liste im Cache ändern (Antwort einer Anlage/Änderung) – derselbe Speicher. */
  const patchList = <T,>(list: 'people' | 'articles' | 'orders' | 'companies', fn: (rows: T[]) => T[]) =>
    qc.setQueryData<T[]>(feedKey(list), (rows) => fn(rows ?? []));

  return {
    profile, staff, isAdmin: profile?.role === 'admin',
    // **Kommunikation**: wer gerade arbeitet.
    me: profile?.object_id ? { object_id: profile.object_id, name: userDisplayName(profile) } : null,
    rows: toRows({
      companies: companies.data ?? [], users: users.data ?? [], articles: articles.data ?? [],
      orders: orders.data ?? [], instances: instanceRows, documents: documents.data ?? [],
    }),
    instanceCount: instanceRows.length,
    todos: todo.data ?? new Map<number, Todo>(),
    // Die Shell erscheint sofort; «Laden…» steht nur, bis die Kern-Listen geantwortet haben.
    loading: users.isPending || articles.isPending || orders.isPending,
    instancesDone: !instances.hasNextPage,
    instanceLoadingMore: instances.isFetchingNextPage,
    /** Die nächste Instanz-Seite – ein Fehler meldet sich über die Query (`meta.what`). */
    fetchMoreInstances: () => { void instances.fetchNextPage(); },
    patchList,
    refresh: (list: 'articles' | 'companies') => { void qc.invalidateQueries({ queryKey: feedKey(list) }); },
  };
}
