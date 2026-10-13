'use client';

/**
 * ►►► **Kommunikation – der Verlauf und die eine Eingabe** (CRM Schritt 2). ◄◄◄
 *
 * Alles ist eine Nachricht, und die Oberfläche kennt keine Art: wie eine Nachricht
 * aussieht, folgt aus ihren Angaben – **rechts**, was von uns kommt (`ours`), **grau**,
 * was das Haus nie verlässt (`channel.outside`), das **Symbol** aus dem Kanal. Ob sie
 * offen oder überfällig ist, sagt der Server; gerechnet wird hier nichts.
 *
 * Die Eingabe hat für E-Mail, Anruf und Intern **dieselbe Form** (Von → An → Antwort auf →
 * Text → Zeitpunkt). Die drei Knöpfe wählen nur den Kanal und belegen vor.
 *
 * An einer **Firma** ist der Verlauf ein Spiegel: dieselbe Liste, keine Eingabe und kein
 * offen/überfällig – geschrieben wird immer von Person zu Person.
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Clock, Lock, Mail, Megaphone, Phone, Send, Check, X } from 'lucide-react';
import { api } from '@/lib/api';
import { day, formatWhen, when, whenTitle } from '@/lib/when';
import { ObjId } from '@/components/erp/obj-id';
import type { Message, MessageChannel, VoucherParty } from '@/types';

type Person = { object_id: number; name: string };
type Mode = 'email' | 'phone' | 'internal';

/** Alle, die das Zeichen im Feed betrifft, hören hierauf und laden die Zahlen neu. */
export const MESSAGES_CHANGED = 'inexxio:messages';

const KIND_ICON = { email: Mail, phone: Phone, internal: Lock } as const;
const MODES: { key: Mode; label: string }[] = [
  { key: 'email', label: 'E-Mail' }, { key: 'phone', label: 'Anruf' },
  { key: 'internal', label: 'Intern' },
];

// ─── Verlauf ────────────────────────────────────────────────────────────────

/** Der Kalendertag einer Nachricht – als Aussage («Heute», «Gestern», «13. Sep.»). */
function dayLabel(iso: string): string {
  const [d, m, y] = day(iso).split('.');
  return when(`${y}-${m}-${d}`);
}

/** Eine 9-stellige Zahl im Text ist eine Objektnummer – sie wird zum Link. */
function withLinks(text: string): ReactNode[] {
  return text.split(/(\b\d{9}\b)/).map((part, i) =>
    /^\d{9}$/.test(part) ? <ObjId key={i} value={Number(part)} mono={false} /> : part);
}

function names(list: Person[]): string {
  return list.map((p) => p.name).join(', ');
}

/** Wer hört mit – «an Lea · Cc Marco», «Bcc an 48 Personen», «Notiz». */
function audience(m: Message): string {
  const parts: string[] = [];
  if (m.to.length) parts.push(`an ${names(m.to)}`);
  if (m.cc.length) parts.push(`Cc ${names(m.cc)}`);
  if (m.bcc.length) parts.push(m.bcc.length > 2 ? `Bcc an ${m.bcc.length} Personen` : `Bcc ${names(m.bcc)}`);
  if (!parts.length) return m.channel.outside ? `an ${m.channel.label}` : 'Notiz';
  return parts.join(' · ');
}

