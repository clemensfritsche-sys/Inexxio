'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, CreditCard, Loader2, X } from 'lucide-react';
import type { BelegNote as Note, BelegView as View } from '@/types';
import { api, ApiError } from '@/lib/api';
import meta from '@/lib/site-meta.json';
import { PayOnline } from '@/components/erp/pay-online';
import { Paper, StageWord } from './paper';
import { Stations } from './stations';
import css from './beleg.module.css';

type Act = 'agree' | 'decline';

/** Nach einer Kartenzahlung: so oft und so lange fragen wir nach, ob sie gebucht ist. */
const POLL_TRIES = 6;
const POLL_MS = 3000;

/** Der Link der Seite in der Adresszeile – `?t=` ist alles, was sie braucht. */
function setUrlToken(token: string) {
  window.history.replaceState(null, '', `${window.location.pathname}?t=${encodeURIComponent(token)}`);
}

/** Ein Link des Servers (absolut, mit seiner Basis-URL) als Pfad dieser Domain. */
function localHref(link: string): string {
  try {
    const u = new URL(link, window.location.href);
    return u.pathname.endsWith('/beleg') ? `${u.pathname}${u.search}` : u.href;
  } catch {
    return link;
  }
}

/**
 * ►►► **Die Seite der Partei** – ein Beleg über seinen unerratbaren Link, ohne Anmeldung. ◄◄◄
 *
 * Das Wort gross im Kopf, der Weg in vier Stationen, die Handlungen, die der Server erlaubt
 * (`actions`, aus `can` als die Partei), oder statt ihrer ein Satz (`note`). Darunter das
 * Papier, wie es hinausging – die AGB sind seine letzte Seite. Die Seite entscheidet nichts
 * selbst: nach jeder Handlung zeigt sie die Antwort des Servers.
 */
