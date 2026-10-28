'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ChevronUp, Clock, ExternalLink, Loader2, Mail, Megaphone, MoreHorizontal, Newspaper, Paperclip, Phone, Reply } from 'lucide-react';
import { api } from '@/lib/api';
import { formatWhen, whenDay, whenTitle } from '@/lib/when';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { DraftSheet } from '@/components/erp/document-draft';
import type { Message } from '@/types';
import { DELIVERIES, ICON_BTN, KIND_ICON, Mode, Person, topicColor } from '@/components/erp/communication/shared';

// ─── Verlauf ────────────────────────────────────────────────────────────────

/** Was im Text auf etwas zeigt: «Text <https://…>» (so schreibt Gmail einen Link als
 *  Klartext) · ein blosses `<https://…>` · eine Adresse (`https://…`, `www.…`) · eine
 *  E-Mail · eine 9-stellige Objektnummer. Als Ziel nur `http(s)` und `mailto`. */
const LINK = new RegExp([
  '(\\S+)[ \\t]*<((?:https?://|mailto:)[^>\\s]+)>',
  '<((?:https?://|mailto:)[^>\\s]+)>',
  '((?:https?://|www\\.)[^\\s<>]+)',
  '([\\w.+-]+@[\\w-]+(?:\\.[\\w-]+)+)',
  '\\b(\\d{9})\\b',
].join('|'), 'g');

function A({ href, children }: { href: string; children: ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer noopener"
    className="text-accent hover:underline" style={{ overflowWrap: 'anywhere' }}>{children}</a>;
}

/** Der Text mit klickbaren Links – der Verweis in spitzen Klammern verschwindet, das
 *  Wort davor wird der Link. Ein Satzzeichen am Ende gehört nicht zur Adresse. */
function linkify(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(LINK)) {
    const [all, word, wordUrl, bare, url, mail, nr] = m;
    const at = m.index ?? 0;
    out.push(text.slice(last, at));
    last = at + all.length;
    const k = at;
    if (word) out.push(<A key={k} href={wordUrl}>{word}</A>);
    else if (bare) out.push(<A key={k} href={bare}>{bare.replace(/^(https?:\/\/|mailto:)/, '').replace(/\/$/, '')}</A>);
    else if (url) {
      const tail = url.match(/[.,;:!?)\]]+$/)?.[0] ?? '';
      const core = url.slice(0, url.length - tail.length);
      out.push(<A key={k} href={core.startsWith('www.') ? `https://${core}` : core}>{core}</A>, tail);
    } else if (mail) out.push(<A key={k} href={`mailto:${mail}`}>{mail}</A>);
    else if (nr) out.push(<ObjId key={k} value={Number(nr)} mono={false} />);
  }
  out.push(text.slice(last));
  return out;
}

/** Wie ein Mensch im Verlauf heisst – mit Firma «Muster AG · Lea Muster», Firma zuerst.
 *  **Nur bei Externen**: dass ein Mitarbeiter zu uns gehört, ist klar. Nie eine nackte
 *  Adresse: die steht im Hover. */
function who(p: Person): string {
  return p.company && !p.staff ? `${p.company} · ${p.name}` : p.name;
}

/** Der Absender – über das Postfach einer Gesellschaft «Inexxio AG · Clemens Fritsche»
 *  (in wessen Namen, und wer es geschrieben hat), sonst wie jeder Mensch. */
function author(m: Message): string {
  const firm = m.ours && m.channel.mail ? m.channel.name : null;
  return firm ? `${firm} · ${m.sender.name}` : who(m.sender);
}

/** Alles Genaue für den Hover – je Rolle ein Block, je Person Name und darunter ihre
 *  Adresse. Wer über ein Postfach schreibt oder in eines schreibt, steht mit dessen
 *  Adresse da: «Inexxio AG · Clemens Fritsche / info@inexxio.com». */
