'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Check, Clock, Hand, Loader2, Pencil, Sparkles, X } from 'lucide-react';
import { api } from '@/lib/api';
import { useAction } from '@/lib/use-action';
import { tell } from '@/lib/notice';
import { NOTHING, when, whenTitle } from '@/lib/when';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { Field, SelectField } from '@/components/form/field';
import { useCapture, type CaptureActions, type DraftFromHandgriff } from '@/components/erp/capture/capture-context';
import type { Handgriff } from '@/types';

/**
 * ►►► **Ein Handgriff als Karte – dieselbe im Gespräch und im Angehefteten.** ◄◄◄
 *
 * Eine Zeile, was geschieht (mit Nummer und Name), die Werte, die Quelle. Entschieden wird
 * einzeln (Projektakte, Phase 5 §7.5):
 *
 * - **Ausführen** (bei einer Notiz «Ablegen») – durch die echte Route, mit meinen Rechten, genau
 *   einmal; was nicht geht, sagt der Satz der Route an der Karte.
 * - **Entwurf öffnen** – überall, wo es «Neu anlegen» gibt: ausgefüllt; angelegt wird erst mit
 *   «Freigeben», dann ist der Handgriff erledigt. Fehlen Werte («Fehlt noch: …»), ist das der Weg
 *   – «Ausführen» geht erst, wenn alles da ist.
 * - **Ändern** – die Felder der Handlung (aus ihrer Beschreibung), geprüft mit einem Probelauf.
 * - **Weg** – geschieht nicht.
 *
 * Was nur von Hand geht (eine Datei), hat «Öffnen» statt «Ausführen».
 */
