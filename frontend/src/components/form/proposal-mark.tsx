'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { Sparkles, X } from 'lucide-react';
import { when, whenTitle } from '@/lib/when';
import { PROPOSAL_OPEN } from '@/lib/proposals';
import type { Proposal } from '@/types';
import type { FieldProposal } from './use-field';

/**
 * ►►► **Das Zeichen am Feld und sein Fenster – EINE Stelle für jeden Vorschlag** (Bauplan
 * Phase 3, Akte §4.3). ◄◄◄
 *
 * Das Zeichen ist **dasselbe wie «zu tun»** (`detail-frame.TodoChip`): eine kleine Zahl im
 * orangen Kreis. Darüberfahren oder Tippen öffnet ein **minimales Fenster** – neuer Wert,
 * Quelle (Text + wann), «Übernehmen», ✕. Mehr steht nicht da; ein eigenes Formular gibt es nicht.
 *
 * - **Standardform** (`Field`, `SelectField`): das Zeichen steht neben der Beschriftung.
 * - **Freies Aussehen** (`Input`, `Select`, `TextArea` – Beleg, Konto, Editor): das Zeichen
 *   schwebt an der oberen rechten Ecke des Elements (`anchor`), per Portal – das Feld behält
 *   seine Geometrie bis aufs Pixel.
 *
 * «Zum Feld» im Angehefteten findet das Feld über `data-proposal` und öffnet das Fenster über
 * `PROPOSAL_OPEN` (`lib/proposals.openAtField`).
 */
export function ProposalMark({ mark, anchor }: { mark: FieldProposal | null; anchor?: Element | null }) {
  if (!mark) return null;
  return <Mark key={mark.proposal.id} mark={mark} anchor={anchor} />;
}

/** Wie lange das Fenster nach dem Wegfahren stehen bleibt (der Weg vom Zeichen ins Fenster). */
const LINGER_MS = 220;
const MARK = 16;
const WIN_W = 288;

function Mark({ mark, anchor }: { mark: FieldProposal; anchor?: Element | null }) {
  const { proposal: p } = mark;
  const btn = useRef<HTMLButtonElement>(null);
  const win = useRef<HTMLDivElement>(null);
  /** `hover` schliesst beim Wegfahren, `held` erst mit Escape, ✕ oder einem Klick daneben. */
  const [open, setOpen] = useState<null | 'hover' | 'held'>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stay = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } };
  const leave = () => {
    stay();
    timer.current = setTimeout(() => setOpen((o) => (o === 'hover' ? null : o)), LINGER_MS);
  };
  useEffect(() => stay, []);

  // «Zum Feld»: das Angeheftete ruft genau diesen Vorschlag.
  useEffect(() => {
    const onOpen = (e: Event) => {
      if ((e as CustomEvent<{ id: number }>).detail?.id === p.id) setOpen('held');
    };
    window.addEventListener(PROPOSAL_OPEN, onOpen);
    return () => window.removeEventListener(PROPOSAL_OPEN, onOpen);
  }, [p.id]);
  // Im freien Aussehen trägt das Feld selbst die Adresse für «Zum Feld».
  useEffect(() => {
    if (!(anchor instanceof HTMLElement)) return;
    anchor.dataset.proposal = String(p.id);
    return () => { delete anchor.dataset.proposal; };
  }, [anchor, p.id]);
  // Gehalten schliesst Escape und ein Klick daneben.
  useEffect(() => {
    if (open !== 'held') return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(null); };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!btn.current?.contains(t) && !win.current?.contains(t)) setOpen(null);
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => { window.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onDown); };
  }, [open]);

  const floating = useFollow(anchor ?? null);
  const markPos = useFollow(open ? btn.current : null);
  const button = (
    <button ref={btn} type="button" data-proposal={anchor ? undefined : p.id}
      aria-label={`Vorschlag: ${p.label} – ${p.value ?? ''}`} aria-expanded={!!open}
      onMouseEnter={() => { stay(); setOpen((o) => o ?? 'hover'); }} onMouseLeave={leave}
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((o) => (o === 'held' ? null : 'held')); }}
      className="tabular-nums"
      style={{ ...CHIP, ...(anchor ? floatAt(floating) : null) }}>
      1
    </button>
  );
  return (
    <>
      {anchor ? (floating && createPortal(button, document.body)) : button}
      {open && markPos && createPortal(
        <div ref={win} role="dialog" aria-label={`Vorschlag: ${p.label}`}
          onMouseEnter={stay} onMouseLeave={() => { if (open === 'hover') leave(); }}
          style={windowAt(markPos)}>
          <ProposalWindow p={p} onTake={() => { setOpen(null); mark.take(); }}
            onReject={() => { setOpen(null); mark.reject(); }} />
        </div>,
        document.body,
      )}
    </>
  );
}