function Bubble({ m, mirror }: { m: Message; mirror: boolean }) {
  const Icon = m.bcc.length > 2 ? Megaphone : KIND_ICON[m.channel.kind as Mode] ?? Mail;
  const showState = !mirror && m.open;
  const tone = m.overdue ? 'var(--danger)' : 'var(--color-warning)';
  const since = formatWhen(m.at);
  const bg = !m.channel.outside ? 'var(--bg-3)' : m.ours ? 'var(--accent-soft)' : 'var(--bg-1)';
  const border = showState ? (m.overdue ? 'var(--danger)' : 'var(--color-warning-icon)')
    : !m.channel.outside ? 'var(--bg-3)' : 'var(--border-1)';
  return (
    <div style={{ display: 'flex', justifyContent: m.ours ? 'flex-end' : 'flex-start' }}>
      <div style={{ width: '74%', minWidth: 0, background: bg, border: `1px solid ${border}`,
        borderRadius: 10, padding: '10px 14px 12px', opacity: m.planned ? 0.65 : 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12,
          lineHeight: '16px', color: 'var(--fg-3)', marginBottom: 4, minWidth: 0 }}>
          <Icon size={14} style={{ flex: 'none', color: 'var(--fg-2)' }} />
          <b style={{ color: 'var(--fg-1)', fontWeight: 600, flex: 'none' }}>{m.sender.name}</b>
          <span className="truncate">{audience(m)}</span>
          <span style={{ marginLeft: 'auto', flex: 'none', display: 'inline-flex',
            alignItems: 'center', gap: 6, fontWeight: showState ? 600 : 400,
            color: showState ? tone : undefined }} className="tabular-nums"
            data-tip={whenTitle(m.at)}>
            {showState && <span style={{ width: 8, height: 8, borderRadius: 999, background: tone }} />}
            {showState ? `${sinceWord(since.text)} ${m.overdue ? 'überfällig' : 'offen'}`
              : since.text}
          </span>
        </div>
        {m.subject && <div style={{ fontWeight: 600 }}>{m.subject}</div>}
        {m.body && <div style={{ color: 'var(--fg-2)', whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere' }}>{withLinks(m.body)}</div>}
        {!m.body && m.reply_to.length > 0 && (
          <div style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>Erledigt ohne Antwort</div>
        )}
      </div>
    </div>
  );
}

/** «vor 3 Stunden» → «seit 3 Stunden»: die Zeit zuerst, dann der Zustand. */
function sinceWord(text: string): string {
  return text.startsWith('vor ') ? `seit ${text.slice(4)}` : text;
}

function Divider({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--fg-3)',
      fontSize: 12, margin: '6px 0' }}>
      <span style={{ flex: 1, height: 1, background: 'var(--border-1)' }} />{label}
      <span style={{ flex: 1, height: 1, background: 'var(--border-1)' }} />
    </div>
  );
}

function Timeline({ messages, mirror }: { messages: Message[]; mirror: boolean }) {
  if (!messages.length) {
    return <p style={{ color: 'var(--fg-3)', fontSize: 13, padding: '24px 0' }}>Noch keine Nachrichten.</p>;
  }
  const rows: ReactNode[] = [];
  let last = '';
  for (const m of messages) {
    const label = m.planned ? 'Geplant' : dayLabel(m.at);
    if (label !== last) rows.push(<Divider key={`d-${m.id}`} label={label} />);
    last = label;
    rows.push(<Bubble key={m.id} m={m} mirror={mirror} />);
  }
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>{rows}</div>;
}

// ─── Eingabe ────────────────────────────────────────────────────────────────

function Chip({ children, onRemove, dot }: { children: ReactNode; onRemove?: () => void; dot?: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 26,
      padding: onRemove ? '0 4px 0 10px' : '0 10px', borderRadius: 13, background: 'var(--bg-3)',
      fontSize: 13, maxWidth: '100%' }}>
      {dot && <span style={{ width: 8, height: 8, borderRadius: 999, background: dot, flex: 'none' }} />}
      <span className="truncate">{children}</span>
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label="Entfernen"
          style={{ border: 0, background: 'none', padding: 2, cursor: 'pointer', color: 'var(--fg-3)',
            display: 'flex' }}><X size={13} /></button>
      )}
    </span>
  );
}

