/**
 * ►►► **Der Kontotyp – Privat ↔ Geschäft** (Testnotiz #1042). ◄◄◄
 *
 * Der **Spiegel** von `backend/app/domain/accounts.py` über die API-Grenze: Beschriftung
 * und Erklärung zu den beiden Schlüsseln, die der generierte Typ (`AccountType`) trägt.
 * Ein Wächter (`test_frontend_mirrors.py`) vergleicht Schlüssel **und** Wörter gegen die
 * Backend-Quelle – ein Spiegel, den niemand prüft, läuft auseinander.
 *
 * **Die Regel spiegelt er nicht.** Dass ein Lieferant immer eine Firma ist und dass ein
 * leerer Wert abgeleitet wird, löst der Server auf: die Antwort trägt den **effektiven**
 * Kontotyp (`UserProfileResponse.account_type`). Die Oberfläche fragt darum nie die Rolle,
 * um zu wissen, ob Firmenfelder gehören – sie fragt diesen einen Wert.
 */

import { Building2, User } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type AccountType = 'private' | 'business';

interface AccountTypeCfg {
  label: string;
  hint: string;
  icon: LucideIcon;
}

/** Reihenfolge = die des Schalters. */
export const ACCOUNT_TYPES: { value: AccountType; label: string; icon: LucideIcon }[] = [
  { value: 'private', label: 'Privat', icon: User },
  { value: 'business', label: 'Geschäft', icon: Building2 },
];

export const ACCOUNT_TYPE: Record<AccountType, AccountTypeCfg> = {
  private: {
    label: 'Privat',
    hint: 'Eine Privatperson – auf dem Beleg steht ihr Name.',
    icon: User,
  },
  business: {
    label: 'Geschäft',
    hint: 'Eine Firma – auf dem Beleg steht die Rechtsperson, die Person darunter als «z. H.».',
    icon: Building2,
  },
};

/**
 * Tritt dieser Datensatz als **Firma** auf?
 *
 * Gefragt wird der Kontotyp, **nie die Rolle** – das war die Verwechslung, aus der #1042
 * entstand: ein Geschäftskunde hatte keinen Firmennamen, weil die Firmenfelder an
 * `role === 'supplier'` hingen.
 */
export function isBusiness(accountType: string | null | undefined): boolean {
  return accountType === 'business';
}

/**
 * ►►► **Der Platzhalter, der die Vererbung SAGT** (Testnotiz #1042). ◄◄◄
 *
 * Die Rechnungs-E-Mail ist freiwillig: leer nimmt der Beleg die Login-/Kontakt-Adresse
 * (`voucher.billing_of`). Vorher stand dort nur diese Adresse – ein Platzhalter, der wie
 * eine Vorbelegung aussieht und nicht wie eine Regel. Er sagt sie jetzt in Worten, und
 * darum braucht es **kein zweites Feld und keine Checkbox** daneben.
 *
 * Die beiden Oberflächen, die den Datensatz schreiben, lesen **denselben** Satz – zwei
 * Formulierungen wären zwei Aussagen über dieselbe Vererbung.
 */
export function inheritedEmail(login: string | null | undefined): string {
  return login ? `übernimmt ${login}` : 'rechnung@firma.ch';
}
