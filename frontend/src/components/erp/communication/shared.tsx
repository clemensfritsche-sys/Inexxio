'use client';

import { Lock, Mail, Megaphone, Newspaper, Phone } from 'lucide-react';
import { MODULE_TONE } from '@/lib/modules';
import type { MessageIn } from '@/types';

// ►►► **Was Verlauf und Eingabe teilen** – wer (`Person`), welche Art (`Mode`, `KINDS`), welcher
// Versand (`DELIVERIES`, Spiegel von `domain/communication.DELIVERIES`) und die Farbe eines
// Anliegens. ◄◄◄

export type Person = { object_id: number; name: string; company?: string | null; email?: string | null;
  staff?: boolean };
export type Mode = 'email' | 'phone' | 'internal';
/** Die Versandart einer E-Mail – Spiegel von ``domain/communication.DELIVERIES``. */
export type Delivery = MessageIn['delivery'];
export const DELIVERIES: { key: Delivery; label: string; tip: string }[] = [
  { key: 'mail', label: 'Mail', tip: 'Normale E-Mail' },
  { key: 'circular', label: 'Rundschreiben', tip: 'Einzeln an mehrere, mit Anrede' },
  { key: 'newsletter', label: 'Newsletter', tip: 'Werbung, nur an Angemeldete' },
];


export const KIND_ICON = { email: Mail, phone: Phone, internal: Lock } as const;
/** ►►► **EINE Leiste für Art und Versand**: Mail · Rundschreiben · Newsletter | Anruf · Intern. ◄◄◄
 *  Eine Wahl setzt beides (`mode` und `delivery`) – eine Zeile «Versand» gibt es nicht. */
export type Kind = { key: string; mode: Mode; delivery: Delivery; label: string; tip: string;
  Icon: typeof Mail; sep?: boolean };
export const KINDS: Kind[] = [
  ...DELIVERIES.map((d) => ({ ...d, mode: 'email' as Mode, delivery: d.key,
    Icon: d.key === 'circular' ? Megaphone : d.key === 'newsletter' ? Newspaper : Mail })),
  { key: 'phone', mode: 'phone', delivery: 'mail', label: 'Anruf', tip: 'Gespräch festhalten', Icon: Phone, sep: true },
  { key: 'internal', mode: 'internal', delivery: 'mail', label: 'Intern', tip: 'Nur im Haus sichtbar', Icon: Lock },
];

/** ►►► **Gleicher Betreff, gleiche Farbe.** ◄◄◄ Fest aus dem Anliegen abgeleitet – nicht
 *  zufällig: dieselbe Farbe nach dem Neuladen und bei jedem Kollegen. Die Farben sind die
 *  gedämpften des Hauses (`MODULE_TONE`), bewusst ohne Rot und Orange: die gehören dem
 *  Zustand (offen · überfällig), und ein Betreff darf nicht wie einer aussehen. */
const TOPIC_TONES = ['slate', 'plum', 'moss', 'teal', 'clay', 'sand'].map((k) => MODULE_TONE[k].fg);
export function topicColor(topic: string): string {
  let h = 0;
  for (const ch of topic.toLocaleLowerCase('de-CH')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TOPIC_TONES[h % TOPIC_TONES.length];
}

export const ICON_BTN = { border: 0, background: 'none', padding: 3, borderRadius: 6, cursor: 'pointer',
  display: 'inline-flex', color: 'var(--fg-3)' } as const;