/** «An»-Feld wie in einem Mailprogramm: Chips, und tippen sucht (Nummer oder Name). */
function People({ value, onChange, placeholder, single }: {
  value: Person[]; onChange: (v: Person[]) => void; placeholder?: string; single?: boolean;
}) {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<VoucherParty[]>([]);
  useEffect(() => {
    if (q.trim().length < 2) { setHits([]); return; }
    let stale = false;
    const t = setTimeout(() => {
      api.searchVoucherParties(q, 8).then((r) => { if (!stale) setHits(r); }).catch(() => {});
    }, 200);
    return () => { stale = true; clearTimeout(t); };
  }, [q]);
  const add = (p: VoucherParty) => {
    const person = { object_id: p.object_id, name: p.name };
    onChange(single ? [person] : [...value.filter((v) => v.object_id !== p.object_id), person]);
    setQ('');
  };
  const full = single && value.length > 0;
  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexWrap: 'wrap',
      gap: 6, alignItems: 'center', minHeight: 28 }}>
      {value.map((p) => (
        <Chip key={p.object_id} onRemove={() => onChange(value.filter((v) => v !== p))}>{p.name}</Chip>
      ))}
      {!full && (
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={value.length ? '' : placeholder}
          style={{ border: 0, outline: 'none', font: 'inherit', fontSize: 13, flex: 1, minWidth: 140,
            background: 'transparent' }} />
      )}
      {hits.length > 0 && (
        <div style={{ position: 'absolute', top: '100%', left: 0, zIndex: 30, marginTop: 4,
          background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 8,
          boxShadow: 'var(--shadow-md)', minWidth: 240, padding: 4 }}>
          {hits.map((h) => (
            <button key={h.object_id} type="button" onClick={() => add(h)}
              style={{ display: 'flex', gap: 10, width: '100%', textAlign: 'left', border: 0,
                padding: '6px 8px', borderRadius: 6, cursor: 'pointer',
                fontSize: 13 }}
              className="bg-transparent hover:bg-bg-2">
              <span className="tabular-nums" style={{ color: 'var(--fg-3)' }}>{h.object_id}</span>
              <span className="truncate">{h.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '7px 0',
      borderBottom: '1px solid var(--border-1)' }}>
      <span style={{ width: 84, flex: 'none', fontSize: 12, color: 'var(--fg-3)', paddingTop: 4 }}>{label}</span>
      {children}
    </div>
  );
}

const LATER = [
  { key: '1h', label: 'In 1 Std.', at: () => new Date(Date.now() + 3_600_000) },
  { key: 'tomorrow', label: 'Morgen 09:00', at: () => {
    const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0); return d; } },
  { key: 'monday', label: 'Montag 09:00', at: () => {
    const d = new Date(); d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7)); d.setHours(9, 0, 0, 0); return d; } },
];

function ModeSwitch({ mode, onPick }: { mode: Mode; onPick: (m: Mode) => void }) {
  return (
      <div role="radiogroup" aria-label="Art" style={{ display: 'inline-flex', background: 'var(--bg-3)',
        borderRadius: 8, padding: 3, gap: 2, flexWrap: 'wrap' }}>
        {MODES.map(({ key, label }) => {
          const Icon = KIND_ICON[key];
          const on = mode === key;
          return (
            <button key={key} type="button" aria-pressed={on} onClick={() => onPick(key)}
              style={{ border: 0, borderRadius: 6, height: 30, padding: '0 12px', fontSize: 13,
                fontWeight: on ? 600 : 500, display: 'inline-flex', alignItems: 'center', gap: 6,
                cursor: 'pointer', background: on ? 'var(--bg-1)' : 'transparent',
                color: on ? 'var(--fg-1)' : 'var(--fg-2)',
                boxShadow: on ? '0 1px 2px rgba(10,10,11,.08)' : 'none' }}>
              <Icon size={14} />{label}
            </button>
          );
        })}
      </div>
  );
}

type Set<T> = (v: T) => void;

