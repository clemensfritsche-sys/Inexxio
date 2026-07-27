'use client';

/**
 * Testnotizen – «Pin setzen, Kommentar hinterlassen» (siehe `docs/feedback.md`).
 *
 * Ein kleiner Launcher unten LINKS (die KI sitzt rechts) öffnet die Notizen dieser
 * Seite. «Notiz anheften» schaltet in den Zeigemodus: das Element unter dem Cursor
 * wird umrandet, ein Klick heftet die Notiz daran – Kontext (Route, Datensatz,
 * Element, Umgebung, letzte Fehler) schneidet die Oberfläche selbst mit.
 *
 * Sichtbar nur in der **Testumgebung** und nur für angemeldete Nutzer – bewusst für
 * JEDE Rolle, damit auch aus Kunden- oder Lieferantensicht gemeldet werden kann.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import {
  Check, ClipboardCheck, Copy, Crosshair, MessageSquarePlus, RotateCcw, Trash2, X,
} from 'lucide-react';
import { api } from '@/lib/api';
import { onAuthChange } from '@/lib/firebase';
import {
  FEEDBACK_ENABLED, UI_MARKER, currentObjectId, currentRoute, describeAnchor,
  describeContext, locateAnchor, notesToMarkdown, startErrorCapture,
} from '@/lib/feedback';
import type { FeedbackAnchor, FeedbackNote, FeedbackStatus } from '@/types';

const ROLE_KEY = 'inexxio_user_role';   // gleiche Quelle wie das ERP-Layout

/** Ampel: offen = gelb (zu tun), erledigt = grün, verworfen = neutral. */
const DOT: Record<FeedbackStatus, string> = {
  open: 'var(--warning, #C8861A)',
  done: 'var(--success, #16a34a)',
  dismissed: 'var(--fg-4, #8A8A82)',
};

type Draft = { anchor: FeedbackAnchor; x: number; y: number };

