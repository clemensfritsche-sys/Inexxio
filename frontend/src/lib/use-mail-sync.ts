'use client';

import { useEffect } from 'react';
import { api } from '@/lib/api';
import { MESSAGES_CHANGED } from '@/lib/feed';
import { notify, tell } from '@/lib/notice';

/** Wie oft die Postfächer abgeglichen werden, solange das ERP offen und sichtbar ist. */
const SYNC_MS = 60_000;

/**
 * ►►► **Die Postfächer werden abgeglichen, solange das ERP offen ist** (der Server drosselt
 * selbst, ohne Anbindung ist es ein No-op). Neues meldet sich über `MESSAGES_CHANGED` wie
 * jede andere Änderung. Dazu die Rückkehr von Google nach «Postfach verbinden» (`?mail=`):
 * ein Satz in der einen Meldezeile (`lib/notice`), bis er geschlossen wird. ◄◄◄
 */
export function useMailSync(staff: boolean): void {
  useEffect(() => {
    if (!staff) return;
    const tick = () => {
      if (document.hidden) return;
      api.syncMail().then((r) => {
        if (r.new > 0 || r.sent > 0) window.dispatchEvent(new Event(MESSAGES_CHANGED));
      }).catch(tell('Postfach', 'Nicht abgeglichen'));
    };
    tick();
    const t = setInterval(tick, SYNC_MS);
    return () => clearInterval(t);
  }, [staff]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const note = params.get('mail');
    if (!note) return;
    if (note === 'ok') notify('Postfach verbunden – neue Mails erscheinen ab jetzt im Verlauf.', Date.now(), { sticky: true, tone: 'info' });
    else notify(note, Date.now(), { sticky: true });
    params.delete('mail');
    const rest = params.toString();
    window.history.replaceState(null, '', `${window.location.pathname}${rest ? `?${rest}` : ''}`);
  }, []);
}
