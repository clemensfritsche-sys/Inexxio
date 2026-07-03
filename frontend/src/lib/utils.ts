import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Betrag im Schweizer Zahlenformat, 2 Nachkommastellen – OHNE Währung («12'345.60»).
// EINE Formatier-Wahrheit (vorher in 7 Komponenten je eine eigene Kopie).
export function formatAmount(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—';
  return Number(v).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Betrag MIT Währungspräfix («CHF 12'345.60»).
export function formatMoney(amount: string | number | null | undefined, currency: string): string {
  if (amount == null || amount === '') return '—';
  return `${currency} ${formatAmount(amount)}`;
}

// ISO-Timestamp → Schweizer Datum («03.07.2026»), leer → «—».
export function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function userDisplayName(user: { first_name?: string | null; last_name?: string | null; email: string }): string {
  const full = [user.first_name, user.last_name].filter(Boolean).join(' ');
  return full || user.email.split('@')[0];
}
