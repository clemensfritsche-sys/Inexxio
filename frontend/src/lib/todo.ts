/**
 * ►►► **Was zu tun ist – die EINE Zahl am Symbol** (Backend `services/todo`). ◄◄◄
 *
 * Offene Nachrichten, Aufgaben der Zeiterfassung, fehlende Pflichtangaben, fehlende Feiertage
 * – der Server zählt, hier steht nur, wie es sich zeigt: die Blase am Symbol (Feed und Kopf),
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
  zeiterfassung: 'Zeiterfassung',
  person: 'Stammdaten',
  adressen: 'Adressen',
  feiertage: 'Feiertage',
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

/** Zum ersten Abschnitt springen, der etwas zu tun hat (`data-todo` an der Stelle). */
export function jumpToTodo(items: TodoItem[]): void {
  const first = [...items].sort((a, b) => ORDER.indexOf(a.section) - ORDER.indexOf(b.section))[0];
  if (!first) return;
  const el = document.querySelector(`[data-todo="${first.section}"]`);
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
