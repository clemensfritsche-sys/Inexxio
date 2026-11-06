'use client';

/**
 * ►►► **Der Verlauf – EIN Verlauf für jeden Datensatz** (Projektakte «Die lernende Firma» §4.2). ◄◄◄
 *
 * Eine Komponente an jeder Detailansicht (Person, Firma, Auftrag, Artikel, Instanz, Dokument),
 * eine Abfrage (`GET /erp/history/{nummer}`, `services/history`): gemischt nach Zeit stehen
 * **Nachrichten** (Mail, Anruf, intern, Notiz – als Blasen, wie in der Kommunikation),
 * **Dokumente**, die am Datensatz hängen, und **Änderungen** aus dem Log – je Handlung ein Block,
 * technisch: wer · wann · Tabelle, darunter `feld: alt → neu` in Festbreite. Übersetzt sind nur
 * die Tabellennamen (vom Server); keine Sätze je Ereignis.
 *
 * **In Seiten wie WhatsApp**: unten das Neueste, nach oben rollen lädt die ältere Seite (der
 * Cursor kommt vom Server). Der Verlauf wächst nie mit – geladen ist, was man gesehen hat.
 *
 * Eingabe gibt es nur an Person (und dort die Kommunikation, `communication.tsx`); andere
 * Datensätze haben keine – Wissen kommt später über «Erfassen».
 */

import { useEffect, useRef, type ReactNode } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { ChevronUp, FileText, PenLine, Zap } from 'lucide-react';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { formatWhen, whenDay, whenTitle } from '@/lib/when';
import { ObjId } from '@/components/erp/obj-id';
import type { ChangeBlock, HistoryEntry, Message } from '@/types';
import { Bubble, Divider, SendingBubble, type Sending } from '@/components/erp/communication/timeline';

/** Die Seiten des Verlaufs – eine Query je Nummer; dieselbe für den Verlauf und die
 *  Kommunikation darüber (React Query fragt nur einmal). */