function details(m: Message): string {
  const box = m.channel.mail ? m.channel.label : null;
  const block = (role: string, lines: string[]) => lines.length ? `${role}  ${lines.join('\n      ')}` : '';
  const person = (p: Person) => [who(p), p.email].filter(Boolean).join('\n      ');
  const from = m.ours && box ? [author(m), box].join('\n      ') : person(m.sender);
  const to = m.to.length ? m.to.map(person)
    : m.channel.mail ? [[m.channel.name, box].filter(Boolean).join('\n      ')] : [];
  return [
    block('Von', [from]), block('An', to), block('Cc', m.cc.map(person)),
    block('Bcc', m.bcc.length > 3 ? [`${m.bcc.length} Personen`] : m.bcc.map(person)),
    m.channel.outside ? '' : 'Intern – verlässt das Haus nicht',
  ].filter(Boolean).join('\n');
}

/** Was man mit einer Nachricht tun kann – beim Zeigen, an ihr selbst (`.ix-rowactions`):
 *  antworten, ohne Antwort erledigen (nur eine offene), in Gmail öffnen. */
function MessageActions({ m, onReply, onDone }: {
  m: Message; onReply?: (m: Message) => void; onDone?: (m: Message) => void;
}) {
  if (!onReply && !m.gmail_url) return null;
  return (
    <span className="ix-rowactions" style={{ display: 'inline-flex', gap: 2, flex: 'none' }}>
      {onReply && (
        <button type="button" style={ICON_BTN} onClick={() => onReply(m)}
          data-tip="Antworten" aria-label="Antworten"><Reply size={14} /></button>
      )}
      {onDone && m.open && (
        <button type="button" style={ICON_BTN} onClick={() => onDone(m)}
          data-tip="Erledigt ohne Antwort" aria-label="Erledigt ohne Antwort"><Check size={14} /></button>
      )}
      {m.gmail_url && (
        <a href={m.gmail_url} target="_blank" rel="noreferrer" style={ICON_BTN}
          data-tip="In Gmail öffnen" aria-label="In Gmail öffnen"><ExternalLink size={14} /></a>
      )}
    </span>
  );
}

/** Die Signatur – eingeklappt hinter «…», wie in jedem Mailprogramm. */
function Signature({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 4 }}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        data-tip={open ? 'Signatur ausblenden' : 'Signatur anzeigen'}
        aria-label={open ? 'Signatur ausblenden' : 'Signatur anzeigen'}
        style={{ border: 0, borderRadius: 6, background: 'var(--bg-3)', height: 14, padding: '0 6px',
          display: 'inline-flex', alignItems: 'center', cursor: 'pointer', color: 'var(--fg-3)' }}>
        <MoreHorizontal size={14} />
      </button>
      {open && <div style={{ color: 'var(--fg-3)', fontSize: 13, whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere', marginTop: 4 }}>{linkify(text)}</div>}
    </div>
  );
}

/** Wie lange etwas wartet – «seit 3 Std. offen» / «seit 3 Std. überfällig». */
function stateText(m: Message): string {
  return `${sinceWord(formatWhen(m.at).text)} ${m.overdue ? 'überfällig' : 'offen'}`;
}

/** ►►► **Ein Anruf ist eine Nachricht** – oben in der Blase ein Telefon-Zeichen und die
 *  Richtung. Wer angerufen hat, sagt zugleich die Seite. ◄◄◄ */
function CallHead({ m }: { m: Message }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '4px 0 6px' }}>
      <span style={{ width: 32, height: 32, borderRadius: 999, flex: 'none', display: 'inline-flex',
        alignItems: 'center', justifyContent: 'center', background: 'var(--success-bg)',
        color: 'var(--success)' }}><Phone size={15} /></span>
      <span style={{ fontWeight: 600, color: 'var(--fg-1)' }}>
        {m.ours ? 'Ausgehender Anruf' : 'Eingehender Anruf'}</span>
    </div>
  );
}

/** Die Zeit einer Nachricht – bei einer offenen als kleine Marke in der Farbe ihres
 *  Zustands (orange wartet, rot überfällig), sonst grau. Wie lange sie wartet, im Hover. */
