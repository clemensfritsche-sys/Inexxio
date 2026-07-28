'use client';

import { Boxes, MapPin } from 'lucide-react';
import type { LocationType, Order } from '@/types';
import { instanceStatusConfig, instanceLabel, LOCATION_META } from '@/lib/process';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge } from '@/components/erp/fields';

// Read-only Übersicht der Bestands-Instanzen eines Auftrags. Die Instanzen
// entstehen bei der Auftragsfreigabe – mit Standort und den zwei Instanz-Achsen
// (quality/disposition) ab Tag 1.
export function OrderInstances({ order, embedded = false }: { order: Order; embedded?: boolean }) {
  const instances = order.instances ?? [];
  if (instances.length === 0) return null;
  const isBatch = order.article_serialization === 'batch';
  const unit = order.article_unit ?? '';

  // ``embedded``: als Block INNERHALB der Auftragsspezifikation statt als eigene Karte –
  // die Instanzen sind das Ergebnis derselben Aussage (Artikel + Menge), kein neues Thema.
  return (
    <div style={embedded ? embeddedStyle : cardStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Boxes size={15} style={{ color: 'var(--fg-3)' }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg-1)', flex: 1 }}>Instanzen</span>
        <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>
          {instances.length === 1 && isBatch
            ? `1 Charge à ${instances[0].quantity} ${unit}`.trim()
            : `${instances.length} Stück`}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 280, overflowY: 'auto' }}>
        {instances.map((i) => {
          const Icon = LOCATION_META[(i.location_type as LocationType)]?.icon ?? MapPin;
          return (
            <div key={i.id} style={rowStyle}>
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>
                {instanceLabel(i.kind, i.quantity, unit)}
              </span>
              {i.location_label && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}>
                  <Icon size={11} /> {i.location_label}
                  {i.location_type === 'instance' && i.physical_location_label && (
                    <span style={{ color: '#cbd5e1' }}> · {i.physical_location_label}</span>
                  )}
                </span>
              )}
              <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Eingebettet: nur eine Haarlinie oben trennt die Instanzen von den Positionen darüber –
// kein zweiter Rahmen um eine Karte.
const embeddedStyle: React.CSSProperties = {
  borderTop: '1px solid var(--border-1)', paddingTop: 14, marginTop: 2,
  display: 'flex', flexDirection: 'column', gap: 10,
};
const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 12,
};
const rowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px',
  border: '1px solid #f1f5f9', borderRadius: 8,
};
