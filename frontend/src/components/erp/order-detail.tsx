'use client';

import { useEffect, useState } from 'react';
import { ClipboardList, ArrowUp, ArrowDown } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderDraft } from '@/types';
import { TYPE_META } from '@/lib/erp-record';
import { orderName } from '@/lib/record-name';
import { orderStatus } from '@/lib/record-status';
import { DetailHeader, HeaderAction } from '@/components/erp/fields';
import { DetailTabs } from '@/components/erp/detail-tabs';

// Genau EIN Reiter. Er steht hier oben, weil es dabei bleibt: der Auftrag bekommt
// keine weiteren – auch keine leeren oder deaktivierten.
const TABS = [{ key: 'auftrag' as const, label: 'Auftrag', icon: ClipboardList }];

/**
 * Auftrag – Detailfenster.
 *
 * **Der Entwurf lebt nur hier.** `record === null` heisst: es gibt in der Datenbank
 * nichts, keine Entwurfs-Zeile, keine vorreservierte Objektnummer, kein Autosave. Der
 * Kopf zeigt darum statt einer Nummer einen Gedankenstrich, und wer das Fenster
 * verlässt, lässt keine Spur. Gespeichert wird über den Knopf – und **erst dann**
 * entsteht die Objektnummer.
 *
 * Ob gespeichert werden darf, entscheidet der Server (`POST /erp/orders/validate` →
 * `services/orders.validate_draft`). Die Oberfläche formuliert die Regel nicht nach,
 * sie fragt sie ab: sonst gäbe es zwei Massstäbe für dieselbe Frage.
 */
export function OrderDetail({ record, onSaved, onBack }: {
  record: Order | null;              // null ⇒ Entwurf (existiert nur im Browser)
  onSaved: (o: Order) => void;
  onBack?: () => void;
}) {
  const isDraft = record === null;
  const meta = TYPE_META.order;

  // Der Entwurfs-Inhalt. Heute leer, weil der Auftrag noch keine Felder trägt – die
  // kommen mit der Prozesslogik und werden hier eingehängt.
  const [draft] = useState<OrderDraft>({});
  const [missing, setMissing] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Speicherbarkeit beim Server erfragen, nicht selbst behaupten.
  useEffect(() => {
    if (!isDraft) { setMissing(null); return; }
    let dead = false;
    api.validateOrder(draft)
      .then((v) => { if (!dead) setMissing(v.missing ?? []); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [isDraft, draft]);

  async function save() {
    setBusy(true); setError(null);
    try {
      onSaved(await api.createOrder(draft));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const blocked = missing != null && missing.length > 0;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        icon={meta.icon}
        iconBg={meta.bg}
        iconFg={meta.fg}
        eyebrow={meta.label}
        title={orderName()}
        objectId={record?.object_id ?? null}
        objectIdText={isDraft ? '—' : undefined}
        objectIdHint={isDraft
          ? 'Die Objektnummer entsteht erst beim Speichern. Bis dahin existiert dieser Auftrag nur in diesem Fenster.'
          : undefined}
        status={record ? orderStatus(record) : undefined}
        actions={isDraft ? (
          <HeaderAction
            label="Speichern"
            hint={blocked ? `Es fehlt: ${missing!.join(', ')}` : undefined}
            disabled={busy || blocked}
            onClick={save}
          />
        ) : undefined}
        onBack={onBack}
        // Genau EIN Reiter – keine leeren, keine deaktivierten.
        tabs={<DetailTabs tabs={TABS} active="auftrag" onChange={() => {}} />}
      />

      <div className="flex-1 p-5" style={{ background: 'var(--bg-2)' }}>
        {error && (
          <p className="mb-3 text-sm" style={{ color: 'var(--danger)' }}>{error}</p>
        )}

        {/* Drei Spuren: links woher der Auftrag kommt, in der Mitte was er tut,
            rechts was aus ihm hervorgeht. Links und rechts sind Platzhalter und sagen
            das auch – keine Beispieldaten, keine erfundene Logik. */}
        <div className="grid gap-3 items-stretch"
          style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.4fr) minmax(0,1fr)' }}>
          <Lane
            icon={ArrowUp}
            title="Übergeordnete Aufträge"
            note="Platzhalter – kommt mit der Prozesslogik."
          />
          <ProcessLane />
          <Lane
            icon={ArrowDown}
            title="Untergeordnete Aufträge"
            note="Platzhalter – kommt mit der Prozesslogik."
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Eine Platzhalter-Spur. Sie ist sichtbar als solche gekennzeichnet (gestrichelt,
 * gedämpft, mit Begründung) – damit niemand sie für einen leeren Datenbestand hält.
 */
function Lane({ icon: Icon, title, note }: {
  icon: React.ElementType; title: string; note: string;
}) {
  return (
    <div
      className="rounded-ds-lg p-4 flex flex-col items-center justify-center text-center gap-2 min-h-[320px]"
      style={{ border: '1px dashed var(--border-2)', background: 'transparent' }}
    >
      <Icon size={18} style={{ color: 'var(--fg-4)' }} />
      <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
        {title}
      </span>
      <span className="text-xs" style={{ color: 'var(--fg-4)' }}>{note}</span>
    </div>
  );
}

/**
 * Die Mitte: hier läuft der Prozess. Heute ein leerer, vorbereiteter Container –
 * die Prozesslogik ist der nächste Schritt und wird bewusst noch nicht angefangen.
 */
function ProcessLane() {
  return (
    <div
      className="rounded-ds-lg p-4 flex flex-col items-center justify-center text-center gap-2 min-h-[320px]"
      style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)' }}
    >
      <ClipboardList size={20} style={{ color: 'var(--fg-4)' }} />
      <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
        Prozess
      </span>
      <span className="text-xs" style={{ color: 'var(--fg-4)' }}>
        Noch nicht definiert.
      </span>
    </div>
  );
}