function Time({ m, state }: { m: Message; state: boolean }) {
  const text = formatWhen(m.at).text;
  if (!state) {
    return <span className="tabular-nums" style={{ flex: 'none' }} data-tip={whenTitle(m.at)}>{text}</span>;
  }
  const fg = m.overdue ? 'var(--danger)' : 'var(--warning)';
  const bg = m.overdue ? 'var(--danger-bg)' : 'var(--warning-bg)';
  return (
    <span className="tabular-nums" aria-label={`${text} · ${stateText(m)}`}
      data-tip={`${stateText(m)}\n${whenTitle(m.at)}`}
      style={{ flex: 'none', height: 18, padding: '0 7px', borderRadius: 999, background: bg,
        color: fg, fontWeight: 600, display: 'inline-flex', alignItems: 'center' }}>{text}</span>
  );
}

function Bubble({ m, mirror, named, onReply, onDone }: {
  m: Message; mirror: boolean;
  /** Den Namen trägt die Blase nur, wo die Seite ihn nicht schon sagt. */
  named: boolean;
  onReply?: (m: Message) => void; onDone?: (m: Message) => void;
}) {
  const call = m.channel.kind === 'phone';
  const Icon = m.bcc.length > 2 ? Megaphone : KIND_ICON[m.channel.kind as Mode] ?? Mail;
  const showState = !mirror && m.open;
  const bg = !m.channel.outside ? 'var(--bg-3)' : m.ours ? 'var(--accent-soft)' : 'var(--bg-1)';
  // Wer ausser dem einen Empfänger dabei war – das «Cc», kurz; alles Genaue im Hover.
  const group = m.delivery === 'mail' ? null
    : `${DELIVERIES.find((d) => d.key === m.delivery)?.label ?? m.delivery}${m.recipients > 1 ? ` · an ${m.recipients}` : ''}`;
  const GroupIcon = m.delivery === 'newsletter' ? Newspaper : Megaphone;
  const cc = group ?? (!m.channel.outside ? null
    : m.cc.length ? `Cc ${m.cc.map(who).join(', ')}` : m.to.length > 1 ? `an ${m.to.length}` : null);
  // ►►► Intern stehen die Empfänger VORNE im Text – «@Monika Fritsche …». Sie kommen aus dem
  // «An», nicht aus dem Text: wer gefragt ist, sieht man, ohne zu zeigen. ◄◄◄
  const mentions = !m.channel.outside ? [...m.to, ...m.cc] : [];
  return (
    <div className="ix-row" style={{ display: 'flex', justifyContent: m.ours ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: '74%', minWidth: 0, background: bg, opacity: m.planned ? 0.65 : 1,
        borderRadius: m.ours ? '12px 12px 4px 12px' : '12px 12px 12px 4px', padding: '8px 12px 6px',
        boxShadow: m.channel.outside && !m.ours ? '0 1px 0 var(--border-1)' : 'none' }}>
        {named && <div className="truncate" style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-2)' }}>{author(m)}</div>}
        {m.topic && <div style={{ fontSize: 12, fontWeight: 600, color: topicColor(m.topic),
          overflowWrap: 'anywhere' }}>{m.topic}</div>}
        {call && <CallHead m={m} />}
        {m.body && <div style={{ color: 'var(--fg-1)', whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: '20px',
          overflowWrap: 'anywhere' }}>
          {mentions.length > 0 && <span style={{ fontWeight: 600, color: 'var(--accent)' }}>
            {mentions.map((p) => `@${p.name}`).join(' ')}{' '}</span>}
          {linkify(m.body)}</div>}
        {!m.body && !m.channel.outside && (
          <div style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>Erledigt ohne Antwort</div>
        )}
        {m.signature && <Signature text={m.signature} />}
        <MailFoot m={m} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6,
          fontSize: 11, lineHeight: '16px', color: 'var(--fg-3)', marginTop: 2, minWidth: 0 }}>
          <MessageActions m={m} onReply={onReply} onDone={onDone} />
          {/* Die Blase hängt an einer Hülle ohne ``overflow`` – ``truncate`` schnitte sie weg. */}
          <span data-tip={details(m)} data-tip-list="" data-tip-pos="bottom"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            {m.channel.kind === 'internal' && <Icon size={12} style={{ flex: 'none' }} />}
            {group && <GroupIcon size={12} style={{ flex: 'none' }} />}
            {cc && <span className="truncate">{cc}</span>}
          </span>
          <Time m={m} state={showState} />
        </div>
      </div>
    </div>
  );
}

