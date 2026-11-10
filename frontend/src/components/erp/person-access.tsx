'use client';

/**
 * ►►► **Der Zugang einer Person – EIN Bauteil für Konto und ERP** (wie `AddressBook`). ◄◄◄
 *
 * Ihre **Passkeys** (Name, hinzugefügt, zuletzt benutzt, «Entfernen») und ihre **Verbindungen mit
 * Claude** (Client, erlaubt, zuletzt benutzt, «Trennen»). Dieselben Dienste dahinter
 * (`services/passkey`, `services/mcp`); `owner`: `null` = die eigene Person (Konto), sonst ihre
 * Objektnummer (ERP – nur sie selbst und der Admin, `policy` «person.access»).
 *
 * **Einen Passkey einrichten** und **Claude verbinden** kann nur die Person selbst, auf ihrem Gerät
 * bzw. in ihrem Claude – darum stehen diese Wege nur im Konto (`owner === null`); das ERP sagt es.
 *
 * **Offen** ist eine Verbindung, solange sie nicht getrennt und zuletzt vor höchstens 30 Tagen
 * benutzt ist (`mcp._OPEN`) – was älter ist, steht nicht mehr da.
 */

import { useEffect, useState, type ElementType, type ReactNode } from 'react';
import { Fingerprint, Plus, Sparkles, Trash2, Unlink } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { registerPasskey, passkeySupported, isPasskeyCancellation } from '@/lib/passkey';
import { when } from '@/lib/when';
import { errorText, useAction } from '@/lib/use-action';
import { ErrorText } from '@/components/erp/hints';
import type { McpGrant, Passkey } from '@/types';

interface Props {
  /** `null` = die eigene Person (Konto), sonst ihre Objektnummer (ERP). */
  owner: number | null;
  /** Konto (Gestaltung der Website): jede Zeile als graue Karte – dieselben Daten, dieselben Aktionen. */
  cards?: boolean;
}

const keyOf = (owner: number | null, what: 'passkeys' | 'mcp') =>
  owner == null ? ['me', what] as const : qk.access(owner, what);

/** Eine Zeile: Symbol, Wort, Angaben – und die eine Aktion. Konto als Karte, ERP an Haarlinien. */
function Row({ icon: Icon, tag, title, meta, action, onAct, actIcon: ActIcon, cards, first }: {
  icon: ElementType; tag: string; title: ReactNode; meta: string; action: string;
  onAct: () => void; actIcon: ElementType; cards?: boolean; first: boolean;
}) {
  const button = (
    <button type="button" className={cards ? 'kt-round' : 'erp-actbtn erp-actbtn-icon'}
      onClick={onAct} aria-label={action} data-tip={action}>
      <ActIcon size={cards ? 16 : 14} />
    </button>
  );
  if (cards) {
    return (
      <div className="kt-card">
        <span className="kt-card-ic is-red"><Icon aria-hidden /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="kt-card-tag">{tag}</span>
          <div className="kt-card-text">{title}<small>{meta}</small></div>
        </div>
        {button}
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '10px 0',
      borderTop: first ? 'none' : '1px solid var(--border-1)' }}>
      <Icon size={16} aria-hidden style={{ color: 'var(--fg-3)', flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ font: '500 13.5px/20px var(--font-body)', color: 'var(--fg-1)' }}>
          {title} <span style={{ fontWeight: 400, color: 'var(--fg-3)' }}>· {tag}</span>
        </div>
        <div className="tabular-nums" style={{ fontSize: 12, color: 'var(--fg-3)' }}>{meta}</div>
      </div>
      {button}
    </div>
  );
}

function Note({ cards, children }: { cards?: boolean; children: ReactNode }) {
  return cards ? <p className="kt-note">{children}</p>
    : <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--fg-3)' }}>{children}</p>;
}