export function FeedbackPin() {
  const pathname = usePathname();
  const [signedIn, setSignedIn] = useState(false);
  const [role, setRole] = useState('');
  const [notes, setNotes] = useState<FeedbackNote[]>([]);
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  // Das Element selbst (nicht sein Rechteck): setzt man dasselbe Element erneut, bricht
  // React das Rendern ab – sonst würde jede Mausbewegung das ganze Widget neu rendern.
  const [hover, setHover] = useState<Element | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [tick, setTick] = useState(0);            // Neuberechnung der Pin-Positionen

  // Eigenständige Auth-Prüfung (das Widget hängt in mehreren Layouts – wie die KI).
  useEffect(() => {
    if (!FEEDBACK_ENABLED) return;
    return onAuthChange(async (fbUser) => {
      if (!fbUser) { setSignedIn(false); return; }
      try {
        api.setToken(await fbUser.getIdToken());
        setSignedIn(true);
        const cached = localStorage.getItem(ROLE_KEY);
        if (cached) { setRole(cached); return; }
        const me = await api.getMe();
        localStorage.setItem(ROLE_KEY, me.role);
        setRole(me.role);
      } catch { /* Rolle ist nur Beiwerk der Notiz – kein Grund, nichts zu rendern */ }
    });
  }, []);

  useEffect(() => (FEEDBACK_ENABLED ? startErrorCapture() : undefined), []);

  const reload = useCallback(async () => {
    if (!signedIn) return;
    try { setNotes(await api.listFeedback(currentRoute())); } catch { setNotes([]); }
  }, [signedIn]);

  useEffect(() => { void reload(); }, [reload, pathname]);

  // Zeigemodus: Element unter dem Cursor umranden, Klick heftet die Notiz an.
  useEffect(() => {
    if (!picking) return;
    const ours = (el: Element | null) => !!el?.closest(`[${UI_MARKER}]`);
    const onMove = (e: MouseEvent) => {
      const el = document.elementFromPoint(e.clientX, e.clientY);
      setHover(el && !ours(el) ? el : null);
    };
    const onClick = (e: MouseEvent) => {
      const el = e.target as Element | null;
      if (!el || ours(el)) return;               // eigene UI bleibt normal bedienbar
      e.preventDefault();
      e.stopPropagation();
      setDraft({ anchor: describeAnchor(el, e.clientX, e.clientY), x: e.clientX, y: e.clientY });
      setPicking(false);
      setHover(null);
    };
    // Zeigen darf NIE auslösen: viele Bedienelemente reagieren schon auf pointer-/mousedown.
    // Ein Klick auf «Freigeben» im Zeigemodus würde sonst den Auftrag wirklich freigeben.
    const swallow = (e: Event) => {
      if (!ours(e.target as Element | null)) { e.preventDefault(); e.stopPropagation(); }
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setPicking(false); };
    document.addEventListener('mousemove', onMove, true);
    document.addEventListener('pointerdown', swallow, true);
    document.addEventListener('mousedown', swallow, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('keydown', onKey, true);
    document.body.style.cursor = 'crosshair';
    return () => {
      document.removeEventListener('mousemove', onMove, true);
      document.removeEventListener('pointerdown', swallow, true);
      document.removeEventListener('mousedown', swallow, true);
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('keydown', onKey, true);
      document.body.style.cursor = '';
      setHover(null);
    };
  }, [picking]);

  // Pins sitzen an echten Elementen – bei Scroll/Resize neu vermessen.
  useEffect(() => {
    if (!open) return;
    const onMove = () => setTick((t) => t + 1);
    window.addEventListener('scroll', onMove, true);
    window.addEventListener('resize', onMove);
    return () => {
      window.removeEventListener('scroll', onMove, true);
      window.removeEventListener('resize', onMove);
    };
  }, [open]);

  const save = useCallback(async (body: string) => {
    if (!draft) return;
    const note = await api.createFeedback({
      body,
      route: currentRoute(),
      target_object_id: currentObjectId(),
      anchor: draft.anchor,
      context: describeContext(role),
    });
    setNotes((cur) => [note, ...cur]);
    setDraft(null);
    setOpen(true);
  }, [draft, role]);

  const setStatus = useCallback(async (id: number, status: FeedbackStatus) => {
    const updated = await api.updateFeedback(id, { status });
    setNotes((cur) => cur.map((n) => (n.id === id ? updated : n)));
  }, []);

  const remove = useCallback(async (id: number) => {
    await api.deleteFeedback(id);
    setNotes((cur) => cur.filter((n) => n.id !== id));
    setActiveId((cur) => (cur === id ? null : cur));
  }, []);

  const openCount = useMemo(() => notes.filter((n) => n.status === 'open').length, [notes]);
  if (!FEEDBACK_ENABLED || !signedIn) return null;

  return (
    <div {...{ [UI_MARKER]: 'true' }}>
      {hover && <HighlightBox el={hover} />}
      {open && (
        <PinLayer notes={notes} activeId={activeId} tick={tick} onSelect={setActiveId} />
      )}
      {draft && (
        <Composer
          draft={draft} onCancel={() => setDraft(null)} onSave={save}
        />
      )}
      {open ? (
        <Panel
          notes={notes} openCount={openCount} picking={picking} activeId={activeId}
          onClose={() => { setOpen(false); setPicking(false); }}
          onPick={() => setPicking((p) => !p)}
          onSelect={setActiveId}
          onStatus={setStatus}
          onRemove={remove}
          onCleared={reload}
        />
      ) : (
        <Launcher count={openCount} onClick={() => setOpen(true)} />
      )}
    </div>
  );
}

/** Umrandung des Elements unter dem Cursor – reine Anzeige, nie klickbar. */
function HighlightBox({ el }: { el: Element }) {
  const rect = el.getBoundingClientRect();
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed z-[60] rounded-ds-xs"
      style={{
        top: rect.top, left: rect.left, width: rect.width, height: rect.height,
        outline: '2px solid var(--inexxio, #E51A14)', outlineOffset: 1,
        background: 'color-mix(in srgb, var(--inexxio, #E51A14) 8%, transparent)',
      }}
    />
  );
}

function Launcher({ count, onClick }: { count: number; onClick: () => void }) {
  return (
    <button
      type="button" onClick={onClick}
      title="Testnotizen – Pin setzen und kommentieren"
      aria-label="Testnotizen öffnen"
      className="fixed bottom-5 left-5 z-50 flex h-11 w-11 items-center justify-center rounded-full border border-border-1 bg-bg-1 text-fg-2 shadow-ds-md transition-transform hover:scale-105 hover:text-inexxio"
    >
      <MessageSquarePlus size={19} />
      {count > 0 && (
        <span
          className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white"
          style={{ background: DOT.open }}
        >
          {count}
        </span>
      )}
    </button>
  );
}

