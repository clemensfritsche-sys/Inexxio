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
/** ►►► **EINE Leiste für Art und Versand**: Mail · Rundschreiben · Newsletter | Anruf · Intern. ◄◄◄
 *  Eine Wahl setzt beides (`mode` und `delivery`) – eine Zeile «Versand» gibt es nicht. */
export type Kind = { key: string; mode: Mode; delivery: Delivery; label: string; tip: string;
  Icon: LucideIcon; sep?: boolean };
export const KINDS: Kind[] = [
  ...DELIVERIES.map((d) => ({ ...d, mode: 'email' as Mode, delivery: d.key })),
  { key: 'phone', mode: 'phone', delivery: 'mail', label: 'Anruf', tip: 'Gespräch festhalten', Icon: Phone, sep: true },
  { key: 'internal', mode: 'internal', delivery: 'mail', label: 'Intern', tip: 'Nur im Haus sichtbar', Icon: Lock },
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
