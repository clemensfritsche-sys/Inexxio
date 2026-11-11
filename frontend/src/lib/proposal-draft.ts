/**
 * ►►► **Ein Vorschlag als Entwurf – ganz.** ◄◄◄
 *
 * Ein Entwurf ist die Form derselben Route, die der Vorschlag aufruft (`POST /erp/orders`,
 * `POST /erp/articles`): «Öffnen» bringt darum **den ganzen Wertesatz**, den die KI vorbereitet
 * hat, in den Entwurf – alle Zeilen, alle Schritte mit ihren Einstellungen (über die Umkehrform
 * `moduleFromConfig`), die Wiederholung. Was der Entwurf nicht darstellen kann, verschwindet
 * nicht still: es steht in `left` und der Entwurf nennt es.
 *
 * Rein (keine Komponente, kein Abruf) – gefahren in `scripts/proposal-draft.test.mjs`.
 */

import { LAGER, NEU, emptyLine, type DefinitionLine } from '@/components/erp/definition-lines';
import type { LoopDraft } from '@/components/erp/loop-card';
import type { OrderDate } from '@/components/erp/order-date';
import { moduleFromConfig, toModulePayload, type ModuleDraft } from '@/lib/modules';
import { MODULE_KEYS, type LoopTake } from '@/lib/vocab';
import { everyOf, takeOf } from '@/lib/loop';

type Body = Record<string, unknown> | null | undefined;

/** Was ein Auftrag aus einem Vorschlag mitbringt. */
export interface OrderProposal {
  lines: DefinitionLine[];
  steps: ModuleDraft[];
  loop: LoopDraft | null;
  /** Das eine Datum – «bis» oder «ab». */
  date: OrderDate | null;
  /** Was der Entwurf nicht darstellen kann – er nennt es, statt es zu verlieren. */
  left: string[];
}

/** Was ein Artikel aus einem Vorschlag mitbringt (die einfachen Felder liest `draftFrom`). */
interface ArticleProposal {
  steps: ModuleDraft[];
  /** Welchen Artikel er ablöst (`replaces_object_id`). */
  replaces: number | null;
  left: string[];
}

const rows = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const empty = (v: unknown) => v == null || v === '' || (Array.isArray(v) && v.length === 0)
  || (isObj(v) && Object.keys(v).length === 0);
const asInt = (v: unknown): number | null => {
  const n = typeof v === 'string' && v.trim() !== '' ? Number(v) : v;
  return typeof n === 'number' && Number.isInteger(n) ? n : null;
};
const show = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v));

/** Schlüssel eines Wertesatzes, die keiner kennt (und nicht leer sind) – als «wo: schlüssel». */
function unknownKeys(o: Record<string, unknown>, known: readonly string[], where: string): string[] {
  return Object.entries(o).filter(([k, v]) => !known.includes(k) && !empty(v))
    .map(([k, v]) => `${where}${k} = ${show(v)}`);
}

/**
 * ►► **Die Schritte eines Vorschlags** – je Schritt die Umkehrform des Editors
 * (`moduleFromConfig`). Ein unbekannter Modultyp und jede Einstellung, die der Editor nicht
 * führt, landen in `left`. ◄◄
 */
function stepsOf(raw: unknown, left: string[]): ModuleDraft[] {
  const out: ModuleDraft[] = [];
  rows(raw).forEach((s, i) => {
    const where = `Schritt ${i + 1}`;
    if (!isObj(s)) { left.push(`${where}: ${show(s)}`); return; }
    const type = String(s.module_type ?? '');
    if (!(MODULE_KEYS as readonly string[]).includes(type)) {
      left.push(`${where}: «${type}» ist kein Modul`);
      return;
    }
    left.push(...unknownKeys(s, ['module_type', 'config'], `${where}: `));
    const config = isObj(s.config) ? s.config : {};
    const draft = moduleFromConfig(out.length + 1, type, config);
    // Was die Umkehrform nicht zurückschreibt, kann der Editor nicht halten.
    const kept = Object.keys(toModulePayload(draft).config);
    left.push(...unknownKeys(config, kept, `${where}: `));
    out.push(draft);
  });
  return out;
}