export function BelegPage() {
  const [token, setToken] = useState<string | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [failed, setFailed] = useState<{ title: string; text: string } | null>(null);
  const [busy, setBusy] = useState<Act | null>(null);
  const [actError, setActError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [paying, setPaying] = useState(false);
  const [paid, setPaid] = useState(false);

  /** Jede Antwort des Servers ist die neue Ansicht; zeigt sie ein anderes Dokument, zeigt die
   *  Adresszeile dessen Link (ein Neuladen bleibt dort). */
  const apply = useCallback((v: View, current: string) => {
    setView(v);
    if (v.token && v.token !== current) {
      setToken(v.token);
      setUrlToken(v.token);
    }
  }, []);

  const load = useCallback(async (t: string) => {
    try {
      apply(await api.publicBeleg(t), t);
      setFailed(null);
    } catch (e) {
      const missing = e instanceof ApiError && e.status === 404;
      setFailed({
        title: missing ? 'Diesen Beleg gibt es nicht.' : 'Der Beleg lässt sich gerade nicht laden.',
        text: missing ? 'Bitte prüfen Sie den Link in unserer Mail.' : 'Bitte laden Sie die Seite in einem Moment neu.',
      });
    }
  }, [apply]);

  // Der Link kommt als Query (`/beleg?t=…`, statischer Export). Kehrt eine Zahlung vom Dienst
  // zurück (TWINT u. a.), steht dessen Antwort dabei – dann gilt sie als ausgeführt.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get('t');
    if (!t) {
      setFailed({ title: 'Diesen Beleg gibt es nicht.', text: 'Bitte prüfen Sie den Link in unserer Mail.' });
      return;
    }
    setToken(t);
    if (q.get('redirect_status') === 'succeeded') setPaid(true);
    if (q.has('redirect_status') || q.has('payment_intent')) setUrlToken(t);
    void load(t);
  }, [load]);

  // Gebucht wird vom Webhook, nicht von diesem Browser – also ein paar Mal nachfragen.
  useEffect(() => {
    if (!paid || !token) return;
    let tries = 0;
    const id = window.setInterval(async () => {
      tries += 1;
      try {
        const v = await api.publicBeleg(token);
        apply(v, token);
        if (!(v.actions ?? []).includes('pay_online')) window.clearInterval(id);
      } catch { /* der nächste Versuch */ }
      if (tries >= POLL_TRIES) window.clearInterval(id);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [paid, token, apply]);

  useEffect(() => {
    if (!view) return;
    document.title = `${view.word}${view.number ? ` ${view.number}` : ''} | ${meta.brand.legalName}`;
  }, [view]);

  const act = useCallback(async (what: Act) => {
    if (!token) return;
    setBusy(what); setActError(null);
    try {
      apply(await (what === 'agree' ? api.acceptBeleg(token) : api.declineBeleg(token)), token);
      setAsking(false);
    } catch (e) {
      setActError(e instanceof Error ? e.message : String(e));
      void load(token);
    } finally {
      setBusy(null);
    }
  }, [token, apply, load]);

  // Stabil je Link – `PayOnline` bereitet bei jeder neuen Funktion neu vor.
  const prepare = useCallback(() => api.prepareBelegPayment(token ?? ''), [token]);
  const onPaid = useCallback(() => { setPaying(false); setPaid(true); }, []);
  const onClosePay = useCallback(() => setPaying(false), []);

  if (failed && !view) {
    return (
      <div className={css.page}>
        <StageWord word="Beleg" />
        <div className={css.wrap}><NoteBlock note={{ kind: 'error', ...failed }} /></div>
      </div>
    );
  }
  if (!view) {
    return <div className={`${css.page} ${css.loading}`}><StageWord word="" /></div>;
  }

  const actions = view.actions ?? [];
  const stations = view.note?.kind === 'cancelled' ? [] : (view.stations ?? []);
  const canPay = actions.includes('pay_online') && !paid;

  return (
    <div className={css.page}>
      <StageWord word={view.word} />
      <section className={css.wrap}>
        {stations.length > 0 && <Stations stations={stations} />}
        {view.note ? (
          <NoteBlock note={view.note} />
        ) : (
          <Actions actions={actions} busy={busy} asking={asking} canPay={canPay} paying={paying}
            onAct={act} onAsk={setAsking} onPay={() => setPaying(true)} />
        )}
        {actError && <p className={css.err} role="alert">{actError}</p>}
        {paying && canPay && (
          <div className={css.pay}>
            <PayOnline orderObjectId={0} stepId={0} prepare={prepare} label="Mit Karte bezahlen"
              onDone={onPaid} onClose={onClosePay} />
          </div>
        )}
        {paid && actions.includes('pay_online') && (
          <p className={css.paid} role="status">
            <Check size={18} strokeWidth={2.25} />
            Zahlung ausgeführt – gebucht wird, sobald sie bestätigt ist.
          </p>
        )}
      </section>
      <Paper html={view.html} label={`${view.word}${view.number ? ` ${view.number}` : ''}`} />
    </div>
  );
}

/** Die Handlungen, die der Server erlaubt – Ablehnen fragt einmal nach. */
function Actions({ actions, busy, asking, canPay, paying, onAct, onAsk, onPay }: {
  actions: string[];
  busy: Act | null;
  asking: boolean;
  canPay: boolean;
  paying: boolean;
  onAct: (what: Act) => void;
  onAsk: (asking: boolean) => void;
  onPay: () => void;
}) {
  const spin = <Loader2 size={18} className="animate-spin" />;
  if (asking) {
    return (
      <div className={css.acts}>
        <p className={css.ask}>Möchten Sie die Offerte wirklich ablehnen?</p>
        <button type="button" className={`${css.btn} ${css.decline}`} disabled={busy !== null}
          onClick={() => onAct('decline')}>
          {busy === 'decline' ? spin : <X size={18} strokeWidth={2.25} />}Ja, ablehnen
        </button>
        <button type="button" className={`${css.btn} ${css.quiet}`} disabled={busy !== null}
          onClick={() => onAsk(false)}>Zurück</button>
      </div>
    );
  }
  const agree = actions.includes('agree');
  const decline = actions.includes('decline');
  const pay = canPay && !paying;
  if (!agree && !decline && !pay) return null;
  return (
    <div className={css.acts}>
      {agree && (
        <button type="button" className={`${css.btn} ${css.agree}`} disabled={busy !== null}
          onClick={() => onAct('agree')}>
          {busy === 'agree' ? spin : <Check size={18} strokeWidth={2.25} />}Offerte annehmen
        </button>
      )}
      {decline && (
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
function NoteBlock({ note }: { note: Note }) {
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