/** Was an einer Mail hängt: Anhänge und ob sie noch hinaus muss. Steht nichts davon an,
 *  steht hier nichts.
 *
 *  ►►► **Ein Anhang öffnet den Entwurf eines Dokuments** – dasselbe Interface wie überall
 *  (Regel: eine Ablage). Gibt es die Datei schon als Dokument, sagt es der Entwurf und öffnet
 *  das vorhandene. Der Absender ist der Hinweis für die Zuordnung. ◄◄◄ */
function MailFoot({ m }: { m: Message }) {
  const files = m.attachments ?? [];
  const nav = useErpNav();
  const [draft, setDraft] = useState<File | null>(null);
  const [loading, setLoading] = useState<number | null>(null);
  const [error, setError] = useState('');
  if (!files.length && !m.pending) return null;
  const open = async (i: number, name: string) => {
    setError('');
    setLoading(i);
    try { setDraft(await api.messageAttachment(m.id, i, name)); } catch (e) { setError((e as Error).message); }
    finally { setLoading(null); }
  };
  const form = files.some((f) => f.url);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: 8,
      fontSize: 12, color: 'var(--fg-3)' }}>
      {files.map((f, i) => (
        <button key={i} type="button" onClick={() => void open(i, f.name)} disabled={loading != null}
          data-tip="Als Dokument öffnen"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, maxWidth: '100%', border: 0,
                   padding: '2px 8px', borderRadius: 6, background: 'var(--bg-3)', color: 'inherit',
                   font: 'inherit', cursor: 'pointer' }}>
          {loading === i ? <Loader2 size={12} className="animate-spin" style={{ flex: 'none' }} />
            : <Paperclip size={12} style={{ flex: 'none' }} />}
          <span className="truncate">{f.name}</span>
        </button>
      ))}
      {m.pending && <span>{m.planned ? 'wird zum Zeitpunkt gesendet' : 'wartet auf Versand'}</span>}
      {error && <span style={{ color: 'var(--danger)' }}>{error}</span>}
      {draft && (
        <DraftSheet onCancel={() => setDraft(null)}
          seed={{ files: [draft], source: form ? 'form' : 'mail', sender: m.sender.object_id,
                  from: `${form ? 'Aus der Anfrage' : 'Aus der Mail'} von ${m.sender.name} · ${draft.name}` }}
          onOpen={(id) => { setDraft(null); nav?.(id); }}
          onFiled={(doc) => { setDraft(null); nav?.(doc.object_id); }} />
      )}
    </div>
  );
}

/** «vor 3 Stunden» → «seit 3 Stunden»: die Zeit zuerst, dann der Zustand. */
function sinceWord(text: string): string {
  return text.startsWith('vor ') ? `seit ${text.slice(4)}` : text;
}

function Divider({ label }: { label: string }) {
  return (
    <div style={{ alignSelf: 'center', color: 'var(--fg-3)', fontSize: 12, margin: '8px 0 4px' }}>{label}</div>
  );
}

/** ►►► **Die Mail, die gleich hinausgeht** – blass dort, wo sie hingehört, mit Uhr und
 *  «Rückgängig». Nach drei Sekunden ist sie eine gewöhnliche Nachricht. ◄◄◄ */
export type Sending = { topic: string; body: string; to: string; left: number; undo: () => void;
  /** Wie es dasteht: eine Mail hellblau, intern grau – wie die Nachricht danach. */
  internal: boolean; verb: string };