/** Eine Zeile eines Auftrags – Artikel, Menge, Herkunft, Stücke, Rückführung. */
function lineOf(raw: unknown, key: number, left: string[]): DefinitionLine {
  const where = `Zeile ${key}: `;
  const line = emptyLine(key);
  if (!isObj(raw)) { left.push(`${where}${show(raw)}`); return line; }
  left.push(...unknownKeys(raw, ['article_object_id', 'quantity', 'origin', 'units', 'returns'], where));
  const article = asInt(raw.article_object_id);
  if (article === null && !empty(raw.article_object_id)) left.push(`${where}Artikel ${show(raw.article_object_id)}`);
  const quantity = asInt(raw.quantity);
  const origin = raw.origin === NEU || raw.origin === LAGER ? raw.origin : null;
  if (origin === null && !empty(raw.origin)) left.push(`${where}Herkunft «${show(raw.origin)}»`);
  const units = rows(raw.units).flatMap((u) => {
    if (typeof u === 'string' && u) return [{ number: u, fromOrder: null }];
    if (isObj(u) && typeof u.number === 'string' && u.number) {
      return [{ number: u.number, fromOrder: asInt(u.from_order) }];
    }
    left.push(`${where}Stück ${show(u)}`);
    return [];
  });
  return {
    ...line,
    articleObjectId: article,
    quantity: quantity !== null && quantity >= 1 ? quantity : units.length || line.quantity,
    origin: origin ?? line.origin,
    units: (origin ?? line.origin) === LAGER ? units : [],
    returns: typeof raw.returns === 'boolean' ? raw.returns : line.returns,
  };
}

/** Die Wiederholung (`LoopIn`) als Entwurf – `takes` gehört je Zeile, in ihrer Reihenfolge. */
function loopOf(raw: unknown, lines: DefinitionLine[], left: string[]): LoopDraft | null {
  if (empty(raw)) return null;
  if (!isObj(raw)) { left.push(`Wiederholung: ${show(raw)}`); return null; }
  left.push(...unknownKeys(raw, ['every', 'first', 'until', 'count', 'takes'], 'Wiederholung: '));
  const takes: Record<number, LoopTake> = {};
  rows(raw.takes).forEach((t, i) => {
    if (t == null || !lines[i]) return;
    const take = takeOf(t);
    if (take) takes[lines[i].key] = take;
    else left.push(`Wiederholung, Zeile ${i + 1}: ${show(t)}`);
  });
  const every = everyOf(raw.every);
  if (raw.every != null && raw.every !== '' && !every) left.push(`Takt: ${show(raw.every)}`);
  const until = typeof raw.until === 'string' ? raw.until : '';
  const count = asInt(raw.count);
  return {
    every: every ?? 'month',
    first: typeof raw.first === 'string' ? raw.first : '',
    end: until ? 'until' : count !== null ? 'count' : 'never',
    until,
    count: count !== null ? String(count) : '',
    takes,
  };
}

/** Das Datum (`OrderDate`) als Entwurf – sonst nennt der Entwurf es oben. */
function dateOf(raw: unknown, left: string[]): OrderDate | null {
  if (empty(raw)) return null;
  if (isObj(raw) && (raw.kind === 'from' || raw.kind === 'until') && typeof raw.on === 'string'
      && /^\d{4}-\d{2}-\d{2}$/.test(raw.on)) {
    return { kind: raw.kind, on: raw.on };
  }
  left.push(`Datum: ${show(raw)}`);
  return null;
}

/** ►► **Ein vorbereiteter Auftrag als Entwurf** – jede Zeile, jeder Schritt, die Wiederholung. ◄◄ */
export function orderFromProposal(body: Body): OrderProposal {
  const left: string[] = [];
  const b = isObj(body) ? body : {};
  left.push(...unknownKeys(b, ['lines', 'steps', 'loop', 'date'], ''));
  const found = rows(b.lines).map((l, i) => lineOf(l, i + 1, left));
  const lines = found.length ? found : [emptyLine(1)];
  return { lines, steps: stepsOf(b.steps, left), loop: loopOf(b.loop, lines, left),
           date: dateOf(b.date, left), left };
}

/**
 * ►► **Ein vorbereiteter Artikel als Entwurf** – die Schritte seines Erzeugungsprozesses und
 * wen er ablöst; `fields` sind die Felder, die die Maske führt (die Werte selbst liest
 * `draftFrom`). ◄◄
 */
export function articleFromProposal(body: Body, fields: readonly string[]): ArticleProposal {
  const left: string[] = [];
  const b = isObj(body) ? body : {};
  left.push(...unknownKeys(b, [...fields, 'steps', 'replaces_object_id'], ''));
  const replaces = asInt(b.replaces_object_id);
  if (replaces === null && !empty(b.replaces_object_id)) left.push(`ersetzt ${show(b.replaces_object_id)}`);
  return { steps: stepsOf(b.steps, left), replaces, left };
}