function Fields(p: {
  mode: Mode; channel?: MessageChannel; from: Person[]; setFrom: Set<Person[]>;
  to: Person[]; setTo: Set<Person[]>; cc: Person[]; setCc: Set<Person[]>;
  bcc: Person[]; setBcc: Set<Person[]>; showCc: boolean; setShowCc: Set<boolean>;
  subject: string; setSubject: Set<string>; open: Message[]; replyTo: number[];
  setReplyTo: Set<number[]>; later: string | null; setLater: Set<string | null>;
}) {
  const { mode, channel, from, setFrom, to, setTo, cc, setCc, bcc, setBcc, showCc, setShowCc,
    subject, setSubject, open, replyTo, setReplyTo, later, setLater } = p;
  return (
      <div style={{ marginTop: 6 }}>
        <Row label="Von">
          <People value={from} onChange={setFrom} single placeholder="Name eintippen" />
          {mode === 'email' && (
            <span style={{ fontSize: 12, color: 'var(--fg-3)', paddingTop: 4, flex: 'none' }}
              data-tip="Eine Antwort geht über den Kanal, auf dem die Nachricht kam">über {channel?.label}</span>
          )}
        </Row>
        <Row label="An">
          <People value={to} onChange={setTo}
            placeholder={mode === 'internal' ? 'Name eintippen – leer lassen für eine Notiz' : 'Name eintippen'} />
          {mode === 'email' && !showCc && (
            <button type="button" onClick={() => setShowCc(true)}
              style={{ border: 0, background: 'none', fontSize: 12, color: 'var(--fg-3)',
                cursor: 'pointer', paddingTop: 4, flex: 'none' }}>Cc&nbsp;&nbsp;Bcc</button>
          )}
        </Row>
        {mode === 'email' && showCc && <>
          <Row label="Cc"><People value={cc} onChange={setCc} /></Row>
          <Row label="Bcc"><People value={bcc} onChange={setBcc} /></Row>
        </>}
        {mode === 'email' && (
          <Row label="Betreff">
            <input value={subject} onChange={(e) => setSubject(e.target.value)}
              style={{ border: 0, outline: 'none', font: 'inherit', fontSize: 13, flex: 1,
                minWidth: 0, background: 'transparent', minHeight: 28 }} />
          </Row>
        )}
        {open.length > 0 && (
          <Row label="Antwort auf">
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: 6, flex: 1, minWidth: 0 }}>
              {open.map((m) => replyTo.includes(m.id) && (
                <Chip key={m.id} dot={m.overdue ? 'var(--danger)' : 'var(--color-warning-icon)'}
                  onRemove={() => setReplyTo(replyTo.filter((i) => i !== m.id))}>
                  {m.subject || m.body.slice(0, 40) || m.sender.name}
                </Chip>
              ))}
              {replyTo.length === 0 && <span style={{ fontSize: 12, color: 'var(--fg-4)', paddingTop: 4 }}>—</span>}
            </span>
          </Row>
        )}
        {later !== null && (
          <Row label={mode === 'internal' ? 'Erinnern' : 'Senden'}>
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {LATER.map((l) => (
                <button key={l.key} type="button" onClick={() => setLater(l.key)}
                  style={{ border: 0, height: 26, padding: '0 10px', borderRadius: 13, fontSize: 13,
                    cursor: 'pointer', background: later === l.key ? 'var(--fg-1)' : 'var(--bg-3)',
                    color: later === l.key ? '#fff' : 'var(--fg-1)' }}>{l.label}</button>
              ))}
            </span>
          </Row>
        )}
      </div>
  );
}