function SendingBubble({ s }: { s: Sending }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ maxWidth: '74%', minWidth: 0, opacity: 0.6,
        background: s.internal ? 'var(--bg-3)' : 'var(--accent-soft)',
        borderRadius: '12px 12px 4px 12px', padding: '8px 12px 6px' }}>
        {s.topic && <div style={{ fontSize: 12, fontWeight: 600, color: topicColor(s.topic),
          overflowWrap: 'anywhere' }}>{s.topic}</div>}
        <div style={{ color: 'var(--fg-1)', whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: '20px',
          overflowWrap: 'anywhere' }}>{s.body}</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10,
          fontSize: 11, lineHeight: '16px', color: 'var(--fg-2)', marginTop: 2 }}>
          {s.to && <span className="truncate">an {s.to}</span>}
          <span className="tabular-nums" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, flex: 'none' }}>
            <Clock size={12} />{s.verb} · {s.left} s</span>
          <button type="button" onClick={s.undo} style={{ border: 0, background: 'none', padding: 0,
            font: 'inherit', fontSize: 11, fontWeight: 600, color: 'var(--accent)', cursor: 'pointer',
            flex: 'none' }}>Rückgängig</button>
        </div>
      </div>
    </div>
  );
}

/** So viele Nachrichten stehen zuerst da – und kommen je Nachladen (Rollen nach oben) dazu. */
const PAGE = 8;

export function Timeline({ messages, mirror, personId, meId, onReply, onDone, sending }: {
  messages: Message[]; mirror: boolean; personId?: number; meId?: number;
  onReply?: (m: Message) => void; onDone?: (m: Message) => void;
  /** Die Mail, die gerade drei Sekunden wartet – sie steht schon am Ende des Verlaufs. */
  sending?: Sending | null;
}) {
  // ►►► Wie WhatsApp: sichtbar sind die jüngsten Nachrichten, Älteres kommt von selbst,
  // sobald man nach oben rollt (Testnotiz #1216). ◄◄◄ Nur die Anzeige ist begrenzt –
  // geladen ist der ganze Verlauf (Betreffe, offene). Der Knopf bleibt als Weg für die
  // Tastatur; der Beobachter drückt ihn, sobald er in Sicht kommt.
  const [shown, setShown] = useState(PAGE);
  const more = useRef<HTMLButtonElement>(null);
  const hasMore = messages.length > shown;
  useEffect(() => {
    const el = more.current;
    if (!el || !hasMore || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver((seen) => {
      if (seen.some((e) => e.isIntersecting)) setShown((n) => n + PAGE);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, shown]);
  if (!messages.length && !sending) {
    return <p style={{ color: 'var(--fg-3)', fontSize: 13, padding: '24px 0' }}>Noch keine Nachrichten.</p>;
  }
  const hidden = Math.max(0, messages.length - shown);
  const rows: ReactNode[] = [];
  if (hidden > 0) rows.push(
    <button key="more" ref={more} type="button" data-more="" onClick={() => setShown((n) => n + PAGE)}
      style={{ alignSelf: 'center', display: 'inline-flex', alignItems: 'center', gap: 6, height: 28,
        padding: '0 12px', border: '1px solid var(--border-1)', borderRadius: 999, cursor: 'pointer',
        background: 'var(--bg-1)', color: 'var(--fg-2)', font: 'inherit', fontSize: 12, fontWeight: 600,
        marginBottom: 4 }}>
      <ChevronUp size={14} />{hidden} ältere {hidden === 1 ? 'Nachricht' : 'Nachrichten'} laden
    </button>);
  let last = '';
  for (const m of messages.slice(hidden)) {
    const label = m.planned ? 'Geplant' : whenDay(m.at);
    if (label !== last) rows.push(<Divider key={`d-${m.id}`} label={label} />);
    last = label;
    const named = mirror || (m.ours ? m.sender.object_id !== meId : m.sender.object_id !== personId);
    rows.push(<Bubble key={m.id} m={m} mirror={mirror} named={named} onReply={onReply} onDone={onDone} />);
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '4px 0' }}>
      {rows}
      {sending && <SendingBubble s={sending} />}
    </div>
  );
}
