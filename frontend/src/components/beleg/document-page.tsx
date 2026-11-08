'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, Clock, X } from 'lucide-react';
import { TextArea } from '@/components/form/field';
import type { Deal, PublicDocument as View } from '@/types';
import { api, ApiError, assetUrl } from '@/lib/api';
import { day } from '@/lib/when';
import meta from '@/lib/site-meta.json';
import { SignaturePad } from '@/components/erp/signature-pad';
import { PayOnline } from '@/components/erp/pay-online';
import { Paper, StageWord } from './paper';
import { Stations } from './stations';
import { DealActions, NoteBlock, type DealAct } from './deal';
import css from './beleg.module.css';
import { errorText } from '@/lib/use-action';

/** Nach einer Kartenzahlung: so oft und so lange fragen wir nach, ob sie gebucht ist. */
const POLL_TRIES = 6;
const POLL_MS = 3000;

const NO_LINK = { title: 'Diesen Link gibt es nicht.', text: 'Bitte prüfen Sie den Link in unserer Mail.' };

/** Der Link der Seite in der Adresszeile – `?t=` ist alles, was sie braucht. */
function setUrlToken(token: string) {
  window.history.replaceState(null, '', `${window.location.pathname}?t=${encodeURIComponent(token)}`);
}

/** Was ein Papier heisst: bei einem Beleg Wort und Nummer, sonst Art und Name. */
function titleOf(view: View): string {
  const d = view.deal;
  return d ? `${d.word}${d.number ? ` ${d.number}` : ''}` : `${view.art} ${view.name}`;
}

/**
 * ►►► **Die Seite eines Dokuments nach aussen** – EINE Seite für jeden Link aus unserer Mail. ◄◄◄
 *
 * Das Wort gross, darunter was der Server erlaubt: unterschreiben oder ablehnen, wer als
 * Unterzeichner verlangt ist; ist es ein **Papier eines Belegs** (`deal`), der Weg in Stationen
 * und die Handlungen der Partei (annehmen, ablehnen, mit Karte bezahlen) oder statt ihrer ein
 * Satz. Darunter das Papier. Die Seite entscheidet nichts selbst: nach jeder Handlung zeigt sie
 * die Antwort des Servers; zeigt die ein anderes Papier, steht dessen Link in der Adresszeile.
 */
export function DocumentPage() {
  const [token, setToken] = useState<string | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [failed, setFailed] = useState<{ title: string; text: string } | null>(null);
  const [paid, setPaid] = useState(false);

  const apply = useCallback((v: View, current: string) => {
    setView(v);
    const next = v.deal?.token;
    if (next && next !== current) { setToken(next); setUrlToken(next); }
  }, []);

  const load = useCallback(async (t: string) => {
    try {
      apply(await api.publicDocument(t), t);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setFailed(status === 410
        ? { title: 'Dieses Dokument ist nicht mehr verfügbar.', text: errorText(e, '') }
        : status === 404 ? NO_LINK
          : { title: 'Das Dokument lässt sich gerade nicht laden.', text: 'Bitte laden Sie die Seite in einem Moment neu.' });
    }
  }, [apply]);

  // Kehrt eine Zahlung vom Dienst zurück (TWINT u. a.), steht dessen Antwort dabei.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const t = q.get('t');
    if (!t) { setFailed(NO_LINK); return; }
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
        const v = await api.publicDocument(token);
        apply(v, token);
        if (!(v.deal?.actions ?? []).includes('pay_online')) window.clearInterval(id);
      } catch { /* der nächste Versuch */ }
      if (tries >= POLL_TRIES) window.clearInterval(id);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [paid, token, apply]);

  useEffect(() => {
    if (view) document.title = `${titleOf(view)} | ${meta.brand.name}`;
  }, [view]);

  if (failed && !view) {
    return (
      <div className={css.page}>
        <StageWord word="Dokument" />
        <div className={css.wrap}><NoteBlock note={{ kind: 'error', ...failed }} /></div>
      </div>
    );
  }
  if (!view || !token) return <div className={`${css.page} ${css.loading}`}><StageWord word="" /></div>;
  return (
    <div className={css.page}>
      <StageWord word={view.deal?.word ?? view.art} />
      <section className={css.wrap}>
        {view.deal && (
          <DealSection token={token} deal={view.deal} paid={paid} onPaid={() => setPaid(true)}
            onView={(v) => apply(v, token)} reload={() => load(token)} />
        )}
        <Signing token={token} view={view} onView={setView} />
      </section>
      <Body view={view} />
    </div>
  );
}

