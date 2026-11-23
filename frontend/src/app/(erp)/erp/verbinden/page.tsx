'use client';

import { useEffect, useState } from 'react';
import { Check, Eye, FileCheck2, Unplug } from 'lucide-react';
import { api } from '@/lib/api';
import type { McpAsk } from '@/types';
import { errorText, useAction } from '@/lib/use-action';

/**
 * ►►► **Claude verbinden** – hierher schickt ein Claude-Client (Claude.ai, Desktop, Code) die
 * Person, wenn sie das ERP als Connector hinzufügt (`services/mcp`). ◄◄◄
 *
 * Gestaltet wie die Anmeldung (`.ix-login-card`, `app/globals.css`): eine Karte, ein Satz, was
 * Claude darf, die eine rote Handlung «Erlauben», darunter leise «Ablehnen». In einer Testumgebung
 * steht das oben (der Server sagt es, `mcp.title`) – damit niemand Test und Produktion verwechselt.
 * Angemeldet ist die Person über das ERP-Layout (`AuthGate staffOnly`, mit Rücksprung samt `?r=`).
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
    <div className="ix-connect">
      <div className="ix-login-card">
        {failed ? (
          <>
            <h1>Das geht so nicht.</h1>
            <p className="ix-login-sub" role="alert">{failed}</p>
          </>
        ) : ask ? (
          <>
            {!ask.production && <p className="ix-connect-stage">{ask.server}</p>}
            <h1>Claude verbinden</h1>
            <p className="ix-login-sub">{ask.client} möchte mit dem ERP arbeiten – in Ihrem Namen, mit Ihren Rechten.</p>
            <ul className="ix-connect-list">
              <li><Eye aria-hidden />Liest, was Sie im ERP sehen.</li>
              <li><FileCheck2 aria-hidden />Bereitet Vorschläge vor – übernehmen tun Sie, am Datensatz.</li>
              <li><Unplug aria-hidden />Trennen jederzeit unter Konto · Sicherheit.</li>
            </ul>
            <button type="button" className="ix-submit-btn" disabled={busy} onClick={() => answer(true)}>
              <Check size={18} strokeWidth={2.25} aria-hidden />Erlauben
            </button>
            <button type="button" className="ix-login-link" disabled={busy} onClick={() => answer(false)}>Ablehnen</button>
            <p className="ix-login-legal">Zurück an {ask.host}</p>
          </>
        ) : (
          <span className="erp-skel" style={{ display: 'block', height: 120 }} aria-busy="true" aria-label="Lädt" />
        )}
        {error && <p className="ix-login-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}
