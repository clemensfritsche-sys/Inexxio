'use client';

import { useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { McpAsk } from '@/types';
import { errorText, useAction } from '@/lib/use-action';
import { StageWord } from '@/components/beleg/paper';
import css from '@/components/beleg/beleg.module.css';

/**
 * ►►► **Claude verbinden** – hierher schickt ein Claude-Client (Claude.ai, Desktop, Code) die
 * Person, wenn sie das ERP als Connector hinzufügt (`services/mcp`). ◄◄◄
 *
 * Angemeldet ist sie über das ERP-Layout (`AuthGate staffOnly`, mit Rücksprung samt `?r=`). Sie
 * sieht, welcher Client was darf, und erlaubt oder lehnt ab; danach geht es zurück zum Client.
 */
export default function ConnectClaude() {
  const [r, setR] = useState<string | null>(null);
  const [ask, setAsk] = useState<McpAsk | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const { run, busy, error } = useAction();

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('r');
    if (!token) { setFailed('Diese Seite öffnet ein Claude-Client, wenn man das ERP verbindet.'); return; }
    setR(token);
    api.mcpRequest(token).then(setAsk).catch((e) => setFailed(errorText(e)));
  }, []);

  const answer = (allow: boolean) => r && run(async () => {
    const out = await api.mcpApprove(r, allow);
    window.location.href = out.redirect;
  });

  return (
    <div className={css.page}>
      <StageWord word="Claude verbinden" />
      <div className={css.wrap}>
        {failed ? (
          <div className={css.note} role="alert">
            <h2 className={css.noteTitle}>Das geht so nicht.</h2>
            <p className={css.noteText}>{failed}</p>
          </div>
        ) : ask && (
          <div className={css.note}>
            <h2 className={css.noteTitle}>{ask.client} möchte mit dem ERP arbeiten – in Ihrem Namen.</h2>
            <p className={css.noteText}>
              Er liest, was Sie im ERP sehen, und bereitet Vorschläge vor. Übernehmen tun Sie im ERP
              («Auf einen Blick» am Datensatz). Trennen können Sie jederzeit unter Konto · Sicherheit.
            </p>
            <p className={css.noteText}>Zurück geht es an: <code style={{ wordBreak: 'break-all' }}>{ask.redirect}</code></p>
          </div>
        )}
        {ask && !failed && (
          <div className={css.acts}>
            <button type="button" className={`${css.btn} ${css.main}`} disabled={busy}
              onClick={() => answer(true)}><Check size={18} strokeWidth={2.25} />Erlauben</button>
            <button type="button" className={`${css.btn} ${css.quiet}`} disabled={busy}
              onClick={() => answer(false)}><X size={18} strokeWidth={2.25} />Ablehnen</button>
          </div>
        )}
        {error && <p className={css.err} role="alert">{error}</p>}
      </div>
    </div>
  );
}
