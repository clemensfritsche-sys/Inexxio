/**
 * ►►► **Aufgaben – das rote Zeichen** (Backend `services/tasks`, Projektakte
 * `docs/konzept/aufgaben.md`). ◄◄◄
 *
 * Der Server teilt zu und sagt, was ich sehe: meine eine Aufgabe, beim Admin jede, bei allen die
 * verwaisten («!»). Hier steht nur, wie es sich zeigt: das rote Zeichen am Symbol (Feed und
 * Kopf), an der Stelle (`data-todo` = `part`) und der Sprung dorthin. Kein Satz – was zu tun
 * ist, sieht man an der Stelle.
 */
import { createContext, useContext } from 'react';
import type { Todo, TodoItem } from '@/types';

/** Etwas, das die Aufgaben ändern kann, ist geschehen – der Feed lädt sie neu. */
export const TODO_CHANGED = 'erp:todo-changed';

export function todoChanged(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(TODO_CHANGED));
}

/** Die Zeichen je Datensatz – gehalten von der Feed-Seite, gelesen an der Stelle (Schritt). */
export const TodoContext = createContext<Map<number, Todo>>(new Map());

/** Die Aufgaben an einer Stelle – mit Datensatz (ein Abschnitt wie «wiederholung») oder ohne
 *  (`step:<id>` ist im ganzen ERP eindeutig). */
export function useTodoAt(part: string, objectId?: number | null): TodoItem[] {
  const all = useContext(TodoContext);
  const rows = objectId != null ? [all.get(objectId)].filter((r): r is Todo => !!r) : [...all.values()];
  return rows.flatMap((r) => r.items.filter((i) => i.part === part));
}

export function sectionItems(todo: Todo | null | undefined, ...sections: string[]): TodoItem[] {
  return (todo?.items ?? []).filter((i) => sections.includes(i.part));
}

/** Der Hover: «Zu tun» – oder, wenn niemand da ist, der es kann, das. Sonst nichts. */
export function todoTip(items: TodoItem[]): string {
  return items.length && items.every((i) => i.orphan && !i.mine)
    ? 'Niemand da, der das kann' : 'Zu tun';
}

/** Zur Stelle springen – zuerst meine Aufgabe; steht eine nicht auf der Seite, die nächste. */
export function jumpToTodo(items: TodoItem[]): void {
  const sorted = [...items].sort((a, b) => Number(!!b.mine) - Number(!!a.mine));
  const el = sorted.map((i) => document.querySelector(`[data-todo="${i.part}"]`)).find(Boolean);
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
