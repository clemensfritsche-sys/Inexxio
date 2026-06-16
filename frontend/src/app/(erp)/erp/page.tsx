'use client';

import { useState, useEffect, useRef } from 'react';
import { Search, Plus, Users, Package, ClipboardList, Warehouse, ChevronDown } from 'lucide-react';
import { cn, userDisplayName } from '@/lib/utils';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Order, StorageLocation, UserProfile, ErpRecordType } from '@/types';
import { statusConfig } from '@/lib/article';
import { orderStatusConfig } from '@/lib/order';
import { storageStatusConfig } from '@/lib/storage-location';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { ROLE_CFG, userInitials, fmtObjId, UserDetail } from '@/components/erp/user-detail';
import { ArticleDetail } from '@/components/erp/article-detail';
import { OrderDetail } from '@/components/erp/order-detail';
import { StorageLocationDetail } from '@/components/erp/storage-location-detail';

// ─── Type metadata ───────────────────────────────────────────────────────────

const TYPE_META: Record<ErpRecordType, { label: string; icon: React.ElementType }> = {
  user:             { label: 'Benutzer',   icon: Users },
  article:          { label: 'Artikel',    icon: Package },
  order:            { label: 'Auftrag',    icon: ClipboardList },
  storage_location: { label: 'Lagerplatz', icon: Warehouse },
};

const FILTER_TYPES: ErpRecordType[] = ['user', 'article', 'order', 'storage_location'];

type Row =
  | { type: 'user'; key: string; objectId: number | null; data: UserProfile }
  | { type: 'article'; key: string; objectId: number | null; data: Article }
  | { type: 'order'; key: string; objectId: number | null; data: Order }
  | { type: 'storage_location'; key: string; objectId: number | null; data: StorageLocation };

function rowTitle(row: Row): string {
  if (row.type === 'user') return userDisplayName(row.data);
  if (row.type === 'order') return 'Auftrag';   // starr – Auftrag trägt keinen freien Namen
  if (row.type === 'storage_location') return 'Lagerplatz';
  return row.data.name; // article
}

function rowSearchText(row: Row): string {
  const id = String(row.objectId ?? '');
  if (row.type === 'user') return `${userDisplayName(row.data)} ${row.data.email} ${id}`.toLowerCase();
  if (row.type === 'article') return `${row.data.name} ${row.data.size} ${id}`.toLowerCase();
  if (row.type === 'order') return `auftrag ${row.data.article_name ?? ''} ${id}`.toLowerCase();
  return `${row.data.name} ${row.data.address_city ?? ''} ${id}`.toLowerCase();
}

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick }: { row: Row; sel: boolean; onClick: () => void }) {
  const title = rowTitle(row);
  const hasTitle = row.type === 'user' ? title !== row.data.email : !!title;

  let badge: { label: string; color: string; bg: string };
  if (row.type === 'user') badge = ROLE_CFG[row.data.role] ?? ROLE_CFG.customer;
  else if (row.type === 'article') badge = statusConfig(row.data.status);
  else if (row.type === 'order') {
    // Bei laufendem Prozess den Beschaffungsstatus zeigen, sonst den Auftragsstatus
    badge = row.data.status === 'released' && row.data.purchase
      ? purchaseStatusConfig(row.data.purchase.status)
      : orderStatusConfig(row.data.status);
  }
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
          <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4, background: badge.bg, color: badge.color }}>{badge.label}</span>
        </div>
      </div>
    </button>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ErpPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
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
  const plusRef = useRef<HTMLDivElement>(null);

  const mapsApiKey = settings?.google_maps_api_key ?? null;
  const suppliers = users.filter((u) => u.role === 'supplier');

  useEffect(() => {
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
    api.getPublicSettings().then(setSettings).catch(() => {});
  }, []);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setPlusOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const rows: Row[] = [
    ...users.map((u): Row => ({ type: 'user', key: `u${u.id}`, objectId: u.object_id, data: u })),
    ...articles.map((a): Row => ({ type: 'article', key: `a${a.id}`, objectId: a.object_id, data: a })),
    ...orders.map((o): Row => ({ type: 'order', key: `o${o.id}`, objectId: o.object_id, data: o })),
    ...storageLocations.map((l): Row => ({ type: 'storage_location', key: `l${l.id}`, objectId: l.object_id, data: l })),
  ].sort((x, y) => (x.objectId ?? Infinity) - (y.objectId ?? Infinity));

  const counts = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.type] = (acc[r.type] ?? 0) + 1;
    return acc;
  }, {});

  const filtered = rows.filter((r) => {
    if (typeFilter && r.type !== typeFilter) return false;
    if (search && !rowSearchText(r).includes(search.toLowerCase())) return false;
    return true;
  });

  const selectedRow = sel ? rows.find((r) => r.type === sel.type && r.objectId === sel.objectId) ?? null : null;

  function handleSelect(type: ErpRecordType, objectId: number | null) {
    if (objectId == null) return;
    setCreating(null);
    setSel({ type, objectId });
    setMobileView('detail');
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
    setOrders((prev) => (prev.some((x) => x.id === o.id) ? prev.map((x) => (x.id === o.id ? o : x)) : [...prev, o]));
    setCreating(null);
    if (o.object_id != null) setSel({ type: 'order', objectId: o.object_id });
    // Bestellungen beeinflussen die Stückpreis-Spanne der Artikel → neu laden
    api.getArticles().then(setArticles).catch(() => {});
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
  const hasDetail = creating !== null || selectedRow !== null;

  return (
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
            <div style={{ position: 'relative' }}>
              <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Name, Bezeichnung, Nummer…"
                style={{
                  width: '100%', paddingLeft: 30, paddingRight: 12, paddingTop: 7, paddingBottom: 7,
                  fontSize: 13, border: '1px solid #E2E8F0', borderRadius: 8, background: '#F8FAFC',
                  outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>
            {/* Type tag filters */}
            <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
              {FILTER_TYPES.filter((t) => counts[t]).map((t) => {
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
                    <Icon size={12} /> {TYPE_META[t].label} {counts[t]}
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
            {filtered.map((r) => (
              <FeedItem
                key={r.key}
                row={r}
                sel={!creating && !!sel && sel.type === r.type && sel.objectId === r.objectId}
                onClick={() => handleSelect(r.type, r.objectId)}
              />
            ))}
          </div>
        </div>

        {/* ── Detail panel ─────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-1 overflow-hidden flex flex-col',
          !showList ? 'flex' : 'hidden md:flex',
        )}>
          {creating === 'article' && (
            <ArticleDetail key="new-article" record={null} suppliers={suppliers} onSaved={handleArticleSaved} onCancel={cancelCreate} onBack={cancelCreate} />
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
            <ArticleDetail key={selectedRow.key} record={selectedRow.data} suppliers={suppliers} onSaved={handleArticleSaved} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
          )}
          {!creating && selectedRow?.type === 'order' && (
            <OrderDetail key={selectedRow.key} record={selectedRow.data} articles={articles} viewerRole={viewerRole} company={settings} onSaved={handleOrderSaved} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
          )}
          {!creating && selectedRow?.type === 'storage_location' && (
            <StorageLocationDetail key={selectedRow.key} record={selectedRow.data} mapsApiKey={mapsApiKey} onSaved={handleStorageSaved} onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
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
  );
}

const menuItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '8px 10px', borderRadius: 7, border: 'none', background: 'none',
  fontSize: 13, fontWeight: 500, color: '#374151', cursor: 'pointer', textAlign: 'left',
};
