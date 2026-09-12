'use client';

import type { StockState } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { ValueBar } from '@/components/erp/module-ui';

/**
 * **Die Bestandsleiste — Menge, Zustand und Auswahl in EINEM Bild.**
 *
 * Eine gestapelte Leiste: ein Segment je Zustand, breit nach Menge, gefärbt nach der
 * einen Statuskarte (`lib/process-status`). Sie beantwortet «wie viel habe ich, und wie
 * viel davon ist verfügbar» in einem Blick, ohne dass jemand Zahlen vergleicht.
 *
 * ►►► **Sie ist die Ausprägung einer allgemeineren Leiste** (`module-ui.ValueBar`). ◄◄◄
 *
 * Die Frage «wie teilt sich ein Ganzes auf, und welchen Teil sehe ich mir an» ist nicht
 * die des Bestands: die **Stufen** eines Prozessschrittmoduls und die Aufteilung
 * *berechnet · bezahlt · offen* eines Geldvorgangs sind dieselbe Aussage mit anderen
 * Segmenten. Die Leiste steht darum einmal; hier bleibt, was wirklich am Bestand hängt –
 * die Übersetzung eines Zustands in Farbe und Wort.
 *
 * Alles, was diese Datei einmal an Regeln trug, gilt unverändert und steht jetzt dort:
 * die Beschriftung gehört zur Leiste (Testnotiz #789), die Haarlinie ist ein `border`
 * und kein `gap`, und der gewählte Zustand tritt hervor, statt die anderen auszublenden –
 * **kein Filter**.
 */
export function StockBar({ states, height = 10, onPick, active }: {
  states: StockState[];
  height?: number;
  /** Klick auf ein Segment bzw. seine Beschriftung. Ohne Handler ist alles reine Anzeige. */
  onPick?: (status: string) => void;
  /** Welcher Zustand gerade offen ist – er tritt hervor, die anderen zurück. */
  active?: string | null;
}) {
  return (
    <ValueBar
      height={height}
      active={active}
      onPick={onPick}
      legendHint={(open) => (open ? 'Nummern ausblenden' : 'Nummern anzeigen')}
      segments={states.map((s) => {
        const cfg = statusCfg(s.status);
        return {
          key: s.status,
          label: cfg.label,
          value: s.quantity,
          color: cfg.color,
          text: String(s.quantity),
          hint: `${s.quantity} × ${cfg.label}${onPick ? ' – Nummern anzeigen' : ''}`,
        };
      })}
    />
  );
}
