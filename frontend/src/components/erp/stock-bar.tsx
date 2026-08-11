'use client';

import type { StockState } from '@/types';
import { statusCfg } from '@/lib/process-status';

/**
 * **Die Bestandsleiste — Menge und Zustand in EINEM Bild.**
 *
 * Eine gestapelte Leiste: ein Segment je Zustand, breit nach Menge, gefärbt nach der
 * einen Statuskarte (`lib/process-status`). Sie beantwortet «wie viel habe ich, und wie
 * viel davon ist verfügbar» in einem Blick, ohne dass jemand Zahlen vergleicht.
 *
 * **Eine Komponente, zwei Massstäbe.** Oben steht sie für den ganzen Artikel, in jeder
 * Instanz-Zeile für diese eine Instanz – dieselbe Aufstellung (`states`), derselbe Code,
 * nur eine andere Bezugsmenge. Eine zweite «kleine» Leiste wäre eine zweite Regel dafür,
 * wie ein Zustand aussieht; sie liefe beim ersten neuen Status auseinander.
 *
 * **Die Farbe ist die einzige Statusanzeige.** Keine Badge daneben, keine Punkte in der
 * Legende: das Segment ist die Farbe, die Legende benennt sie. Zweimal dasselbe zu
 * zeigen macht eine Liste nicht klarer, nur voller.
 *
 * Ein **Segment ist anklickbar**, wo es etwas zu öffnen gibt – dann ist es zugleich das
 * Bedienelement für die Ebene darunter («zeig mir diese Nummern»). Damit braucht es
 * keinen Filter: was man sehen will, klickt man an, und was man nicht anklickt, ist
 * trotzdem sichtbar.
 */
export function StockBar({ states, height = 8, onPick, active }: {
  states: StockState[];
  height?: number;
  /** Klick auf ein Segment. Ohne Handler ist die Leiste reine Anzeige. */
  onPick?: (status: string) => void;
  /** Welches Segment gerade offen ist – es tritt hervor, die anderen zurück. */
  active?: string | null;
}) {
  const total = states.reduce((n, s) => n + s.quantity, 0);
  if (total === 0) {
    return (
      <div className="rounded-full bg-bg-3" style={{ height }} aria-hidden />
    );
  }

  return (
    <div className="flex w-full overflow-hidden rounded-full" style={{ height }}>
      {states.map((s) => {
        const cfg = statusCfg(s.status);
        const share = (s.quantity / total) * 100;
        const dimmed = active != null && active !== s.status;
        const title = `${s.quantity} × ${cfg.label}`;
        if (!onPick) {
          return (
            <span
              key={s.status}
              data-tip={title}
              style={{ width: `${share}%`, background: cfg.color, opacity: dimmed ? 0.3 : 1 }}
            />
          );
        }
        return (
          <button
            key={s.status}
            type="button"
            aria-label={title}
            data-tip={`${title} – Nummern anzeigen`}
            onClick={(e) => { e.stopPropagation(); onPick(s.status); }}
            style={{
              width: `${share}%`,
              background: cfg.color,
              opacity: dimmed ? 0.3 : 1,
              transition: 'opacity .12s',
            }}
          />
        );
      })}
    </div>
  );
}

/**
 * Die Legende zur Leiste: Wort und Menge je Zustand, in derselben Reihenfolge und
 * derselben Farbe. Sie steht **nur oben** – in einer Liste von 50 Instanzen würde
 * dieselbe Legende 50-mal dasselbe erklären.
 */
export function StockLegend({ states, unit }: { states: StockState[]; unit?: string | null }) {
  if (states.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {states.map((s) => {
        const cfg = statusCfg(s.status);
        return (
          <span key={s.status} className="flex items-center gap-1.5 text-[12.5px]">
            <span className="rounded-full" style={{
              width: 7, height: 7, background: cfg.color, flex: 'none',
            }} />
            <span className="text-fg-3">{cfg.label}</span>
            <span className="ix-tnum">{s.quantity}{unit ? ` ${unit}` : ''}</span>
          </span>
        );
      })}
    </div>
  );
}
