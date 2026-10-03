'use client';

/**
 * Passkey-Nudge – **nicht** blockierender Anstoss, nach dem Login einen Passkey einzurichten.
 *
 * Der stärkste Hebel für Passkey-Adoption ist der Moment direkt nach einer erfolgreichen
 * Anmeldung (der Nutzer ist im «Anmelde-Mindset»). Genau dann – und nur dann – zeigt diese
 * Karte einen dezenten, **nutzen**-orientierten Hinweis («künftig in Sekunden anmelden»),
 * NICHT angst-orientiert. Sie erscheint ausschliesslich, wenn
 *   • das Gerät einen plattformeigenen Authenticator hat (Face/Touch ID, Windows Hello) UND
 *   • der Nutzer noch KEINEN Passkey hat UND
 *   • sie nicht kürzlich weggeklickt wurde (Cooldown) und das Limit nicht erreicht ist.
 *
 * Selbst-enthalten (eigenes Auth-Handling über onAuthChange) – mountbar in jedem Layout,
 * exakt wie das ConsentGate, nur nicht blockierend. Wegklickbar, respektiert einen Cooldown.
 */

import { useEffect, useState } from 'react';
import { Fingerprint, X, Loader2, CheckCircle2 } from 'lucide-react';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { platformPasskeyAvailable, registerPasskey, isPasskeyCancellation } from '@/lib/passkey';

const KEY = 'inexxio_passkey_nudge';
const COOLDOWN_MS = 30 * 24 * 60 * 60 * 1000;   // 30 Tage Ruhe nach «Später»
const MAX_DISMISS = 3;                            // danach nicht mehr fragen

type State = { dismissals?: number; lastDismiss?: number; done?: boolean };

function readState(): State {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; }
}
function writeState(s: State) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* Storage voll/blockiert – egal */ }
}
/** Soll der Anstoss aktuell unterdrückt werden (bereits eingerichtet / zu oft weggeklickt / Cooldown)? */
function suppressed(): boolean {
  const s = readState();
  if (s.done) return true;
  if ((s.dismissals ?? 0) >= MAX_DISMISS) return true;
  if (s.lastDismiss && Date.now() - s.lastDismiss < COOLDOWN_MS) return true;
  return false;
}

export function PasskeyNudge() {
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let evaluated = false;   // pro Login nur EINMAL prüfen (onIdTokenChanged feuert auch bei Token-Rotation)
    const unsub = onAuthChange(async (fbUser) => {
      if (!fbUser) { evaluated = false; if (!cancelled) setShow(false); return; }
      if (evaluated || suppressed()) return;
      evaluated = true;
      try {
        api.setToken(await fbUser.getIdToken());
        if (!(await platformPasskeyAvailable())) return;
        const list = await api.listPasskeys();
        if (!cancelled && list.length === 0 && !suppressed()) {
          // Kleiner Verzug: erst zeigen, wenn die Zielseite «angekommen» ist – kein Sprung.
          setTimeout(() => { if (!cancelled) setShow(true); }, 1200);
        }
      } catch {
        // Netzwerk/Recht – still bleiben, der Nudge ist rein optional.
      }
    });
    return () => { cancelled = true; unsub(); };
  }, []);

  if (!show) return null;

  function later() {
    const s = readState();
    writeState({ ...s, dismissals: (s.dismissals ?? 0) + 1, lastDismiss: Date.now() });
    setShow(false);
  }

  async function create() {
    setBusy(true); setErr(null);
    try {
      await registerPasskey();
      writeState({ ...readState(), done: true });
      setDone(true);
      setTimeout(() => setShow(false), 2200);
    } catch (e) {
      // Abbruch (Dialog geschlossen) ist kein Fehler – Karte offen lassen, erneut möglich.
      if (!isPasskeyCancellation(e)) {
        setErr(e instanceof Error ? e.message : 'Passkey konnte nicht eingerichtet werden.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ix-passkey-nudge" role="dialog" aria-label="Passkey einrichten">
      {!done && (
        <button type="button" className="ix-nudge-close" onClick={later} aria-label="Schliessen">
          <X size={16} />
        </button>
      )}

      <div className="ix-nudge-icon">
        {done ? <CheckCircle2 size={22} /> : <Fingerprint size={22} />}
      </div>

      {done ? (
        <div className="ix-nudge-body">
          <div className="ix-nudge-title">Passkey eingerichtet</div>
          <p className="ix-nudge-text">Beim nächsten Mal melden Sie sich in Sekunden an.</p>
        </div>
      ) : (
        <div className="ix-nudge-body">
          <div className="ix-nudge-title">In Sekunden anmelden</div>
          <p className="ix-nudge-text">
            Richten Sie einen Passkey ein und melden Sie sich künftig mit Face&nbsp;ID, Touch&nbsp;ID
            oder Windows&nbsp;Hello an – ohne Link, ohne Passwort.
          </p>
          {err && <p className="ix-nudge-err">{err}</p>}
          <div className="ix-nudge-actions">
            <button type="button" className="ix-nudge-primary" onClick={create} disabled={busy}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Fingerprint size={15} />}
              Passkey einrichten
            </button>
            <button type="button" className="ix-nudge-later" onClick={later} disabled={busy}>
              Später
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
