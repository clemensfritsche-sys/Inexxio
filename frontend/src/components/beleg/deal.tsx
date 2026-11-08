'use client';

import { Check, CreditCard, Loader2, X } from 'lucide-react';
import type { BelegNote as Note } from '@/types';
import css from './beleg.module.css';

/** Was die Partei an einem Papier eines Belegs tun kann (`voucher_docs.PUBLIC_VERBS`). */
export type DealAct = 'agree' | 'reject';

/** Ein Link des Servers (absolut, mit seiner Basis-URL) als Pfad dieser Domain. */
function localHref(link: string): string {
  try {
    const u = new URL(link, window.location.href);
    return u.pathname.endsWith('/dokument') ? `${u.pathname}${u.search}` : u.href;
  } catch {
    return link;
  }
}

/** ►► **Die Handlungen am Vorgang**, die der Server erlaubt – Ablehnen fragt einmal nach. ◄◄ */
export function DealActions({ actions, busy, asking, canPay, paying, onAct, onAsk, onPay }: {
  actions: string[];
  busy: DealAct | null;
  asking: boolean;
  canPay: boolean;
  paying: boolean;
  onAct: (what: DealAct) => void;
  onAsk: (asking: boolean) => void;
  onPay: () => void;
}) {
  const spin = <Loader2 size={18} className="animate-spin" />;
  if (asking) {
    return (
      <div className={css.acts}>
        <p className={css.ask}>Möchten Sie die Offerte wirklich ablehnen?</p>
        <button type="button" className={`${css.btn} ${css.decline}`} disabled={busy !== null}
          onClick={() => onAct('reject')}>
          {busy === 'reject' ? spin : <X size={18} strokeWidth={2.25} />}Ja, ablehnen
        </button>
        <button type="button" className={`${css.btn} ${css.quiet}`} disabled={busy !== null}
          onClick={() => onAsk(false)}>Zurück</button>
      </div>
    );
  }
  const agree = actions.includes('agree');
  const reject = actions.includes('reject');
  const pay = canPay && !paying;
  if (!agree && !reject && !pay) return null;
  return (
    <div className={css.acts}>
      {agree && (
        <button type="button" className={`${css.btn} ${css.agree}`} disabled={busy !== null}
          onClick={() => onAct('agree')}>
          {busy === 'agree' ? spin : <Check size={18} strokeWidth={2.25} />}Offerte annehmen
        </button>
      )}
      {reject && (
        <button type="button" className={`${css.btn} ${css.decline}`} disabled={busy !== null}
          onClick={() => onAsk(true)}>
          <X size={18} strokeWidth={2.25} />Ablehnen
        </button>
      )}
      {pay && (
        <button type="button" className={`${css.btn} ${css.main}`} onClick={onPay}>
          <CreditCard size={18} strokeWidth={2.25} />Mit Karte bezahlen
        </button>
      )}
    </div>
  );
}

/** Ein Satz statt einer Handlung – mit dem Weg zur aktuellen Fassung, wo es sie gibt. */
export function NoteBlock({ note }: { note: Note }) {
  return (
    <div className={css.note} role={note.kind === 'error' ? 'alert' : undefined}>
      <h2 className={css.noteTitle}>{note.title}</h2>
      <p className={css.noteText}>{note.text}</p>
      {note.link && (
        <a className={`${css.btn} ${css.main}`} href={localHref(note.link)}>Zur aktuellen Fassung</a>
      )}
    </div>
  );
}
