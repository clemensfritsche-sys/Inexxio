import type { ChangeEvent, KeyboardEvent } from 'react';

/**
 * ►►► **Die Logik eines Feldes – EINE Stelle für das ganze ERP** (Projektakte «Die lernende
 * Firma» §4.3, Schritt 2.1). ◄◄◄
 *
 * Das Speichern ist zentral (`lib/use-autosave`), das Feld war es nicht: rund dreissig
 * Dateien schrieben ihr `<input>` selbst – jedes mit seiner Fassung von «Enter», «Pflicht»
 * und «stimmt das Format?». Hier steht das einmal; das **Aussehen** bleibt frei
 * (`form/field.tsx`: `Field` ist die Standardform, `Input` · `Select` · `TextArea` tragen
 * dieselbe Logik in jedem Aussehen – der Beleg sieht aus wie gedrucktes Papier).
 *
 * **Was das Feld weiss:**
 * - **Wert und Änderung** – `onChange` bekommt den Text, nicht das Ereignis. Ohne `onChange`
 *   ist das Feld nur Anzeige.
 * - **Pflicht** – `required` und leer heisst `empty`; gemeldet, nicht gesperrt.
 * - **Format** – Telefon und E-Mail werden weich geprüft (`fieldFormatIssue`).
 * - **Meldung** – `note`: zuerst eine Abweisung (`error`), dann das Format, dann der Hinweis.
 * - **Enter** – heisst «fertig»: `onEnter` läuft (das Auto-Save speichert sofort), und kein
 *   Formular schickt sich ab. Ein Feld nur zur Anzeige tut nichts. Mehrzeilig gibt es kein
 *   `onEnter` – dort ist Enter eine neue Zeile.
 *
 * Was die KI an einem Feld ändern will, ist ein **Handgriff** im Angehefteten (Phase 5) – das
 * Feld selbst trägt kein Zeichen.
 */
export interface FieldSpec {
  /** API-Schlüssel des Feldes (`first_name`, `voucher.reference` …) – nicht das HTML-`name`. */
  name: string;
  value: string;
  onChange?: (value: string) => void;
  /** HTML-Typ: `text` · `tel` · `email` · `number` · `date` … – entscheidet die Format-Prüfung. */
  type?: string;
  required?: boolean;
  readOnly?: boolean;
  /** Enter = fertig. Bekommt das Feld, falls es z. B. den Fokus abgeben will. */
  onEnter?: (el: HTMLElement) => void;
  /** Eine Abweisung (Server, Regel) – steht vor jeder anderen Meldung. */
  error?: string | null;
  /** Ein leiser Satz unter dem Feld, solange nichts zu melden ist. */
  hint?: string;
}

/** Die Farbe des Feldes – dieselben drei Lagen wie `inputClass` (components/erp/controls). */
type FieldTone = 'normal' | 'warn' | 'read';

export interface FieldNote { text: string; tone: 'danger' | 'warning' | 'quiet' }

type FieldElement = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

interface FieldState {
  /** Pflicht und leer. */
  empty: boolean;
  /** Was am Format nicht stimmt (weich – gespeichert wird trotzdem). */
  issue: string | null;
  /** Die eine Meldung unter dem Feld, oder nichts. */
  note: FieldNote | null;
  tone: FieldTone;
  /** Was an das Element geht: Wert, Änderung, Enter, Tastatur am Handy. */
  control: {
    value: string;
    readOnly?: boolean;
    onChange?: (e: ChangeEvent<FieldElement>) => void;
    onKeyDown: (e: KeyboardEvent<FieldElement>) => void;
    inputMode?: 'tel' | 'email';
  };
}

/**
 * **Weiche Format-Prüfung** (Testnotiz #326) – für Telefon und E-Mail.
 *
 * Warum weich: eine harte Telefon-Validierung ist der Klassiker unter den
 * Formular-Ärgernissen. Gültige Nummern gibt es in Dutzenden Schreibweisen (`+41 44 …`,
 * `0044 …`, mit Klammern, mit Durchwahl), und jede strenge Regex sperrt irgendwann eine
 * echte Nummer aus. Die verlässliche Lösung wäre libphonenumber – ~150 kB für ein Feld,
 * das niemand automatisiert wählt. Also: **melden statt blockieren.** Wer eine Nummer
 * tippt, die offensichtlich keine ist (zu wenige Ziffern, fremde Zeichen), sieht einen
 * Hinweis; gespeichert wird trotzdem, denn die Angabe ist informativ, nicht funktional.
 */
function fieldFormatIssue(type: string, value: string): string | null {
  const v = value.trim();
  if (!v) return null;
  if (type === 'tel') {
    if (/[^\d\s+()/.-]/.test(v)) return 'Enthält Zeichen, die in einer Telefonnummer nicht vorkommen.';
    const digits = v.replace(/\D/g, '');
    if (digits.length < 7) return 'Wirkt zu kurz für eine Telefonnummer.';
    if (digits.length > 15) return 'Wirkt zu lang – international sind max. 15 Ziffern üblich.';
    return null;
  }
  if (type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) {
    return 'Sieht nicht wie eine E-Mail-Adresse aus.';
  }
  return null;
}

export function useField(spec: FieldSpec): FieldState {
  const { value, onChange, type = 'text', required, readOnly, onEnter, error, hint } = spec;
  const empty = !!required && !value.trim();
  const issue = readOnly ? null : fieldFormatIssue(type, value);
  // Der Hinweis meldet, blockiert aber nicht (#326) – gespeichert wird trotzdem.
  const note: FieldNote | null = error ? { text: error, tone: 'danger' }
    : issue ? { text: issue, tone: 'warning' }
      : hint ? { text: hint, tone: 'quiet' } : null;
  return {
    empty,
    issue,
    note,
    tone: empty || issue || error ? 'warn' : readOnly ? 'read' : 'normal',
    control: {
      value,
      readOnly,
      onChange: onChange ? (e) => onChange(e.target.value) : undefined,
      onKeyDown: (e) => {
        if (e.key === 'Enter' && !readOnly && onEnter) { e.preventDefault(); onEnter(e.currentTarget); }
      },
      inputMode: type === 'tel' ? 'tel' : type === 'email' ? 'email' : undefined,
    },
  };
}
