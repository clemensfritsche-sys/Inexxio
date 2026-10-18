'use client';

/**
 * ►►► **Kommunikation – der Verlauf und die eine Eingabe** (CRM Schritt 2). ◄◄◄
 *
 * Alles ist eine Nachricht, und die Oberfläche kennt keine Art: wie eine Nachricht
 * aussieht, folgt aus ihren Angaben – **rechts**, was von uns kommt (`ours`), **grau**,
 * was das Haus nie verlässt (`channel.outside`), das **Symbol** aus dem Kanal. Ob sie
 * offen oder überfällig ist, sagt der Server; gerechnet wird hier nichts.
 *
 * Die Eingabe hat für E-Mail, Anruf und Intern **dieselbe Form** (Von → An → Betreff → Text →
 * Zeitpunkt). Die drei Knöpfe wählen nur den Kanal und belegen vor. **Geschrieben wird nur
 * im eigenen Namen** – oder, bei einer E-Mail, in dem einer eigenen Gesellschaft: «Von»
 * ist ein Chip wie «An» und wählt unter den **verbundenen** Postfächern.
 *
 * ►►► **Ein Chat je Person – wie WhatsApp.** ◄◄◄ Die **Seite** sagt, wer schreibt (links
 * von aussen, rechts wir, grau intern); eine Kopfzeile gibt es nicht. Den Namen trägt eine
 * Blase nur, wo die Seite ihn nicht schon sagt (ein Kollege, eine zweite Person der Firma).
 * Wer an wen, mit Adressen, steht im Hover.
 *
 * **Das Anliegen ist der Betreff** – klein und farbig oben in der Blase, gleicher Betreff
 * gleiche Farbe (`topicColor`, fest aus dem Betreff abgeleitet). Ein «Antwort auf» gibt es
 * nicht: «Antworten» belegt den **festen** Betreff («Re: » davor, wie Gmail) und **alle**
 * Beteiligten vor (`reply_all`); nur der Absender lässt sich nicht entfernen. Die Antwort
 * erledigt alle offenen Nachrichten dieses Betreffs – das sagt der Server.
 *
 * **Eine Mail wartet drei Sekunden** («Rückgängig», wie Gmail) – im Browser, nicht auf dem
 * Server. Wer die Ansicht verlässt, schickt sie damit sofort; verloren geht sie nie.
 *
 * **E-Mail geht über ein Postfach** (CRM Schritt 3): Gmail ist der Speicher, abgeglichen
 * wird im Hintergrund (`erp/page`). Die Mail bleibt dort – hier stehen Text, Anhänge (nur
 * Namen) und der Weg zurück nach Gmail. **Verbunden wird ein Postfach dort, wem es gehört**:
 * das einer eigenen Gesellschaft an ihrem Datensatz, das persönliche am eigenen.
 *
 * An einer **Firma** ist der Verlauf ein Spiegel: dieselbe Liste, keine Eingabe und kein
 * offen/überfällig – geschrieben wird immer von Person zu Person.
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowDownUp, Check, ChevronDown, Clock, ExternalLink, Lock, Mail, Megaphone, MoreHorizontal,
  Paperclip, Phone, Reply, Send, X } from 'lucide-react';
import { MODULE_TONE } from '@/lib/modules';
import { api } from '@/lib/api';
import { day, formatWhen, when, whenTitle } from '@/lib/when';
import { ObjId } from '@/components/erp/obj-id';
import type { Mailbox, Message, MessageChannel, MessageIn, VoucherParty } from '@/types';

type Person = { object_id: number; name: string; company?: string | null; email?: string | null;
  staff?: boolean };
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
  const firm = m.ours && m.channel.mail && !m.channel.personal ? m.channel.name : null;
  return firm ? `${firm} · ${m.sender.name}` : who(m.sender);
}

/** Der Empfänger – der erste mit Name, die übrigen gezählt («Lea Muster +2»). Ohne
 *  bekannten Empfänger heisst eine Mail wie das Postfach, in das sie kam («Inexxio AG»),
 *  eine interne Nachricht «Notiz»; ein Anruf ohne Gegenüber hat keinen Pfeil. */
