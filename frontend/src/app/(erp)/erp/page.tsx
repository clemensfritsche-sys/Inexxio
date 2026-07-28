'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Plus, Package, ClipboardList, ScanLine, X, Repeat, Loader2, Building2, AlertTriangle } from 'lucide-react';
import { cn, userDisplayName } from '@/lib/utils';
import { TYPE_META, FILTER_TYPES } from '@/lib/erp-record';
import { StatusBadge } from '@/components/erp/fields';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderSummary, UserProfile, ErpRecordType } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';
import { statusConfig } from '@/lib/article';
import { orderStatusConfig } from '@/lib/order';
import { instanceStatusConfig } from '@/lib/process';
import { ROLE_CFG, userInitials, fmtObjId, UserDetail } from '@/components/erp/user-detail';
import { ErpNavContext } from '@/components/erp/obj-id';
import { ErrorBoundary } from '@/components/erp/error-boundary';
import { DATA_CHANGED_EVENT } from '@/components/ai/assistant';
import { setOpenRecord } from '@/lib/feedback';
import { DocumentIngestDialog } from '@/components/erp/object-documents';
import { ArticleDetail } from '@/components/erp/article-detail';
import { OrderDetail } from '@/components/erp/order-detail';
import { InstanceDetail } from '@/components/erp/instance-detail';
import { OrganizationDetail } from '@/components/erp/organization-detail';

// Typ-Metadaten (Label, Symbol, Symbolfarbe) + Filter-Reihenfolge sind mit dem Detail
// geteilt – EINE Quelle der Wahrheit für die Typ-Identität: lib/erp-record.ts.
const INSTANCE_PAGE = 100;   // Seitengrösse des server-paginierten Instanz-Feeds
// Ab wann gilt der Feed nach einer Pause als veraltet und wird bei der Rückkehr (Tab wieder
// sichtbar / Fenster fokussiert) EINMAL nachgeladen. Bewusst kein Polling – das kostet
// Cloud-Run-Zeit, ohne dass jemand hinschaut.
const STALE_AFTER_MS = 60_000;

type Row =
  | { type: 'user'; key: string; objectId: number | null; data: UserProfile }
  | { type: 'article'; key: string; objectId: number | null; data: Article }
  | { type: 'order'; key: string; objectId: number | null; data: OrderSummary }
  | { type: 'instance'; key: string; objectId: number | null; data: Instance }
  | { type: 'organization'; key: string; objectId: number | null; data: CompanySettings };

function rowTitle(row: Row): string {
  if (row.type === 'user') return userDisplayName(row.data);
  if (row.type === 'order') return 'Auftrag';   // starr – Auftrag trägt keinen freien Namen
  if (row.type === 'instance') return 'Instanz';   // starr – Instanz trägt keinen freien Namen
  if (row.type === 'organization') return row.data.company_name || 'Unternehmen';
  return row.data.name; // article
}