/** Notizen dieser Seite + die zwei Aktionen: anheften und exportieren. */
function Panel({ notes, openCount, picking, activeId, onClose, onPick, onSelect, onStatus, onRemove, onCleared }: {
  notes: FeedbackNote[]; openCount: number; picking: boolean; activeId: number | null;
  onClose: () => void; onPick: () => void; onSelect: (id: number | null) => void;
  onStatus: (id: number, status: FeedbackStatus) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
  onCleared: () => Promise<void>;
}) {
  return (
    <div
      className="fixed bottom-5 left-5 z-50 flex flex-col overflow-hidden rounded-ds-lg border border-border-1 bg-bg-1 shadow-ds-lg"
      style={{ width: 'min(340px, calc(100vw - 24px))', maxHeight: 'min(60vh, 520px)' }}
      role="dialog" aria-label="Testnotizen"
    >
      <div className="flex items-center gap-2 border-b border-border-1 bg-bg-2 px-3 py-2.5">
        <MessageSquarePlus size={15} className="text-fg-3" />
        <div className="flex-1 font-display text-sm font-bold tracking-tight text-fg-1">
          Testnotizen
        </div>
        <span className="text-[11px] text-fg-4">{openCount} offen</span>
        <button type="button" onClick={onClose} aria-label="Schliessen"
          className="rounded-ds-sm p-1 text-fg-3 transition-colors hover:bg-bg-3 hover:text-fg-1">
          <X size={15} />
        </button>
      </div>

      <div className="border-b border-border-1 p-2.5">
        <button
          type="button" onClick={onPick}
          className={`flex w-full items-center justify-center gap-2 rounded-ds-md px-3 py-2.5 text-xs font-semibold transition-colors ${
            picking ? 'bg-fg-1 text-bg-1' : 'bg-inexxio text-white'
          }`}
        >
          <Crosshair size={14} />
          {picking ? 'Element anklicken … (Esc bricht ab)' : 'Notiz anheften'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {notes.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-fg-4">
            Noch keine Notiz auf dieser Seite.
          </p>
        ) : (
          notes.map((n, i) => (
            <NoteRow key={n.id} note={n} index={i + 1} active={n.id === activeId}
              onSelect={() => onSelect(n.id === activeId ? null : n.id)}
              onStatus={onStatus} onRemove={onRemove} />
          ))
        )}
      </div>

      <FooterActions onCleared={onCleared} />
    </div>
  );
}

