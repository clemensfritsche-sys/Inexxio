'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { formatAmount } from '@/lib/utils';
import type { PaymentRow } from '@/types';
import { Amount } from '@/components/erp/module-ui';
import { useErpNav } from '@/components/erp/obj-id';

/**
 * ►►► **Die Zahlungen einer Person bzw. einer eigenen Gesellschaft – eine Ableitung.** ◄◄◄
 *
 * Keine eigene Liste: jede Zeile ist ein Zahlungsmodul (Backend `services/payments`), die
 * Reihenfolge sagt der Server (neueste Nummer zuoberst). **Kein Datum, keine
 * Abkürzungs-Knöpfe** – ein Klick öffnet den Auftrag, dort wird gehandelt. **Der Betrag sagt
 * alles**: `+` kommt zu uns, `−` geht von uns; die Farbe ist der Stand.
 */

/** Der Stand → die Farbe des Betrags (rot überfällig · schwarz ausstehend · grün bezahlt ·
 *  grau storniert). Das Wort dazu kommt vom Server (`state_label`). */
const TONE: Record<string, string> = {
  overdue: 'var(--danger)',
  open: 'var(--fg-1)',
  paid: 'var(--success)',
  void: 'var(--fg-4)',
};

/** Der Hover am Wort «Zahlungen» – was die Liste ist und wie sie zu lesen ist. */
export const PAYMENTS_TIP = 'Eine Ableitung aus allen Zahlungsmodulen – keine eigene Liste. '
  + 'Neueste Nummer zuoberst; ein Klick öffnet den Auftrag. Betrag: + kommt zu uns, '
  + '− geht von uns · rot überfällig · schwarz ausstehend · grün bezahlt · grau storniert.';

/** Die Zahlungen einer Person oder Gesellschaft. `null` = noch nicht geladen; ein Fehler
 *  meldet sich (`meta.what`), der alte Stand bleibt. */
export function usePayments(scope: { person: number } | { company: number } | null): PaymentRow[] | null {
  const query = useQuery({
    queryKey: qk.payments(scope ?? { person: 0 }),
    queryFn: ({ signal }) => api.paymentsOf(scope!, { signal }),
    enabled: scope != null,
    meta: { what: 'Zahlungen' },
  });
  return query.data ?? null;
}

/** Die Stellen der Währung stehen im Betrag selbst (`domain/currency.money`). */
function decimalsOf(amount: string): number {
  return (amount.split('.')[1] ?? '').length;
}

function PaymentLine({ row, withParty, first }: {
  row: PaymentRow; withParty: boolean; first: boolean;
}) {
  const nav = useErpNav();
  const order = row.order_object_id;
  // **Die Nummer des Papiers** (Rechnung «100000013-1», sonst der Auftrag) – keine
  // Stück-Nummer, darum nicht durch <UnitNumber>: ihr Suffix ist die laufende Rechnung.
  const paperNo = row.number;
  const tip = `${row.sign === '+' ? 'Einnahme' : 'Ausgabe'} · ${row.state_label}`;
  return (
    <button type="button" className="ix-row flex items-center"
      onClick={() => { if (order != null) nav?.(order); }}
      style={{
        gap: 12, padding: '10px 0', minWidth: 0, width: '100%', textAlign: 'left',
        background: 'none', border: 0, borderTop: first ? 0 : '1px solid var(--border-1)',
        cursor: order != null ? 'pointer' : 'default', font: 'inherit', color: 'inherit',
      }}>
      <span className="erp-objid" style={{
        flex: 'none', minWidth: 104, fontFamily: 'var(--font-mono), monospace', fontSize: 12.5,
        fontWeight: 600, fontVariantNumeric: 'tabular-nums',
      }}>{paperNo}</span>
      {/* Art und Partei – breit nebeneinander, schmal untereinander (kein Seitwärts-Scrollen). */}
      <span className="flex flex-1 flex-col sm:flex-none sm:flex-row sm:items-center sm:gap-3"
        style={{ minWidth: 0 }}>
        <span className="truncate sm:w-[130px] sm:flex-none" style={{
          minWidth: 0, fontSize: 12.5, fontWeight: 500, color: 'var(--fg-1)',
        }}>{row.kind}</span>
        {withParty && (
          <span className="truncate sm:w-[150px] sm:flex-none" style={{
            minWidth: 0, fontSize: 12.5, color: 'var(--fg-1)',
          }} {...(row.party_object_id != null ? { title: String(row.party_object_id) } : {})}>
            {row.party_name ?? '—'}
          </span>
        )}
      </span>
      {/* Der Auftrag – schmal entfällt er: die Nummer des Papiers beginnt mit ihm. */}
      <span className="hidden sm:block truncate" style={{
        flex: '1 1 auto', minWidth: 0, fontSize: 12.5, color: 'var(--fg-3)',
        fontVariantNumeric: 'tabular-nums',
      }}>{order != null ? `Auftrag ${order}` : ''}</span>
      <span style={{ flex: 'none', textAlign: 'right' }}>
        <Amount currency={row.currency} color={TONE[row.state] ?? 'var(--fg-1)'} size={13.5}
          weight={500} tip={tip}>
          {row.amount != null ? `${row.sign}${formatAmount(row.amount, decimalsOf(row.amount))}` : '—'}
        </Amount>
      </span>
    </button>
  );
}

/** **Die eine Karte** – Zeile je Zahlung; mit `withParty` steht die Partei je Zeile dabei
 *  (an der Gesellschaft, wo die Liste viele Personen umfasst). */
export function PaymentList({ rows, withParty = false }: {
  rows: PaymentRow[]; withParty?: boolean;
}) {
  return (
    <div style={{
      background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 12,
      padding: '6px 20px',
    }}>
      {rows.map((r, i) => (
        <PaymentLine key={r.voucher_id} row={r} withParty={withParty} first={i === 0} />
      ))}
    </div>
  );
}
