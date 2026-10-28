'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, Plus, Package, ClipboardList, ScanLine, X, Loader2, Building2, User, FileText } from 'lucide-react';
import { cn, formatObjectId, userDisplayName } from '@/lib/utils';
import { TYPE_META, FILTER_TYPES } from '@/lib/erp-record';
import {userName, articleName, organizationName, orderName } from '@/lib/record-name';
import { articleStatus, isStaff, organizationStatus, userStatus, orderStatus } from '@/lib/record-status';
import { RecordIcon, StatusBadge } from '@/components/erp/fields';
import { api } from '@/lib/api';
import type {Article, CompanySettings, UserProfile, ErpRecordType, InstanceSummary, OrderSummary, Order, Todo, DocumentSummary } from '@/types';
import type { StatusCfg } from '@/lib/status-tone';
import { userInitials, UserDetail } from '@/components/erp/user-detail';
import { ErpNavContext } from '@/components/erp/obj-id';
import { useScan } from '@/components/scan/scan-provider';
import type { ScanCandidate } from '@/lib/scan';
import { ErrorBoundary } from '@/components/erp/error-boundary';
import { setOpenRecord } from '@/lib/feedback';
import { ArticleDetail } from '@/components/erp/article-detail';
import { OrderDetail, type OrderSeed } from '@/components/erp/order-detail';
import { InstanceDetail } from '@/components/erp/instance-detail';
import { OrganizationDetail } from '@/components/erp/organization-detail';
import { ERP_NOTICE, MESSAGES_CHANGED } from '@/components/erp/communication';
import { TODO_CHANGED } from '@/lib/todo';
import { NewCompany, NewPerson } from '@/components/erp/new-record';
import { DocumentDetail } from '@/components/erp/document-detail';
import { DocumentDraft } from '@/components/erp/document-draft';
import { statusCfg } from '@/lib/process-status';
import { tell } from '@/lib/notice';
import { feedKey } from '@/lib/feed';

// Typ-Metadaten (Label, Symbol, Symbolfarbe) + Filter-Reihenfolge sind mit dem Detail
// geteilt – EINE Quelle der Wahrheit für die Typ-Identität: lib/erp-record.ts.
const INSTANCE_PAGE = 100;   // Seitengrösse des server-paginierten Instanz-Feeds

/** «zu tun» je Objektnummer – die Zahl am Symbol. */
const todoByObject = (rows: Todo[]) => new Map(rows.map((r) => [r.object_id, r]));

/** Eine Seite kann sich mit der nächsten überschneiden, wenn dazwischen etwas dazukam. */
function dedupeById(rows: InstanceSummary[]): InstanceSummary[] {
  const seen = new Set<number>();
  return rows.filter((r) => (seen.has(r.id) ? false : (seen.add(r.id), true)));
}

type Row =
  | { type: 'user'; key: string; objectId: number | null; data: UserProfile }
  | { type: 'article'; key: string; objectId: number | null; data: Article }
  | { type: 'order'; key: string; objectId: number | null; data: OrderSummary }
  | { type: 'instance'; key: string; objectId: number | null; data: InstanceSummary }
  | { type: 'organization'; key: string; objectId: number | null; data: CompanySettings }
  | { type: 'document'; key: string; objectId: number | null; data: DocumentSummary };

// Der Name eines Datensatzes kommt aus der EINEN Ableitung (`lib/record-name`) – nie steht
// hier der Typ (den sagt das Symbol). `null` = noch ohne Namen (Notiz #177).
function rowTitle(row: Row): string | null {
  if (row.type === 'user') return userName(row.data);
  if (row.type === 'order') return orderName(row.data);
  if (row.type === 'instance') return row.data.article_name?.trim() || null;
  if (row.type === 'organization') return organizationName(row.data);
  if (row.type === 'document') return `${row.data.art} · ${row.data.name}`;
  return articleName(row.data);
}

