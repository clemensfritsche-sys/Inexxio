'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, X, Package, ClipboardList, Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { DeactivationImpact, OrdersMode } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';

// Banner «Ersetzt durch …» / «Ersetzt …» – Nachvollziehbarkeit der Ersetzen-Kette.
export function ReplacedBanner({ replacedBy, replaces }: { replacedBy: number | null; replaces: number | null }) {
  if (replacedBy == null && replaces == null) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, padding: '6px 10px', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: 12, color: '#64748b' }}>
      {replacedBy != null && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Ersetzt durch <ObjId value={replacedBy} /></span>}
      {replaces != null && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Ersetzt <ObjId value={replaces} /></span>}
    </div>
  );
}

// Dialog für «Inaktiv setzen» / «Ersetzen» – mit Wirkungsanalyse (nur Artikel) und
// der einen Entscheidung «Auslaufen vs. Abbrechen», sobald laufende Aufträge betroffen sind.
export function DeactivateDialog({ mode, articleObjectId, title, message, confirmLabel, onConfirm, onClose }: {
  mode: 'deactivate' | 'replace';
  articleObjectId?: number | null;   // gesetzt ⇒ Wirkungsanalyse (Artikel) laden
  title: string;
  message?: string;
  confirmLabel: string;
  onConfirm: (ordersMode: OrdersMode) => Promise<void>;
  onClose: () => void;
}) {
  const [impact, setImpact] = useState<DeactivationImpact | null>(null);
  const [loading, setLoading] = useState(articleObjectId != null);
  const [ordersMode, setOrdersMode] = useState<OrdersMode>('phase_out');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (articleObjectId == null) return;
    api.getArticleDeactivationImpact(articleObjectId)
      .then(setImpact).catch(() => {}).finally(() => setLoading(false));
  }, [articleObjectId]);

  const orders = impact?.orders ?? [];
  const articles = impact?.articles ?? [];
  const stock = impact?.stock ?? 0;
  const hasOrders = orders.length > 0;

  async function confirm() {
    setBusy(true); setError(null);
    try {
      await onConfirm(ordersMode);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
      setBusy(false);
    }
  }

  return (
    <div onClick={onClose} style={overlay}>
      <div onClick={(e) => e.stopPropagation()} style={card}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={18} style={{ color: '#d97706' }} />
          <span style={{ fontSize: 15, fontWeight: 700, color: '#0F172A', flex: 1 }}>{title}</span>
          <button onClick={onClose} style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2 }}><X size={18} /></button>
        </div>

        {message && <p style={{ fontSize: 13, color: '#475569', margin: 0 }}>{message}</p>}

        {loading ? (
          <div style={{ fontSize: 13, color: '#94a3b8' }}>Wirkungsanalyse…</div>
        ) : impact && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <ImpactRow icon={Package} label="Mitbetroffene Artikel"
              detail={articles.length === 0 ? 'keine' : articles.map((a) => fmtObjId(a.object_id ?? null)).join(', ')}
              hint={articles.length > 0 ? 'werden ebenfalls inaktiv (enthalten diesen Artikel)' : undefined} />
            <ImpactRow icon={ClipboardList} label="Laufende Aufträge"
              detail={orders.length === 0 ? 'keine' : `${orders.length} · ${orders.map((o) => fmtObjId(o.object_id ?? null)).join(', ')}`} />
            <ImpactRow icon={Boxes} label="Lagerbestand"
              detail={stock === 0 ? 'keiner' : `${stock} Stück`}
              hint={stock > 0 ? 'bleibt erhalten (Auslaufbestand, separat verschrottbar)' : undefined} />
          </div>
        )}

        {hasOrders && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Laufende Aufträge:</span>
            <ModeOption active={ordersMode === 'phase_out'} onClick={() => setOrdersMode('phase_out')}
              title="Auslaufen lassen (empfohlen)" desc="Laufende Aufträge dürfen normal fertig werden." />
            <ModeOption active={ordersMode === 'cancel'} onClick={() => setOrdersMode('cancel')}
              title="Abbrechen" desc="Aufträge abbrechen: Reservierungen frei, unfertige Instanzen verworfen." />
          </div>
        )}

        {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} disabled={busy} style={btnGhost}>Abbrechen</button>
          <button onClick={confirm} disabled={busy || loading}
            style={{ ...btnPrimary, background: mode === 'replace' ? '#2563eb' : '#dc2626' }}>
            {busy ? '…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function ImpactRow({ icon: Icon, label, detail, hint }: { icon: React.ElementType; label: string; detail: string; hint?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
      <Icon size={15} style={{ color: '#64748b', flexShrink: 0, marginTop: 1 }} />
      <div style={{ minWidth: 0 }}>
        <span style={{ color: '#94a3b8' }}>{label}: </span>
        <span style={{ color: '#0F172A', fontWeight: 600 }}>{detail}</span>
        {hint && <div style={{ fontSize: 11, color: '#94a3b8' }}>{hint}</div>}
      </div>
    </div>
  );
}

function ModeOption({ active, onClick, title, desc }: { active: boolean; onClick: () => void; title: string; desc: string }) {
  return (
    <button onClick={onClick} type="button"
      style={{ textAlign: 'left', padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
        border: `1px solid ${active ? '#2563eb' : '#e2e8f0'}`, background: active ? '#eff6ff' : '#fff' }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: active ? '#2563eb' : '#0F172A' }}>{title}</div>
      <div style={{ fontSize: 11, color: '#64748b' }}>{desc}</div>
    </button>
  );
}

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15,23,42,0.45)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
const card: React.CSSProperties = {
  background: '#fff', borderRadius: 12, padding: '18px 20px', width: '100%', maxWidth: 440,
  display: 'flex', flexDirection: 'column', gap: 14, boxShadow: '0 20px 48px rgba(0,0,0,0.25)',
};
const btnGhost: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff',
  color: '#374151', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const btnPrimary: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 8, border: 'none', color: '#fff',
  fontSize: 13, fontWeight: 700, cursor: 'pointer',
};