function recipient(m: Message): string | null {
  const all = [...m.to, ...m.cc, ...m.bcc];
  if (all.length) return all.length > 1 ? `${who(all[0])} +${all.length - 1}` : who(all[0]);
  if (m.channel.mail) return m.channel.name ?? m.channel.label;
  return m.channel.outside ? null : 'Notiz';
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

/** ►►► **Gleicher Betreff, gleiche Farbe.** ◄◄◄ Fest aus dem Anliegen abgeleitet – nicht
 *  zufällig: dieselbe Farbe nach dem Neuladen und bei jedem Kollegen. Die Farben sind die
 *  gedämpften des Hauses (`MODULE_TONE`), bewusst ohne Rot und Orange: die gehören dem
 *  Zustand (offen · überfällig), und ein Betreff darf nicht wie einer aussehen. */
const TOPIC_TONES = ['slate', 'plum', 'moss', 'teal', 'clay', 'sand'].map((k) => MODULE_TONE[k].fg);
export function topicColor(topic: string): string {
  let h = 0;
  for (const ch of topic.toLocaleLowerCase('de-CH')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TOPIC_TONES[h % TOPIC_TONES.length];
}

const ICON_BTN = { border: 0, background: 'none', padding: 3, borderRadius: 6, cursor: 'pointer',
  display: 'inline-flex', color: 'var(--fg-3)' } as const;

/** Was man mit einer Nachricht tun kann – beim Zeigen, an ihr selbst (`.ix-rowactions`):
 *  antworten, ohne Antwort erledigen (nur eine offene), in Gmail öffnen. */
function Actions({ m, onReply, onDone }: {
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

function Bubble({ m, mirror, named, onReply, onDone }: {
  m: Message; mirror: boolean;
  /** Den Namen trägt die Blase nur, wo die Seite ihn nicht schon sagt. */
  named: boolean;
  onReply?: (m: Message) => void; onDone?: (m: Message) => void;
}) {
  const Icon = m.bcc.length > 2 ? Megaphone : KIND_ICON[m.channel.kind as Mode] ?? Mail;
  const showState = !mirror && m.open;
  const tone = m.overdue ? 'var(--danger)' : 'var(--color-warning)';
  const bg = !m.channel.outside ? 'var(--bg-3)' : m.ours ? 'var(--accent-soft)' : 'var(--bg-1)';
  // Wer ausser dem einen Empfänger dabei war – das «Cc», kurz; alles Genaue im Hover.
  const cc = m.cc.length ? `Cc ${m.cc.map(who).join(', ')}` : m.to.length > 1 ? `an ${m.to.length}` : null;
  return (
    <div className="ix-row" style={{ display: 'flex', justifyContent: m.ours ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: '74%', minWidth: 0, background: bg, opacity: m.planned ? 0.65 : 1,
        borderRadius: m.ours ? '12px 12px 4px 12px' : '12px 12px 12px 4px', padding: '8px 12px 6px',
        boxShadow: m.channel.outside && !m.ours ? '0 1px 0 var(--border-1)' : 'none' }}>
        {named && <div className="truncate" style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-2)' }}>{author(m)}</div>}
        {m.topic && <div style={{ fontSize: 12, fontWeight: 600, color: topicColor(m.topic),
          overflowWrap: 'anywhere' }}>{m.topic}</div>}
        {m.body && <div style={{ color: 'var(--fg-1)', whiteSpace: 'pre-wrap', lineHeight: '20px',
          overflowWrap: 'anywhere' }}>{linkify(m.body)}</div>}
        {!m.body && !m.channel.outside && (
          <div style={{ color: 'var(--fg-3)', fontStyle: 'italic' }}>Erledigt ohne Antwort</div>
        )}
        {m.signature && <Signature text={m.signature} />}
        <MailFoot m={m} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6,
          fontSize: 11, lineHeight: '16px', color: 'var(--fg-3)', marginTop: 2, minWidth: 0 }}>
          <Actions m={m} onReply={onReply} onDone={onDone} />
          {/* Die Blase hängt an einer Hülle ohne ``overflow`` – ``truncate`` schnitte sie weg. */}
          <span data-tip={details(m)} data-tip-list="" data-tip-pos="bottom"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            {m.channel.kind !== 'email' && <Icon size={12} style={{ flex: 'none' }} />}
            {cc && <span className="truncate">{cc}</span>}
          </span>
          <span className="tabular-nums" style={{ flex: 'none' }} data-tip={whenTitle(m.at)}>
            {formatWhen(m.at).text}</span>
          {showState && <span aria-label={stateText(m)} data-tip={stateText(m)}
            style={{ width: 8, height: 8, borderRadius: 999, background: tone, flex: 'none' }} />}
        </div>
      </div>
    </div>
  );
}

/** Ein Anruf ist ein Gespräch, keine Nachricht im Chat – eine schlichte Zeile in der Mitte. */
function Call({ m, onReply }: { m: Message; onReply?: (m: Message) => void }) {
  const to = recipient(m);
  return (
    <div className="ix-row" style={{ display: 'flex', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)',
        maxWidth: '86%', minWidth: 0, flexWrap: 'wrap', justifyContent: 'center', textAlign: 'center' }}>
        <Phone size={13} style={{ flex: 'none' }} />
        <span data-tip={details(m)} data-tip-list="" data-tip-pos="bottom">
          {who(m.sender)}{to && <> → {to}</>}</span>
        <span className="tabular-nums" data-tip={whenTitle(m.at)}>· {formatWhen(m.at).text}</span>
        {m.topic && <span style={{ color: topicColor(m.topic), fontWeight: 600 }}>· {m.topic}</span>}
        {m.body && <span style={{ color: 'var(--fg-2)', overflowWrap: 'anywhere' }}>· {linkify(m.body)}</span>}
        <Actions m={m} onReply={onReply} />
      </div>
    </div>
  );
}

/** Was an einer Mail hängt: Anhänge (die Datei liegt in Gmail) und ob sie noch hinaus
 *  muss. Steht nichts davon an, steht hier nichts. */
function MailFoot({ m }: { m: Message }) {
  const files = m.attachments ?? [];
  if (!files.length && !m.pending) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: 8,
      fontSize: 12, color: 'var(--fg-3)' }}>
      {files.map((f, i) => {
        const chip = { display: 'inline-flex', alignItems: 'center', gap: 4, maxWidth: '100%',
          padding: '2px 8px', borderRadius: 6, background: 'var(--bg-3)', color: 'inherit' } as const;
        const inner = <><Paperclip size={12} style={{ flex: 'none' }} /><span className="truncate">{f.name}</span></>;
        // Ein Bild aus dem Anfrage-Formular liegt bei uns – es öffnet sich direkt.
        return f.url
          ? <a key={i} href={f.url} target="_blank" rel="noreferrer" style={chip}>{inner}</a>
          : <span key={i} style={chip}>{inner}</span>;
      })}
      {m.pending && <span>{m.planned ? 'wird zum Zeitpunkt gesendet' : 'wartet auf Versand'}</span>}
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

