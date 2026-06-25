'use client';

import { useState } from 'react';
import { Wrench, Lock, CheckCircle2, Package, Boxes, ScanLine, Info } from 'lucide-react';
import { api } from '@/lib/api';
import type {
  Order, OrderResourceLine, OrderResourceProduct, ResourceToolPickInput,
} from '@/types';
import type { ScanStep } from '@/lib/scan';
import { ObjId } from '@/components/erp/obj-id';
import { fmtObjId } from '@/components/erp/user-detail';
import { PrimaryButton } from '@/components/erp/fields';
import { instanceKindLabel } from '@/lib/process';
import { unitLabel } from '@/lib/article';
import { useScan } from '@/components/scan/scan-provider';

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
  const scan = useScan();

  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Validierungs-Fortschritt bleibt bei Abbruch erhalten: bereits vollständig
  // gescannte Produkt-Instanzen bzw. Betriebsmittel werden gemerkt; bei Wieder-
  // aufnahme wird die nächste offene Produkt-Instanz erneut von der übergeordneten
  // Instanz an gescannt.
  const [vProducts, setVProducts] = useState<number[]>([]);
  const [vTools, setVTools] = useState<Record<number, number>>({});

  const consumeOk = consumeLines.every((l) => l.sufficient !== false);
  const toolsOk = toolLines.every((l) => (l.candidates?.length ?? 0) > 0);
  const productCount = consumeLines.length > 0 ? products.length : 0;
  const validatedCount = vProducts.length + Object.keys(vTools).length;
  const totalToValidate = productCount + toolLines.length;
  const inProgress = validatedCount > 0 && validatedCount < totalToValidate;

  // Eine Einheit (Produkt-Instanz ODER Betriebsmittel) pro Scan-Session validieren –
  // nach jeder vollständigen Session den Fortschritt speichern und fortfahren.
  function resume(accProducts: number[], accTools: Record<number, number>) {
    if (consumeLines.length > 0) {
      const p = products.find((pp) => !accProducts.includes(pp.instance_id));
      if (p) {
        const steps: ScanStep[] = [
          { label: `Produkt-Instanz ${fmtObjId(p.instance_id)}`, hint: 'Übergeordnete Instanz scannen', kind: 'instance',
            expected: p.instance_id, candidates: [{ objectId: p.instance_id, label: instanceKindLabel(p.kind) }] },
          ...(p.components ?? []).map((c) => ({
            label: `Komponente ${fmtObjId(c.instance_id)}`,
            hint: `${c.article_name ?? ''} in ${fmtObjId(p.instance_id)} verbauen`,
            kind: 'instance' as const,
            expected: c.instance_id,
            candidates: [{ objectId: c.instance_id, label: c.article_name ?? 'Komponente' }],
          })),
        ];
        scan({
          title: `Verbrauch · ${fmtObjId(p.instance_id)}`,
          steps,
          onComplete: () => { const np = [...accProducts, p.instance_id]; setVProducts(np); resume(np, accTools); },
        });
        return;
      }
    }
    const tl = toolLines.find((l) => accTools[l.article_id] == null);
    if (tl) {
      scan({
        title: `Betriebsmittel · ${tl.article_name ?? ''}`,
        steps: [{
          label: `Betriebsmittel: ${tl.article_name ?? `#${tl.article_id}`}`,
          hint: 'Genutztes Betriebsmittel scannen', kind: 'instance', restrict: true,
          candidates: (tl.candidates ?? []).map((c) => ({ objectId: c.object_id, label: tl.article_name ?? '' })),
        }],
        onComplete: ([id]) => { const nt = { ...accTools, [tl.article_id]: id }; setVTools(nt); resume(accProducts, nt); },
      });
      return;
    }
    // Alles validiert → buchen
    const tools: ResourceToolPickInput[] = toolLines.map((l) => ({
      article_id: l.article_id, instance_ids: accTools[l.article_id] != null ? [accTools[l.article_id]] : [],
    }));
    record(tools);
  }

  function startScan() { setError(null); resume(vProducts, vTools); }

  async function record(tools: ResourceToolPickInput[]) {
    setSaving(true); setError(null);
    try {
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

      {!done && (
        <div style={infoStyle}>
          <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Verbrauchte Komponenten werden in die Produkt-Instanz eingebaut, Betriebsmittel an deren Standort gebracht – der Standort wandert mit dem Produkt mit.</span>
        </div>
      )}

      {/* Betriebsmittel: was gebraucht wird (Auswahl erfolgt per Scan) */}
      {!done && toolLines.map((l, i) => <ToolNeed key={`t${i}`} line={l} />)}

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
            {products.map((p) => <ProductCard key={p.instance_id} product={p} validated={vProducts.includes(p.instance_id)} />)}
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
          <PrimaryButton icon={ScanLine} onClick={startScan} disabled={saving || !consumeOk || !toolsOk}>
            {saving ? 'Speichert…' : inProgress ? `Fortsetzen (${validatedCount}/${totalToValidate})` : 'Scannen & buchen'}
          </PrimaryButton>
        </>
      )}
    </div>
  );
}

// Verbrauch je Produkt-Instanz: Kopf = Produkt, Liste = eingebaute Komponenten
function ProductCard({ product, validated }: { product: OrderResourceProduct; validated?: boolean }) {
  const comps = product.components ?? [];
  return (
    <div style={{ ...lineBox, borderColor: validated ? '#bbf7d0' : '#f1f5f9' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Boxes size={14} style={{ color: '#0f766e' }} />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#0F172A' }}>{instanceKindLabel(product.kind)}</span>
        <ObjId value={product.instance_id} />
        {validated
          ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 700, color: '#16a34a', marginLeft: 'auto' }}><CheckCircle2 size={12} /> validiert</span>
          : <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>Produkt-Instanz</span>}
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
        {line.article_object_id != null && <span style={{ fontFamily: 'monospace', color: '#0f172a' }}>{fmtObjId(line.article_object_id)} · </span>}
        {line.article_name ?? `#${line.article_id}`}
        <span style={{ color: '#94a3b8' }}> · {line.quantity}{line.unit ? ` ${unitLabel(line.unit)}` : ''}/Stk</span>
      </span>
      <span style={{ fontWeight: 700, color: ok ? '#16a34a' : '#dc2626' }}>
        benötigt {line.need} · verfügbar {line.available}
      </span>
    </div>
  );
}

function ToolNeed({ line }: { line: OrderResourceLine }) {
  const none = (line.candidates?.length ?? 0) === 0;
  return (
    <div style={lineBox}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Wrench size={14} style={{ color: '#2563eb' }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#0F172A', flex: 1 }}>{line.article_name ?? `#${line.article_id}`}</span>
        <span style={{ fontSize: 11, color: none ? '#dc2626' : '#94a3b8' }}>
          {none ? 'kein Betriebsmittel verfügbar' : 'Betriebsmittel · per Scan wählen'}
        </span>
      </div>
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
const infoStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px',
  background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 12, color: '#1e40af',
};
const lineBox: React.CSSProperties = {
  border: '1px solid #f1f5f9', borderRadius: 8, padding: '8px 10px',
  display: 'flex', flexDirection: 'column', gap: 6,
};
const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px',
  borderRadius: 12, fontSize: 12, border: '1px solid #e2e8f0', background: '#f8fafc', color: '#475569',
};