export function HandgriffCard({ h, onChanged }: {
  h: Handgriff;
  /** Nach einer Handlung – das Gespräch bzw. das Angeheftete lädt nach (`lib/feed`). */
  onChanged?: () => void;
}) {
  const { busy, error: problem, run } = useAction('Ging nicht.');
  const [editing, setEditing] = useState(false);
  const capture = useCapture();
  const open = h.state === 'open';
  const draft = capture ? draftOf(h, capture) : null;
  const isNote = isNoteBody(h.body);

  const act = (call: () => Promise<unknown>) => run(async () => { await call(); onChanged?.(); });

  return (
    <div className="erp-hg" data-state={h.state}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, minWidth: 0 }}>
        <StateIcon h={h} />
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span className="erp-hg-line">{h.line || h.summary}</span>
          <span className="erp-hg-meta">
            <ObjId value={h.object_id} />
            <span className="truncate" style={{ minWidth: 0 }}>{h.label}</span>
            <span aria-hidden>·</span>
            <span>{h.source}</span>
            <span aria-hidden>·</span>
            <span className="tabular-nums" data-tip={whenTitle(h.at)}>{when(h.at)}</span>
          </span>
          {!editing && <Values body={h.body} />}
          <StateLine h={h} />
        </div>
      </div>
      {editing && open && (
        <ChangeForm h={h} onCancel={() => setEditing(false)}
          onRun={(body) => act(() => api.runHandgriff(h.id, body).then(() => setEditing(false)))} />
      )}
      {problem && <p role="alert" className="erp-capture-problem"><AlertCircle size={15} aria-hidden />{problem}</p>}
      {open && !editing && (
        <div className="erp-hg-actions">
          {h.hand ? (
            draft && <button type="button" disabled={busy} onClick={() => draft()} className="erp-actbtn erp-actbtn-primary erp-hg-btn">
              <Hand size={14} />Öffnen
            </button>
          ) : (
            <button type="button" disabled={busy || !!h.missing} onClick={() => void act(() => api.runHandgriff(h.id))}
              data-tip={h.missing ? `Erst ergänzen – ${h.missing}` : undefined}
              className={h.missing ? 'erp-actbtn erp-actbtn-neutral erp-hg-btn' : 'erp-actbtn erp-actbtn-primary erp-hg-btn'}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}{isNote ? 'Ablegen' : 'Ausführen'}
            </button>
          )}
          {draft && !h.hand && (
            <button type="button" disabled={busy} onClick={() => draft()}
              className={h.missing ? 'erp-actbtn erp-actbtn-primary erp-hg-btn' : 'erp-actbtn erp-actbtn-neutral erp-hg-btn'}>
              Entwurf öffnen
            </button>
          )}
          {!h.hand && (
            <button type="button" disabled={busy} onClick={() => setEditing(true)} className="erp-actbtn erp-actbtn-neutral erp-hg-btn">
              <Pencil size={13} />Ändern
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button type="button" disabled={busy} onClick={() => void act(() => api.dropHandgriff(h.id))}
            aria-label="Weg" data-tip="Weg – geschieht nicht" className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon erp-hg-x">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function StateIcon({ h }: { h: Handgriff }) {
  const style = { flex: 'none', marginTop: 1 } as const;
  if (h.state === 'done') return <Check size={15} aria-hidden style={{ ...style, color: 'var(--success)' }} />;
  if (h.state === 'dropped') return <X size={15} aria-hidden style={{ ...style, color: 'var(--fg-4)' }} />;
  if (h.state === 'waiting') return <Clock size={15} aria-hidden style={{ ...style, color: 'var(--fg-3)' }} />;
  return <Sparkles size={15} aria-hidden style={{ ...style, color: 'var(--warning)' }} />;
}

function StateLine({ h }: { h: Handgriff }) {
  if (h.state === 'done') {
    return <span className="erp-hg-state">Ausgeführt{h.result ? <> · <ObjId value={h.result} /></> : null}</span>;
  }
  if (h.state === 'dropped') return <span className="erp-hg-state">Weggelegt</span>;
  if (h.state === 'waiting') return <span className="erp-hg-state">Wartet auf Handgriff {(h.waits_for ?? []).join(', ')}</span>;
  if (h.hand) return <span className="erp-hg-state">Geht nur von Hand ({h.hand})</span>;
  if (h.missing) return <span className="erp-hg-state erp-hg-missing">Fehlt noch: {h.missing}</span>;
  return null;
}

/** Die Werte des Handgriffs – Schlüssel und Wert, knapp; was verschachtelt ist, als Text. */
function Values({ body }: { body: unknown }) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  // Was die Karte oben schon nennt (die Datensätze, an denen er hängt), steht hier nicht noch einmal.
  const rows = Object.entries(body as Record<string, unknown>).filter(([k, v]) => v !== null && v !== '' && v !== undefined
    && !Array.isArray(v) && k !== 'channel');
  if (!rows.length) return null;
  return (
    <dl className="erp-hg-values">
      {rows.slice(0, 8).map(([k, v]) => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k}</dt>
          <dd>{show(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function show(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (v && typeof v === 'object' && '$handgriff' in (v as object)) return `aus Handgriff ${(v as { $handgriff: number }).$handgriff}`;
  return JSON.stringify(v);
}

const isNoteBody = (b: unknown) => !!b && typeof b === 'object' && (b as { channel?: string }).channel === 'note';

/**
 * **Wo das ERP einen Entwurf hat** – überall, wo es «Neu anlegen» gibt (Person, Firma, Artikel,
 * Auftrag, Dokument): die Anlage-Route der Handlung ist der Schlüssel (`DRAFTS`). Der Entwurf
 * öffnet ausgefüllt; mit «Freigeben» ist der Handgriff erledigt.
 */
const DRAFTS: Record<string, DraftFromHandgriff['kind']> = {
  '/api/v1/erp/records': 'user',
  '/api/v1/admin/companies': 'organization',
  '/api/v1/erp/articles': 'article',
  '/api/v1/erp/orders': 'order',
  '/api/v1/erp/documents': 'document',
};

function draftOf(h: Handgriff, capture: CaptureActions): (() => void) | null {
  const kind = h.method === 'POST' ? DRAFTS[h.path] : undefined;
  if (!kind) return null;
  const body = (h.body && typeof h.body === 'object' ? h.body : {}) as Record<string, unknown>;
  const values = Object.fromEntries(Object.entries(body).filter(([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
    .map(([k, v]) => [k, String(v)]));
  return () => capture.openDraft({ kind, values, body, handgriff: h.id });
}

// ─── Ändern ────────────────────────────────────────────────────────────────────────────

interface Prop { type?: string; enum?: string[]; anyOf?: Prop[]; items?: Prop; description?: string; maxLength?: number }
interface Schema { properties?: Record<string, Prop>; required?: string[] }

/** Der eigentliche Typ eines Feldes – `anyOf [X, null]` ist X. */
function base(p: Prop): Prop {
  return p.anyOf?.find((x) => x.type && x.type !== 'null') ?? p;
}

/**
 * ►► **Ändern – die Felder der Handlung, aus ihrer Beschreibung.** ◄◄ Was das ERP an Feldern
 * nimmt (Typ, Pflicht, Auswahl), steht im Schema der Route; die KI hat nur vorausgefüllt. Jede
 * Eingabe läuft (entprellt) durch den Probelauf – die Meldung ist der Satz der Route.
 */
function ChangeForm({ h, onCancel, onRun }: { h: Handgriff; onCancel: () => void; onRun: (body: unknown) => void }) {
  const { data: op } = useQuery({
    queryKey: ['talks', 'operation', h.id],
    queryFn: ({ signal }) => api.handgriffOperation(h.id, { signal }),
    meta: { what: 'Felder der Handlung' },
  });
  const [values, setValues] = useState<Record<string, unknown>>(
    () => (h.body && typeof h.body === 'object' ? { ...(h.body as Record<string, unknown>) } : {}));
  const [check, setCheck] = useState<{ ok: boolean; detail: string } | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    const t = window.setTimeout(() => {
      api.probeHandgriff(h.id, values, { signal: ctl.signal })
        .then((r) => setCheck({ ok: r.ok, detail: r.detail || r.hand }), (e) => {
          if (!ctl.signal.aborted) tell('Probelauf', 'Nicht geprüft')(e);
        });
    }, 400);
    return () => { window.clearTimeout(t); ctl.abort(); };
  }, [h.id, values]);
  const schema = (op?.schema ?? {}) as Schema;
  const props = Object.entries(schema.properties ?? {});
  const set = (k: string, v: unknown) => setValues((x) => ({ ...x, [k]: v }));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {!op && <span className="erp-skel" style={{ height: 40, borderRadius: 8 }} />}
      {props.map(([k, raw]) => (
        <SchemaField key={k} name={k} prop={base(raw)} required={(schema.required ?? []).includes(k)}
          value={values[k]} onChange={(v) => set(k, v)} />
      ))}
      {check && !check.ok && (
        <p role="alert" className="erp-capture-problem"><AlertCircle size={15} aria-hidden />{check.detail || 'Geht so nicht.'}</p>
      )}
      <div className="erp-hg-actions">
        <button type="button" disabled={!check?.ok} onClick={() => onRun(values)}
          data-tip={check && !check.ok ? check.detail : undefined}
          className="erp-actbtn erp-actbtn-primary erp-hg-btn"><Check size={14} />Ausführen</button>
        <button type="button" onClick={onCancel} className="erp-actbtn erp-actbtn-neutral erp-hg-btn">Zurück</button>
      </div>
    </div>
  );
}

/** Ein Feld aus dem Schema – Text, Zahl, Ja/Nein, Auswahl, Datensatz; Verschachteltes als JSON. */
function SchemaField({ name, prop, required, value, onChange }: {
  name: string; prop: Prop; required: boolean; value: unknown; onChange: (v: unknown) => void;
}) {
  const label = prop.description ? `${name} – ${prop.description}` : name;
  if (prop.enum) {
    return <SelectField name={name} label={label} required={required} value={String(value ?? '')}
      onChange={(v) => onChange(v || null)} options={[{ value: '', label: NOTHING }, ...prop.enum.map((e) => ({ value: e, label: e }))]} />;
  }
  if (prop.type === 'boolean') {
    return <SelectField name={name} label={label} value={value === true ? 'ja' : value === false ? 'nein' : ''}
      onChange={(v) => onChange(v === 'ja' ? true : v === 'nein' ? false : null)}
      options={[{ value: '', label: NOTHING }, { value: 'ja', label: 'ja' }, { value: 'nein', label: 'nein' }]} />;
  }
  if (prop.type === 'integer' && name.endsWith('object_id')) {
    return <ObjectSelect label={label} value={typeof value === 'number' ? value : null} required={required}
      onChange={(oid) => onChange(oid)} find={findRecords} />;
  }
  if (prop.type === 'integer' || prop.type === 'number') {
    return <Field name={name} label={label} type="number" required={required} value={value == null ? '' : String(value)}
      onChange={(v) => onChange(v === '' ? null : Number(v))} />;
  }
  if (prop.type === 'string') {
    const long = (prop.maxLength ?? 0) > 300;
    return <Field name={name} label={label} required={required} rows={long ? 4 : undefined}
      value={typeof value === 'string' ? value : value == null ? '' : String(value)} onChange={(v) => onChange(v)} />;
  }
  return <JsonField name={name} label={label} value={value} onChange={onChange} />;
}

/** Verschachteltes (Listen, Unterobjekte) – als JSON; gültig wird es erst übernommen. */
function JsonField({ name, label, value, onChange }: { name: string; label: string; value: unknown; onChange: (v: unknown) => void }) {
  const [text, setText] = useState(() => JSON.stringify(value ?? null, null, 1));
  const [bad, setBad] = useState(false);
  return <Field name={name} label={label} rows={3} value={text} error={bad ? 'Kein gültiges JSON.' : null}
    onChange={(t) => {
      setText(t);
      try { onChange(JSON.parse(t)); setBad(false); } catch { setBad(true); }
    }} />;
}

const findRecords = (q: string) => api.documentTargets(q)
  .then((rs) => rs.map((r) => ({ object_id: r.object_id, name: r.label })));
