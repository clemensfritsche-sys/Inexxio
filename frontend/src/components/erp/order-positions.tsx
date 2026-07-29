'use client';

import { Boxes, MapPin } from 'lucide-react';
import type { LocationType, Order, OrderInstance } from '@/types';
import { instanceStatusConfig, instanceLabel, LOCATION_META } from '@/lib/process';
import { unitLabel } from '@/lib/article';
import { ObjId } from '@/components/erp/obj-id';
import { StatusBadge, TileShell, TILE } from '@/components/erp/fields';

/**
 * **Was dieser Auftrag betrifft – in EINER Aufstellung.**
 *
 * Vorher stand dieselbe Aussage an zwei Stellen und in zwei Formen: oben die Positionen
 * (Artikel → Menge) als flache Liste, darunter alle Instanzen des Auftrags in einer
 * zweiten, ebenso flachen Liste. Bei mehreren Positionen war damit nicht erkennbar,
 * **welche Instanz zu welchem Artikel gehört** – die entscheidende Frage.
 *
 * Jetzt trägt jede Position ihre eigenen Instanzen unter sich (eingerückt an einer
 * Haarlinie). Der Einzel-Artikel-Auftrag ist dabei kein Sonderfall mehr, sondern schlicht
 * ein Auftrag mit EINER Position; ein Unter-Auftrag ohne Artikel zeigt nur seine
 * Instanzen. Eine Form für alle drei Fälle – und sie bricht auf schmalen Schirmen um,
 * statt zu überlaufen.
 */
export function OrderPositions({ order }: { order: Order }) {
  const groups = buildGroups(order);
  if (groups.length === 0) return null;

  const total = (order.instances ?? []).length;
  const onlyInstances = groups.length === 1 && !groups[0].name;

  return (
    <TileShell
      icon={Boxes}
      label={onlyInstances ? 'Instanzen' : groups.length === 1 ? 'Position' : 'Positionen'}
      style={{ gridColumn: '1 / -1' }}
      right={total > 0 && !onlyInstances
        ? <span style={countStyle}>{total === 1 ? '1 Instanz' : `${total} Instanzen`}</span>
        : undefined}
    >
      <div style={{ ...TILE.v, display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: 14, whiteSpace: 'normal', overflow: 'visible' }}>
        {groups.map((g) => (
          <div key={g.key}>
            {/* Kopfzeile der Position: Nummer · Artikel · Menge. */}
            {g.name && (
              <div style={headStyle}>
                {g.articleObjectId != null && <ObjId value={g.articleObjectId} />}
                <span style={nameStyle}>{g.name}</span>
                {g.quantity != null && (
                  <span style={qtyStyle}>
                    {g.quantity}
                    {g.unit && <span style={unitStyle}>{g.unit}</span>}
                  </span>
                )}
              </div>
            )}

            {g.instances.length > 0 && (
              <div style={g.name ? nestStyle : plainStyle}>
                {g.instances.map((i) => <InstanceLine key={i.id} instance={i} unit={g.unit} />)}
              </div>
            )}
          </div>
        ))}
      </div>
    </TileShell>
  );
}

/** Eine Instanz – Nummer, Art/Menge, Standort, Zustand. Umbricht statt zu überlaufen. */
function InstanceLine({ instance: i, unit }: { instance: OrderInstance; unit: string }) {
  const Icon = LOCATION_META[(i.location_type as LocationType)]?.icon ?? MapPin;
  return (
    <div style={lineStyle}>
      <ObjId value={i.object_id} />
      <span style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' }}>
        {instanceLabel(i.kind, i.quantity, unit)}
      </span>
      {i.location_label && (
        <span style={locStyle}>
          <Icon size={11} /> {i.location_label}
          {i.location_type === 'instance' && i.physical_location_label && (
            <span style={{ color: 'var(--fg-4)' }}> · {i.physical_location_label}</span>
          )}
        </span>
      )}
      <span style={{ marginLeft: 'auto' }}>
        <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} />
      </span>
    </div>
  );
}