// Der Zustand kommt aus der EINEN Ableitung (`lib/record-status`) – genau wie der Name.
// Hier wird nur verteilt, nie gebaut: sonst läuft der Feed vom Detail weg (Notiz #379).
function rowStatus(row: Row): StatusCfg | null {
  if (row.type === 'user') return userStatus(row.data);
  if (row.type === 'order') return orderStatus(row.data);
  // Die Instanz ist eine Gruppe und trägt keinen Zustand (Testnotiz #675) – ein Wort
  // hier wäre bei einer Charge mit gemischten Stücken eine Behauptung.
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
 * Scanner – nicht als zweite Implementierung «für die Kamera», sondern als derselbe
 * Aufruf: sonst fände die eine Suche etwas, das die andere nicht kennt.
 *
 * `needle` kommt bereits in Kleinschreibung.
 */
function feedMatch(row: Row, needle: string): boolean {
  return rowSearchText(row).includes(needle);
}

/** Ein Datensatz als Scanner-Vorschlag: Nummer + «Typ · Name». */
function toCandidate(row: Row): ScanCandidate {
  const label = TYPE_META[row.type].label;
  const title = rowTitle(row);
  return { objectId: row.objectId as number, label: title ? `${label} · ${title}` : label };
}

// Wie viele Vorschläge der Scanner höchstens anbietet (er zeigt ohnehin nur die ersten).
const SUGGEST_LIMIT = 8;

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick, todo }: {
  row: Row; sel: boolean; onClick: () => void;
  /** Was zu tun ist – die Zahl am Symbol (`lib/todo`). */
  todo?: Todo | null;
}) {
  const title = rowTitle(row);

  const badge = rowStatus(row);

  return (
    <button
      onClick={onClick}
      className={cn(
        // Leichter (Notizen #206/#300): kleineres Symbol, halbfetter Titel, **mehr Luft**
        // (12 px statt 10 px innen, 4 px zwischen den Zeilen). Der Feed ist eine Liste zum
        // Überfliegen – die Trennung machen Weissraum und Ausrichtung, nicht Fläche.
        'w-full flex items-center gap-3 px-3 py-3 mb-1 rounded-ds-md text-left transition-colors',
        sel ? 'bg-accent-soft' : 'hover:bg-bg-2',
      )}
    >
      {/* **Dieselbe Komponente wie im Detail-Kopf** (#697/#699) – Symbol, Farbfamilie,
          Form und das Abweichungs-Zeichen kommen aus EINER Stelle; nur die Grösse
          unterscheidet die beiden Orte. Zwei Implementierungen driften garantiert
          auseinander (#688). */}
      <RecordIcon
        type={row.type}
        size={28}
        photoUrl={row.type === 'user' ? row.data.photo_url : undefined}
        initials={row.type === 'user' ? userInitials(title ?? '', row.data.email) : undefined}
        deviation={row.type === 'order' && row.data.is_deviation}
        own={row.type === 'organization' && !!row.data.is_own}
        todo={todo}
      />
      <div className="min-w-0 flex-1">
        <div className={cn('text-sm font-semibold truncate', sel ? 'text-accent-ink' : title ? 'text-fg-1' : 'text-fg-4 italic')}>
          {title ?? (row.type === 'user' ? 'Kein Name' : 'Ohne Bezeichnung')}
        </div>
        {/* Zweite Zeile: Kennung + Zustand. Der Zustand ist die **gefüllte Pille mit Symbol**
            – dieselbe Form wie im Detail-Kopf (Notiz #334): derselbe Zustand soll überall
            gleich aussehen. Die Luft, die den Feed leichter macht (Notiz #300), kommt aus
            Polsterung und Zeilenabstand, nicht aus einer zweiten Status-Form. */}
        <div className="flex items-center gap-2.5 mt-1">
          <span className="text-fg-4 tabular-nums" style={{ font: 'var(--mono-sm)' }}>{formatObjectId(row.objectId)}</span>
          {badge && <StatusBadge cfg={badge} size={11} />}
        </div>
      </div>
    </button>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ErpPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  // **Die Suche, für die der Server gefragt wird** – entprellt (300 ms), leer sofort. Sie ist
  // Teil des Schlüssels: eine ältere Antwort kann eine neuere nicht überholen, und was zu
  // einer anderen Suche gehört, steht nicht da (Chrome-Test: beim Tippen blitzten
  // ungefilterte Treffer auf).
  const [query, setQuery] = useState('');
  useEffect(() => {
    const q = search.trim();
    const t = setTimeout(() => setQuery(q), q ? 300 : 0);
    return () => clearTimeout(t);
  }, [search]);
  const current = query === search.trim();

  // ►►► **Die Listen des Feeds sind Queries** (`lib/feed.ts`, `lib/use-feed.ts`): EINE
  // Datenquelle je Liste, nachgeladen nur, was ein Schreibvorgang betrifft, und beim
  // Zurückkommen nach einer Pause. Ein Fehler meldet sich über `meta.what` (`lib/notice`).
  const meQuery = useQuery({ queryKey: ['me'], queryFn: () => api.getMe(), staleTime: Infinity, meta: { what: 'Profil' } });
  const profile = meQuery.data;
  // Ins ERP kommt ohnehin nur Personal (`AuthGate staffOnly`) – `staff` sagt, dass die
  // Antwort da ist. Firmen, Dokumente und «zu tun» fragen erst dann (Personal-Endpunkte).
  const staff = !!profile && isStaff(profile.role);
  const isAdmin = profile?.role === 'admin';
  // **Kommunikation** (CRM Schritt 2): wer gerade arbeitet.
  const me = profile?.object_id ? { object_id: profile.object_id, name: userDisplayName(profile) } : null;
  const usersQuery = useQuery({ queryKey: feedKey('people'), queryFn: () => api.getErpRecords(), meta: { what: 'Personen' } });
  const articlesQuery = useQuery({ queryKey: feedKey('articles'), queryFn: () => api.getArticles(), meta: { what: 'Artikel' } });
  const ordersQuery = useQuery({ queryKey: feedKey('orders'), queryFn: () => api.getOrders(), meta: { what: 'Aufträge' } });
  // Unternehmen: ein ERP-Datensatztyp `organization` – eigene Gesellschaften und fremde Firmen.
  const companiesQuery = useQuery({
    queryKey: feedKey('companies'), queryFn: () => api.getCompanies(), enabled: staff, meta: { what: 'Firmen' },
  });
  // Je Datensatz, was zu tun ist – die Zahl am Symbol.
  const todoQuery = useQuery({
    queryKey: feedKey('todo'), queryFn: () => api.todo(), enabled: staff, meta: { what: 'Zu tun' },
    select: todoByObject,
  });
  // Instanzen (höchste Kardinalität): server-paginiert + server-durchsucht. Die letzte Seite
  // war nicht voll → es gibt nichts mehr nachzuladen (der Server nennt keine Gesamtzahl).
  const instancesQuery = useInfiniteQuery({
    queryKey: [...feedKey('instances'), query],
    queryFn: ({ pageParam }) => api.getInstances(INSTANCE_PAGE, pageParam, query),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length < INSTANCE_PAGE ? undefined : pages.reduce((n, p) => n + p.length, 0)),
    meta: { what: 'Instanzen' },
  });
  // **Dokumente** – wie die Instanzen auf dem Server durchsucht (Nummer, Name, gelesener Text).
  const documentsQuery = useQuery({
    queryKey: [...feedKey('documents'), query], queryFn: () => api.getDocuments(query, 200),
    enabled: staff, meta: { what: 'Dokumente' },
  });

  const users = usersQuery.data ?? [];
  const articles = articlesQuery.data ?? [];
  const orders = ordersQuery.data ?? [];
  const companies = companiesQuery.data ?? [];
  const todos = todoQuery.data ?? new Map<number, Todo>();
  const instances = dedupeById(instancesQuery.data?.pages.flat() ?? []);
  const documents = documentsQuery.data ?? [];
  const instanceLoadingMore = instancesQuery.isFetchingNextPage;
  const instancesDone = !instancesQuery.hasNextPage;
  // Die Shell erscheint sofort; «Laden…» steht nur, bis die Kern-Listen geantwortet haben.
  const loading = usersQuery.isPending || articlesQuery.isPending || ordersQuery.isPending;

  /** Eine Liste im Cache ändern (Antwort einer Anlage/Änderung) – derselbe Speicher. */
  const patchList = <T,>(list: 'people' | 'articles' | 'orders' | 'companies', fn: (rows: T[]) => T[]) =>
    qc.setQueryData<T[]>(feedKey(list), (rows) => fn(rows ?? []));

  const [typeFilter, setTypeFilter] = useState<ErpRecordType | null>(null);
  const [sel, setSel] = useState<{ type: ErpRecordType; objectId: number } | null>(null);
  const [creating, setCreating] = useState<'article' | 'order' | 'person' | 'company' | 'document' | null>(null);
  /**
   * **Der Entwurf mit einer bereits gewählten Einzelinstanz** (Abweichungsauftrag §3.1).
   *
   * Der Klick an einem Stück im Prozess öffnet einen **ganz gewöhnlichen** Auftragsentwurf –
   * er steht nur schon in der Definition drin. Angelegt wird dabei nichts: ein Entwurf lebt
   * im Browser, bis er freigegeben wird (§6.1). Eine eigene «Abweichung anlegen»-Aktion
   * gäbe es nicht zu bauen, sie wäre ein zweiter Anlage-Weg.
   */
  const [orderSeed, setOrderSeed] = useState<OrderSeed | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [plusOpen, setPlusOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(50);
  const plusRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  // Aktueller «mehr laden»-Handler (immer frisch, vom Sentinel-Observer aufgerufen).
  const loadMoreRef = useRef<() => void>(() => {});

  const scan = useScan();

  // Neue oder verschickte Nachrichten, eine erledigte Aufgabe: «zu tun» ändert sich – und ein
  // unbekannter Absender ist jetzt eine Person.
  useEffect(() => {
    const onMessages = () => {
      void qc.invalidateQueries({ queryKey: feedKey('todo') });
      void qc.invalidateQueries({ queryKey: feedKey('people') });
    };
    const onTodo = () => { void qc.invalidateQueries({ queryKey: feedKey('todo') }); };
    window.addEventListener(MESSAGES_CHANGED, onMessages);
    window.addEventListener(TODO_CHANGED, onTodo);
    return () => {
      window.removeEventListener(MESSAGES_CHANGED, onMessages);
      window.removeEventListener(TODO_CHANGED, onTodo);
    };
  }, [qc]);

  // ►►► Die Postfächer werden abgeglichen, solange das ERP offen ist (der Server drosselt
  // selbst, ohne Anbindung ist es ein No-op). Neues meldet sich wie jede andere Änderung.
  useEffect(() => {
    if (!staff) return;
    const tick = () => {
      if (document.hidden) return;
      api.syncMail().then((r) => {
        if (r.new > 0 || r.sent > 0) window.dispatchEvent(new Event(MESSAGES_CHANGED));
      }).catch(tell('Postfach', 'Nicht abgeglichen'));
    };
    tick();
    const t = setInterval(tick, 60_000);
    return () => clearInterval(t);
  }, [staff]);

  // Rückkehr von Google nach «Postfach verbinden»: ein Satz, dann ist der Parameter weg.
  const [mailNote, setMailNote] = useState<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const note = params.get('mail');
    if (!note) return;
    setMailNote(note === 'ok' ? 'Postfach verbunden – neue Mails erscheinen ab jetzt im Verlauf.' : note);
    params.delete('mail');
    const rest = params.toString();
    window.history.replaceState(null, '', `${window.location.pathname}${rest ? `?${rest}` : ''}`);
  }, []);
  // Was scheitert, nachdem die auslösende Ansicht geschlossen ist, meldet sich hier.
  useEffect(() => {
    const show = (e: Event) => setMailNote(String((e as CustomEvent).detail ?? ''));
    window.addEventListener(ERP_NOTICE, show);
    return () => window.removeEventListener(ERP_NOTICE, show);
  }, []);

  // «?typ=<Datensatztyp>» aus der Arbeitsleiste: stellt nur den Filter vor, wie ein Klick
  // auf seinen Chip. Unbekannte Werte bleiben ohne Wirkung.
  useEffect(() => {
    const typ = new URLSearchParams(window.location.search).get('typ');
    const known = FILTER_TYPES.find((t) => t === typ);
    if (known) setTypeFilter(known);
  }, []);

  // Tiefer Link «?open=<Objektnummer>» (z. B. aus einem Etikett): den Datensatz direkt
  // öffnen. Typ serverseitig auflösen (funktioniert auch, bevor der Feed geladen ist).
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('open');
    const oid = raw ? Number(raw) : NaN;
    if (!Number.isFinite(oid)) return;
    api.resolveObject(oid).then((r) => {
      setCreating(null);
      setSel({ type: r.object_type as ErpRecordType, objectId: oid });
      setMobileView('detail');
    }).catch(tell(`Datensatz ${oid}`, 'Nicht geöffnet'));
  }, []);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setPlusOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  // Infinite scroll: Observer per Callback-Ref an den Sentinel hängen (robust, auch
  // wenn der Sentinel erst nach dem Nachladen der Daten erscheint). Ruft den stets
  // frischen loadMoreRef-Handler.
  const sentinelCb = useCallback((node: HTMLDivElement | null) => {
    observerRef.current?.disconnect();
    if (!node) return;
    observerRef.current = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) loadMoreRef.current(); },
      { threshold: 0.1 },
    );
    observerRef.current.observe(node);
  }, []);

  // Sichtbarkeits-Zähler zurücksetzen, wenn Suche oder Filter wechselt
  useEffect(() => { setVisibleCount(50); }, [typeFilter, search]);

  const rows: Row[] = [
    // Jede **Firma** ist ein nummerierter ERP-Datensatz – eigene wie fremde, für jedes
    // Personal (CRM Schritt 1).
    ...companies.map((s): Row => ({
      type: 'organization', key: `org${s.object_id}`, objectId: s.object_id ?? null, data: s,
    })),
    ...users.map((u): Row => ({ type: 'user', key: `u${u.id}`, objectId: u.object_id, data: u })),
    ...articles.map((a): Row => ({ type: 'article', key: `a${a.id}`, objectId: a.object_id, data: a })),
    ...orders.map((o): Row => ({ type: 'order', key: `o${o.id}`, objectId: o.object_id, data: o })),
    ...instances.map((i): Row => ({ type: 'instance', key: `i${i.id}`, objectId: i.object_id, data: i })),
    ...documents.map((d): Row => ({ type: 'document', key: `d${d.object_id}`, objectId: d.object_id, data: d })),
    // FIX: Fallback -Infinity ergab NaN, sobald ZWEI Zeilen ohne Objektnummer verglichen
    // wurden (-Infinity − -Infinity = NaN) – ein NaN-Komparator verletzt die Sortier-Ordnung
    // und macht die Reihenfolge undefiniert. 0 sortiert Zeilen ohne Nummer stabil ans Ende
    // (alle echten Nummern sind 9-stellig > 0).
  ].sort((x, y) => (y.objectId ?? 0) - (x.objectId ?? 0));   // höchste Nummer zuerst

  const counts = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.type] = (acc[r.type] ?? 0) + 1;
    return acc;
  }, {});

  const filtered = rows.filter((r) => {
    if (typeFilter && r.type !== typeFilter) return false;
    // Instanzen sind bereits server-seitig durchsucht (kein erneuter Client-Filter) –
    // aber nur, wenn sie zu DIESER Suche gehören.
    if (r.type === 'instance' || r.type === 'document') return current;
    if (search && !feedMatch(r, search.toLowerCase())) return false;
    return true;
  });

  const selectedRow = sel ? rows.find((r) => r.type === sel.type && r.objectId === sel.objectId) ?? null : null;

  // Cross-Feed-Navigation (z. B. Klick auf den Artikel im Instanz-Detail): zeigt der ausgewählte
  // Datensatz auf einen Typ, dessen Detail sonst AUS DER LISTE rendert (Artikel), er aber
  // (noch) nicht geladen ist, wird er on-demand nachgeladen – sonst bliebe die Detailseite leer.
  // Auftrag/Instanz haben bereits ihren eigenen Fetch-Pfad (orderDetail/instanceDetail).
  const [navRecord, setNavRecord] = useState<Row | null>(null);
  useEffect(() => {
    if (!sel || selectedRow || sel.type === 'instance' || sel.type === 'document') { setNavRecord(null); return; }
    let cancelled = false;
    const load: Promise<Row | null> =
      sel.type === 'article'
        ? api.getArticle(sel.objectId).then((d): Row => ({ type: 'article', key: `a${d.id}`, objectId: sel.objectId, data: d }))
        : Promise.resolve(null);
    load.then((row) => { if (!cancelled) setNavRecord(row); }).catch(() => { if (!cancelled) setNavRecord(null); });
    return () => { cancelled = true; };
  }, [sel, selectedRow]);
  // Für aus-der-Liste rendernde Typen: der geladene Feed-Datensatz ODER der on-demand nachgeladene.
  const activeRow = selectedRow ?? navRecord;

  // Testnotizen: dem Notiz-Widget melden, WAS gerade offen ist. Der Feed ist ein
  // Master-Detail auf EINER Route – ohne diese Meldung trüge eine Notiz aus dem
  // Detailfenster keine Objektnummer (die Route bleibt schlicht `/erp`).
  useEffect(() => {
    setOpenRecord(sel ? { kind: TYPE_META[sel.type]?.label ?? sel.type, objectId: sel.objectId } : null);
  }, [sel]);

  // Instanz-Pagination: nur laden, wenn Instanzen sichtbar sind (Feed «alle» oder «Instanzen»).
  const instancesRelevant = typeFilter === null || typeFilter === 'instance';
  const hasMoreInstances = instancesRelevant && !instancesDone;
  const displayCount = (t: ErpRecordType): number => (t === 'instance' ? instances.length : (counts[t] ?? 0));

  function loadMoreInstances() {
    // Ein Fehler meldet sich über die Query (`meta.what`), nicht hier.
    if (!instanceLoadingMore && current) void instancesQuery.fetchNextPage();
  }

  // Beim Sichtbarwerden des Sentinels: mehr Zeilen rendern + ggf. nächste Instanz-Seite laden.
  loadMoreRef.current = () => {
    setVisibleCount((c) => c + 50);
    if (hasMoreInstances) loadMoreInstances();
  };

  function handleSelect(type: ErpRecordType, objectId: number | null) {
    if (objectId == null) return;
    setCreating(null);
    setSel({ type, objectId });
    setMobileView('detail');
  }

  // Klick/Scan auf eine Objektnummer → Datensatz öffnen. Ist er nicht im geladenen
  // Feed (z. B. eine nicht geladene Instanz), wird der Typ serverseitig aufgelöst.
  async function openByObjectId(objectId: number) {
    const row = rows.find((r) => r.objectId === objectId);
    if (row) { handleSelect(row.type, objectId); return; }
    try {
      const r = await api.resolveObject(objectId);
      handleSelect(r.object_type as ErpRecordType, objectId);
    } catch { /* Objekt nicht gefunden – ignorieren */ }
  }

  /**
   * **Die Suche des Feeds – für den Scanner.** Nicht nachgebaut, sondern derselbe Aufruf:
   * die geladenen Zeilen durch `feedMatch`, die Instanzen durch dieselbe Server-Suche
   * (`api.getInstances(…, search)`), die auch der Instanz-Feed benutzt. Eine zweite
   * Fassung «für die Kamera» hätte anders getroffen als die Liste daneben.
   */
  async function suggestFromFeed(q: string): Promise<ScanCandidate[]> {
    const needle = q.trim().toLowerCase();
    if (!needle) return [];
    const local = rows
      .filter((r) => r.objectId != null && r.type !== 'instance' && r.type !== 'document' && feedMatch(r, needle))
      .slice(0, SUGGEST_LIMIT)
      .map(toCandidate);
    // Instanzen haben die höchste Kardinalität und werden darum serverseitig gesucht –
    // genau wie im Feed. Fällt die Abfrage aus, bleiben die lokalen Treffer.
    const found = await api.getInstances(SUGGEST_LIMIT, 0, needle).catch(() => []);
    return [
      ...local,
      ...found.map((i): ScanCandidate => ({
        objectId: i.object_id,
        label: `${TYPE_META.instance.label} · ${i.article_name ?? 'Ohne Bezeichnung'}`,
      })),
    ];
  }

  /**
   * **Suchen mit der Kamera.** Ein freier Lookup: kein `expected`, kein `restrict` –
   * jede Objektnummer des Hauses darf es sein, und was sie ist, löst der Server auf.
   *
   * `exists` ist dabei der Unterschied zwischen «funktioniert» und «tut so»: ohne die
   * Frage gilt jede formal gültige 9-stellige Zahl, der Dialog meldet Erfolg, schliesst –
   * und hier passiert nichts, weil die Nummer keinen Datensatz hat. Mit ihr sagt es der
   * Rahmen im Bild, wo der Mensch gerade hinschaut.
   *
   * `suggest` ist die **Vorschlagsquelle**: ohne sie gab es hier nichts zu filtern (der
   * freie Lookup hat naturgemäss keine Kandidatenliste), und wer eine Teilnummer tippte,
   * sah nichts. Die Gültigkeitsregel bleibt davon unberührt.
   */
  function openScanner() {
    scan({
      steps: [{
        label: 'Datensatz',
        exists: (id) => api.resolveObject(id).then(() => true).catch(() => false),
        suggest: suggestFromFeed,
      }],
      onComplete: ([objectId]) => { void openByObjectId(objectId); },
    });
  }

  function startCreate(type: 'article' | 'order' | 'person' | 'company' | 'document', seed?: OrderSeed) {
    setPlusOpen(false);
    setSel(null);
    setOrderSeed(seed ?? null);
    setCreating(type);
    setMobileView('detail');
  }

  function handleCompanySaved(s: CompanySettings) {
    patchList<CompanySettings>('companies', (rows) => rows.map((x) => (x.object_id === s.object_id ? s : x)));
    if (s.is_operator) {
      // Betreiber gewechselt: die ganze Liste neu laden, damit der frühere Betreiber
      // seinen Titel verliert (genau EINE Gesellschaft trägt is_operator). Und die im
      // Fenster mitgeführte Firmenangabe (Impressum) nachziehen.
      void qc.invalidateQueries({ queryKey: feedKey('companies') });
    }
  }

  /** Eine neu angelegte Firma bzw. Person in den Feed nehmen und öffnen. */
  function handleCompanyCreated(c: CompanySettings) {
    patchList<CompanySettings>('companies', (rows) => [...rows, c]);
    setCreating(null);
    if (c.object_id != null) setSel({ type: 'organization', objectId: c.object_id });
  }

  function handlePersonCreated(u: UserProfile) {
    patchList<UserProfile>('people', (rows) => [...rows, u]);
    setCreating(null);
    if (u.object_id != null) setSel({ type: 'user', objectId: u.object_id });
  }

  function handleArticleSaved(a: Article) {
    patchList<Article>('articles', (rows) => (rows.some((x) => x.id === a.id) ? rows.map((x) => (x.id === a.id ? a : x)) : [...rows, a]));
    setCreating(null);
    if (a.object_id != null) setSel({ type: 'article', objectId: a.object_id });
  }


  function handleUserSaved(u: UserProfile) {
    patchList<UserProfile>('people', (rows) => rows.map((x) => (x.id === u.id ? u : x)));
  }

  // Erst hier existiert der Auftrag: die Anlage liefert ihn samt frisch vergebener
  // Objektnummer zurück, und der Feed übernimmt ihn ohne Nachladen.
  function handleOrderSaved(o: Order) {
    setCreating(null);
    patchList<OrderSummary>('orders', (rows) => (rows.some((x) => x.id === o.id) ? rows.map((x) => (x.id === o.id ? o : x)) : [...rows, o]));
    setSel({ type: 'order', objectId: o.object_id });
  }

  const refreshArticles = () => { void qc.invalidateQueries({ queryKey: feedKey('articles') }); };

  function cancelCreate() {
    setCreating(null);
    setMobileView('list');
  }

  const showList = mobileView === 'list';
  const hasDetail = creating !== null || activeRow !== null || sel?.type === 'instance' || sel?.type === 'document';

  return (
    <ErpNavContext.Provider value={openByObjectId}>
    {/* 100dvh statt 100vh: auf Mobile berücksichtigt die dynamische Viewport-Höhe die
        Browser-Leiste – sonst rutscht der «+»-FAB (bottom) unter die Adressleiste (unsichtbar). */}
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - var(--site-header-h))' }}>
      {mailNote && (
        <div role="status" className="flex items-center gap-3 px-5 py-2.5 text-sm border-b border-border-1 bg-bg-2 text-fg-2">
          <span className="flex-1 min-w-0">{mailNote}</span>
          <button onClick={() => setMailNote(null)} aria-label="Schliessen" title="Schliessen"
            className="flex-none w-7 h-7 rounded-ds-sm flex items-center justify-center text-fg-3 hover:text-fg-1">
            <X size={13} />
          </button>
        </div>
      )}
      <div className="flex overflow-hidden" style={{ flex: 1, minHeight: 0 }}>

        {/* ── List panel ───────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-shrink-0 border-r border-border-1 flex flex-col bg-bg-1 relative',
          'w-full md:w-[300px] lg:w-[336px]',
          showList ? 'flex' : 'hidden md:flex',
        )}>
          {/* Suche + Scan */}
          <div className="flex items-center gap-2.5 px-5 pt-4 pb-3.5">
            <div className="flex-1 min-w-0 flex items-center gap-2.5 rounded-ds-md border border-border-2 px-2.5 py-2">
              <Search size={17} className="flex-none text-fg-4" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Suchen…"
                className="flex-1 min-w-0 border-none outline-none bg-transparent text-sm text-fg-1 placeholder:text-fg-4"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  title="Eingabe löschen"
                  aria-label="Eingabe löschen"
                  className="flex-none w-8 h-8 rounded-ds-sm flex items-center justify-center bg-bg-3 text-fg-3 hover:text-fg-1 transition-colors"
                >
                  <X size={13} />
                </button>
              )}
              <button
                onClick={openScanner}
                data-tip="Datensatz scannen"
                data-tip-pos="bottom"
                aria-label="Datensatz scannen"
                className="flex-none w-10 h-10 rounded-ds-sm flex items-center justify-center bg-bg-2 border border-border-1 text-fg-3 hover:text-fg-1 hover:bg-bg-3 transition-colors"
              >
                <ScanLine size={18} />
              </button>
            </div>
          </div>
          {/* Typ-Filter — Symbol-first, aktiv expandiert zu Label + Anzahl (Farbe = Typ) */}
          <div className="flex flex-wrap gap-1.5 px-5 pb-4 border-b border-border-1">
            {FILTER_TYPES.filter((t) => displayCount(t)).map((t) => {
              const active = typeFilter === t;
              const meta = TYPE_META[t];
              const Icon = meta.icon;
              return (
                <button
                  key={t}
                  onClick={() => setTypeFilter(active ? null : t)}
                  data-tip={`${meta.label} · ${displayCount(t)}`}
                  data-tip-pos="bottom"
                  {...(active ? { 'data-tip-hidden': '' } : {})}
                  className={cn(
                    'h-[42px] rounded-ds-md flex items-center justify-center gap-1.5 border transition-colors',
                    active ? 'border-transparent px-3.5' : 'min-w-[42px] border-border-1 bg-bg-1 hover:bg-bg-2',
                  )}
                  style={active ? { background: meta.bg, color: meta.fg } : { color: meta.fg }}
                >
                  <Icon size={18} />
                  {active && (
                    <>
                      <span className="text-[13px] font-bold">{meta.label}</span>
                      <span className="text-[12.5px] font-bold tabular-nums opacity-60">{displayCount(t)}</span>
                    </>
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 p-2 pb-24">
            {loading && <div className="p-6 text-center text-sm text-fg-4">Laden…</div>}
            {!loading && filtered.length === 0 && (
              <div className="p-6 text-center text-sm text-fg-4">
                {search || typeFilter ? 'Keine Treffer' : 'Keine Datensätze'}
              </div>
            )}
            {filtered.slice(0, visibleCount).map((r) => (
              <FeedItem
                key={r.key}
                row={r}
                sel={!creating && !!sel && sel.type === r.type && sel.objectId === r.objectId}
                onClick={() => handleSelect(r.type, r.objectId)}
                todo={r.objectId != null ? todos.get(r.objectId) : null}
              />
            ))}
            {(visibleCount < filtered.length || hasMoreInstances) && (
              <div ref={sentinelCb} className="flex items-center justify-center gap-2 p-3.5 text-fg-4 text-xs">
                <Loader2 size={15} className="animate-spin" />
                <span>Weitere werden geladen…</span>
              </div>
            )}
          </div>

          {/* FAB — neuen Datensatz anlegen (Menü öffnet nach oben) */}
          {staff && (
            <div ref={plusRef} className="absolute right-5 bottom-5 z-20">
              {plusOpen && (
                <div className="absolute right-0 bottom-[calc(100%+10px)] bg-bg-1 border border-border-1 rounded-ds-md shadow-ds-lg p-1 min-w-[170px]">
                  <button onClick={() => startCreate('article')} style={menuItemStyle}>
                    <Package size={15} style={{ color: 'var(--fg-3)' }} /> Artikel
                  </button>
                  <button onClick={() => startCreate('order')} style={menuItemStyle}>
                    <ClipboardList size={15} style={{ color: 'var(--fg-3)' }} /> Auftrag
                  </button>
                  <button onClick={() => startCreate('person')} style={menuItemStyle}>
                    <User size={15} style={{ color: 'var(--fg-3)' }} /> Person
                  </button>
                  {/* Firmen legt jedes Personal an; «eigen» setzt nur ein Admin. */}
                  <button onClick={() => startCreate('company')} style={menuItemStyle}>
                    <Building2 size={15} style={{ color: 'var(--fg-3)' }} /> Unternehmen
                  </button>
                  {/* **Ein Anlageweg für jedes Dokument** – Scan, Datei, Verfassen. */}
                  <button onClick={() => startCreate('document')} style={menuItemStyle}>
                    <FileText size={15} style={{ color: 'var(--fg-3)' }} /> Dokument
                  </button>
                </div>
              )}
              <button
                onClick={() => setPlusOpen((o) => !o)}
                data-tip={plusOpen ? undefined : 'Neuen Datensatz anlegen'}
                aria-label="Neuen Datensatz anlegen"
                className="w-[54px] h-[54px] rounded-full bg-inexxio hover:bg-inexxio-deep text-white flex items-center justify-center transition-all hover:-translate-y-0.5"
                style={{ boxShadow: '0 10px 22px rgba(179,18,15,.28)' }}
              >
                <Plus size={24} className={cn('transition-transform', plusOpen && 'rotate-45')} />
              </button>
            </div>
          )}
        </div>

        {/* ── Detail panel ─────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-1 overflow-hidden flex flex-col',
          !showList ? 'flex' : 'hidden md:flex',
        )}>
          {/* Ein Render-Fehler in EINEM Datensatz darf nie die ganze ERP-Oberfläche
              sperren – der Boundary zeigt eine erholbare Meldung; `resetKey` setzt ihn
              beim Wechsel der Auswahl zurück, «Zurück» führt in die Liste. */}
          <ErrorBoundary
            resetKey={creating ?? (sel ? `${sel.type}-${sel.objectId}` : 'none')}
            onReset={() => { setSel(null); setCreating(null); setMobileView('list'); }}
          >
          {/* **Im Entwurf führt keine Nummer weg** (Chrome-Test): der Entwurf lebt nur im
              Browser, ein Sprung zu einem Datensatz verwarf ihn ohne Warnung. Darum steht
              jede Nummer hier als Text – keine Navigation im Kontext. */}
          <ErpNavContext.Provider value={null}>
          {creating === 'article' && (
            <ArticleDetail key="new-article" record={null} onSaved={handleArticleSaved}
              onRefresh={refreshArticles}
              onBack={cancelCreate} />
          )}
          {creating === 'person' && (
            <NewPerson key="new-person" isAdmin={isAdmin} onSaved={handlePersonCreated} onBack={cancelCreate} />
          )}
          {creating === 'company' && (
            <NewCompany key="new-company" isAdmin={isAdmin} onSaved={handleCompanyCreated} onBack={cancelCreate} />
          )}
          {creating === 'order' && (
            <OrderDetail key="new-order" record={null} seed={orderSeed} onSaved={handleOrderSaved} onBack={cancelCreate} />
          )}
          {creating === 'document' && (
            <DocumentDraft key="new-document" onCancel={cancelCreate}
              onFiled={(d) => { setCreating(null); setSel({ type: 'document', objectId: d.object_id }); }}
              onOpen={(oid) => { setCreating(null); setSel({ type: 'document', objectId: oid }); }} />
          )}
          </ErpNavContext.Provider>
          {!creating && activeRow?.type === 'order' && (
            <OrderDetail
              key={activeRow.key}
              record={activeRow.data as Order}
              onSaved={handleOrderSaved}
              onDeviate={(seed) => startCreate('order', seed)}
              onBack={() => setMobileView('list')}
            />
          )}
          {!creating && activeRow?.type === 'user' && (
            <UserDetail key={activeRow.key} record={activeRow.data} onSave={handleUserSaved} isAdmin={isAdmin} onBack={() => setMobileView('list')}
              me={me} todo={activeRow.data.object_id != null ? todos.get(activeRow.data.object_id) : null} />
          )}
          {!creating && activeRow?.type === 'article' && (
            <ArticleDetail key={activeRow.key} record={activeRow.data}
              onSaved={handleArticleSaved}
              onRefresh={refreshArticles}
              // **Ein reiner Shortcut, kein zweiter Anlagepfad** (#690): derselbe Entwurf
              // wie über «+», nur mit vorbelegtem Artikel. Angelegt wird nichts – einen
              // Auftrag gibt es erst mit der Freigabe (#386).
              onCreateOrder={(articleObjectId) => startCreate('order', { articleObjectId })}
              onBack={() => setMobileView('list')} />
          )}
          {!creating && sel?.type === 'document' && (
            <DocumentDetail key={`d-${sel.objectId}`} objectId={sel.objectId} onBack={() => setMobileView('list')} />
          )}
          {!creating && sel?.type === 'instance' && (
            <InstanceDetail key={`i-${sel.objectId}`} objectId={sel.objectId} onBack={() => setMobileView('list')} />
          )}
          {!creating && activeRow?.type === 'organization' && (
            <OrganizationDetail key={activeRow.key} record={activeRow.data} isAdmin={isAdmin}
              todo={activeRow.data.object_id != null ? todos.get(activeRow.data.object_id) : null}
              onSaved={handleCompanySaved} onBack={() => setMobileView('list')} />
          )}
          {!hasDetail && (
            <div className="flex-1 flex flex-col items-center justify-center bg-bg-2">
              <Package size={48} strokeWidth={1} className="text-fg-4" />
              <p className="mt-3 text-sm text-fg-3">Datensatz auswählen oder neu anlegen</p>
            </div>
          )}
          </ErrorBoundary>
        </div>
      </div>
    </div>
    </ErpNavContext.Provider>
  );
}

const menuItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '9px 11px', borderRadius: 8, border: 'none', background: 'none',
  fontSize: 13, fontWeight: 600, color: 'var(--fg-2)', cursor: 'pointer', textAlign: 'left',
};
