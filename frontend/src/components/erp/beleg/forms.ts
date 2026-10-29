import { parseDay } from '@/lib/when';
import type { Action, Filled } from './shared';
import { unsigned } from './shared';

/**
 * ►►► **Was am Beleg erfasst wird – EINE Stelle für Felder, Prüfung und Befehl.** ◄◄◄
 *
 * Ein Formular steht im Abschnitt, zu dem es gehört (die Zahlung in «Rechnung», der Grund
 * des Ausbuchens in der Leiste), der Knopf, der es abschickt, steht in der Leiste. Beide
 * lesen dieselben drei Funktionen: `formProblem` (warum noch nicht – der Satz im Hover des
 * gesperrten Knopfs), `formBody` (der Befehl an den Dienst) und `formWord` (das Wort).
 */
type FormKind = 'pay' | 'refund' | 'bill' | 'export' | 'accept' | 'writeoff' | 'revoke';

export type Form = { kind: FormKind; f: Record<string, string> };

/** Die Zahlungsarten, mit denen erstattet wird (die Karte geht über den Dienst). */
export const CASH = 'cash';
export const TRANSFER = 'transfer';

/** Ein Formular mit seiner Vorbelegung – was das ERP weiss, wird nicht gefragt. */
export function startForm(kind: FormKind, d: Filled, method?: string): Form {
  switch (kind) {
    case 'pay':
      return { kind, f: { amount: d.next_payment ?? '', method: method ?? CASH, iban: '' } };
    case 'refund':
      return { kind, f: { amount: unsigned(d.open ?? ''), method: method ?? TRANSFER, iban: '' } };
    case 'bill':
      return { kind, f: { amount: d.amount ?? '', vat: d.vat_rate, reference: '',
                          billed_on: '', party_uid: '', original: d.original ? String(d.original) : '' } };
    case 'export':
      return { kind, f: { reference: '', original: d.export_photo ? String(d.export_photo) : '' } };
    case 'writeoff':
      return { kind, f: { reason: '' } };
    default:
      return { kind, f: { note: '' } };
  }
}

/** Braucht diese Zahlung eine IBAN? – Geld, das per Überweisung an die Partei zurückgeht. */
export function needsIban(form: Form, d: Filled): boolean {
  if (form.f.method !== TRANSFER) return false;
  return form.kind === 'refund' || (form.kind === 'pay' && d.minus);
}

/** Trägt der gewählte Satz Steuer? Dann braucht die Lieferantenrechnung die MWST-Nr. */
export function taxed(form: Form, d: Filled): boolean {
  const rate = (d.vat_rates ?? []).find((v) => v.key === form.f.vat)?.rate ?? '0';
  return Number(rate) > 0;
}

/**
 * **Warum der Knopf noch nicht kann** – derselbe Satz, den der Dienst sagen würde, nur
 * vorher. `null` heisst: bereit.
 */
export function formProblem(form: Form, d: Filled): string | null {
  const f = form.f;
  const blank = (k: string) => (f[k] ?? '').trim() === '';
  switch (form.kind) {
    case 'pay':
    case 'refund':
      if (blank('amount') || Number(f.amount) === 0) return 'Erst den Betrag eintragen.';
      if (needsIban(form, d) && blank('iban')) {
        return 'Ohne IBAN geht kein Geld zurück – sie kommt von der Zahlung oder von Hand.';
      }
      return null;
    case 'bill':
      if (blank('amount')) return 'Erst den Betrag seiner Rechnung eintragen.';
      if (blank('reference')) return `Ohne ${d.ref_label ?? 'Rechnungsnummer'} lässt sich die Rechnung nicht zuordnen.`;
      if (!parseDay(f.billed_on ?? '')) return 'Das Rechnungsdatum steht auf seinem Papier (TT.MM.JJJJ).';
      if (taxed(form, d) && blank('party_uid')) {
        return 'Ohne die MWST-Nummer auf seiner Rechnung gibt es keinen Vorsteuerabzug (MWSTG Art. 28).';
      }
      if (blank('original')) return 'Ohne die Rechnung als Dokument geht es nicht – sie ist der Beleg.';
      return null;
    case 'export':
      if (blank('reference')) return 'Erst die Nummer der Veranlagungsverfügung eintragen.';
      if (blank('original')) return 'Ohne die Veranlagungsverfügung als Dokument gilt der Nachweis nicht.';
      return null;
    case 'accept':
      return blank('note') ? 'Eine Abweichung nimmt man mit Grund an – er bleibt als Nachweis.' : null;
    case 'writeoff':
      return blank('reason') ? 'Erst den Grund wählen.' : null;
    default:
      return null;
  }
}

/** **Der Befehl an den Dienst** – nur, was das Verb kennt. */
export function formBody(form: Form, d: Filled): Action {
  const f = form.f;
  const trim = (k: string) => (f[k] ?? '').trim();
  switch (form.kind) {
    case 'pay':
    case 'refund':
      return { action: form.kind, amount: trim('amount'), method: f.method,
               ...(needsIban(form, d) ? { iban: trim('iban') } : {}) };
    case 'bill':
      return { action: 'bill', amount: trim('amount'), vat: f.vat, reference: trim('reference'),
               billed_on: parseDay(f.billed_on ?? ''), original: Number(f.original),
               ...(trim('party_uid') ? { party_uid: trim('party_uid') } : {}) };
    case 'export':
      return { action: 'export', reference: trim('reference'), original: Number(f.original) };
    case 'accept':
      return { action: 'accept', note: trim('note') };
    case 'writeoff':
      return { action: 'writeoff', reason: f.reason };
    default:
      return { action: 'revoke', ...(trim('note') ? { note: trim('note') } : {}) };
  }
}

/** **Das Wort des Knopfs**, der das Formular abschickt. */
export function formWord(form: Form, d: Filled): string {
  switch (form.kind) {
    case 'writeoff':
      return `${d.write_off_word} · ${unsigned(d.open ?? '')} ${d.currency}`;
    case 'accept':
      return 'So annehmen';
    case 'revoke':
      return d.undo ?? 'Stornieren';
    default:
      return 'Buchen';
  }
}
