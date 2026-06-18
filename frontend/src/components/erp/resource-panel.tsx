'use client';

import { useState } from 'react';
import { Wrench, Lock, CheckCircle2, Package, Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type {
  Order, OrderResourceLine, OrderResourceProduct, ResourceToolPickInput,
} from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { instanceKindLabel } from '@/lib/process';
import { unitLabel } from '@/lib/article';

export function ResourcePanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  onOrderUpdated: (o: Order) => void;
}) {
  const res = order.resource;
  const lines = (res?.lines ?? []) as OrderResourceLine[];
  const products = (res?.products ?? []) as OrderResourceProduct[];
  const done = !!res?.done;
  const consumeLines = lines.filter((l) => l.mode === 'consume');
  const toolLines = lines.filter((l) => l.mode === 'tool');

  const [picks, setPicks] = useState<Record<number, number[]>>({});
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(articleId: number, objId: number) {
    setPicks((p) => {
      const cur = p[articleId] ?? [];
      return { ...p, [articleId]: cur.includes(objId) ? cur.filter((x) => x !== objId) : [...cur, objId] };
    });
  }

  const consumeOk = consumeLines.every((l) => l.sufficient !== false);
  const toolsOk = toolLines.every((l) => (picks[l.article_id]?.length ?? 0) > 0);
  const canConfirm = consumeOk && toolsOk && !saving;

  async function confirm() {
    setSaving(true); setError(null);
    try {
      const tools: ResourceToolPickInput[] = toolLines.map((l) => ({
        article_id: l.article_id, instance_ids: picks[l.article_id] ?? [],
      }));
      onOrderUpdated(await api.updateOrderResource(order.object_id as number, {
        tools, note: note.trim() || null, step_id: stepId ?? null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally { setSaving(false); }
  }

  if (stepState === 'locked') {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Lock size={14} /> Wird aktiv, sobald der vorherige Schritt erledigt ist.
        </div>
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <Header />

      {done && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#f0fdf4', color: '#16a34a' }}>
          <CheckCircle2 size={16} />
          <span style={{ fontSize: 13, fontWeight: 700 }}>Ressourcen erfasst</span>
          {res?.used_by_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{res.used_by_name}</span>}
        </div>
      )}

      {/* Betriebsmittel wählen (nicht im Done-Zustand) */}
      {!done && toolLines.map((l, i) => (
        <ToolLine key={`t${i}`} line={l} selected={picks[l.article_id] ?? []} onToggle={(oid) => toggle(l.article_id, oid)} />
      ))}

      {/* Verbrauch je Produkt-Instanz: welche Komponenten-Instanz wird wohin verbaut */}
      {consumeLines.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <SubTitle>Verbrauch je Instanz {done ? '' : '(Vorschau, FIFO nach Freigabe)'}</SubTitle>
          {consumeLines.map((l, i) => <ConsumeAvailability key={`c${i}`} line={l} />)}
          {!consumeOk && (
            <div style={{ fontSize: 12, color: '#dc2626', fontWeight: 600 }}>
              Nicht genügend freigegebener Bestand für den Verbrauch.
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 340, overflowY: 'auto' }}>
            {products.map((p) => <ProductCard key={p.instance_id} product={p} />)}
          </div>
        </div>
      )}

      {/* Genutzte Betriebsmittel (Done-Zusammenfassung) */}
      {done && toolLines.map((l, i) => <ToolSummary key={`ts${i}`} line={l} />)}

      {res?.note && done && <div style={{ fontSize: 12, color: '#64748b' }}>Notiz: {res.note}</div>}

      {!done && (
        <>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Notiz (optional)"
            className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
          {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={confirm} disabled={!canConfirm}
              style={{ padding: '7px 16px', borderRadius: 7, border: 'none', background: canConfirm ? '#2563eb' : '#93c5fd', color: '#fff', fontSize: 13, fontWeight: 600, cursor: canConfirm ? 'pointer' : 'not-allowed' }}>
              {saving ? 'Speichert…' : 'Ressourcen buchen'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// Verbrauch je Produkt-Instanz: Kopf = Produkt, Liste = eingebaute Komponenten
function ProductCard({ product }: { product: OrderResourceProduct }) {
  const comps = product.components ?? [];
  return (
    <div style={lineBox}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Boxes size={14} style={{ color: '#0f766e' }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#0F172A' }}>{instanceKindLabel(product.kind)}</span>
        <ObjId value={product.instance_id} />
        <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>Produkt-Instanz</span>
      </div>
      {comps.length === 0 ? (
        <div style={{ fontSize: 12, color: '#cbd5e1' }}>Keine Komponenten.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {comps.map((c, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#475569' }}>
              <Package size={12} style={{ color: '#2563eb', flexShrink: 0 }} />
              <span style={{ flex: 1, minWidth: 0 }}>{c.article_name ?? `#${c.article_id}`}</span>
              <ObjId value={c.instance_id} />
              <span style={{ fontWeight: 700, color: '#0f172a' }}>×{c.quantity}</span>
              {c.split_from != null && (
                <span style={{ fontSize: 11, color: '#94a3b8' }}>(Teilcharge aus {String(c.split_from).padStart(9, '0')})</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConsumeAvailability({ line }: { line: OrderResourceLine }) {
  const ok = line.sufficient !== false;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
      <Package size={13} style={{ color: '#2563eb' }} />
      <span style={{ flex: 1, color: '#475569' }}>
        {line.article_name ?? `#${line.article_id}`}
        <span style={{ color: '#94a3b8' }}> · {line.quantity}{line.unit ? ` ${unitLabel(line.unit)}` : ''}/Stk</span>
      </span>
      <span style={{ fontWeight: 700, color: ok ? '#16a34a' : '#dc2626' }}>
        benötigt {line.need} · verfügbar {line.available}
      </span>
    </div>
  );
}

function ToolLine({ line, selected, onToggle }: {
  line: OrderResourceLine; selected: number[]; onToggle: (oid: number) => void;
}) {
  return (
    <div style={lineBox}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Wrench size={14} style={{ color: '#2563eb' }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', flex: 1 }}>{line.article_name ?? `#${line.article_id}`}</span>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>Betriebsmittel · wählen</span>
      </div>
      {(line.candidates?.length ?? 0) === 0 ? (
        <div style={{ fontSize: 12, color: '#dc2626' }}>Kein freigegebenes Betriebsmittel vorhanden.</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {line.candidates!.map((c) => {
            const on = selected.includes(c.object_id);
            return (
              <button key={c.object_id} type="button" onClick={() => onToggle(c.object_id)}
                style={{ padding: '4px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, fontFamily: 'monospace',
                  cursor: 'pointer', border: `1px solid ${on ? '#2563eb' : '#e2e8f0'}`,
                  background: on ? '#eff6ff' : '#fff', color: on ? '#2563eb' : '#64748b' }}>
                {c.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ToolSummary({ line }: { line: OrderResourceLine }) {
  return (
    <div style={lineBox}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Wrench size={14} style={{ color: '#2563eb' }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', flex: 1 }}>{line.article_name ?? `#${line.article_id}`}</span>
        <span style={{ fontSize: 11, color: '#94a3b8' }}>genutzt</span>
      </div>
      {(line.picked?.length ?? 0) > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {line.picked!.map((oid, i) => <span key={i} style={chip}><ObjId value={oid} /></span>)}
        </div>
      )}
    </div>
  );
}

function SubTitle({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
      {children}
    </span>
  );
}

function Header() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Wrench size={15} style={{ color: '#2563eb' }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Ressource</span>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
const lineBox: React.CSSProperties = {
  border: '1px solid #f1f5f9', borderRadius: 8, padding: '8px 10px',
  display: 'flex', flexDirection: 'column', gap: 6,
};
const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px',
  borderRadius: 12, fontSize: 12, border: '1px solid #e2e8f0', background: '#f8fafc', color: '#475569',
};
