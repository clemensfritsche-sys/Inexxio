'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatObjectId } from '@/lib/utils';
import { TYPE_META } from '@/lib/erp-record';
import { absentOn404, api } from '@/lib/api';
import type { Article, CompanySettings, ErpRecordType, Order, OrderSummary, UserProfile } from '@/types';
import { ErpNavContext } from '@/components/erp/obj-id';
import { useScan } from '@/components/scan/scan-provider';
import type { ScanCandidate } from '@/lib/scan';
import { setOpenRecord } from '@/lib/feedback';
import type { OrderSeed } from '@/components/erp/order-detail';
import { qk } from '@/lib/queries';
import { tell } from '@/lib/notice';
import { type Row, feedMatch, toCandidate, useFeedLists } from '@/lib/use-feed-lists';
import { useMailSync } from '@/lib/use-mail-sync';
import { useUrlParams } from '@/lib/use-url-params';
import { type Creatable, FeedPanel } from '@/components/erp/feed-panel';
import { DetailPane, type DetailHandlers } from '@/components/erp/detail-pane';

// Wie viele Vorschläge der Scanner höchstens anbietet (er zeigt ohnehin nur die ersten).
const SUGGEST_LIMIT = 8;

/**
 * ►►► **Der ERP-Feed** – Master-Detail auf EINER Route: die Liste (`FeedPanel`), das Detail
 * (`DetailPane`), dazwischen die Auswahl. Die Listen hält `lib/use-feed-lists`; was nach
 * einer Anlage oder Änderung im Feed passiert, steht hier an EINER Stelle (`handlers`). ◄◄◄
 */