/** ►► **Die Passkeys einer Person.** ◄◄ Im Konto dazu «Passkey hinzufügen» (nur auf dem eigenen Gerät). */
export function PasskeyList({ owner, cards }: Props) {
  const qc = useQueryClient();
  const key = keyOf(owner, 'passkeys');
  const query = useQuery({ queryKey: key, queryFn: () => api.listPasskeys(owner), meta: { what: 'Passkeys' } });
  const passkeys: Passkey[] = query.data ?? [];
  const setPasskeys = (next: (rows: Passkey[]) => Passkey[]) =>
    qc.setQueryData<Passkey[]>(key, (rows = []) => next(rows));
  const [supported, setSupported] = useState(true);
  const { busy: adding, error, setError, run } = useAction('Passkey konnte nicht hinzugefügt werden.');
  useEffect(() => { setSupported(passkeySupported()); }, []);

  async function add() {
    if (adding) return;
    await run(async () => {
      const created = await registerPasskey();       // Name vergibt der Server (durchnummeriert)
      setPasskeys((rows) => [created, ...rows]);
    }, (err) => { if (isPasskeyCancellation(err)) setError(null); });   // Abbruch ist kein Fehler
  }

  async function remove(id: number) {
    setError(null);
    const before = passkeys;
    setPasskeys((rows) => rows.filter((p) => p.id !== id));
    try {
      await api.deletePasskey(owner, id);
    } catch (err: unknown) {
      setPasskeys(() => before);
      setError(errorText(err, 'Passkey konnte nicht entfernt werden.'));
    }
  }

  const self = owner == null;
  const empty = !query.isPending && passkeys.length === 0;
  return (
    <>
      {error && (cards ? <p className="kt-note is-error">{error}</p> : <ErrorText msg={error} />)}
      {query.isPending ? <Note cards={cards}>Passkeys werden geladen…</Note>
        : empty ? (cards ? (
          <div className="kt-card">
            <span className="kt-card-ic is-red"><Fingerprint aria-hidden /></span>
            <div className="kt-card-text" style={{ flex: 1 }}>
              Noch kein Passkey
              <small>Melden Sie sich mit Face&nbsp;ID, Touch&nbsp;ID oder Windows&nbsp;Hello an – ohne E-Mail-Link. Ein Passkey verlässt Ihr Gerät nie.</small>
            </div>
          </div>
        ) : <Note>Kein Passkey eingerichtet.</Note>)
        : passkeys.map((pk, i) => (
          <Row key={pk.id} icon={Fingerprint} first={i === 0} cards={cards}
            tag={pk.backed_up ? 'Passkey · synchronisiert' : 'Passkey'} title={pk.device_name || 'Passkey'}
            meta={`Hinzugefügt ${when(pk.created_at)}${pk.last_used_at ? ` · zuletzt benutzt ${when(pk.last_used_at)}` : ''}`}
            action="Passkey entfernen" actIcon={Trash2} onAct={() => void remove(pk.id)} />
        ))}
      {!self ? (
        <Note cards={cards}>Einen Passkey richtet die Person selbst im Konto ein – auf ihrem Gerät, das ihn nie verlässt.</Note>
      ) : !supported ? (
        <p className="kt-note">Dieser Browser unterstützt keine Passkeys. Bitte einen aktuellen Browser verwenden.</p>
      ) : empty ? (
        <button type="button" className="kt-pill" onClick={add} disabled={adding} style={{ alignSelf: 'flex-start' }}>
          <Fingerprint size={16} aria-hidden />{adding ? 'Wird erstellt…' : 'Passkey einrichten'}
        </button>
      ) : !query.isPending && (
        <button type="button" className="kt-add" onClick={add} disabled={adding}>
          <Plus size={16} aria-hidden />{adding ? 'Wird erstellt…' : 'Passkey hinzufügen'}
        </button>
      )}
    </>
  );
}

/** ►► **Die Verbindungen einer Person mit Claude** – je erlaubtem Client eine, mit «Trennen». ◄◄
 *  Im Konto davor die Adresse, mit der man Claude verbindet. */
export function ClaudeList({ owner, cards }: Props) {
  const qc = useQueryClient();
  const key = keyOf(owner, 'mcp');
  const grants: McpGrant[] = useQuery({
    queryKey: key, queryFn: () => api.mcpGrants(owner), meta: { what: 'Verbindungen mit Claude' },
  }).data ?? [];
  const [error, setError] = useState('');
  const self = owner == null;

  const cut = async (id: number) => {
    setError('');
    try { qc.setQueryData(key, await api.revokeMcpGrant(owner, id)); } catch (e) { setError(errorText(e)); }
  };

  return (
    <>
      {self && cards && (
        <div className="kt-card">
          <span className="kt-card-ic"><Sparkles aria-hidden /></span>
          <div className="kt-card-text" style={{ flex: 1, minWidth: 0 }}>
            Claude mit dem ERP verbinden
            <small>In Claude unter Connectors «Eigenen Connector hinzufügen» mit dieser Adresse: <code>{`${window.location.origin}/api/v1/mcp`}</code></small>
          </div>
        </div>
      )}
      {error && (cards ? <p className="kt-note is-error">{error}</p> : <ErrorText msg={error} />)}
      {grants.map((g, i) => (
        <Row key={g.id} icon={Sparkles} first={i === 0} cards={cards} tag="Verbunden" title={g.client}
          meta={`Erlaubt ${when(g.at)} · zuletzt benutzt ${when(g.used)}`}
          action="Trennen" actIcon={Unlink} onAct={() => void cut(g.id)} />
      ))}
      {!self && grants.length === 0 && <Note>Kein Claude verbunden.</Note>}
      {!cards && grants.length > 0 && (
        <Note>Trennt jemand in Claude selbst, erfährt das ERP es nicht – nach 30 Tagen ohne Benutzung verschwindet die Verbindung von selbst.</Note>
      )}
    </>
  );
}