/** ►►► **Der Zustand steht EINMAL – unten im Verlauf.** ◄◄◄ Wie viele warten, und wie lange
 *  die älteste schon; an der einzelnen Blase steht nur ein Punkt neben der Zeit. */
function Waiting({ open }: { open: Message[] }) {
  if (!open.length) return null;
  const oldest = open.reduce((a, b) => (b.at < a.at ? b : a));
  const late = open.some((m) => m.overdue);
  const tone = late ? 'var(--danger)' : 'var(--color-warning)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600,
      color: tone, marginTop: 4 }}>
      <span style={{ width: 8, height: 8, borderRadius: 999, background: tone, flex: 'none' }} />
      {open.length} {open.length === 1 ? 'wartet' : 'warten'} auf Antwort · älteste {stateText(oldest)}
    </div>
  );
}

function Timeline({ messages, mirror, personId, meId, onReply, onDone }: {
  messages: Message[]; mirror: boolean; personId?: number; meId?: number;
  onReply?: (m: Message) => void; onDone?: (m: Message) => void;
}) {
  if (!messages.length) {
    return <p style={{ color: 'var(--fg-3)', fontSize: 13, padding: '24px 0' }}>Noch keine Nachrichten.</p>;
  }
  const rows: ReactNode[] = [];
  let last = '';
  for (const m of messages) {
    const label = m.planned ? 'Geplant' : dayLabel(m.at);
    if (label !== last) rows.push(<Divider key={`d-${m.id}`} label={label} />);
    last = label;
    if (m.channel.kind === 'phone') { rows.push(<Call key={m.id} m={m} onReply={onReply} />); continue; }
    const named = mirror || (m.ours ? m.sender.object_id !== meId : m.sender.object_id !== personId);
    rows.push(<Bubble key={m.id} m={m} mirror={mirror} named={named} onReply={onReply} onDone={onDone} />);
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, background: 'var(--bg-2)',
      borderRadius: 12, padding: '12px 16px' }}>
      {rows}
      {!mirror && <Waiting open={messages.filter((m) => m.open)} />}
    </div>
  );
}

// ─── Eingabe ────────────────────────────────────────────────────────────────

/** Ein Chip – die eine Form für «Von» und «An». */
const CHIP = { display: 'inline-flex', alignItems: 'center', gap: 6, height: 26, padding: '0 10px',
  borderRadius: 13, background: 'var(--bg-3)', fontSize: 13, maxWidth: '100%', minWidth: 0,
  color: 'var(--fg-1)' } as const;
/** Die Vorschlagsliste unter einem Chip-Feld – für «An» wie für «Von». */
const LIST = { position: 'absolute', top: '100%', left: 0, zIndex: 30, marginTop: 4,
  background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 8,
  boxShadow: 'var(--shadow-md)', minWidth: 240, maxWidth: '100%', padding: 4 } as const;
const HIT = { display: 'flex', gap: 10, width: '100%', textAlign: 'left', border: 0,
  padding: '6px 8px', borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--fg-1)' } as const;

function Chip({ children, onRemove, onMove, moveTip, tip }: {
  children: ReactNode; onRemove?: () => void; onMove?: () => void; moveTip?: string; tip?: string;
}) {
  return (
    <span data-tip={tip} style={{ ...CHIP, padding: onRemove || onMove ? '0 4px 0 10px' : '0 10px' }}>
      <span className="truncate">{children}</span>
      {onMove && (
        <button type="button" onClick={onMove} aria-label={moveTip} data-tip={moveTip}
          style={{ border: 0, background: 'none', padding: 2, cursor: 'pointer', color: 'var(--fg-3)',
            display: 'flex' }}><ArrowDownUp size={13} /></button>
      )}
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label="Entfernen"
          style={{ border: 0, background: 'none', padding: 2, cursor: 'pointer', color: 'var(--fg-3)',
            display: 'flex' }}><X size={13} /></button>
      )}
    </span>
  );
}

