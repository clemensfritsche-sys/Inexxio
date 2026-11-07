'use client';

/**
 * ►►► **Kommen ↔ Gehen: ein kleiner Knopf auf dem Tagesbalken.** ◄◄◄
 *
 * Die Bahn ist das Soll (grau), die grüne Fläche das Ist. Der Knopf zeigt die **nächste**
 * Handlung: abwesend → links grün «Kommen», nach rechts wischen; anwesend → rechts rot
 * «Gehen», nach links. Ausgelöst wird ab 70 % des Weges; Tastatur: Pfeil oder Enter. Ein
 * Klick allein stempelt nicht – das Wischen ist die Bestätigung.
 */
import { useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { hm } from './time-ui';

const TRIGGER = 0.7;

export function TimeSwipe({ present, since, lastOut, ist, soll, busy, onSwipe }: {
  present: boolean; since: string | null; lastOut: string | null;
  ist: number; soll: number; busy: boolean; onSwipe: () => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  const knob = useRef<HTMLButtonElement>(null);
  const start = useRef<{ x: number; room: number } | null>(null);
  const [dx, setDx] = useState(0);
  // Ohne Soll (kein Arbeitstag, Feiertag) gibt es keinen Fortschritt – die Bahn bleibt grau.
  const pct = soll > 0 ? Math.min(100, Math.round((ist / soll) * 100)) : 0;
  const figure = soll > 0 ? `${hm(ist)} / ${hm(soll)} h` : `${hm(ist)} h · heute kein Soll`;
  const tip = `${present ? `Anwesend seit ${since}` : lastOut ? `Gegangen um ${lastOut}` : 'Noch nicht gekommen'}`
    + (soll > 0 ? ` · heute ${hm(ist)} h von ${hm(soll)} h` : ` · heute ${hm(ist)} h – kein Arbeitstag, kein Soll`);
  const dir = present ? -1 : 1;

  const down = (e: ReactPointerEvent<HTMLButtonElement>) => {
    if (busy || !track.current || !knob.current) return;
    const room = track.current.clientWidth - knob.current.offsetWidth - 8;
    start.current = { x: e.clientX, room };
    knob.current.setPointerCapture(e.pointerId);
  };
  const move = (e: ReactPointerEvent<HTMLButtonElement>) => {
    if (!start.current) return;
    const d = (e.clientX - start.current.x) * dir;
    setDx(Math.max(0, Math.min(start.current.room, d)));
  };
  const up = () => {
    if (!start.current) return;
    const done = dx >= start.current.room * TRIGGER;
    start.current = null;
    setDx(0);
    if (done) onSwipe();
  };

  return (
    <div ref={track} data-tip={tip} style={{ position: 'relative', height: 48, borderRadius: 999,
      background: 'var(--bg-3)', userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'pan-y' }}>
      <div aria-hidden style={{ position: 'absolute', inset: 0, borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pct}%`,
          background: 'color-mix(in srgb, var(--success) 22%, transparent)' }} />
      </div>
      {/* Die Zahl steht in der Mitte der freien Bahn – nie unter dem Knopf (schmal). */}
      <span aria-hidden className="tabular-nums" style={{ position: 'absolute', inset: 0, display: 'flex',
        alignItems: 'center', justifyContent: 'center', font: '600 13px var(--font-body)',
        color: 'var(--fg-3)', pointerEvents: 'none',
        ...(present ? { paddingRight: 120 } : { paddingLeft: 120 }) }}>{figure}</span>
      <button ref={knob} type="button" disabled={busy}
        aria-label={present ? 'Gehen – nach links wischen' : 'Kommen – nach rechts wischen'}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || (present ? e.key === 'ArrowLeft' : e.key === 'ArrowRight')) {
            e.preventDefault(); onSwipe();
          }
        }}
        style={{ position: 'absolute', top: 4, ...(present ? { right: 4 } : { left: 4 }), height: 40,
          padding: '0 16px', borderRadius: 999, border: 0, color: '#fff', display: 'flex',
          alignItems: 'center', gap: 6, font: '600 14px var(--font-body)', touchAction: 'none',
          cursor: busy ? 'wait' : 'grab', boxShadow: 'var(--shadow-sm)',
          background: present ? 'var(--danger)' : 'var(--success)',
          transform: `translateX(${dx * dir}px)`, transition: start.current ? 'none' : 'transform .2s' }}>
        {present ? <><ChevronLeft size={16} />Gehen</> : <>Kommen<ChevronRight size={16} /></>}
      </button>
    </div>
  );
}
