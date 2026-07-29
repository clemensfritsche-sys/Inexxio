'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Package, ClipboardList, Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { DeactivationImpact, OrdersMode } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { Dialog, ChoiceButton, PrimaryButton } from '@/components/erp/fields';

// Banner «Ersetzt durch …» / «Ersetzt …» – Nachvollziehbarkeit der Ersetzen-Kette.
export function ReplacedBanner({ replacedBy, replaces }: { replacedBy: number | null; replaces: number | null }) {
  if (replacedBy == null && replaces == null) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, padding: '6px 10px', borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--border-1)', fontSize: 12, color: 'var(--fg-3)' }}>
      {replacedBy != null && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Ersetzt durch <ObjId value={replacedBy} /></span>}
      {replaces != null && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Ersetzt <ObjId value={replaces} /></span>}
    </div>
  );
}

/**
 * Dialog für «Deaktivieren» / «Ersetzen».
 *
 * **Der Klick auf den Weg IST die Ausführung** (Notiz #155): früher wählte man erst eine
 * Option und bestätigte sie darunter noch einmal – zwei Schritte für eine Entscheidung.
 * Jetzt führen die Wege selbst aus, es gibt kein ×, kein «Abbrechen» und keine
 * hervorgehobene Vorauswahl (#152–#154); geschlossen wird per Klick daneben oder `Esc`.
 *
 * Die **Wirkungsanalyse** bleibt – sie ist die Tatsachengrundlage der Entscheidung, nicht
 * ihre Erklärung. Die erläuternden Unterzeilen sind entfallen (#148–#150).
 *
 * Die einzige Angabe, die vorab gewählt werden MUSS, ist der Umgang mit laufenden
 * Aufträgen (Auslaufen ↔ Abbrechen) – sie ändert die Wirkung, nicht den Weg, und bleibt
 * darum eine Auswahl.
 */
export function DeactivateDialog({ mode, articleObjectId, title, message, confirmLabel, offerSuccessor, onConfirm, onClose }: {
  mode: 'deactivate' | 'replace';
  articleObjectId?: number | null;   // gesetzt ⇒ Wirkungsanalyse (Artikel) laden
  title: string;
  message?: string;
  confirmLabel: string;
  offerSuccessor?: boolean;          // gesetzt ⇒ optional einen Nachfolger anlegen («Ersetzen»)
  onConfirm: (ordersMode: OrdersMode, createSuccessor: boolean) => Promise<void>;
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

  async function run(createSuccessor: boolean) {
    setBusy(true); setError(null);
    try {
      await onConfirm(ordersMode, createSuccessor);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
      setBusy(false);
    }
  }

  return (
    <Dialog icon={AlertTriangle} title={title} width={440} onClose={onClose}>
      {message && <p style={{ fontSize: 13, color: 'var(--fg-2)', margin: 0 }}>{message}</p>}

      {loading ? (
        <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Wirkungsanalyse…</div>
      ) : impact && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ImpactRow icon={Package} label="Mitbetroffene Artikel"
            detail={articles.length === 0 ? 'keine' : articles.map((a) => fmtObjId(a.object_id ?? null)).join(', ')} />
          <ImpactRow icon={ClipboardList} label="Laufende Aufträge"
            detail={orders.length === 0 ? 'keine' : `${orders.length} · ${orders.map((o) => fmtObjId(o.object_id ?? null)).join(', ')}`} />
          <ImpactRow icon={Boxes} label="Lagerbestand" detail={stock === 0 ? 'keiner' : `${stock} Stück`} />
        </div>
      )}

      {hasOrders && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--fg-2)' }}>Laufende Aufträge</span>
          <ModeOption active={ordersMode === 'phase_out'} onClick={() => setOrdersMode('phase_out')}
            title="Auslaufen lassen" desc="Laufende Aufträge dürfen normal fertig werden." />
          <ModeOption active={ordersMode === 'cancel'} onClick={() => setOrdersMode('cancel')}
            title="Abbrechen" desc="Freigegebene Aufträge werden abgebrochen – ihre Instanzen gehen in einen Folgeauftrag." />
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

      {/* Zwei gleichwertige Wege statt Auswahl + Bestätigung – der Klick führt aus.
          «Ersetzen» ist der prägnante Name für «Nachfolger anlegen (Ersatz)» (#151):
          derselbe Vorgang, den der Artikel-Kopf ohnehin so nennt. */}
      {offerSuccessor ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ChoiceButton disabled={busy || loading} onClick={() => run(false)} title="Deaktivieren" />
          <ChoiceButton disabled={busy || loading} onClick={() => run(true)} title="Ersetzen" />
        </div>
      ) : (
        <PrimaryButton onClick={() => run(false)} disabled={busy || loading}>
          {busy ? '…' : confirmLabel}
        </PrimaryButton>
      )}
    </Dialog>
  );
}

// Nur die Tatsache – die erklärenden Unterzeilen sind entfallen (#148).
function ImpactRow({ icon: Icon, label, detail }: { icon: React.ElementType; label: string; detail: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 13 }}>
      <Icon size={15} style={{ color: 'var(--fg-3)', flexShrink: 0, marginTop: 1 }} />
      <div style={{ minWidth: 0 }}>
        <span style={{ color: 'var(--fg-4)' }}>{label}: </span>
        <span style={{ color: 'var(--fg-1)', fontWeight: 600 }}>{detail}</span>
      </div>
    </div>
  );
}

function ModeOption({ active, onClick, title, desc }: { active: boolean; onClick: () => void; title: string; desc: string }) {
  return (
    <button onClick={onClick} type="button"
      style={{ textAlign: 'left', padding: '8px 10px', borderRadius: 'var(--r-sm)', cursor: 'pointer',
        border: `1px solid ${active ? 'var(--fg-1)' : 'var(--border-1)'}`, background: '#fff' }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg-1)' }}>{title}</div>
      <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{desc}</div>
    </button>
  );
}