/** ►► **Der Vorgang eines Belegs** – Stationen, Handlungen der Partei oder ein Satz, Bezahlen. ◄◄ */
function DealSection({ token, deal, paid, onPaid, onView, reload }: {
  token: string;
  deal: Deal;
  paid: boolean;
  onPaid: () => void;
  onView: (v: View) => void;
  reload: () => void;
}) {
  const [busy, setBusy] = useState<DealAct | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [paying, setPaying] = useState(false);

  const act = async (what: DealAct) => {
    setBusy(what); setError(null);
    try {
      onView(await (what === 'agree' ? api.agreeDocument(token) : api.rejectDocument(token)));
      setAsking(false);
    } catch (e) {
      setError(errorText(e));
      reload();
    } finally {
      setBusy(null);
    }
  };
  // Stabil je Link – `PayOnline` bereitet bei jeder neuen Funktion neu vor.
  const prepare = useCallback(() => api.prepareDocumentPayment(token), [token]);
  const done = useCallback(() => { setPaying(false); onPaid(); }, [onPaid]);
  const close = useCallback(() => setPaying(false), []);

  const actions = deal.actions ?? [];
  const stations = deal.note?.kind === 'cancelled' ? [] : (deal.stations ?? []);
  const canPay = actions.includes('pay_online') && !paid;
  return (
    <>
      {stations.length > 0 && <Stations stations={stations} />}
      {deal.note ? <NoteBlock note={deal.note} /> : (
        <DealActions actions={actions} busy={busy} asking={asking} canPay={canPay} paying={paying}
          onAct={act} onAsk={setAsking} onPay={() => setPaying(true)} />
      )}
      {error && <p className={css.err} role="alert">{error}</p>}
      {paying && canPay && (
        <div className={css.pay}>
          <PayOnline orderObjectId={0} stepId={0} prepare={prepare} label="Mit Karte bezahlen"
            onDone={done} onClose={close} />
        </div>
      )}
      {paid && actions.includes('pay_online') && (
        <p className={css.paid} role="status">
          <Check size={18} strokeWidth={2.25} />
          Zahlung ausgeführt – gebucht wird, sobald sie bestätigt ist.
        </p>
      )}
    </>
  );
}

/** ►► **Unterschreiben** – ein Zug auf der Fläche; Ablehnen fragt nach dem Grund. Endgültig. ◄◄ */
function Signing({ token, view, onView }: { token: string; view: View; onView: (v: View) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  const act = async (run: () => Promise<View>) => {
    setBusy(true); setError(null);
    try { onView(await run()); setDeclining(false); } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  const actions = view.actions ?? [];
  return (
    <>
      <Signers view={view} />
      {actions.includes('sign') && !declining && (
        <div style={{ maxWidth: 460, margin: '32px auto 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <SignaturePad value={null} onChange={() => {}} disabled={busy} signerHint="Mit dem Finger oder der Maus unterschreiben"
            onSigned={(png) => act(async () => api.signDocument(token, await dataUrl(png)))} />
          <button type="button" className={`${css.btn} ${css.quiet}`} onClick={() => setDeclining(true)}>Ablehnen</button>
        </div>
      )}
      {declining && (
        <div className={css.acts}>
          <TextArea name="reason" value={reason} onChange={setReason} maxLength={300} rows={3}
            placeholder="Warum lehnen Sie ab?" aria-label="Grund"
            style={{ width: '100%', maxWidth: 460, padding: 12, borderRadius: 'var(--r-md)', border: '1px solid var(--border-2)', font: 'inherit' }} />
          <button type="button" className={`${css.btn} ${css.decline}`} disabled={busy || !reason.trim()}
            onClick={() => act(() => api.declineDocument(token, reason.trim()))}><X size={18} />Ablehnen</button>
          <button type="button" className={`${css.btn} ${css.quiet}`} onClick={() => setDeclining(false)}>Zurück</button>
        </div>
      )}
      {error && <p className={css.err} role="alert">{error}</p>}
    </>
  );
}

/** Das Papier: A4-HTML, wie es hinausging; ein PDF oder Bild steht, wie es ist; sonst ein Knopf. */
function Body({ view }: { view: View }) {
  if (view.html) return <Paper html={view.html} label={titleOf(view)} />;
  if (!view.url) return null;
  return (
    <div className={css.wrap} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, marginTop: 32 }}>
      {view.mime === 'application/pdf' && (
        <iframe title={view.name} src={assetUrl(view.url)}
          style={{ width: '100%', maxWidth: 880, aspectRatio: '210 / 297', border: '1px solid var(--border-1)', background: '#fff' }} />
      )}
      {view.mime.startsWith('image/') && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={assetUrl(view.url)} alt={view.name} style={{ maxWidth: '100%', border: '1px solid var(--border-1)' }} />
      )}
      <a className={`${css.btn} ${css.quiet}`} href={assetUrl(view.url)} target="_blank" rel="noreferrer">
        {view.filename ?? 'Dokument'} öffnen
      </a>
    </div>
  );
}

/** Wer unterschreibt – und wie es steht. */
function Signers({ view }: { view: View }) {
  const list = view.signers ?? [];
  if (!list.length) return null;
  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: '8px auto 0', maxWidth: 460, display: 'flex',
                 flexDirection: 'column', gap: 8, fontSize: 15 }}>
      {list.map((s) => (
        <li key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 8,
          color: s.signed_at ? 'var(--success)' : s.declined_at ? 'var(--danger)' : 'var(--fg-2)' }}>
          {s.signed_at ? <Check size={16} /> : s.declined_at ? <X size={16} /> : <Clock size={16} />}
          <span style={{ color: 'var(--fg-1)' }}>{s.name}</span>
          <span>{s.signed_at ? `unterschrieben am ${day(s.signed_at)}` : s.declined_at ? 'abgelehnt' : 'ausstehend'}</span>
        </li>
      ))}
    </ul>
  );
}

function dataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(new Error('Die Unterschrift liess sich nicht lesen.'));
    r.readAsDataURL(blob);
  });
}
