'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Plus, Users, Package, ClipboardList, Warehouse, Boxes, ChevronDown, ScanLine, X, Repeat, Loader2, Building2 } from 'lucide-react';
import { cn, userDisplayName } from '@/lib/utils';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderSummary, PurchaseOrderStatus, StorageLocation, UserProfile, ErpRecordType } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';
import { statusConfig } from '@/lib/article';
import { orderStatusConfig, deviationBadge } from '@/lib/order';
import { storageStatusConfig } from '@/lib/storage-location';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { instanceStatusConfig } from '@/lib/process';
import { ROLE_CFG, userInitials, fmtObjId, UserDetail } from '@/components/erp/user-detail';
import { ErpNavContext } from '@/components/erp/obj-id';
import { useScan } from '@/components/scan/scan-provider';
import { ArticleDetail } from '@/components/erp/article-detail';
import { OrderDetail } from '@/components/erp/order-detail';
import { InstanceDetail } from '@/components/erp/instance-detail';
import { StorageLocationDetail } from '@/components/erp/storage-location-detail';
import { OrganizationDetail } from '@/components/erp/organization-detail';

// ─── Type metadata ───────────────────────────────────────────────────────────

const TYPE_META: Record<ErpRecordType, { label: string; icon: React.ElementType }> = {
  user:             { label: 'Benutzer',     icon: Users },
  article:          { label: 'Artikel',      icon: Package },
  order:            { label: 'Auftrag',      icon: ClipboardList },
  instance:         { label: 'Instanzen',    icon: Boxes },
  storage_location: { label: 'Lagerplatz',   icon: Warehouse },
  organization:     { label: 'Unternehmen',  icon: Building2 },
};

// 'organization' erscheint nur für Admins als Chip (displayCount blendet 0-Zähler aus).
const FILTER_TYPES: ErpRecordType[] = ['user', 'article', 'order', 'instance', 'storage_location', 'organization'];
const INSTANCE_PAGE = 100;   // Seitengrösse des server-paginierten Instanz-Feeds

type Row =
  | { type: 'user'; key: string; objectId: number | null; data: UserProfile }
  | { type: 'article'; key: string; objectId: number | null; data: Article }
  | { type: 'order'; key: string; objectId: number | null; data: OrderSummary }
  | { type: 'instance'; key: string; objectId: number | null; data: Instance }
  | { type: 'storage_location'; key: string; objectId: number | null; data: StorageLocation }
  | { type: 'organization'; key: string; objectId: number | null; data: CompanySettings };

function rowTitle(row: Row): string {
  if (row.type === 'user') return userDisplayName(row.data);
  if (row.type === 'order') return 'Auftrag';   // starr – Auftrag trägt keinen freien Namen
  if (row.type === 'instance') return 'Instanz';   // starr – Instanz trägt keinen freien Namen
  if (row.type === 'storage_location') return 'Lagerplatz';
  if (row.type === 'organization') return row.data.company_name || 'Unternehmen';
  return row.data.name; // article
}