/** **Das Fenster** – neuer Wert, wovon er abweicht, Quelle, «Übernehmen», ✕. */
function ProposalWindow({ p, onTake, onReject }: { p: Proposal; onTake?: () => void; onReject: () => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)' }}>
        <Sparkles size={13} style={{ color: 'var(--warning)', flex: 'none' }} aria-hidden />
        <span className="truncate" style={{ flex: 1, minWidth: 0 }}>{p.label}</span>
        <button type="button" onClick={onReject} aria-label="Vorschlag verwerfen" data-tip="Verwerfen"
          className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon" style={{ height: 28, ['--actbtn-w' as string]: '28px' }}>
          <X size={14} />
        </button>
      </div>
      <div style={{ font: '600 15px var(--font-body)', color: 'var(--fg-1)', overflowWrap: 'anywhere' }}>
        {p.value || '–'}
      </div>
      {p.current && (
        <div style={{ fontSize: 12, color: 'var(--fg-3)', overflowWrap: 'anywhere' }}>bisher: {p.current}</div>
      )}
      <div style={{ fontSize: 12, color: 'var(--fg-3)', lineHeight: 1.4 }}>
        {p.source.text} · <span data-tip={whenTitle(p.source.at)}>{when(p.source.at)}</span>
      </div>
      {onTake && (
        <button type="button" onClick={onTake} className="erp-actbtn erp-actbtn-primary"
          style={{ height: 36, alignSelf: 'stretch' }}>
          Übernehmen
        </button>
      )}
    </div>
  );
}

/** Dieselbe Form wie «zu tun» (`TodoChip`) – nur als Knopf. */
const CHIP: CSSProperties = {
  minWidth: MARK, height: MARK, padding: '0 4px', borderRadius: 999, border: 'none', cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none',
  color: '#fff', background: 'var(--warning)', font: '700 10.5px/1 var(--font-body)', letterSpacing: 0,
  boxShadow: '0 0 0 2px var(--bg-1)', verticalAlign: 'middle',
};

type Box = { top: number; left: number; right: number; bottom: number };

/** Das schwebende Zeichen an der oberen rechten Ecke des Feldes (unter Dialogen, z 40). */
function floatAt(b: Box | null): CSSProperties {
  return b ? { position: 'fixed', top: b.top - MARK / 2, left: b.right - MARK / 2 - 2, zIndex: 40 }
    : { display: 'none' };
}

/** Das Fenster unter dem Zeichen, im Bild gehalten; reicht der Platz unten nicht, darüber. */
function windowAt(b: Box): CSSProperties {
  const vw = typeof window === 'undefined' ? 1024 : window.innerWidth;
  const vh = typeof window === 'undefined' ? 768 : window.innerHeight;
  const left = Math.max(8, Math.min(b.left - 12, vw - WIN_W - 8));
  const below = b.bottom + 8;
  const place: CSSProperties = below + 200 > vh ? { bottom: vh - b.top + 8 } : { top: below };
  return {
    position: 'fixed', left, ...place, width: `min(${WIN_W}px, calc(100vw - 16px))`, zIndex: 70,
    background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)',
    boxShadow: 'var(--shadow-md)', padding: 12,
  };
}

/**
 * **Wo steht das Element gerade?** – folgt Rollen (auch in inneren Listen), Grösse und Umbruch;
 * `null`, solange es nicht zu sehen ist (weggerollt, im geschlossenen Reiter).
 */
function useFollow(el: Element | null): Box | null {
  const [box, setBox] = useState<Box | null>(null);
  const seen = useRef(true);
  const measure = useCallback(() => {
    if (!el || !el.isConnected) { setBox(null); return; }
    const r = el.getBoundingClientRect();
    const shown = seen.current && r.width > 0 && r.height > 0;
    setBox((b) => {
      if (!shown) return null;
      return b && b.top === r.top && b.left === r.left && b.right === r.right && b.bottom === r.bottom
        ? b : { top: r.top, left: r.left, right: r.right, bottom: r.bottom };
    });
  }, [el]);
  useLayoutEffect(() => {
    if (!el) { setBox(null); return; }
    measure();
    let frame = 0;
    const later = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure); };
    const io = typeof IntersectionObserver === 'undefined' ? null
      : new IntersectionObserver((e) => { seen.current = e.some((x) => x.isIntersecting); later(); });
    io?.observe(el);
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(later);
    ro?.observe(el);
    window.addEventListener('scroll', later, { capture: true, passive: true });
    window.addEventListener('resize', later);
    return () => {
      cancelAnimationFrame(frame);
      io?.disconnect(); ro?.disconnect();
      window.removeEventListener('scroll', later, { capture: true });
      window.removeEventListener('resize', later);
    };
  }, [el, measure]);
  return box;
}