export function useHistory(objectId: number) {
  return useInfiniteQuery({
    queryKey: qk.history(objectId),
    queryFn: ({ pageParam, signal }) => api.history(objectId, pageParam, { signal }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.before ?? undefined,
    meta: { what: 'Verlauf' },
  });
}

/** Die geladenen Nachrichten – chronologisch (die Eingabe liest daraus Offenes und Anliegen). */
export function loadedMessages(entries: HistoryEntry[]): Message[] {
  return entries.filter((e) => e.message).map((e) => e.message as Message).reverse();
}

/** Wer gehandelt hat – die Person beim Namen, sonst die Art (System, von aussen, KI). */
function actorOf(c: ChangeBlock): string {
  const name = c.actor_name ?? (c.actor_id != null ? String(c.actor_id) : null);
  if (c.actor_kind === 'ai') return name ? `KI für ${name}` : 'KI';
  if (c.actor_kind === 'system') return 'System';
  if (c.actor_kind === 'external') return 'Von aussen';
  return name ?? 'Unbekannt';
}

const MONO = { fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: '17px',
  color: 'var(--fg-2)', overflowWrap: 'anywhere' } as const;
const NIL = '∅';

/** ►►► **Eine Handlung** – eine Kopfzeile «wer · wann · Tabelle», darunter je Zeile
 *  `feld: alt → neu` (neu angelegt: `feld: neu`, gelöscht: `feld: alt`). Ein Ereignis steht
 *  mit seinem Namen und seinen einfachen Angaben da. ◄◄◄ */
function ChangeRow({ c, at }: { c: ChangeBlock; at: string }) {
  const words = [...new Set(c.rows.map((r) => r.word ?? r.table ?? r.event ?? ''))].filter(Boolean);
  const evented = c.rows.every((r) => r.event);
  const Icon = evented ? Zap : PenLine;
  return (
    <div className="ix-row" style={{ alignSelf: 'stretch', padding: '6px 2px 6px 10px',
      borderLeft: '1px solid var(--border-1)', margin: '2px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)',
        minWidth: 0 }}>
        <Icon size={12} style={{ flex: 'none' }} />
        <span className="truncate" data-tip={`Quelle: ${c.source}`}>{actorOf(c)}</span>
        <span aria-hidden>·</span>
        <span className="tabular-nums" style={{ flex: 'none' }} data-tip={whenTitle(at)}>{formatWhen(at).text}</span>
        {words.length > 0 && <><span aria-hidden>·</span><span className="truncate">{words.join(', ')}</span></>}
      </div>
      {c.rows.map((r, i) => (
        <div key={i} style={{ ...MONO, marginTop: 2 }}>
          {(c.rows.length > 1 || r.event) && (
            <div style={{ color: 'var(--fg-3)' }}>
              {r.event ?? `${r.word ?? r.table} · ${r.action}`}{r.row && !r.event ? ` #${r.row}` : ''}
            </div>
          )}
          {r.event
            ? Object.entries(r.payload ?? {}).map(([k, v]) => <div key={k}>{k}: {v}</div>)
            : (r.changes ?? []).map((ch) => (
              <div key={ch.field}>
                {ch.field}: {r.action === 'insert' ? ch.new ?? NIL
                  : r.action === 'delete' && ch.new == null ? ch.old ?? NIL
                    : `${ch.old ?? NIL} → ${ch.new ?? NIL}`}
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}

/** Ein Dokument, das an diesem Datensatz hängt – Nummer, «Art · Name», wann. */
function DocumentRow({ e }: { e: HistoryEntry }) {
  const d = e.document!;
  return (
    <div className="ix-row" style={{ alignSelf: 'stretch', display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 2px 6px 10px', borderLeft: '1px solid var(--border-1)', margin: '2px 0',
      fontSize: 13, color: d.deleted ? 'var(--fg-4)' : 'var(--fg-2)', minWidth: 0 }}>
      <FileText size={14} style={{ flex: 'none', color: 'var(--fg-3)' }} />
      <ObjId value={d.object_id} />
      <span className="truncate" style={{ flex: 1, minWidth: 0 }}>
        {d.art} · {d.name}{d.deleted ? ' (gelöscht)' : ''}</span>
      <span className="tabular-nums" style={{ flex: 'none', fontSize: 11, color: 'var(--fg-3)' }}
        data-tip={whenTitle(e.at)}>{formatWhen(e.at).text}</span>
    </div>
  );
}

export function History({ objectId, mirror = true, personId, meId, onReply, onDone, sending }: {
  objectId: number;
  /** Nur lesend (Firma, jeder Datensatz ausser der Person): Namen an jeder Blase, kein
   *  offen/überfällig. */
  mirror?: boolean;
  personId?: number; meId?: number;
  onReply?: (m: Message) => void; onDone?: (m: Message) => void;
  /** Die Mail, die gerade drei Sekunden wartet – sie steht schon am Ende des Verlaufs. */
  sending?: Sending | null;
}) {
  const q = useHistory(objectId);
  const more = useRef<HTMLButtonElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = q;
  // ►►► Älteres kommt von selbst, sobald man nach oben rollt; der Knopf bleibt als Weg für
  // die Tastatur – der Beobachter drückt ihn, sobald er in Sicht kommt. ◄◄◄
  useEffect(() => {
    const el = more.current;
    if (!el || !hasNextPage || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver((seen) => {
      if (seen.some((x) => x.isIntersecting) && !isFetchingNextPage) void fetchNextPage();
    });
    io.observe(el);
    return () => io.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (!q.data && q.error) {
    return <p style={{ color: 'var(--danger)', fontSize: 13 }}>{q.error.message || 'Konnte nicht geladen werden.'}</p>;
  }
  if (!q.data) return <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>Lädt …</p>;
  const entries = q.data.pages.flatMap((p) => p.entries ?? []).slice().reverse();
  if (!entries.length && !sending) {
    return <p style={{ color: 'var(--fg-3)', fontSize: 13, padding: '24px 0' }}>Noch nichts im Verlauf.</p>;
  }
  const rows: ReactNode[] = [];
  if (hasNextPage) rows.push(
    <button key="more" ref={more} type="button" data-more="" disabled={isFetchingNextPage}
      onClick={() => void fetchNextPage()}
      style={{ alignSelf: 'center', display: 'inline-flex', alignItems: 'center', gap: 6, height: 28,
        padding: '0 12px', border: '1px solid var(--border-1)', borderRadius: 999, cursor: 'pointer',
        background: 'var(--bg-1)', color: 'var(--fg-2)', font: 'inherit', fontSize: 12, fontWeight: 600,
        marginBottom: 4 }}>
      <ChevronUp size={14} />{isFetchingNextPage ? 'Lädt …' : 'Ältere laden'}
    </button>);
  let last = '';
  for (const e of entries) {
    const m = e.message;
    const label = m?.planned ? 'Geplant' : whenDay(e.at);
    if (label !== last) rows.push(<Divider key={`d-${e.key}`} label={label} />);
    last = label;
    if (m) {
      const named = mirror || (m.ours ? m.sender.object_id !== meId : m.sender.object_id !== personId);
      rows.push(<Bubble key={e.key} m={m} mirror={mirror} named={named} onReply={onReply} onDone={onDone} />);
    } else if (e.document) rows.push(<DocumentRow key={e.key} e={e} />);
    else if (e.change) rows.push(<ChangeRow key={e.key} c={e.change} at={e.at} />);
  }
  // ►►► Der Verlauf steht beim NEUESTEN. ◄◄◄ `column-reverse` verankert das Rollen am unteren
  // Ende: ohne Skript beim Öffnen unten, Neues bleibt im Blick, und «ältere laden» schiebt
  // nichts weg. Höhe begrenzt, damit darunter alles erreichbar bleibt; oben läuft er weich aus.
  return (
    <div style={{ maxHeight: 'min(60vh, 560px)', overflowY: 'auto', display: 'flex',
      flexDirection: 'column-reverse',
      maskImage: 'linear-gradient(to bottom, transparent 0, #000 32px)',
      WebkitMaskImage: 'linear-gradient(to bottom, transparent 0, #000 32px)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '4px 0' }}>
        {rows}
        {sending && <SendingBubble s={sending} />}
      </div>
    </div>
  );
}