// ─── Gruppierung ──────────────────────────────────────────────────────────────

type Group = {
  key: string;
  articleId: number | null;
  articleObjectId: number | null;
  name: string;                 // leer = titellose Restgruppe (Unter-Auftrag ohne Position)
  quantity: number | null;
  unit: string;
  instances: OrderInstance[];
};

/**
 * Positionen bilden, Instanzen über ``InstanceEmbed.article_id`` zuordnen. Ein
 * Mehrpositionen-Auftrag hat ``order_lines``, ein Einzel-Artikel-Auftrag den Anker am
 * Auftrag selbst; ein Unter-Auftrag (Abweichung/Bereitstellung) hat beides nicht und
 * trägt sein Subjekt als fixierte Instanzen. Was sich keiner Position zuordnen lässt,
 * fällt nicht unter den Tisch, sondern in eine Restgruppe.
 */
function buildGroups(order: Order): Group[] {
  const instances = order.instances ?? [];
  const lines = order.order_lines ?? [];
  const orderUnit = order.article_unit ? unitLabel(order.article_unit) : '';
  const groups: Group[] = [];

  if (lines.length > 0) {
    lines.forEach((l) => groups.push({
      key: `line-${l.id}`,
      articleId: l.article_id,
      articleObjectId: l.article_object_id ?? null,
      name: l.article_name ?? `Artikel #${l.article_id}`,
      quantity: l.quantity,
      unit: l.article_unit ? unitLabel(l.article_unit) : '',
      instances: [],
    }));
  } else if (order.article_id != null) {
    groups.push({
      key: 'anchor',
      articleId: order.article_id,
      articleObjectId: order.article_object_id ?? null,
      name: order.article_name ?? `Artikel #${order.article_id}`,
      quantity: order.quantity ?? null,
      unit: orderUnit,
      instances: [],
    });
  }

  const rest: OrderInstance[] = [];
  instances.forEach((i) => {
    const g = groups.find((x) => x.articleId === i.article_id);
    if (g) g.instances.push(i); else rest.push(i);
  });
  if (rest.length > 0) {
    groups.push({
      key: 'rest', articleId: null, articleObjectId: null,
      // Ohne Position (Unter-Auftrag) steht die Gruppe titellos da – die Kachel heisst
      // dann bereits «Instanzen», ein zweiter Titel wäre eine Dopplung.
      name: groups.length > 0 ? 'Weitere Instanzen' : '',
      quantity: null, unit: orderUnit, instances: rest,
    });
  }
  return groups;
}

// ─── Stile ────────────────────────────────────────────────────────────────────

const countStyle: React.CSSProperties = {
  font: '600 11.5px var(--font-body)', color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums',
  textTransform: 'none', letterSpacing: 0,
};
const headStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap',
};
const nameStyle: React.CSSProperties = {
  font: '700 15px var(--font-body)', color: 'var(--fg-1)', flex: '1 1 140px', minWidth: 0,
  overflow: 'hidden', textOverflow: 'ellipsis',
};
const qtyStyle: React.CSSProperties = {
  font: '700 15px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums', flexShrink: 0,
};
const unitStyle: React.CSSProperties = {
  font: '500 12.5px var(--font-body)', color: 'var(--fg-4)', marginLeft: 4,
};
// Zugehörigkeit als Einrückung an einer Haarlinie – ohne Kästen, ohne zweite Karte.
const nestStyle: React.CSSProperties = {
  marginTop: 8, marginLeft: 3, paddingLeft: 13, borderLeft: '1px solid var(--border-1)',
  display: 'flex', flexDirection: 'column', gap: 7,
};
const plainStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 7,
};
const lineStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
};
const locStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  font: '500 11.5px var(--font-body)', color: 'var(--fg-4)',
};