function NoteRow({ note, index, active, onSelect, onStatus, onRemove }: {
  note: FeedbackNote; index: number; active: boolean; onSelect: () => void;
  onStatus: (id: number, status: FeedbackStatus) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } finally { setBusy(false); }
  };
  const act = (status: FeedbackStatus) => run(() => onStatus(note.id, status));
  return (
    <div
      className={`border-b border-border-1 px-3 py-2.5 transition-colors ${active ? 'bg-accent-soft' : 'hover:bg-bg-2'}`}
      onClick={onSelect} role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onSelect(); }}
    >
      <div className="flex items-start gap-2">
        <span aria-hidden className="mt-1 h-2 w-2 shrink-0 rounded-full"
          style={{ background: DOT[note.status] }} />
        <div className="min-w-0 flex-1">
          <p className="text-xs leading-snug text-fg-1">
            <span className="text-fg-4">#{index}</span> {note.body}
          </p>
          {note.anchor?.label && (
            <p className="mt-0.5 truncate text-[11px] text-fg-4">«{note.anchor.label}»</p>
          )}
          {note.resolution && (
            <p className="mt-1 text-[11px] text-success">{note.resolution}</p>
          )}
        </div>
        {note.mine && (
          <div className="flex shrink-0 items-center gap-0.5">
            <button
              type="button" disabled={busy}
              onClick={(e) => { e.stopPropagation(); void act(note.status === 'open' ? 'done' : 'open'); }}
              title={note.status === 'open' ? 'Als erledigt markieren' : 'Wieder öffnen'}
              className="rounded-ds-sm p-1 text-fg-3 transition-colors hover:bg-bg-3 hover:text-fg-1 disabled:opacity-40"
            >
              {note.status === 'open' ? <Check size={14} /> : <RotateCcw size={13} />}
            </button>
            <button
              type="button" disabled={busy}
              onClick={(e) => { e.stopPropagation(); void run(() => onRemove(note.id)); }}
              title="Notiz löschen"
              className="rounded-ds-sm p-1 text-fg-4 transition-colors hover:bg-bg-3 hover:text-danger disabled:opacity-40"
            >
              <Trash2 size={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Fusszeile: exportieren und aufräumen. «Alles löschen» verlangt einen zweiten Klick
 * (der Knopf fragt zurück) – ein Modal wäre für eine Testumgebung zu viel Zeremonie,
 * ein einzelner Klick zu wenig Schutz. Gelöscht wird weich (`is_active=false`).
 */
function FooterActions({ onCleared }: { onCleared: () => Promise<void> }) {
  const [copied, setCopied] = useState<'idle' | 'done' | 'error'>('idle');
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const copy = async () => {
    try {
      const all = await api.listFeedback();
      await navigator.clipboard.writeText(notesToMarkdown(all));
      setCopied('done');
    } catch { setCopied('error'); }
    setTimeout(() => setCopied('idle'), 2500);
  };

  const clear = async (scope: 'done' | 'all') => {
    setBusy(true);
    try { await api.clearFeedback(scope); await onCleared(); }
    finally { setBusy(false); setConfirming(false); }
  };

  return (
    <div className="flex flex-col gap-1 border-t border-border-1 bg-bg-2 px-3 py-2">
      <button
        type="button" onClick={copy}
        className="flex items-center justify-center gap-1.5 text-[11px] font-semibold text-fg-3 transition-colors hover:text-fg-1"
      >
        {copied === 'done' ? <ClipboardCheck size={12} /> : <Copy size={12} />}
        {copied === 'done' ? 'Kopiert – in die Entwicklungs-Sitzung einfügen'
          : copied === 'error' ? 'Kopieren fehlgeschlagen'
          : 'Alle offenen Notizen als Markdown kopieren'}
      </button>
      <div className="flex items-center justify-center gap-3 text-[11px] text-fg-4">
        <button
          type="button" disabled={busy} onClick={() => clear('done')}
          title="Erledigte und verworfene Notizen entfernen"
          className="transition-colors hover:text-fg-2 disabled:opacity-40"
        >
          Erledigte aufräumen
        </button>
        <span aria-hidden>·</span>
        <button
          type="button" disabled={busy}
          onClick={() => (confirming ? clear('all') : setConfirming(true))}
          onBlur={() => setConfirming(false)}
          title="Alle eigenen Notizen löschen"
          className={`transition-colors disabled:opacity-40 ${confirming ? 'font-semibold text-danger' : 'hover:text-fg-2'}`}
        >
          {confirming ? 'Wirklich alle löschen?' : 'Alles zurücksetzen'}
        </button>
      </div>
    </div>
  );
}

/** Die Pins auf der Seite – sichtbar, solange die Liste offen ist. */
function PinLayer({ notes, activeId, tick, onSelect }: {
  notes: FeedbackNote[]; activeId: number | null; tick: number; onSelect: (id: number) => void;
}) {
  void tick;   // erzwingt die Neuvermessung bei Scroll/Resize
  return (
    <>
      {notes.map((note, i) => {
        const rect = locateAnchor(note);
        if (!rect) return null;
        const a = note.anchor!;
        return (
          <button
            key={note.id} type="button" onClick={() => onSelect(note.id)}
            title={note.body}
            className="fixed z-[55] flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-[10px] font-bold text-white shadow-ds-sm transition-transform hover:scale-110"
            style={{
              top: rect.top + a.ry * rect.height,
              left: rect.left + a.rx * rect.width,
              background: DOT[note.status],
              outline: note.id === activeId ? '2px solid var(--fg-1)' : 'none',
            }}
          >
            {i + 1}
          </button>
        );
      })}
    </>
  );
}

/** Das Kommentarfeld direkt am angeklickten Punkt. */
function Composer({ draft, onCancel, onSave }: {
  draft: Draft; onCancel: () => void; onSave: (body: string) => Promise<void>;
}) {
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const text = body.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try { await onSave(text); } catch (e) {
      setError(e instanceof Error ? e.message : 'Speichern fehlgeschlagen');
      setBusy(false);
    }
  };

  const width = 300;
  const left = Math.min(Math.max(12, draft.x - width / 2), window.innerWidth - width - 12);
  const top = Math.min(draft.y + 14, window.innerHeight - 190);

  return (
    <div
      className="fixed z-[60] rounded-ds-lg border border-border-1 bg-bg-1 p-3 shadow-ds-lg"
      style={{ top, left, width }}
    >
      <div className="mb-2 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider text-fg-3">
        <Crosshair size={11} /> Notiz
        {draft.anchor.label && (
          <span className="truncate font-normal normal-case tracking-normal text-fg-4">
            · «{draft.anchor.label}»
          </span>
        )}
      </div>
      <textarea
        autoFocus value={body} onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); }
          if (e.key === 'Escape') onCancel();
        }}
        rows={3} maxLength={2000}
        placeholder="Was stört hier? (Enter speichert)"
        className="w-full resize-none rounded-ds-md border border-border-1 bg-bg-1 px-2.5 py-2 text-sm text-fg-2 outline-none placeholder:text-fg-4 focus:ring-2 focus:ring-accent"
      />
      {error && <p className="mt-1 text-[11px] text-danger">{error}</p>}
      <div className="mt-2 flex gap-2">
        <button
          type="button" onClick={submit} disabled={busy || !body.trim()}
          className="flex-1 rounded-ds-md bg-inexxio px-3 py-2 text-xs font-semibold text-white transition-opacity disabled:opacity-40"
        >
          {busy ? 'Speichert…' : 'Speichern'}
        </button>
        <button
          type="button" onClick={onCancel}
          className="rounded-ds-md border border-border-1 px-3 py-2 text-xs font-semibold text-fg-3 transition-colors hover:bg-bg-2"
        >
          Abbrechen
        </button>
      </div>
    </div>
  );
}