function rowSearchText(row: Row): string {
  const id = String(row.objectId ?? '');
  if (row.type === 'user') return `${userDisplayName(row.data)} ${row.data.email} ${id}`.toLowerCase();
  if (row.type === 'article') return `${row.data.name} ${row.data.size} ${id}`.toLowerCase();
  if (row.type === 'order') return `auftrag ${row.data.article_name ?? ''} ${id}`.toLowerCase();
  if (row.type === 'instance') return `instanz ${row.data.article_name ?? ''} ${id}`.toLowerCase();
  if (row.type === 'organization') return `unternehmen firma ${row.data.company_name} ${id}`.toLowerCase();
  return `${row.data.name} ${row.data.address_city ?? ''} ${id}`.toLowerCase();
}

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick }: { row: Row; sel: boolean; onClick: () => void }) {
  const title = rowTitle(row);
  const hasTitle = row.type === 'user' ? title !== row.data.email : !!title;

  let badge: StatusCfg;
  if (row.type === 'user') badge = ROLE_CFG[row.data.role] ?? ROLE_CFG.customer;
  else if (row.type === 'article') badge = statusConfig(row.data.status);
  else if (row.type === 'order') {
    // Abweichung (Unter-Auftrag) hat Vorrang; dann wiederkehrend & fällig; sonst Status.
    // Die Abweichungs-Badge folgt dem Status (grün, sobald erledigt).
    badge = row.data.parent_order_id != null
      ? deviationBadge(row.data.status)
      : row.data.recurrence_due
        ? { label: 'fällig', color: '#dc2626', bg: '#fef2f2', icon: Repeat }
        : row.data.status === 'released' && row.data.purchase_status
          ? purchaseStatusConfig(row.data.purchase_status as PurchaseOrderStatus)
          : orderStatusConfig(row.data.status);
  }
  else if (row.type === 'instance') badge = instanceStatusConfig(row.data.quality, row.data.disposition, (row.data.reserved_quantity ?? 0) > 0);
  else if (row.type === 'organization') badge = { label: 'Stammdaten', color: '#0f766e', bg: '#f0fdfa', icon: Building2 };
  else badge = storageStatusConfig(row.data.status);

  const TypeIcon = TYPE_META[row.type].icon;

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px', width: '100%', textAlign: 'left',
        background: sel ? '#EFF6FF' : 'transparent',
        borderLeft: `3px solid ${sel ? '#2563eb' : 'transparent'}`,
        borderBottom: '1px solid #F1F5F9', cursor: 'pointer',
      }}
    >
      {row.type === 'user' ? (
        <div style={{
          width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
          background: row.data.photo_url ? 'transparent' : badge.bg, color: badge.color,
          overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 700,
        }}>
          {row.data.photo_url
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={row.data.photo_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : userInitials(title, row.data.email)}
        </div>
      ) : (
        <div style={{ width: 36, height: 36, borderRadius: 8, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <TypeIcon size={17} />
        </div>
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: hasTitle ? '#0F172A' : '#94a3b8', fontStyle: hasTitle ? 'normal' : 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {hasTitle ? title : (row.type === 'user' ? 'Kein Name' : 'Ohne Bezeichnung')}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
          <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: '#475569' }}>{fmtObjId(row.objectId)}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 999, background: badge.bg, color: badge.color }}>
            {badge.icon && <badge.icon size={11} strokeWidth={2.5} />}{badge.label}
          </span>
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
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
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
  const [creating, setCreating] = useState<'article' | 'order' | 'storage_location' | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [isAdmin, setIsAdmin] = useState(false);
  const [viewerRole, setViewerRole] = useState<'staff' | 'supplier'>('staff');
  const [plusOpen, setPlusOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(50);
  const plusRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  // Aktueller «mehr laden»-Handler (immer frisch, vom Sentinel-Observer aufgerufen).
  const loadMoreRef = useRef<() => void>(() => {});

  const mapsApiKey = settings?.google_maps_api_key ?? null;
  const suppliers = users.filter((u) => u.role === 'supplier');
  const scan = useScan();

  useEffect(() => {
    // Kern-Feeds (geringe Kardinalität) blockierend laden – die Shell erscheint
    // sofort. Instanzen (höchste Kardinalität) danach nachladen.
    Promise.allSettled([
      api.getErpRecords(), api.getArticles(), api.getOrders(),
      api.getStorageLocations(), api.getMe(),
    ]).then(([u, a, o, sl, me]) => {
      if (u.status === 'fulfilled') setUsers(u.value);
      if (a.status === 'fulfilled') setArticles(a.value);
      if (o.status === 'fulfilled') setOrders(o.value);
      if (sl.status === 'fulfilled') setStorageLocations(sl.value);
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

  // Instanz-Feed: server-paginiert + server-durchsucht. Lädt Seite 0 beim Start und
  // bei jeder (entprellten) Suchänderung neu; weitere Seiten via Infinite-Scroll.
  useEffect(() => {
    const q = search.trim();
    const t = setTimeout(() => {
      api.getInstances(INSTANCE_PAGE, 0, q).then(setInstances).catch(() => {});
      api.getInstanceCount(q).then((r) => setInstanceTotal(r.count)).catch(() => {});
    }, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setPlusOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

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
    ...storageLocations.map((l): Row => ({ type: 'storage_location', key: `l${l.id}`, objectId: l.object_id, data: l })),
  ].sort((x, y) => (y.objectId ?? -Infinity) - (x.objectId ?? -Infinity));   // höchste Nummer zuerst

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

  // Kamera-Scan im Feed → gescannten Datensatz öffnen. Kandidaten = alle Datensätze
  // (restrict): ein Code ausserhalb des ERP wird im Dialog abgewiesen, Kamera läuft weiter.
  function scanToOpen() {
    // Freier Lookup: jede gültige Objektnummer wird akzeptiert und serverseitig
    // aufgelöst (auch nicht geladene Instanzen). Kandidaten dienen der manuellen Suche.
    scan({
      title: 'Datensatz scannen',
      steps: [{
        label: 'Datensatz',
        hint: 'QR-/Barcode eines beliebigen Datensatzes',
        kind: 'object',
        candidates: rows
          .filter((r) => r.objectId != null)
          .map((r) => ({ objectId: r.objectId as number, label: `${rowTitle(r)} · ${TYPE_META[r.type].label}` })),
      }],
      onComplete: ([objectId]) => { openByObjectId(objectId); },
    });
  }

  function startCreate(type: 'article' | 'order' | 'storage_location') {
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

  function handleStorageSaved(loc: StorageLocation) {
    setStorageLocations((prev) => (prev.some((x) => x.id === loc.id) ? prev.map((x) => (x.id === loc.id ? loc : x)) : [...prev, loc]));
    setCreating(null);
    if (loc.object_id != null) setSel({ type: 'storage_location', objectId: loc.object_id });
  }

  function handleUserSaved(u: UserProfile) {
    setUsers((prev) => prev.map((x) => (x.id === u.id ? u : x)));
  }


  function cancelCreate() {
    setCreating(null);
    setMobileView('list');
  }

  const showList = mobileView === 'list';
  const hasDetail = creating !== null || selectedRow !== null || sel?.type === 'order' || sel?.type === 'instance';

  return (
    <ErpNavContext.Provider value={openByObjectId}>
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 72px)' }}>
      <div className="flex overflow-hidden" style={{ flex: 1, minHeight: 0 }}>

        {/* ── List panel ───────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-shrink-0 border-r border-slate-200 flex flex-col bg-white',
          'w-full md:w-[300px] lg:w-[340px]',
          showList ? 'flex' : 'hidden md:flex',
        )}>
          <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid #F1F5F9' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Datensätze</span>
              {viewerRole === 'staff' && (
              <div ref={plusRef} style={{ position: 'relative' }}>
                <button
                  onClick={() => setPlusOpen((o) => !o)}
                  style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                >
                  <Plus size={14} /> Neu <ChevronDown size={12} />
                </button>
                {plusOpen && (
                  <div style={{ position: 'absolute', right: 0, top: 'calc(100% + 4px)', background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: 4, zIndex: 30, minWidth: 160 }}>
                    <button onClick={() => startCreate('article')} style={menuItemStyle}>
                      <Package size={15} style={{ color: '#64748b' }} /> Artikel
                    </button>
                    <button onClick={() => startCreate('order')} style={menuItemStyle}>
                      <ClipboardList size={15} style={{ color: '#64748b' }} /> Auftrag
                    </button>
                    <button onClick={() => startCreate('storage_location')} style={menuItemStyle}>
                      <Warehouse size={15} style={{ color: '#64748b' }} /> Lagerplatz
                    </button>
                  </div>
                )}
              </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Name, Bezeichnung, Nummer…"
                  style={{
                    width: '100%', paddingLeft: 30, paddingRight: search ? 30 : 12, paddingTop: 7, paddingBottom: 7,
                    fontSize: 13, border: '1px solid #E2E8F0', borderRadius: 8, background: '#F8FAFC',
                    outline: 'none', boxSizing: 'border-box',
                  }}
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    title="Eingabe löschen"
                    aria-label="Eingabe löschen"
                    style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 20, height: 20, borderRadius: 5, border: 'none', background: '#e2e8f0', color: '#64748b', cursor: 'pointer' }}
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
              <button
                onClick={scanToOpen}
                title="Code scannen"
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  width: 36, borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff',
                  color: '#2563eb', cursor: 'pointer',
                }}
              >
                <ScanLine size={17} />
              </button>
            </div>
            {/* Type tag filters */}
            <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
              {FILTER_TYPES.filter((t) => displayCount(t)).map((t) => {
                const active = typeFilter === t;
                const Icon = TYPE_META[t].icon;
                return (
                  <button
                    key={t}
                    onClick={() => setTypeFilter(active ? null : t)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5,
                      padding: '3px 9px', borderRadius: 12,
                      border: `1px solid ${active ? '#2563eb' : '#E2E8F0'}`,
                      background: active ? '#eff6ff' : '#fff',
                      color: active ? '#2563eb' : '#64748b',
                      fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    <Icon size={12} /> {TYPE_META[t].label} {displayCount(t)}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading && <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>Laden…</div>}
            {!loading && filtered.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>
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
              <div ref={sentinelCb} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '14px', color: '#94a3b8', fontSize: 12 }}>
                <Loader2 size={15} className="animate-spin" />
                <span>Weitere werden geladen…</span>
              </div>
            )}
          </div>
        </div>

        {/* ── Detail panel ─────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-1 overflow-hidden flex flex-col',
          !showList ? 'flex' : 'hidden md:flex',
        )}>
          {creating === 'article' && (
            <ArticleDetail key="new-article" record={null} suppliers={suppliers} articleNames={settings?.article_names ?? []} onSaved={handleArticleSaved} onCancel={cancelCreate} onBack={cancelCreate} />
          )}
          {creating === 'order' && (
            <OrderDetail key="new-order" record={null} articles={articles} viewerRole={viewerRole} company={settings} onSaved={handleOrderSaved} onCancel={cancelCreate} onBack={cancelCreate} />
          )}
          {creating === 'storage_location' && (
            <StorageLocationDetail key="new-storage" record={null} mapsApiKey={mapsApiKey} onSaved={handleStorageSaved} onCancel={cancelCreate} onBack={cancelCreate} />
          )}
          {!creating && selectedRow?.type === 'user' && (
            <UserDetail key={selectedRow.key} record={selectedRow.data} onSave={handleUserSaved} isAdmin={isAdmin} onBack={() => setMobileView('list')} />
          )}
          {!creating && selectedRow?.type === 'article' && (
            <ArticleDetail key={selectedRow.key} record={selectedRow.data} suppliers={suppliers} articleNames={settings?.article_names ?? []} onSaved={handleArticleSaved} onRefresh={() => api.getArticles().then(setArticles).catch(() => {})} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
          )}
          {!creating && sel?.type === 'order' && (
            orderDetail && orderDetail.object_id === sel.objectId ? (
              <OrderDetail key={`order-${sel.objectId}`} record={orderDetail} articles={articles} viewerRole={viewerRole} company={settings} onSaved={handleOrderSaved} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
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
          {!creating && selectedRow?.type === 'storage_location' && (
            <StorageLocationDetail key={selectedRow.key} record={selectedRow.data} mapsApiKey={mapsApiKey} onSaved={handleStorageSaved} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
          )}
          {!creating && selectedRow?.type === 'organization' && (
            <OrganizationDetail key={selectedRow.key} record={selectedRow.data}
              onSaved={(s) => setSettings(s)} onBack={() => setMobileView('list')} />
          )}
          {!hasDetail && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Package size={48} strokeWidth={1} style={{ color: '#CBD5E1' }} />
              <p style={{ marginTop: 12, fontSize: 14, color: '#94a3b8' }}>Datensatz auswählen oder neu anlegen</p>
            </div>
          )}
        </div>
      </div>
    </div>
    </ErpNavContext.Provider>
  );
}

const menuItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '8px 10px', borderRadius: 7, border: 'none', background: 'none',
  fontSize: 13, fontWeight: 500, color: '#374151', cursor: 'pointer', textAlign: 'left',
};
