'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, Clock, X } from 'lucide-react';
import type { PublicDocument as View } from '@/types';
import { api, ApiError, assetUrl } from '@/lib/api';
import { day } from '@/lib/when';
import meta from '@/lib/site-meta.json';
import { SignaturePad } from '@/components/erp/signature-pad';
import { Paper, StageWord } from './paper';
import css from './beleg.module.css';

/**
 * ►►► **Die Seite eines Dokuments nach aussen** – über den Link aus unserer Mail. ◄◄◄
 *
 * Das Wort gross, wer unterschreibt und wie es steht, die Handlungen, die der Server erlaubt
 * (`actions`), darunter das Papier mit den Unterschriften darin. Unterschreiben ist ein Zug
 * auf der Fläche, Ablehnen fragt nach dem Grund; beides ist endgültig. Ist das Dokument
 * gelöscht, steht ein Satz da (410) – nie ein Fehler.
 */
export function DocumentPage() {
  const [token, setToken] = useState<string | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [failed, setFailed] = useState<{ title: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (t: string) => {
    try {
      setView(await api.publicDocument(t));
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setFailed(status === 410
        ? { title: 'Dieses Dokument ist nicht mehr verfügbar.', text: e instanceof Error ? e.message : '' }
        : status === 404
          ? { title: 'Diesen Link gibt es nicht.', text: 'Bitte prüfen Sie den Link in unserer Mail.' }
          : { title: 'Das Dokument lässt sich gerade nicht laden.', text: 'Bitte laden Sie die Seite in einem Moment neu.' });
    }
  }, []);

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get('t');
    if (!t) { setFailed({ title: 'Diesen Link gibt es nicht.', text: 'Bitte prüfen Sie den Link in unserer Mail.' }); return; }
    setToken(t);
    void load(t);
  }, [load]);

  useEffect(() => {
    if (view) document.title = `${view.art} · ${view.name} | ${meta.brand.legalName}`;
  }, [view]);

  const act = async (run: () => Promise<View>) => {
    setBusy(true); setError(null);
    try { setView(await run()); setDeclining(false); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  if (failed && !view) {
    return (
      <div className={css.page}>
        <StageWord word="Dokument" />
        <div className={css.wrap}>
          <div className={css.note}><h2 className={css.noteTitle}>{failed.title}</h2><p className={css.noteText}>{failed.text}</p></div>
        </div>
      </div>
    );
  }
  if (!view || !token) return <div className={`${css.page} ${css.loading}`}><StageWord word="" /></div>;
  const actions = view.actions ?? [];
  return (
    <div className={css.page}>
      <StageWord word={view.art} />
      <section className={css.wrap}>
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
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} rows={3}
              placeholder="Warum lehnen Sie ab?" aria-label="Grund"
              style={{ width: '100%', maxWidth: 460, padding: 12, borderRadius: 'var(--r-md)', border: '1px solid var(--border-2)', font: 'inherit' }} />
            <button type="button" className={`${css.btn} ${css.decline}`} disabled={busy || !reason.trim()}
              onClick={() => act(() => api.declineDocument(token, reason.trim()))}><X size={18} />Ablehnen</button>
            <button type="button" className={`${css.btn} ${css.quiet}`} onClick={() => setDeclining(false)}>Zurück</button>
          </div>
        )}
        {error && <p className={css.err} role="alert">{error}</p>}
      </section>
      {view.html
        ? <Paper html={view.html} label={`${view.art} ${view.name}`} />
        : view.url && (
          <div className={css.wrap} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, marginTop: 32 }}>
            {/* Ein PDF oder Bild steht, wie es ist; alles andere öffnet der Knopf. */}
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
        )}
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
