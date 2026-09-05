'use client';

import type { StockState } from '@/types';
import { statusCfg } from '@/lib/process-status';

/**
 * **Die Bestandsleiste — Menge, Zustand und Auswahl in EINEM Bild.**
 *
 * Eine gestapelte Leiste: ein Segment je Zustand, breit nach Menge, gefärbt nach der
 * einen Statuskarte (`lib/process-status`). Sie beantwortet «wie viel habe ich, und wie
 * viel davon ist verfügbar» in einem Blick, ohne dass jemand Zahlen vergleicht.
 *
 * ►►► **Und sie nennt, was sie zeigt** (Testnotiz #789). ◄◄◄
 *
 * Die Farbe allein kann es nicht: der Katalog kennt **drei** Ampeltöne für **sechs**
 * Zustände eines Stücks – *Freigegeben*, *Verbaut* und *Verkauft* sind alle grün,
 * *Im Prozess* und *Gesperrt* beide gelb. Zwei gleichfarbige Segmente nebeneinander
 * sind damit **strukturell** nicht unterscheidbar, und keine Feinabstimmung der Farbe
 * ändert daran etwas: das Wort ist die Unterscheidung, nicht der Ton.
 *
 * Die Beschriftungen stehen darum **unter der Leiste, als Teil von ihr** – Punkt, Wort,
 * Menge – und sie sind zugleich das **Bedienelement**: ein Klick heisst «zeig mir diese
 * Nummern». Damit ist die frühere Liste darunter (eine aufklappbare Sektion je Zustand,
 * jede mit Punkt, Wort und Menge im Kopf) ersatzlos entfallen – sie sagte Zeile für
 * Zeile dasselbe noch einmal, nur zwanzigmal höher.
 *
 * *Das ist kein Rückschritt hinter #716, sondern sein zweiter Schritt.* Damals stand
 * eine Legende **neben** den Gruppen und sagte dasselbe zweimal; entfernt wurde die
 * Doppelung, nicht die Beschriftung. Jetzt gibt es die Gruppen nicht mehr – es gibt nur
 * noch diese eine Zeile, und sie ist die Fassung, mit der man arbeitet.
 *
 * **Kein Filter.** Was man nicht anklickt, bleibt sichtbar: die Leiste zeigt weiterhin
 * den ganzen Bestand, nur der **Ausschnitt darunter** wechselt. Ein Filter würde
 * verstecken, was er nicht zeigt.
 */
export function StockBar({ states, height = 10, onPick, active }: {
  states: StockState[];
  height?: number;
  /** Klick auf ein Segment bzw. seine Beschriftung. Ohne Handler ist alles reine Anzeige. */
  onPick?: (status: string) => void;
  /** Welcher Zustand gerade offen ist – er tritt hervor, die anderen zurück. */
  active?: string | null;
}) {
  const total = states.reduce((n, s) => n + s.quantity, 0);
  if (total === 0) {
    return (
      <div className="rounded-full bg-bg-3" style={{ height }} aria-hidden />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex w-full overflow-hidden rounded-full" style={{ height }}>
        {states.map((s, i) => {
          const cfg = statusCfg(s.status);
          const share = (s.quantity / total) * 100;
          const dimmed = active != null && active !== s.status;
          const title = `${s.quantity} × ${cfg.label}`;
          // **Eine Haarlinie zwischen den Segmenten** – sonst verschmelzen zwei
          // gleichfarbige Nachbarn zu einem (Freigegeben + Verbaut + Verkauft sind alle
          // grün, #789). Sie ist ein `border`, kein `gap`: bei `gap` summierten sich die
          // Prozentbreiten über 100 %, und das letzte Segment fiele hinter
          // `overflow: hidden`. `box-sizing: border-box` gilt global, die Linie frisst
          // die Breite also nicht auf.
          const style: React.CSSProperties = {
            width: `${share}%`,
            background: cfg.color,
            opacity: dimmed ? 0.3 : 1,
            borderRight: i < states.length - 1 ? '1px solid var(--bg-1)' : undefined,
            transition: 'opacity .12s',
          };
          if (!onPick) return <span key={s.status} data-tip={title} style={style} />;
          return (
            <button
              key={s.status}
              type="button"
              aria-label={title}
              data-tip={`${title} – Nummern anzeigen`}
              onClick={(e) => { e.stopPropagation(); onPick(s.status); }}
              style={style}
            />
          );
        })}
      </div>
      {/* **Die Beschriftung gehört zur Leiste, nicht daneben.** Sie bricht um statt zu
          scrollen: seitwärts scrollen ist im ERP verboten, und bei sechs Zuständen auf
          375 px passen sie nicht in eine Zeile. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {states.map((s) => (
          <StateMark
            key={s.status}
            state={s}
            active={active === s.status}
            dimmed={active != null && active !== s.status}
            onPick={onPick}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * **Punkt · Wort · Menge** – die kleinste vollständige Aussage über einen Zustand, und
 * dieselbe Anatomie, die im Haus jeden Status schreibt (Design System: Status = Punkt +
 * Wort). Die Menge steht in Tabellenziffern daneben, damit untereinander stehende
 * Zahlen bündig bleiben.
 *
 * **Der gewählte tritt hervor, statt dass die anderen verschwinden**: kräftigere Farbe
 * und ein Strich darunter – ein Zustand, der aus der Zeile fällt, sobald man einen
 * anderen ansieht, wäre ein Filter.
 */
function StateMark({ state, active, dimmed, onPick }: {
  state: StockState;
  active: boolean;
  dimmed: boolean;
  onPick?: (status: string) => void;
}) {
  const cfg = statusCfg(state.status);
  const body = (
    <>
      <span aria-hidden className="rounded-full" style={{
        width: 7, height: 7, flex: 'none', background: cfg.color,
      }} />
      <span className={active ? 'font-medium' : undefined}
        style={{ color: active ? 'var(--fg-1)' : 'var(--fg-2)' }}>
        {cfg.label}
      </span>
      <span className="ix-tnum" style={{ color: 'var(--fg-3)' }}>{state.quantity}</span>
    </>
  );
  const style: React.CSSProperties = {
    opacity: dimmed ? 0.55 : 1,
    borderBottom: `1px solid ${active ? cfg.color : 'transparent'}`,
    paddingBottom: 1,
    transition: 'opacity .12s',
  };
  if (!onPick) {
    return <span className="flex items-center gap-1.5 text-[12.5px]" style={style}>{body}</span>;
  }
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onPick(state.status); }}
      aria-pressed={active}
      data-tip={active ? 'Nummern ausblenden' : 'Nummern anzeigen'}
      className="flex items-center gap-1.5 text-[12.5px]"
      style={style}
    >
      {body}
    </button>
  );
}
