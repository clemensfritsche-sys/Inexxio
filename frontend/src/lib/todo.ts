/**
 * ►►► **Was zu tun ist – die EINE Zahl am Symbol** (Backend `services/todo`). ◄◄◄
 *
 * Offene Nachrichten, Aufgaben der Zeiterfassung, überfällige Rechnungen, fehlende
 * Pflichtangaben, fehlende Feiertage – der Server zählt, hier steht nur, wie es sich zeigt: die Blase am Symbol (Feed und Kopf),
 * die kleine Zahl am Abschnitt und der Sprung dorthin.
 */
import type { Todo, TodoItem } from '@/types';

/** Etwas, das die Zahl ändern kann, ist geschehen – der Feed lädt sie neu. */
export const TODO_CHANGED = 'erp:todo-changed';

export function todoChanged(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(TODO_CHANGED));
}

/** Die Abschnitte, in der Reihenfolge der Seite – und ihr Wort im Hover. */
const SECTION: Record<string, string> = {
  kommunikation: 'Kommunikation',
  // Offene Vorschläge der KI (und meine nicht abgelegten Erfassungen) – sie stehen im
  // Angehefteten unten im Verlauf (`components/erp/pinned.tsx`, `data-todo="vorschlaege"`).
  vorschlaege: 'Vorschläge',
  zeiterfassung: 'Zeiterfassung',
  // Überfällige Rechnungen – keine eigene Mahnliste, sie zählen an der Person.
  zahlungen: 'Zahlungen',
  person: 'Stammdaten',
  adressen: 'Adressen',
  feiertage: 'Feiertage',
  // Der Deckel der KI (nur Admin, am Betreiber): ab 80 % mit dem Betrag, am Deckel rot.
  ki: 'KI',
};
const ORDER = Object.keys(SECTION);

export function sectionItems(todo: Todo | null | undefined, ...sections: string[]): TodoItem[] {
  return (todo?.items ?? []).filter((i) => sections.includes(i.section));
}

/** Der Hover: «Zu tun» und darunter je Abschnitt, was fehlt. */
export function todoTip(items: TodoItem[]): string {
  const sorted = [...items].sort((a, b) => ORDER.indexOf(a.section) - ORDER.indexOf(b.section));
  const groups = new Map<string, string[]>();
  for (const i of sorted) groups.set(i.section, [...(groups.get(i.section) ?? []), i.label]);
  return ['Zu tun', ...Array.from(groups, ([s, labels]) => `${SECTION[s] ?? s}: ${labels.join(' · ')}`)]
    .join('\n');
}

/** Zum ersten Abschnitt springen, der etwas zu tun hat (`data-todo` an der Stelle) – steht
 *  einer nicht auf der Seite, zum nächsten. */
export function jumpToTodo(items: TodoItem[]): void {
  const rank = (s: string) => (ORDER.includes(s) ? ORDER.indexOf(s) : ORDER.length);
  const sorted = [...items].sort((a, b) => rank(a.section) - rank(b.section));
  const el = sorted.map((i) => document.querySelector(`[data-todo="${i.section}"]`)).find(Boolean);
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