function rowSearchText(row: Row): string {
  const id = String(row.objectId ?? '');
  if (row.type === 'user') return `${userDisplayName(row.data)} ${row.data.email} ${id}`.toLowerCase();
  if (row.type === 'order') return `auftrag ${row.data.article_name ?? ''} ${id}`.toLowerCase();
  if (row.type === 'instance') return `instanz ${row.data.article_name ?? ''} ${id}`.toLowerCase();
  if (row.type === 'organization') return `unternehmen firma ${row.data.company_name} ${id}`.toLowerCase();
  return `${row.data.name} ${row.data.size} ${id}`.toLowerCase();   // article
}

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick }: { row: Row; sel: boolean; onClick: () => void }) {
  const title = rowTitle(row);
  const hasTitle = row.type === 'user' ? title !== row.data.email : !!title;

  let badge: StatusCfg;
  if (row.type === 'user') badge = ROLE_CFG[row.data.role] ?? ROLE_CFG.customer;
  else if (row.type === 'article') badge = statusConfig(row.data.status);
  else if (row.type === 'order') {
    // EINHEITLICHER Status für ALLE Aufträge – auch Unter-Aufträge (kein Sonder-«Abweichung»-
    // Badge mehr): wiederkehrend & fällig zuerst, sonst der Status des AUFTRAGS.
    // Früher schlug bei einem freigegebenen Auftrag der **Beschaffungs**-Status durch – ein
    // Auftrag, dessen Bestellung geliefert war, stand auf «Geliefert», obwohl Prüfung,
    // Bewegung und Verkauf noch offen waren. Der Stand eines einzelnen Schritts ist nicht
    // der Stand des Auftrags; er steht im Detail am Ablauf. Hier zählt: läuft er noch?
    // Ein abgebrochener Auftrag heisst «Abgebrochen» (rot), nicht «Inaktiv»: der Unterschied
    // ist, dass er in einem Abweichungsauftrag fortgeführt wird. Projektion, kein Status.
    badge = row.data.recurrence_due
      ? { label: 'fällig', color: 'var(--danger)', bg: 'var(--danger-bg)', icon: Repeat }
      : orderStatusConfig(row.data.status, row.data.abort_into_id != null);
  }
  else if (row.type === 'instance') badge = instanceStatusConfig(row.data.quality, row.data.disposition, (row.data.reserved_quantity ?? 0) > 0);
  // Unternehmen ist ein aktiver Stammdaten-Singleton → GRÜN (wie ein aktiver Benutzer),
  // kein Grau (das läse sich als «aus»).
  else badge = { label: 'Stammdaten', color: 'var(--success)', bg: 'var(--success-bg)', icon: Building2 };

  const meta = TYPE_META[row.type];
  const TypeIcon = meta.icon;
  // Abweichungs-Auftrag (Unter-Auftrag reason='deviation'): identisch zu handhaben wie ein
  // regulärer Auftrag – nur ein dezentes Tag am Symbol (fürs spätere Audit).
  const isDeviation = row.type === 'order' && row.data.reason === 'deviation';

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2.5 mb-0.5 rounded-ds-md text-left transition-colors',
        sel ? 'bg-accent-soft' : 'hover:bg-bg-2',
      )}
    >
      {row.type === 'user' && row.data.photo_url ? (
        <div className="w-9 h-9 rounded-full flex-none overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={row.data.photo_url} alt="" className="w-full h-full object-cover" />
        </div>
      ) : (
        <div
          className={cn('w-9 h-9 flex-none flex items-center justify-center relative', row.type === 'user' ? 'rounded-full' : 'rounded-ds-sm')}
          style={{ background: meta.bg, color: meta.fg }}
        >
          {row.type === 'user'
            ? <span className="text-xs font-bold">{userInitials(title, row.data.email)}</span>
            : <TypeIcon size={17} />}
          {isDeviation && (
            <span
              title="Abweichungs-Auftrag"
              className="absolute -bottom-1 -right-1 flex items-center justify-center rounded-full"
              style={{ width: 14, height: 14, background: '#fffbeb', border: '1px solid #fbbf24' }}
            >
              <AlertTriangle size={9} style={{ color: '#d97706' }} />
            </span>
          )}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className={cn('text-sm font-bold truncate', sel ? 'text-accent-ink' : hasTitle ? 'text-fg-1' : 'text-fg-4 italic')}>
          {hasTitle ? title : (row.type === 'user' ? 'Kein Name' : 'Ohne Bezeichnung')}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-fg-3 tabular-nums" style={{ font: 'var(--mono-sm)' }}>{fmtObjId(row.objectId)}</span>
          <StatusBadge cfg={badge} size={11} />
        </div>
      </div>
    </button>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ErpPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  // Vollständiger Auftrag wird erst bei Auswahl geladen (Detail-on-Demand)
  const [orderDetail, setOrderDetail] = useState<Order | null>(null);
  // Instanzen (höchste Kardinalität): server-paginiert + server-durchsucht.
  const [instances, setInstances] = useState<Instance[]>([]);
  const [instanceTotal, setInstanceTotal] = useState(0);
  const [instanceLoadingMore, setInstanceLoadingMore] = useState(false);
  // Instanz-Detail wird – wie der Auftrag – bei Auswahl on-demand geladen
  // (funktioniert auch für Instanzen, die (noch) nicht im Feed geladen sind).
  const [instanceDetail, setInstanceDetail] = useState<Instance | null>(null);
  const [settings, setSettings] = useState<Partial<CompanySettings> | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<ErpRecordType | null>(null);
  const [sel, setSel] = useState<{ type: ErpRecordType; objectId: number } | null>(null);
  const [creating, setCreating] = useState<'article' | 'order' | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [isAdmin, setIsAdmin] = useState(false);
  const [viewerRole, setViewerRole] = useState<'staff' | 'supplier'>('staff');
  const [plusOpen, setPlusOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(50);
  const plusRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  // Aktueller «mehr laden»-Handler (immer frisch, vom Sentinel-Observer aufgerufen).
  const loadMoreRef = useRef<() => void>(() => {});
  const lastLoadRef = useRef<number>(0);   // Zeitpunkt des letzten Feed-Ladens (Rückkehr-Refresh)

  const mapsApiKey = settings?.google_maps_api_key ?? null;
  const suppliers = users.filter((u) => u.role === 'supplier');
  // Kombinierte Kamera im Feed: EIN Knopf für Scannen (Code → Datensatz öffnen) UND
  // Dokument erfassen (Auslöser → KI-Aufnahme). Kein Moduswechsel.
  const [feedCapture, setFeedCapture] = useState(false);

  useEffect(() => {
    // Kern-Feeds (geringe Kardinalität) blockierend laden – die Shell erscheint
    // sofort. Instanzen (höchste Kardinalität) danach nachladen.
    lastLoadRef.current = Date.now();
    Promise.allSettled([
      api.getErpRecords(), api.getArticles(), api.getOrders(), api.getMe(),
    ]).then(([u, a, o, me]) => {
      if (u.status === 'fulfilled') setUsers(u.value);
      if (a.status === 'fulfilled') setArticles(a.value);
      if (o.status === 'fulfilled') setOrders(o.value);
      if (me.status === 'fulfilled') {
        setIsAdmin(me.value.role === 'admin');
        setViewerRole(me.value.role === 'admin' || me.value.role === 'employee' ? 'staff' : 'supplier');
      }
      setLoading(false);
    });
    // Nicht-blockierend nachladen (Shell erscheint sofort). Instanzen werden
    // separat server-paginiert/-durchsucht geladen (Effekt unten).
    api.getPublicSettings().then(setSettings).catch(() => {});
  }, []);

  // Tiefer Link «?open=<Objektnummer>» (z. B. von der KI-Navigation): den Datensatz direkt
  // öffnen. Typ serverseitig auflösen (funktioniert auch, bevor der Feed geladen ist).
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('open');
    const oid = raw ? Number(raw) : NaN;
    if (!Number.isFinite(oid)) return;
    api.resolveObject(oid).then((r) => {
      setCreating(null);
      setSel({ type: r.object_type as ErpRecordType, objectId: oid });
      setMobileView('detail');
    }).catch(() => {});
  }, []);

  // Instanz-Feed: server-paginiert + server-durchsucht. Lädt Seite 0 beim Start und
  // bei jeder (entprellten) Suchänderung neu; weitere Seiten via Infinite-Scroll.
  useEffect(() => {
    const q = search.trim();
    // FIX: Antworten einer ÄLTEREN Suche konnten eine neuere überholen (Suche tippen und
    // sofort löschen → 0ms- vor 300ms-Antwort) und Liste/Zähler inkonsistent überschreiben.
    // Der Cleanup markiert den vorherigen Effekt als veraltet – späte Antworten verfallen.
    let stale = false;
    const t = setTimeout(() => {
      api.getInstances(INSTANCE_PAGE, 0, q).then((rows) => { if (!stale) setInstances(rows); }).catch(() => {});
      api.getInstanceCount(q).then((r) => { if (!stale) setInstanceTotal(r.count); }).catch(() => {});
    }, q ? 300 : 0);
    return () => { stale = true; clearTimeout(t); };
  }, [search]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setPlusOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  // KI-Live-Refresh: legt/ändert die KI im Chat einen Artikel/Auftrag/Prozessschritt,
  // feuert das Widget DATA_CHANGED_EVENT – der Feed lädt sofort nach, ohne dass der
  // Nutzer manuell aktualisieren muss (Optimierung #2). Re-Abo bei Suchänderung, damit
  // die Instanzen mit der aktuellen Suche neu geladen werden.
  useEffect(() => {
    const q = search.trim();
    function onDataChanged() {
      lastLoadRef.current = Date.now();
      api.getErpRecords().then(setUsers).catch(() => {});
      api.getArticles().then(setArticles).catch(() => {});
      api.getOrders().then(setOrders).catch(() => {});
      api.getInstances(INSTANCE_PAGE, 0, q).then(setInstances).catch(() => {});
      api.getInstanceCount(q).then((r) => setInstanceTotal(r.count)).catch(() => {});
    }
    // **Rückkehr nach Pause**: Der Feed war ein Schnappschuss vom Seitenaufbau – wer das ERP
    // ein paar Minuten liegen liess, sah alte Daten (und musste F5 drücken). Jetzt lädt er
    // beim Zurückkommen nach, aber NUR wenn er wirklich veraltet ist (Schwelle unten) –
    // kein Polling, kein Traffic beim kurzen Tab-Wechsel: ein Nachladen je Rückkehr.
    function onBack() {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastLoadRef.current < STALE_AFTER_MS) return;
      onDataChanged();
    }
    window.addEventListener(DATA_CHANGED_EVENT, onDataChanged);
    document.addEventListener('visibilitychange', onBack);
    window.addEventListener('focus', onBack);
    return () => {
      window.removeEventListener(DATA_CHANGED_EVENT, onDataChanged);
      document.removeEventListener('visibilitychange', onBack);
      window.removeEventListener('focus', onBack);
    };
  }, [search]);

  // Auftrag-Detail (inkl. Prozess-Embeds) erst bei Auswahl laden (Detail-on-Demand)
  useEffect(() => {
    if (sel?.type !== 'order') { setOrderDetail(null); return; }
    let cancelled = false;
    api.getOrder(sel.objectId).then((o) => { if (!cancelled) setOrderDetail(o); }).catch(() => {});
    return () => { cancelled = true; };
  }, [sel]);

  // Instanz-Detail on-demand (funktioniert auch für nicht im Feed geladene Instanzen)
  useEffect(() => {
    if (sel?.type !== 'instance') { setInstanceDetail(null); return; }
    let cancelled = false;
    api.getInstance(sel.objectId).then((i) => { if (!cancelled) setInstanceDetail(i); }).catch(() => {});
    return () => { cancelled = true; };
  }, [sel]);

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
    // Das Unternehmen ist ein nummerierter ERP-Datensatz – nur für Admins sichtbar
    // (Firmen-/Bank-/API-Konfiguration ist sensibel).
    ...(isAdmin && settings?.object_id
      ? [{ type: 'organization', key: 'org', objectId: settings.object_id, data: settings } as Row]
      : []),
    ...users.map((u): Row => ({ type: 'user', key: `u${u.id}`, objectId: u.object_id, data: u })),
    ...articles.map((a): Row => ({ type: 'article', key: `a${a.id}`, objectId: a.object_id, data: a })),
    ...orders.map((o): Row => ({ type: 'order', key: `o${o.id}`, objectId: o.object_id, data: o })),
    ...instances.map((i): Row => ({ type: 'instance', key: `i${i.id}`, objectId: i.object_id, data: i })),
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
    // Instanzen sind bereits server-seitig durchsucht (kein erneuter Client-Filter).
    if (search && r.type !== 'instance' && !rowSearchText(r).includes(search.toLowerCase())) return false;
    return true;
  });

  const selectedRow = sel ? rows.find((r) => r.type === sel.type && r.objectId === sel.objectId) ?? null : null;

  // Cross-Feed-Navigation (z. B. Klick auf den Artikel im Instanz-Detail): zeigt der ausgewählte
  // Datensatz auf einen Typ, dessen Detail sonst AUS DER LISTE rendert (Artikel), er aber
  // (noch) nicht geladen ist, wird er on-demand nachgeladen – sonst bliebe die Detailseite leer.
  // Auftrag/Instanz haben bereits ihren eigenen Fetch-Pfad (orderDetail/instanceDetail).
  const [navRecord, setNavRecord] = useState<Row | null>(null);
  useEffect(() => {
    if (!sel || selectedRow || sel.type === 'order' || sel.type === 'instance') { setNavRecord(null); return; }
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
  const hasMoreInstances = instancesRelevant && instances.length < instanceTotal;
  const displayCount = (t: ErpRecordType): number => (t === 'instance' ? instanceTotal : (counts[t] ?? 0));

  async function loadMoreInstances() {
    if (instanceLoadingMore) return;
    setInstanceLoadingMore(true);
    try {
      const next = await api.getInstances(INSTANCE_PAGE, instances.length, search.trim());
      setInstances((prev) => {
        const seen = new Set(prev.map((i) => i.id));
        return [...prev, ...next.filter((i) => !seen.has(i.id))];
      });
    } catch { /* ignore */ } finally {
      setInstanceLoadingMore(false);
    }
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

  function startCreate(type: 'article' | 'order') {
    setPlusOpen(false);
    setSel(null);
    setCreating(type);
    setMobileView('detail');
  }

  function handleArticleSaved(a: Article) {
    setArticles((prev) => (prev.some((x) => x.id === a.id) ? prev.map((x) => (x.id === a.id ? a : x)) : [...prev, a]));
    setCreating(null);
    if (a.object_id != null) setSel({ type: 'article', objectId: a.object_id });
  }

  function handleOrderSaved(o: Order) {
    setCreating(null);
    setOrderDetail(o);                                   // volles Detail sofort anzeigen
    if (o.object_id != null) setSel({ type: 'order', objectId: o.object_id });
    // Schlanken Feed aktualisieren (Status/Badge) + abhängige Daten neu laden:
    // Prozessschritte beeinflussen Artikel-Preisspanne/Durchlaufzeit, Instanzen &
    // ggf. Abweichungen (fehlgeschlagene Datenerfassung erzeugt einen Abweichungs-
    // Unterauftrag – erscheint im Auftrag-Feed).
    api.getOrders().then(setOrders).catch(() => {});
    api.getArticles().then(setArticles).catch(() => {});
    reloadInstances();
  }

  // Instanz-Feed neu laden (Seite 0 + Gesamtzahl, aktuelle Suche)
  function reloadInstances() {
    const q = search.trim();
    api.getInstances(INSTANCE_PAGE, 0, q).then(setInstances).catch(() => {});
    api.getInstanceCount(q).then((r) => setInstanceTotal(r.count)).catch(() => {});
  }

  function handleUserSaved(u: UserProfile) {
    setUsers((prev) => prev.map((x) => (x.id === u.id ? u : x)));
  }


  function cancelCreate() {
    setCreating(null);
    setMobileView('list');
  }

  const showList = mobileView === 'list';
  const hasDetail = creating !== null || activeRow !== null || sel?.type === 'order' || sel?.type === 'instance';

  return (
    <ErpNavContext.Provider value={openByObjectId}>
    {/* 100dvh statt 100vh: auf Mobile berücksichtigt die dynamische Viewport-Höhe die
        Browser-Leiste – sonst rutscht der «+»-FAB (bottom) unter die Adressleiste (unsichtbar). */}
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - 72px)' }}>
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
                onClick={() => setFeedCapture(true)}
                data-tip="Scannen oder Dokument erfassen"
                data-tip-pos="bottom"
                aria-label="Scannen oder Dokument erfassen"
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
          {viewerRole === 'staff' && (
            <div ref={plusRef} className="absolute left-5 bottom-5 z-20">
              {plusOpen && (
                <div className="absolute left-0 bottom-[calc(100%+10px)] bg-bg-1 border border-border-1 rounded-ds-md shadow-ds-lg p-1 min-w-[170px]">
                  <button onClick={() => startCreate('article')} style={menuItemStyle}>
                    <Package size={15} style={{ color: 'var(--fg-3)' }} /> Artikel
                  </button>
                  <button onClick={() => startCreate('order')} style={menuItemStyle}>
                    <ClipboardList size={15} style={{ color: 'var(--fg-3)' }} /> Auftrag
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
          {creating === 'article' && (
            <ArticleDetail key="new-article" record={null} suppliers={suppliers} mapsApiKey={mapsApiKey} onSaved={handleArticleSaved} onCancel={cancelCreate} onBack={cancelCreate} />
          )}
          {creating === 'order' && (
            <OrderDetail key="new-order" record={null} articles={articles} viewerRole={viewerRole} company={settings} suppliers={suppliers} onSaved={handleOrderSaved} onCancel={cancelCreate} onBack={cancelCreate} />
          )}
          {!creating && activeRow?.type === 'user' && (
            <UserDetail key={activeRow.key} record={activeRow.data} onSave={handleUserSaved} isAdmin={isAdmin} onBack={() => setMobileView('list')} />
          )}
          {!creating && activeRow?.type === 'article' && (
            <ArticleDetail key={activeRow.key} record={activeRow.data} suppliers={suppliers} mapsApiKey={mapsApiKey} onSaved={handleArticleSaved} onRefresh={() => api.getArticles().then(setArticles).catch(() => {})} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
          )}
          {!creating && sel?.type === 'order' && (
            orderDetail && orderDetail.object_id === sel.objectId ? (
              <OrderDetail key={`order-${sel.objectId}`} record={orderDetail} articles={articles} viewerRole={viewerRole} company={settings} suppliers={suppliers} onSaved={handleOrderSaved} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
            ) : (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: '#94a3b8' }}>
                Auftrag wird geladen…
              </div>
            )
          )}
          {!creating && sel?.type === 'instance' && instanceDetail && (
            <InstanceDetail key={`i-${sel.objectId}`} record={instanceDetail} onBack={() => setMobileView('list')}
              onChanged={() => { api.getOrders().then(setOrders).catch(() => {}); reloadInstances(); }} />
          )}
          {!creating && activeRow?.type === 'organization' && (
            <OrganizationDetail key={activeRow.key} record={activeRow.data}
              onSaved={(s) => setSettings(s)} onBack={() => setMobileView('list')} />
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
      {feedCapture && (
        <DocumentIngestDialog
          contextObjectId={null}
          captureEnabled={viewerRole === 'staff'}
          title={viewerRole === 'staff' ? 'Scannen oder Dokument erfassen' : 'Datensatz scannen'}
          onCode={(oid) => { setFeedCapture(false); openByObjectId(oid); }}
          onClose={() => setFeedCapture(false)}
          onDone={() => setFeedCapture(false)}
        />
      )}
    </div>
    </ErpNavContext.Provider>
  );
}

const menuItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '9px 11px', borderRadius: 8, border: 'none', background: 'none',
  fontSize: 13, fontWeight: 600, color: 'var(--fg-2)', cursor: 'pointer', textAlign: 'left',
};