function Composer({ person, me, channels, open, onSent }: {
  person: Person; me: Person; channels: MessageChannel[]; open: Message[];
  onSent: () => void;
}) {
  const [mode, setMode] = useState<Mode>('email');
  const [from, setFrom] = useState<Person[]>([me]);
  const [to, setTo] = useState<Person[]>([person]);
  const [cc, setCc] = useState<Person[]>([]);
  const [bcc, setBcc] = useState<Person[]>([]);
  const [showCc, setShowCc] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [replyTo, setReplyTo] = useState<number[]>(open.map((m) => m.id));
  const [later, setLater] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Was offen ist, wird vorbelegt – auch nachdem eine Antwort ankam.
  const openKey = open.map((m) => m.id).join(',');
  useEffect(() => { setReplyTo(open.map((m) => m.id)); }, [openKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const subj = open.find((m) => m.subject)?.subject;
    if (subj && !subject) setSubject(subj.startsWith('Re:') ? subj : `Re: ${subj}`);
  }, [openKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (m: Mode) => {
    setMode(m); setError(null);
    setFrom([me]);
    setTo(m === 'internal' ? [] : [person]);
  };
  const channel = channels.find((c) => c.kind === mode);
  const verb = mode === 'phone' ? 'Anruf festhalten'
    : mode === 'internal' ? (later ? 'Erinnerung setzen' : 'Speichern')
      : (later ? 'Später senden' : 'Senden');

  const send = async (silent = false) => {
    if (!channel || !from[0]) return;
    setBusy(true); setError(null);
    const named = new Set([from[0].object_id, ...[...to, ...cc, ...bcc].map((p) => p.object_id)]);
    try {
      await api.createMessage({
        channel: channel.key, sender: from[0].object_id,
        to: to.map((p) => p.object_id), cc: cc.map((p) => p.object_id),
        bcc: bcc.map((p) => p.object_id),
        about: named.has(person.object_id) ? [] : [person.object_id],
        subject: mode === 'email' ? subject : null, body: silent ? '' : body,
        at: later ? LATER.find((l) => l.key === later)!.at().toISOString() : null,
        reply_to: replyTo,
      });
      setBody(''); setLater(null); setSubject('');
      onSent();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Konnte nicht gespeichert werden.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); void send(); }}
      style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 12,
        padding: '12px 16px 14px', marginTop: 16 }}>
      <ModeSwitch mode={mode} onPick={pick} />

      <Fields mode={mode} channel={channel} from={from} setFrom={setFrom} to={to} setTo={setTo}
        cc={cc} setCc={setCc} bcc={bcc} setBcc={setBcc} showCc={showCc} setShowCc={setShowCc}
        subject={subject} setSubject={setSubject} open={open} replyTo={replyTo}
        setReplyTo={setReplyTo} later={later} setLater={setLater} />

      <label htmlFor="msg-body" className="sr-only">Text</label>
      <textarea id="msg-body" value={body} onChange={(e) => setBody(e.target.value)} rows={3}
        placeholder={mode === 'phone' ? 'Was wurde besprochen?'
          : mode === 'internal' ? `Notiz oder Frage zu ${person.name} – nur intern sichtbar. Eine Objektnummer wird zum Link.`
            : `Nachricht an ${to[0]?.name ?? person.name} …`}
        style={{ width: '100%', border: 0, outline: 'none', resize: 'vertical', font: 'inherit',
          fontSize: 14, padding: '10px 0', minHeight: 64, background: 'transparent' }} />
      {error && <p style={{ color: 'var(--danger)', fontSize: 13, margin: '0 0 8px' }}>{error}</p>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" aria-label={mode === 'internal' ? 'Erinnerung' : 'Später'}
          data-tip={mode === 'internal' ? 'Erinnerung' : 'Später senden'}
          onClick={() => setLater(later ? null : 'tomorrow')}
          style={{ width: 36, height: 36, borderRadius: 8, border: 0, cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            background: later ? 'var(--fg-1)' : 'transparent', color: later ? '#fff' : 'var(--fg-3)' }}>
          <Clock size={16} />
        </button>
        <span style={{ flex: 1 }} />
        {mode === 'internal' && replyTo.length > 0 && (
          <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={busy}
            onClick={() => void send(true)} style={{ height: 40 }}>
            <Check size={15} /> Erledigt ohne Antwort
          </button>
        )}
        <button type="submit" className="erp-actbtn erp-actbtn-primary"
          disabled={busy || !body.trim() || !from[0]} style={{ height: 40 }}>
          {mode === 'internal' ? <Lock size={15} /> : <Send size={15} />} {verb}
        </button>
      </div>
    </form>
  );
}

// ─── Die Ansicht ────────────────────────────────────────────────────────────

export function Communication({ person, company, me }: {
  /** Person: Verlauf mit Eingabe. */
  person?: Person;
  /** Firma: der Verlauf ihrer Personen, nur lesend. */
  company?: number;
  me?: Person | null;
}) {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [channels, setChannels] = useState<MessageChannel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    api.getMessages(person ? { person: person.object_id } : { company })
      .then((m) => { setMessages(m); setError(null); })
      .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht geladen werden.'));
  }, [person, company]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (person) api.messageChannels().then(setChannels).catch(() => {}); }, [person]);
  const open = useMemo(() => (messages ?? []).filter((m) => m.open), [messages]);

  if (error) return <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>;
  if (!messages) return <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>Lädt …</p>;
  return (
    <div>
      <Timeline messages={messages} mirror={!person} />
      {person && me && channels.length > 0 && (
        <Composer key={person.object_id} person={person} me={me} channels={channels} open={open}
          onSent={() => { load(); window.dispatchEvent(new Event(MESSAGES_CHANGED)); }} />
      )}
    </div>
  );
}
