'use client';

/**
 * ►►► **Der Monat** – ein Feld je Tag, antippen zeigt den Tag. ◄◄◄
 *
 * Unten im Feld: Stunden · Symbol einer ganztägigen Absenz · Summe + kleines Symbol bei
 * Stunden-Absenz · «?» wenn «Gehen» fehlt · «Feiertag». Punkt oben rechts: orange = Hinweis
 * oder es fehlt etwas, rot = gesetzliche Grenze. **Abgeschlossen (älter als 7 Tage) ist
 * blass** – antippen geht trotzdem, der Tag sagt dann, warum er sich nicht mehr ändern lässt.
 * Monatswechsel: ‹ › oder seitwärts wischen.
 */
import { useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { InfoHint } from '@/components/erp/hints';
import { MICRO_LABEL } from '@/components/erp/fields';
import { dayTitle, monthTitle } from '@/lib/when';
import type { TimeDay, TimeVocab } from '@/types';
import { IconButton, WEEKDAYS, hm, timeIcon, weekday } from './time-ui';

function Cell({ d, vocab, selected, inRange, onPick }: {
  d: TimeDay; vocab: TimeVocab; selected: boolean; inRange: boolean; onPick: () => void;
}) {
  const muted = !d.workday;
  const full = !!d.absence && d.absence.minutes == null;
  const art = d.absence ? vocab.arts.find((a) => a.key === d.absence?.art) : undefined;
  const Icon = art ? timeIcon(art.icon) : null;
  const tones = d.hints.map((h) => vocab.hints.find((x) => x.key === h)?.tone);
  const dot = tones.includes('danger') ? 'var(--danger)' : tones.length ? 'var(--warning)' : null;
  let bottom: React.ReactNode = null;
  if (full && Icon) {
    bottom = <span data-tip={art?.label} style={{ display: 'inline-flex', color: 'var(--fg-2)' }}><Icon size={13} /></span>;
  } else if (d.absence && Icon) {
    bottom = (
      <span data-tip={`${art?.label} ${hm(d.absence.minutes_on_day)} h`}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
        {d.open ? '?' : hm(d.ist + d.credit)}<Icon size={11} />
      </span>
    );
  } else if (d.open) {
    bottom = <span style={{ color: 'var(--warning)', fontWeight: 700 }}>?</span>;
  } else if (d.today && (d.ist || d.workday)) {
    bottom = <span style={{ color: 'var(--success)', fontWeight: 600 }}>{hm(d.ist)}</span>;
  } else if (d.ist) {
    bottom = hm(d.ist);
  } else if (d.holiday) {
    bottom = <span data-tip={d.holiday}>Feiertag</span>;
  }
  const bg = selected ? 'var(--accent-soft)' : inRange ? 'var(--accent-soft)'
    : full && !muted ? 'var(--bg-3)' : muted ? 'var(--bg-2)' : 'var(--bg-1)';
  const border = inRange ? '1px dashed var(--accent)'
    : `1px solid ${selected ? 'var(--accent)' : d.today ? 'var(--border-2)' : 'transparent'}`;
  return (
    <button type="button" onClick={onPick} aria-pressed={selected}
      aria-label={`${dayTitle(d.day)}${d.locked ? ' – abgeschlossen' : ''}`}
      style={{ position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        alignItems: 'flex-start', height: 54, padding: '6px 5px 6px 6px', borderRadius: 8, cursor: 'pointer',
        textAlign: 'left', minWidth: 0, border, background: bg,
        // Abgeschlossen: blass, als liesse er sich nicht wählen – er lässt sich ansehen.
        opacity: d.locked && !selected ? 0.45 : 1 }}>
      <span className="tabular-nums" style={{ font: `${d.today ? 700 : 600} 12.5px var(--font-body)`,
        color: muted ? 'var(--fg-4)' : d.today ? 'var(--accent-ink)' : 'var(--fg-2)' }}>
        {Number(d.day.slice(8))}
      </span>
      <span className="tabular-nums" style={{ fontSize: 11, color: 'var(--fg-3)', whiteSpace: 'nowrap', maxWidth: '100%' }}>
        {bottom}
      </span>
      {dot && <span aria-hidden style={{ position: 'absolute', top: 7, right: 7, width: 7, height: 7,
        borderRadius: 999, background: dot }} />}
    </button>
  );
}

export function TimeCalendar({ month, days, vocab, selected, range, onPick, onMonth }: {
  month: string; days: TimeDay[]; vocab: TimeVocab; selected: string | null;
  /** Die Spanne einer Absenz im Werkzeug «Erfassen» (gestrichelt). */
  range: { from: string; until: string } | null;
  onPick: (day: string) => void; onMonth: (step: -1 | 1) => void;
}) {
  const swipe = useRef<number | null>(null);
  const offset = days.length ? weekday(days[0].day) : 0;
  return (
    <div style={{ display: 'grid', gap: 10, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <IconButton icon={ChevronLeft} label="Voriger Monat" height={30} onClick={() => onMonth(-1)} />
        <span className="tabular-nums" style={{ font: '600 15px var(--font-body)', color: 'var(--fg-1)',
          minWidth: 132, textAlign: 'center' }}>{monthTitle(month)}</span>
        <IconButton icon={ChevronRight} label="Nächster Monat" height={30} onClick={() => onMonth(1)} />
        <span style={{ flex: 1 }} />
        <InfoHint text={vocab.texts.calendar} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 4 }}>
        {WEEKDAYS.map((w) => <span key={w} style={{ ...MICRO_LABEL, textAlign: 'center', padding: '2px 0' }}>{w}</span>)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 4, touchAction: 'pan-y' }}
        onPointerDown={(e) => { if (e.pointerType !== 'mouse') swipe.current = e.clientX; }}
        onPointerUp={(e) => {
          if (swipe.current == null) return;
          const dx = e.clientX - swipe.current;
          swipe.current = null;
          if (Math.abs(dx) > 60) onMonth(dx < 0 ? 1 : -1);
        }}>
        {Array.from({ length: offset }, (_, i) => <span key={`e${i}`} />)}
        {days.map((d) => (
          <Cell key={d.day} d={d} vocab={vocab} selected={d.day === selected}
            inRange={!!range && d.day > range.from && d.day <= range.until}
            onPick={() => onPick(d.day)} />
        ))}
      </div>
    </div>
  );
}
