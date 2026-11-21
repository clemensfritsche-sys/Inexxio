'use client';

import { Lock, Mail, Megaphone, Newspaper, Phone, StickyNote, type LucideIcon } from 'lucide-react';
import { MODULE_TONE } from '@/lib/modules';
import { DELIVERY_LABELS, lookup, type ChannelKind, type DeliveryKey } from '@/lib/vocab';

// ►►► **Was Verlauf und Eingabe teilen** – wer (`Person`), welche Art (`Mode`, `KINDS`), welcher
// Versand (`DELIVERIES`, Schlüssel und Wort generiert aus `domain/communication.DELIVERIES`) und
// die Farbe eines Anliegens. ◄◄◄

export type Person = { object_id: number; name: string; company?: string | null; email?: string | null;
  staff?: boolean };
export type Mode = 'email' | 'phone' | 'internal';
/** Die Versandart einer E-Mail (`domain/communication.DELIVERIES`, generiert). */
export type Delivery = DeliveryKey;
/** Was die Oberfläche je Versandart dazulegt – Hover und Symbol; getippt gegen die Schlüssel. */
const DELIVERY_UI: Record<DeliveryKey, { tip: string; Icon: LucideIcon }> = {
  mail: { tip: 'Normale E-Mail', Icon: Mail },
  circular: { tip: 'Einzeln an mehrere, mit Anrede', Icon: Megaphone },
  newsletter: { tip: 'Werbung, nur an Angemeldete', Icon: Newspaper },
};
export const DELIVERIES: { key: Delivery; label: string; tip: string; Icon: LucideIcon }[] =
  (Object.keys(DELIVERY_LABELS) as DeliveryKey[]).map((key) => ({
    key, label: DELIVERY_LABELS[key], ...DELIVERY_UI[key],
  }));

/** Das Symbol je Art eines Kanals (`ChannelOut.kind`, generiert aus `domain/communication`).
 *  Die Notiz trägt den Zettel. */
const KIND_ICON: Record<ChannelKind, LucideIcon> = {
  email: Mail, phone: Phone, internal: Lock, note: StickyNote,
};
/** Das Symbol einer Kanal-Art; eine unbekannte sieht aus wie eine Mail. */
export function kindIcon(kind: string): LucideIcon {
  return lookup(KIND_ICON, kind) ?? Mail;
}
/** ►►► **Die Leiste: drei Arten** – Mail · Anruf · Intern. ◄◄◄ Wie eine Mail an mehrere
 *  hinausgeht (Rundschreiben, Newsletter), ist keine Art, sondern eine Frage an die
 *  Empfänger: die Zeile «Versand» erscheint, sobald zwei im «An» stehen. */
export type Kind = { key: Mode; label: string; tip: string; Icon: LucideIcon };
export const KINDS: Kind[] = [
  { key: 'email', label: 'Mail', tip: 'E-Mail über das Postfach der Gesellschaft', Icon: Mail },
  { key: 'phone', label: 'Anruf', tip: 'Gespräch festhalten', Icon: Phone },
  { key: 'internal', label: 'Intern', tip: 'Nur im Haus sichtbar', Icon: Lock },
];

/** ►►► **Gleicher Betreff, gleiche Farbe.** ◄◄◄ Fest aus dem Anliegen abgeleitet – nicht
 *  zufällig: dieselbe Farbe nach dem Neuladen und bei jedem Kollegen. Die Farben sind die
 *  gedämpften des Hauses (`MODULE_TONE`), bewusst ohne Rot und Orange: die gehören dem
 *  Zustand (offen · überfällig), und ein Betreff darf nicht wie einer aussehen. */
const TOPIC_TONES = (['slate', 'plum', 'moss', 'teal', 'clay', 'sand'] as const).map((k) => MODULE_TONE[k].fg);
export function topicColor(topic: string): string {
  let h = 0;
  for (const ch of topic.toLocaleLowerCase('de-CH')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TOPIC_TONES[h % TOPIC_TONES.length];
}

export const ICON_BTN = { border: 0, background: 'none', padding: 3, borderRadius: 6, cursor: 'pointer',
  display: 'inline-flex', color: 'var(--fg-3)' } as const;