export default function ErpPage() {
  const [search, setSearch] = useState('');
  // **Die Suche, für die der Server gefragt wird** – entprellt (300 ms), leer sofort. Sie ist
  // Teil des Schlüssels: eine ältere Antwort kann eine neuere nicht überholen, und was zu
  // einer anderen Suche gehört, steht nicht da.
  const [query, setQuery] = useState('');
  useEffect(() => {
    const q = search.trim();
    const t = setTimeout(() => setQuery(q), q ? 300 : 0);
    return () => clearTimeout(t);
  }, [search]);
  const current = query === search.trim();
  const feed = useFeedLists(query);
  const { rows, staff, isAdmin, me, todos, patchList } = feed;

  const [typeFilter, setTypeFilter] = useState<ErpRecordType | null>(null);
  const [sel, setSel] = useState<{ type: ErpRecordType; objectId: number } | null>(null);
  const [creating, setCreating] = useState<Creatable | null>(null);
  /**
   * **Der Entwurf mit einer bereits gewählten Einzelinstanz** (Abweichungsauftrag §3.1): ein
   * ganz gewöhnlicher Auftragsentwurf, das Stück steht nur schon drin. Angelegt wird dabei
   * nichts – ein Entwurf lebt im Browser, bis er freigegeben wird (§6.1).
   */
  const [orderSeed, setOrderSeed] = useState<OrderSeed | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const scan = useScan();

  useMailSync(staff);
  const open = (type: ErpRecordType, objectId: number) => {
    setCreating(null);
    setSel({ type, objectId });
    setMobileView('detail');
  };
  useUrlParams({ onType: setTypeFilter, onOpen: open });

  const counts = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.type] = (acc[r.type] ?? 0) + 1;
    return acc;
  }, {});
  const count = (t: ErpRecordType): number => (t === 'instance' ? feed.instanceCount : (counts[t] ?? 0));
  const filtered = rows.filter((r) => {
    if (typeFilter && r.type !== typeFilter) return false;
    // Instanzen und Dokumente sind auf dem Server durchsucht – aber nur, wenn sie zu
    // DIESER Suche gehören.
    if (r.type === 'instance' || r.type === 'document') return current;
    return !search || feedMatch(r, search.toLowerCase());
  });

  const selectedRow = sel ? rows.find((r) => r.type === sel.type && r.objectId === sel.objectId) ?? null : null;
  // Ein Artikel, der (noch) nicht im Feed steht (Sprung aus einem anderen Datensatz), wird
  // geholt – derselbe Schlüssel wie das Umfeld im Artikel, EIN Abruf.
  const navId = sel && !selectedRow && sel.type === 'article' ? sel.objectId : null;
  const navArticle = useQuery({
    queryKey: qk.article(navId ?? 0),
    queryFn: ({ signal }) => api.getArticle(navId!, { signal }),
    enabled: navId != null,
    meta: { what: 'Artikel' },
  }).data;
  const activeRow: Row | null = selectedRow ?? (navId != null && navArticle
    ? { type: 'article', key: `a${navArticle.id}`, objectId: navId, data: navArticle } : null);

  // Testnotizen: dem Notiz-Widget melden, WAS gerade offen ist – die Route bleibt `/erp`.
  useEffect(() => {
    setOpenRecord(sel ? { kind: TYPE_META[sel.type]?.label ?? sel.type, objectId: sel.objectId } : null);
  }, [sel]);

  // Instanzen nur nachladen, wenn sie sichtbar sind (Feed «alle» oder «Instanzen»).
  const more = (typeFilter === null || typeFilter === 'instance') && !feed.instancesDone;
  const loadMore = () => { if (!feed.instanceLoadingMore && current) feed.fetchMoreInstances(); };

  // Klick/Scan auf eine Objektnummer → Datensatz öffnen. Ist er nicht im geladenen Feed,
  // wird der Typ auf dem Server aufgelöst; was nichts öffnet, sagt warum.
  async function openByObjectId(objectId: number) {
    const row = rows.find((r) => r.objectId === objectId);
    if (row) { open(row.type, objectId); return; }
    try {
      const r = await api.resolveObject(objectId);
      open(r.object_type as ErpRecordType, objectId);
    } catch (e) {
      tell(formatObjectId(objectId), 'Nicht geöffnet')(e);
    }
  }

  /**
   * **Die Suche des Feeds – für den Scanner.** Derselbe Aufruf, nicht nachgebaut: die
   * geladenen Zeilen durch `feedMatch`, die Instanzen durch dieselbe Server-Suche.
   */
  async function suggestFromFeed(q: string): Promise<ScanCandidate[]> {
    const needle = q.trim().toLowerCase();
    if (!needle) return [];
    const local = rows
      .filter((r) => r.objectId != null && r.type !== 'instance' && r.type !== 'document' && feedMatch(r, needle))
      .slice(0, SUGGEST_LIMIT)
      .map(toCandidate);
    // Fällt die Abfrage aus, bleiben die lokalen Treffer – gemeldet.
    const found = await api.getInstances(SUGGEST_LIMIT, 0, needle)
      .catch((e: unknown) => { tell('Instanzen')(e); return []; });
    return [
      ...local,
      ...found.map((i): ScanCandidate => ({
        objectId: i.object_id,
        label: `${TYPE_META.instance.label} · ${i.article_name ?? 'Ohne Bezeichnung'}`,
      })),
    ];
  }

  /**
   * **Suchen mit der Kamera.** Ein freier Lookup – jede Objektnummer des Hauses darf es
   * sein. `exists` macht aus «tut so» ein «funktioniert»: eine Nummer ohne Datensatz meldet
   * der Rahmen im Bild; `suggest` bietet beim Tippen an, was der Feed findet.
   */
  function openScanner() {
    scan({
      steps: [{
        label: 'Datensatz',
        exists: (id) => api.resolveObject(id).then(() => true, absentOn404),
        suggest: suggestFromFeed,
      }],
      onComplete: ([objectId]) => { void openByObjectId(objectId); },
    });
  }

  function startCreate(type: Creatable, seed?: OrderSeed) {
    setSel(null);
    setOrderSeed(seed ?? null);
    setCreating(type);
    setMobileView('detail');
  }
  const select = (s: { type: ErpRecordType; objectId: number | null }) => {
    setCreating(null);
    if (s.objectId != null) setSel({ type: s.type, objectId: s.objectId });
  };
  const replace = <T extends { id: number }>(x: T) => (list: T[]) =>
    (list.some((y) => y.id === x.id) ? list.map((y) => (y.id === x.id ? x : y)) : [...list, x]);

  const handlers: DetailHandlers = {
    onArticleSaved: (a: Article) => {
      patchList<Article>('articles', replace(a));
      select({ type: 'article', objectId: a.object_id });
    },
    // Erst hier existiert der Auftrag: die Anlage liefert ihn samt frisch vergebener
    // Objektnummer zurück, und der Feed übernimmt ihn ohne Nachladen.
    onOrderSaved: (o: Order) => {
      patchList<OrderSummary>('orders', replace<OrderSummary>(o));
      select({ type: 'order', objectId: o.object_id });
    },
    onUserSaved: (u: UserProfile) => patchList<UserProfile>('people', (list) => list.map((x) => (x.id === u.id ? u : x))),
    onCompanySaved: (s: CompanySettings) => {
      patchList<CompanySettings>('companies', (list) => list.map((x) => (x.object_id === s.object_id ? s : x)));
      // Betreiber gewechselt: die ganze Liste neu, damit der frühere seinen Titel verliert.
      if (s.is_operator) feed.refresh('companies');
    },
    onPersonCreated: (u: UserProfile) => {
      patchList<UserProfile>('people', (list) => [...list, u]);
      select({ type: 'user', objectId: u.object_id });
    },
    onCompanyCreated: (c: CompanySettings) => {
      patchList<CompanySettings>('companies', (list) => [...list, c]);
      select({ type: 'organization', objectId: c.object_id ?? null });
    },
    onRefreshArticles: () => feed.refresh('articles'),
    onCreate: startCreate,
    onOpen: select,
    onCancelCreate: () => { setCreating(null); setMobileView('list'); },
    onBack: () => setMobileView('list'),
    onReset: () => { setSel(null); setCreating(null); setMobileView('list'); },
  };

  return (
    <ErpNavContext.Provider value={openByObjectId}>
      {/* 100dvh statt 100vh: auf Mobile zählt die Browser-Leiste mit – sonst rutscht «+»
          unter die Adressleiste. */}
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - var(--site-header-h))' }}>
        <div className="flex overflow-hidden" style={{ flex: 1, minHeight: 0 }}>
          <FeedPanel show={mobileView === 'list'} search={search} onSearch={setSearch}
            typeFilter={typeFilter} onTypeFilter={setTypeFilter} rows={filtered} count={count}
            loading={feed.loading} more={more} onMore={loadMore}
            isSelected={(r) => !creating && !!sel && sel.type === r.type && sel.objectId === r.objectId}
            onSelect={(r) => { if (r.objectId != null) open(r.type, r.objectId); }}
            todos={todos} staff={staff} onScan={openScanner} onCreate={(t) => startCreate(t)} />
          <DetailPane show={mobileView !== 'list'} creating={creating} sel={sel} activeRow={activeRow}
            orderSeed={orderSeed} isAdmin={isAdmin} me={me} todos={todos} h={handlers} />
        </div>
      </div>
    </ErpNavContext.Provider>
  );
}