/** «An»-Feld wie in einem Mailprogramm: Chips, und tippen sucht (Nummer oder Name). */
function People({ value, onChange, placeholder, locked, onMove, moveTip, max }: {
  value: Person[]; onChange: (v: Person[]) => void; placeholder?: string;
  /** Wer nicht entfernt werden kann – der Absender der Nachricht, auf die ich antworte.
   *  Er lässt sich nur zwischen «An» und «Cc» verschieben (``onMove``). */
  locked?: ReadonlySet<number>; onMove?: (p: Person) => void; moveTip?: string;
  /** Höchstens so viele (ein Anrufer ist einer). */
  max?: number;
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
    onChange([...value.filter((v) => v.object_id !== p.object_id), { object_id: p.object_id, name: p.name }]);
    setQ('');
  };
  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexWrap: 'wrap',
      gap: 6, alignItems: 'center', minHeight: 28 }}>
      {value.map((p) => locked?.has(p.object_id)
        ? <Chip key={p.object_id} onMove={onMove && (() => onMove(p))} moveTip={moveTip}
            tip="Eine Antwort geht an den, der geschrieben hat – wer frei schreiben will, beginnt eine neue Nachricht">{p.name}</Chip>
        : <Chip key={p.object_id} onRemove={() => onChange(value.filter((v) => v !== p))}>{p.name}</Chip>)}
      {(max === undefined || value.length < max) && <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={value.length ? '' : placeholder}
        style={{ border: 0, outline: 'none', font: 'inherit', fontSize: 13, flex: 1, minWidth: 140,
          background: 'transparent' }} />}
      {hits.length > 0 && (
        <div style={LIST}>
          {hits.map((h) => (
            <button key={h.object_id} type="button" onClick={() => add(h)} style={HIT}
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

/** ►►► **Senden ist ein Symbol – wie in jedem Chat.** ◄◄◄ Was er tut, steht im Hover; was
 *  noch fehlt, ebenso (gesperrt, mit Grund). Nach dem Klick läuft der Countdown IM Knopf –
 *  ein Ring, der sich leert, und die Sekunden darin; ein Klick holt die Mail zurück. */
function SendButton({ mode, verb, problem, busy, held, onUndo }: {
  mode: Mode; verb: string; problem: string | null; busy: boolean;
  /** Sekunden bis zum Versand – solange eine Mail zurückgehalten wird. */
  held: number | null; onUndo: () => void;
}) {
  const Icon = mode === 'internal' ? Lock : mode === 'phone' ? Check : Send;
  const waiting = held !== null;
  const off = !waiting && (busy || !!problem);
  const tip = waiting ? 'Rückgängig' : problem ?? verb;
  return (
    // Die Blase hängt an der Hülle – an einem gesperrten Knopf feuert kein Zeiger-Ereignis.
    // ``preventDefault`` beim Rückgängig: React rendert noch im Klick neu, der Knopf ist
    // dann schon wieder ``submit`` – und die Mail ginge gleich ein zweites Mal ab.
    <span data-tip={tip} style={{ display: 'inline-flex' }}>
      <button type={waiting ? 'button' : 'submit'} onClick={waiting ? (e) => { e.preventDefault(); onUndo(); } : undefined}
        aria-label={tip} disabled={off} className="tabular-nums"
        style={{ position: 'relative', width: 40, height: 40, borderRadius: 999, border: 0,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none',
          cursor: off ? 'not-allowed' : 'pointer', fontFamily: 'inherit', fontWeight: 700,
          fontSize: 14, color: off ? 'var(--fg-4)' : '#fff',
          background: waiting ? 'var(--fg-1)' : off ? 'var(--bg-3)' : 'var(--inexxio-red)' }}>
        {waiting ? <>
          <svg className="ix-countdown" viewBox="0 0 40 40" aria-hidden="true">
            <circle cx="20" cy="20" r="17" pathLength={100}
              style={{ animationDuration: `${UNDO_MS}ms` }} />
          </svg>
          {held}
        </> : <Icon size={17} />}
      </button>
    </span>
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

/** «Von»: in wessen Namen die Mail hinausgeht – mein eigenes Postfach oder das einer
 *  eigenen Gesellschaft; angeboten wird nur, was verbunden ist (sagt der Server). **Er sieht
 *  aus wie «An»**: ein Chip, und bei mehr als einem Postfach klappt ein Klick dieselbe
 *  Liste auf – getippt wird nichts, es gibt nur diese. */
function From({ mails, value, onChange, me }: {
  mails: MessageChannel[]; value?: MessageChannel; onChange: (key: string) => void; me: Person;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);
  if (!mails.length) {
    return <span style={{ fontSize: 13, color: 'var(--danger)', paddingTop: 4 }}
      data-tip="Ein Postfach verbindet man am eigenen Datensatz bzw. an der Gesellschaft">
      Kein Postfach verbunden</span>;
  }
  const text = (c: MessageChannel) => `${c.name ?? me.name} · ${c.label}`;
  const cur = value ?? mails[0];
  if (mails.length === 1) return <span style={CHIP}><span className="truncate">{text(cur)}</span></span>;
  return (
    <div ref={box} style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex',
      alignItems: 'center', minHeight: 28 }}>
      <button type="button" onClick={() => setOpen(!open)} aria-haspopup="listbox"
        aria-expanded={open} aria-label="Von" style={{ ...CHIP, border: 0, cursor: 'pointer',
          fontFamily: 'inherit', fontWeight: 400, lineHeight: '26px', padding: '0 6px 0 10px' }}>
        <span className="truncate">{text(cur)}</span>
        <ChevronDown size={13} style={{ flex: 'none', color: 'var(--fg-3)' }} />
      </button>
      {open && (
        <div role="listbox" aria-label="Von" style={LIST}>
          {mails.map((c) => (
            <button key={c.key} type="button" role="option" aria-selected={c.key === cur.key}
              onClick={() => { onChange(c.key); setOpen(false); }} style={HIT}
              className="bg-transparent hover:bg-bg-2">
              <span className="truncate" style={{ fontWeight: c.key === cur.key ? 600 : 400 }}>{text(c)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

type Set<T> = (v: T) => void;

/** Wann: später senden bzw. erinnern – drei Zeitpunkte, ein Klick. */
function LaterRow({ mode, later, setLater }: { mode: Mode; later: string; setLater: Set<string | null> }) {
  return (
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
  );
}

function Fields(p: {
  mode: Mode; me: Person; channel?: MessageChannel; mails: MessageChannel[]; setChannel: Set<string>;
  to: Person[]; setTo: Set<Person[]>; cc: Person[]; setCc: Set<Person[]>;
  bcc: Person[]; setBcc: Set<Person[]>; showCc: boolean; setShowCc: Set<boolean>;
  subject: string; setSubject: Set<string>;
  /** Bei einer Antwort steht der Betreff fest – wie in Gmail. */
  fixed: boolean; locked: ReadonlySet<number>;
  later: string | null; setLater: Set<string | null>;
  incoming: boolean; setIncoming: Set<boolean>;
}) {
  const { mode, me, channel, mails, setChannel, to, setTo, cc, setCc, bcc, setBcc, showCc, setShowCc,
    subject, setSubject, fixed, locked, later, setLater, incoming, setIncoming } = p;
  const meChip = <span style={CHIP}><span className="truncate">{me.name}</span></span>;
  // Wer beantwortet wird, lässt sich nicht entfernen – nur zwischen «An» und «Cc» schieben.
  const toCc = (x: Person) => { setTo(to.filter((v) => v !== x)); setCc([...cc, x]); setShowCc(true); };
  const toTo = (x: Person) => { setCc(cc.filter((v) => v !== x)); setTo([...to, x]); };
  const contact = (
    <People value={to} onChange={setTo} locked={locked} max={incoming ? 1 : undefined}
      onMove={mode === 'email' ? toCc : undefined} moveTip="Ins «Cc» schieben"
      placeholder={mode === 'internal' ? 'Name eintippen – leer lassen für eine Notiz' : 'Name eintippen'} />
  );
  // Ein Anruf hat eine Richtung: wer hat wen angerufen? Getauscht werden nur Von und An.
  const swap = (
    <button type="button" onClick={() => setIncoming(!incoming)} aria-label="Richtung tauschen"
      data-tip="Richtung tauschen" style={{ border: 0, background: 'none', fontSize: 12,
        color: 'var(--fg-3)', cursor: 'pointer', paddingTop: 4, flex: 'none', display: 'inline-flex',
        alignItems: 'center', gap: 4, fontFamily: 'inherit' }}>
      <ArrowDownUp size={13} />{incoming ? 'Wurde angerufen' : 'Ich habe angerufen'}
    </button>
  );
  return (
      <div style={{ marginTop: 6 }}>
        {mode === 'email' && (
          <Row label="Von"><From mails={mails} value={channel} onChange={setChannel} me={me} /></Row>
        )}
        {mode === 'phone' && (
          <Row label="Von">
            {incoming ? contact : <span style={{ flex: 1, minWidth: 0 }}>{meChip}</span>}{swap}
          </Row>
        )}
        <Row label="An">
          {mode === 'phone' && incoming ? <span style={{ flex: 1, minWidth: 0 }}>{meChip}</span> : contact}
          {mode === 'email' && !showCc && (
            <button type="button" onClick={() => setShowCc(true)}
              style={{ border: 0, background: 'none', fontSize: 12, color: 'var(--fg-3)',
                cursor: 'pointer', paddingTop: 4, flex: 'none' }}>Cc&nbsp;&nbsp;Bcc</button>
          )}
        </Row>
        {mode === 'email' && showCc && <>
          <Row label="Cc"><People value={cc} onChange={setCc} locked={locked} onMove={toTo}
            moveTip="Ins «An» schieben" /></Row>
          <Row label="Bcc"><People value={bcc} onChange={setBcc} /></Row>
        </>}
        {mode !== 'phone' && !fixed && (
          <Row label="Betreff">
            <input value={subject} onChange={(e) => setSubject(e.target.value)}
              aria-label="Betreff" placeholder={mode === 'internal' ? 'Worum geht es?' : ''}
              style={{ border: 0, outline: 'none', font: 'inherit', fontSize: 13, flex: 1,
                minWidth: 0, background: 'transparent', minHeight: 28 }} />
          </Row>
        )}
        {later !== null && <LaterRow mode={mode} later={later} setLater={setLater} />}
      </div>
  );
}

const MODE_OF: Record<string, Mode> = { email: 'email', phone: 'phone', internal: 'internal' };

/** Worauf ein Klick auf «Antworten» zielt – mit einem Zähler, damit derselbe Klick auf
 *  dieselbe Nachricht ein zweites Mal wirkt. */
type Target = { m: Message; n: number };

/** Wie lange «Rückgängig» steht, bevor eine Mail wirklich hinausgeht. */
const UNDO_MS = 3000;

/** Was die Eingabe trägt – genug, um sie nach «Rückgängig» genau so wiederherzustellen. */
type Draft = {
  to: Person[]; cc: Person[]; bcc: Person[]; showCc: boolean; subject: string;
  reply: Message | null; mailKey?: string; body: string; later: string | null;
};

function Composer({ person, me, channels, target, onSent }: {
  person: Person; me: Person; channels: MessageChannel[]; target: Target | null; onSent: () => void;
}) {
  const mails = channels.filter((c) => c.mail);
  const [mode, setMode] = useState<Mode>('email');
  const [to, setTo] = useState<Person[]>([person]);
  const [cc, setCc] = useState<Person[]>([]);
  const [bcc, setBcc] = useState<Person[]>([]);
  const [showCc, setShowCc] = useState(false);
  const [subject, setSubject] = useState('');
  // ►►► Worauf geantwortet wird – nur für Betreff und Empfänger, kein «Antwort auf». ◄◄◄
  const [reply, setReply] = useState<Message | null>(null);
  // Bei einer Antwort stehen die Empfänger als eine Zeile da; «ändern» klappt sie auf.
  const [edit, setEdit] = useState(false);
  const [mailKey, setMailKey] = useState<string | undefined>(undefined);
  const [body, setBody] = useState('');
  const [later, setLater] = useState<string | null>(null);
  // Ein Anruf: «ich habe angerufen» (Vorgabe) ↔ «wurde angerufen» – dann ist der Kontakt
  // der Absender (der Server tauscht, ``MessageIn.incoming``).
  const [incoming, setIncoming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  // Die Mail, die gleich hinausgeht – mit allem, was «Rückgängig» wiederherstellt.
  const [held, setHeld] = useState<Draft | null>(null);
  const pending = useRef<{ timer: ReturnType<typeof setTimeout>; payload: MessageIn } | null>(null);
  const sent = useRef(onSent);
  sent.current = onSent;

  const calledIn = mode === 'phone' && incoming;
  // Pflicht bleibt nur der Absender dessen, worauf ich antworte – ausser ich bin es selbst.
  const asker = reply && reply.sender.object_id !== me.object_id ? reply.sender.object_id : null;
  const locked = new Set(asker !== null && !calledIn ? [asker] : []);
  const reached = asker === null || [...to, ...cc].some((p) => p.object_id === asker);
  const cameIn = reply && mails.find((c) => c.key === reply.channel.key)?.key;
  const channel = mode === 'email'
    ? mails.find((c) => c.key === (mailKey ?? cameIn)) ?? mails[0]
    : channels.find((c) => c.kind === mode && !c.mail);
  const fixed = !!reply;
  const theSubject = reply ? reply.reply_subject : subject;

  // ►►► «Antworten»: fester Betreff, alle Beteiligten – wie «Allen antworten». ◄◄◄ Wer im
  // «Cc» stand, bleibt im «Cc»; ich selbst falle heraus.
  useEffect(() => {
    if (!target) return;
    const m = target.m;
    const next = MODE_OF[m.channel.kind] ?? 'email';
    const all = m.reply_all.filter((p) => p.object_id !== me.object_id);
    const inCc = new Set(m.cc.map((p) => p.object_id));
    setReply(m); setEdit(false); setMailKey(undefined); setError(null); setIncoming(false);
    setMode(next === 'email' && !mails.length ? 'internal' : next);
    setTo(all.filter((p) => !inCc.has(p.object_id)));
    setCc(all.filter((p) => inCc.has(p.object_id)));
    setShowCc(all.some((p) => inCc.has(p.object_id)));
    textRef.current?.focus();
    textRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Eine neue Nachricht statt einer Antwort – freier Betreff, Empfänger von vorn. */
  const fresh = () => {
    setReply(null); setEdit(false); setSubject(''); setCc([]); setBcc([]); setShowCc(false);
    setTo(mode === 'internal' ? [] : [person]);
  };
  const pick = (m: Mode) => {
    setMode(m); setError(null); setIncoming(false);
    if (!reply) setTo(m === 'internal' ? [] : [person]);
    else if (m === 'internal') setTo([]);
  };
  const verb = mode === 'phone' ? 'Anruf festhalten'
    : mode === 'internal' ? (later ? 'Erinnerung setzen' : 'Speichern')
      : (later ? 'Später senden' : 'Senden');

  /** Warum noch nicht gesendet werden kann – dieselben Regeln wie im Dienst, hier nur
   *  früher gesagt: am Knopf, im Hover. ``null`` = vollständig. */
  const problem = !channel ? (mode === 'email' ? 'Kein Postfach verbunden' : 'Kein Kanal verfügbar')
    : mode === 'email' && !to.length ? 'Mindestens ein Empfänger im «An»'
      : mode === 'email' && !theSubject.trim() ? 'Betreff fehlt'
        : calledIn && to.length !== 1 ? 'Wer hat angerufen?'
          : !reached && !calledIn ? `${reply?.sender.name} muss im «An» oder «Cc» stehen`
            : !body.trim() ? 'Text fehlt' : null;

  const restore = (d: Draft) => {
    setMode('email'); setTo(d.to); setCc(d.cc); setBcc(d.bcc); setShowCc(d.showCc);
    setSubject(d.subject); setReply(d.reply); setMailKey(d.mailKey); setBody(d.body);
    setLater(d.later);
  };
  const clear = () => {
    setBody(''); setLater(null); setSubject(''); setReply(null); setEdit(false); setMailKey(undefined);
    setCc([]); setBcc([]); setShowCc(false); setTo(mode === 'internal' ? [] : [person]);
  };

  const post = async (payload: MessageIn, draft?: Draft) => {
    setBusy(true); setError(null);
    try {
      await api.createMessage(payload);
      sent.current();
      return true;
    } catch (e) {
      if (draft) restore(draft);
      setError(e instanceof Error ? e.message : 'Konnte nicht gespeichert werden.');
      return false;
    } finally {
      setBusy(false);
    }
  };

  /** Die zurückgehaltene Mail sofort hinausschicken – nach Ablauf, vor einer zweiten oder
   *  beim Verlassen der Ansicht. Eine Mail geht nie verloren, weil jemand weiterklickt. */
  const flush = () => {
    const p = pending.current;
    if (!p) return;
    clearTimeout(p.timer);
    pending.current = null;
    const draft = held ?? undefined;
    setHeld(null);
    void post(p.payload, draft);
  };
  const flushRef = useRef(flush);
  flushRef.current = flush;
  useEffect(() => () => {
    const p = pending.current;
    if (!p) return;
    clearTimeout(p.timer);
    void api.createMessage(p.payload).then(() => sent.current()).catch(() => {});
  }, []);
  // Wer das Fenster schliesst, während «Rückgängig» steht, wird gewarnt; geht er trotzdem,
  // geht die Mail noch hinaus.
  useEffect(() => {
    if (!held) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    const leave = () => flushRef.current();
    window.addEventListener('beforeunload', warn);
    window.addEventListener('pagehide', leave);
    return () => {
      window.removeEventListener('beforeunload', warn);
      window.removeEventListener('pagehide', leave);
    };
  }, [held]);

  const send = async () => {
    if (!channel || problem) return;
    flush();
    const named = new Set([me.object_id, ...[...to, ...cc, ...bcc].map((p) => p.object_id)]);
    const payload: MessageIn = {
      channel: channel.key,
      to: to.map((p) => p.object_id), cc: cc.map((p) => p.object_id),
      bcc: bcc.map((p) => p.object_id),
      about: named.has(person.object_id) ? [] : [person.object_id],
      subject: theSubject.trim() || null, body,
      at: later ? LATER.find((l) => l.key === later)!.at().toISOString() : null,
      incoming: calledIn,
    };
    if (mode !== 'email') {
      if (await post(payload)) clear();
      return;
    }
    // ►►► Eine Mail wartet drei Sekunden – «Rückgängig» holt sie genau so zurück. ◄◄◄
    const draft: Draft = { to, cc, bcc, showCc, subject, reply, mailKey, body, later };
    clear();
    setError(null);
    setHeld(draft);
    pending.current = { payload, timer: setTimeout(() => flushRef.current(), UNDO_MS) };
  };
  // Die Sekunden im Knopf – der Ring läuft über CSS, die Zahl hier.
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (!held) return;
    const end = Date.now() + UNDO_MS;
    setLeft(Math.ceil(UNDO_MS / 1000));
    const t = setInterval(() => setLeft(Math.max(1, Math.ceil((end - Date.now()) / 1000))), 200);
    return () => clearInterval(t);
  }, [held]);
  const undo = () => {
    const p = pending.current;
    if (!p || !held) return;
    clearTimeout(p.timer);
    pending.current = null;
    restore(held);
    setHeld(null);
    textRef.current?.focus();
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); void send(); }}
      style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 12,
        padding: '12px 16px 14px', marginTop: 16 }}>
      <ModeSwitch mode={mode} onPick={pick} />

      {reply && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 10,
          fontSize: 12, color: 'var(--fg-3)', minWidth: 0 }}>
          {reply.topic && <span style={{ fontWeight: 600, color: topicColor(reply.topic) }}>{reply.topic}</span>}
          {!edit && <span className="truncate" style={{ minWidth: 0 }}>
            {to.length ? `an ${to.map((p) => p.name).join(', ')}` : 'Notiz'}
            {cc.length > 0 && `, Cc ${cc.map((p) => p.name).join(', ')}`}</span>}
          {!edit && <button type="button" onClick={() => setEdit(true)}
            style={{ border: 0, background: 'none', padding: 0, font: 'inherit', fontSize: 12,
              color: 'var(--accent)', cursor: 'pointer' }}>ändern</button>}
          <button type="button" onClick={fresh} aria-label="Neue Nachricht statt Antwort"
            data-tip="Neue Nachricht statt Antwort" data-tip-pos="bottom"
            style={{ ...ICON_BTN, marginLeft: 'auto' }}><X size={14} /></button>
        </div>
      )}
      {(!reply || edit) && (
        <Fields mode={mode} me={me} channel={channel} mails={mails} setChannel={setMailKey}
          to={to} setTo={setTo} cc={cc} setCc={setCc} bcc={bcc} setBcc={setBcc}
          showCc={showCc} setShowCc={setShowCc}
          subject={subject} setSubject={setSubject} fixed={fixed} locked={locked}
          later={later} setLater={setLater} incoming={incoming} setIncoming={setIncoming} />
      )}
      {reply && !edit && later !== null && <LaterRow mode={mode} later={later} setLater={setLater} />}
      <label htmlFor="msg-body" className="sr-only">Text</label>
      <textarea id="msg-body" ref={textRef} value={body} onChange={(e) => setBody(e.target.value)} rows={3}
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
        <SendButton mode={mode} verb={verb} problem={problem} busy={busy}
          held={held ? left : null} onUndo={undo} />
      </div>
    </form>
  );
}

/** Das Postfach dieses Datensatzes – mit Zustand und, wo ich darf, Verbinden/Trennen.
 *  Ohne Anbindung (kein OAuth-Client) steht hier nichts: dann wird eine Mail erfasst. */
function Mailboxes({ boxes, onChange }: { boxes: Mailbox[]; onChange: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const shown = boxes.filter((b) => b.connected || b.may_connect || b.problem);
  if (!shown.length) return null;
  const connect = (b: Mailbox) => api.connectMailbox(b.channel)
    .then((r) => { window.location.href = r.url; })
    .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht verbinden.'));
  const drop = (b: Mailbox) => api.disconnectMailbox(b.channel).then(onChange)
    .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht trennen.'));
  const link = { border: 0, background: 'none', padding: 0, font: 'inherit', fontSize: 12,
    color: 'var(--accent)', cursor: 'pointer' } as const;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', marginBottom: 16, fontSize: 12,
      color: 'var(--fg-3)' }}>
      <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Postfach</span>
      {shown.map((b) => (
        <span key={b.channel} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}
          data-tip={b.problem ?? (b.connected ? 'Verbunden – Mails gehen hinaus und kommen herein'
            : 'Nicht verbunden')}>
          <span style={{ width: 7, height: 7, borderRadius: 999, flex: 'none',
            background: b.problem ? 'var(--danger)' : b.connected ? 'var(--success)' : 'var(--fg-4)' }} />
          <span className="truncate">{b.address || 'Kein Postfach'}</span>
          {b.may_connect && (b.connected
            ? <button type="button" style={link} onClick={() => void drop(b)}>Trennen</button>
            : <button type="button" style={link} onClick={() => void connect(b)}>
                {b.problem ? 'Neu verbinden' : 'Verbinden'}</button>)}
        </span>
      ))}
      {error && <span style={{ color: 'var(--danger)' }}>{error}</span>}
    </div>
  );
}

// ─── Die Ansicht ────────────────────────────────────────────────────────────

export function Communication({ person, company, ownCompany, me }: {
  /** Person: Verlauf mit Eingabe. */
  person?: Person;
  /** Firma: der Verlauf ihrer Personen, nur lesend. */
  company?: number;
  /** Eine eigene Gesellschaft – dann steht hier ihr Postfach. */
  ownCompany?: boolean;
  me?: Person | null;
}) {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [channels, setChannels] = useState<MessageChannel[]>([]);
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    api.getMessages(person ? { person: person.object_id } : { company })
      .then((m) => { setMessages(m); setError(null); })
      .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht geladen werden.'));
  }, [person, company]);
  useEffect(() => { load(); }, [load]);
  // Das Postfach steht dort, wem es gehört: an der eigenen Gesellschaft ihres, am eigenen
  // Datensatz das persönliche – nie am Datensatz eines anderen.
  const mine = !!person && person.object_id === me?.object_id;
  const loadChannels = useCallback(() => {
    if (person) api.messageChannels().then(setChannels).catch(() => {});
    if (company && ownCompany) api.mailboxes(company).then(setMailboxes).catch(() => {});
    else if (mine) api.mailboxes().then(setMailboxes).catch(() => {});
  }, [person, company, ownCompany, mine]);
  useEffect(() => { loadChannels(); }, [loadChannels]);
  // Neues aus dem Abgleich erscheint ohne Neuladen der Seite.
  useEffect(() => {
    window.addEventListener(MESSAGES_CHANGED, load);
    return () => window.removeEventListener(MESSAGES_CHANGED, load);
  }, [load]);
  const [target, setTarget] = useState<Target | null>(null);
  const changed = () => window.dispatchEvent(new Event(MESSAGES_CHANGED));
  // «Erledigt ohne Antwort» – eine stille interne Nachricht mit demselben Betreff, die den
  // Absender betrifft: dieselbe Regel wie jede Antwort, kein Sonderfall.
  const done = (m: Message) => {
    if (!person) return;
    api.createMessage({ channel: 'intern', about: [m.sender.object_id], subject: m.reply_subject || null,
      body: '', incoming: false })
      .then(changed).catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht gespeichert werden.'));
  };
  const writable = !!person && !!me && channels.length > 0;

  if (error) return <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>;
  if (!messages) return <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>Lädt …</p>;
  return (
    <div>
      <Mailboxes boxes={mailboxes} onChange={loadChannels} />
      <Timeline messages={messages} mirror={!person} personId={person?.object_id} meId={me?.object_id}
        onReply={writable ? (m) => setTarget({ m, n: Date.now() }) : undefined}
        onDone={writable ? done : undefined} />
      {writable && person && me && (
        <Composer key={person.object_id} person={person} me={me} channels={channels}
          target={target} onSent={changed} />
      )}
    </div>
  );
}
