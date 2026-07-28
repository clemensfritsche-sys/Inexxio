'use client';

import { useEffect, useState } from 'react';
import { Lock, CheckCircle2, XCircle, Info, AlertTriangle, RotateCcw, ScanLine, ThumbsUp, ThumbsDown, Camera, PenLine } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';
import type { CaptureField, InspectionSampleInput, Order } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { Label, PrimaryButton, numericOnly, numericInputProps } from '@/components/erp/fields';
import { PhotoCapture } from '@/components/erp/photo-capture';
import { SignaturePad } from '@/components/erp/signature-pad';
import { useScan } from '@/components/scan/scan-provider';

type Val = string | number | boolean | undefined;

function measureOk(f: CaptureField, v: Val): boolean {
  if (v == null || v === '') return false;
  const n = Number(v);
  if (!Number.isFinite(n)) return false;
  if (f.target == null) return true;          // nur erfasst, kein Soll
  return Math.abs(n - f.target) <= (f.tolerance ?? 0);
}
function fieldOk(f: CaptureField, v: Val): boolean {
  if (f.type === 'measure') return measureOk(f, v);
  if (f.type === 'bool') return v === true;
  return true; // text
}

// Schlüssel je Stichprobe (Instanz + Probe-Nr.)
const sKey = (instanceId: number, slot: number) => `${instanceId}:${slot}`;

export function InspectionPanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  onOrderUpdated: (o: Order) => void;
}) {
  const insp = order.inspection;
  const fields = (insp?.fields ?? []) as CaptureField[];
  const samples = insp?.samples ?? [];
  const required = insp?.required_count ?? 0;
  const pct = insp?.sample_percent ?? 100;
  const result = insp?.result ?? 'pending';
  // Ein fehlgeschlagener Befund wird NICHT an dieser Stelle wiederholt: der Folgeauftrag
  // (Abweichung) klärt ihn, sein Abschluss erledigt den Schritt. Der frühere Knopf
  // «Erneut erfassen» ist entfallen – er war ausserdem eine Sackgasse, weil das Backend
  // nur einen *aktiven* Schritt ausführt und ein fehlgeschlagener das nicht ist (409).
  const resolvedBy = insp?.resolved_by_order_id ?? null;
  const done = result === 'passed' || result === 'failed';
  // Bei einem Mehrpositionen-Auftrag ist ``order.quantity`` NULL – die Gesamtmenge ergibt
  // sich dann aus der Summe der Positionsmengen (Spiegel von ``order_lines.effective_quantity``).
  const qty = order.quantity ?? (order.order_lines ?? []).reduce((s, l) => s + l.quantity, 0);
  const isBatch = order.article_serialization === 'batch';
  const escalated = insp?.escalated ?? false;

  // Werte je Stichprobe: { "instanceId:slot": { fieldKey: value } }
  const [values, setValues] = useState<Record<string, Record<string, Val>>>(() => {
    const init: Record<string, Record<string, Val>> = {};
    samples.forEach((s) => { init[sKey(s.instance_id, s.slot)] = { ...(s.values as Record<string, Val>) }; });
    return init;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scan = useScan();

  // Bild/Unterschrift sind jetzt Erfassungs-FELDTYPEN (kein übergeordnetes Schritt-Flag mehr).
  // Ihre Präsenz je Stichprobe muss erfasst sein (das Backend erzwingt es ebenfalls).
  const mediaKeys = fields.filter((f) => f.type === 'photo' || f.type === 'signature').map((f) => f.key);
  const mediaComplete = samples.every((s) => {
    const vs = values[sKey(s.instance_id, s.slot)] ?? {};
    return mediaKeys.every((mk) => { const v = vs[mk]; return v != null && v !== ''; });
  });
  // Datenerfassung Instanz für Instanz: erst scannen (richtiges Teil?), dann erfassen,
  // dann die nächste. `unlocked` = bereits gescannte (freigeschaltete) Instanzen.
  const [unlocked, setUnlocked] = useState<number[]>([]);
  const distinctInstances = Array.from(new Set(samples.map((s) => s.instance_id)));
  const nextInstance = distinctInstances.find((iid) => !unlocked.includes(iid)) ?? null;
  const allUnlocked = distinctInstances.length > 0 && nextInstance == null;

  function scanNext() {
    if (nextInstance == null) return;
    scan({
      steps: [{
        label: `Instanz ${fmtObjId(nextInstance)}`,
        expected: nextInstance, candidates: [{ objectId: nextInstance, label: 'Instanz' }],
      }],
      onComplete: () => setUnlocked((u) => [...u, nextInstance]),
    });
  }

  function setVal(key: string, fieldKey: string, v: Val) {
    setValues((p) => ({ ...p, [key]: { ...(p[key] ?? {}), [fieldKey]: v } }));
  }

  function sampleOk(key: string): boolean {
    return fields.every((f) => fieldOk(f, values[key]?.[f.key]));
  }
  // Ist überhaupt etwas erfasst? Erst dann lässt sich abschliessen (Notiz #101) – sonst
  // liesse ein Klick die Prüfung mit lauter leeren Werten durchfallen.
  const anyCaptured = samples.some((s) => {
    const vs = values[sKey(s.instance_id, s.slot)] ?? {};
    return fields.some((f) => { const v = vs[f.key]; return v != null && v !== ''; });
  });

  function sampleLabel(instanceId: number, slot: number): string {
    return isBatch ? `Charge ${fmtObjId(instanceId)} · Probe ${slot}` : `Instanz ${fmtObjId(instanceId)}`;
  }

  async function submit() {
    setSaving(true); setError(null);
    try {
      const payload: InspectionSampleInput[] = samples.map((s) => {
        const key = sKey(s.instance_id, s.slot);
        const out: Record<string, unknown> = {};
        fields.forEach((f) => {
          const v = values[key]?.[f.key];
          if (f.type === 'measure') out[f.key] = v === '' || v == null ? null : Number(v);
          else if (f.type === 'bool') out[f.key] = v === true;
          else out[f.key] = v ?? '';
        });
        return { instance_id: s.instance_id, slot: s.slot, values: out, photos: [] };
      });
      onOrderUpdated(await api.updateOrderInspection(order.object_id as number, {
        samples: payload, note: null, step_id: stepId ?? null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally { setSaving(false); }
  }

  if (stepState === 'locked') {
    return (
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Lock size={14} /> Wird aktiv, sobald der vorherige Schritt erledigt ist.
        </div>
      </div>
    );
  }

  return (
    <div style={cardStyle}>

      {/* Eine Zeile, kein Kasten: die Angabe ist Beiwerk, nicht ein eigener Bereich. */}
      <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>
        Prüfumfang: <b>{required}</b> von {qty} Stück <span style={{ color: 'var(--fg-4)' }}>({escalated ? '100 % – hochgestuft' : `${pct}% Stichprobe`})</span>
        {isBatch && required > 1 && <span style={{ color: 'var(--fg-4)' }}> · {required} Proben aus der Charge</span>}
      </div>

      {escalated && !done && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', fontSize: 12 }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Eine Stichprobe war ungenügend – die Prüfung wurde auf <b>100 %</b> hochgestuft. Bitte alle aufgeführten Instanzen erfassen.</span>
        </div>
      )}

      {/* Ergebnis-Banner. «Nicht bestanden» ist NICHT das Ende, aber auch nichts, was man
          hier wegklickt: die **Abweichung** klärt den Fall (nacharbeiten / ersetzen /
          aussortieren), und ihr Abschluss erledigt diesen Schritt. Der Befund selbst bleibt
          stehen – was gemessen wurde, wird nicht überschrieben. */}
      {done && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', padding: '10px 12px', borderRadius: 8,
          background: result === 'passed' ? 'var(--success-bg)' : 'var(--danger-bg)',
          color: result === 'passed' ? 'var(--success)' : 'var(--danger)' }}>
          {result === 'passed' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          <span style={{ fontSize: 13, fontWeight: 700 }}>{result === 'passed' ? 'Bestanden' : 'Nicht bestanden'}</span>
          {insp?.checked_count != null && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>· {insp.checked_count} geprüft</span>}
          {insp?.inspector_name && <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>{insp.inspector_name}</span>}
          {resolvedBy != null && (
            <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--fg-3)' }}
              title="Der Folgeauftrag hat den Befund geklärt – damit ist dieser Schritt erledigt.">
              <RotateCcw size={13} /> Geklärt durch <ObjId value={resolvedBy} />
            </span>
          )}
        </div>
      )}

      {/* Fehlgeschlagen, noch nicht geklärt: der Weg nach vorn führt über die Abweichung,
          nicht über ein erneutes Erfassen an dieser Stelle. */}
      {result === 'failed' && resolvedBy == null && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 8,
          background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', fontSize: 12 }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Die betroffenen Instanzen sind <b>gesperrt</b>. Der Fall wird über die
            <b> Abweichung</b> geklärt (nacharbeiten, ersetzen, aussortieren) – sobald dieser
            Folgeauftrag abgeschlossen ist, gilt dieser Schritt als erledigt und der Auftrag
            läuft weiter.</span>
        </div>
      )}

      {samples.length === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Info size={14} /> Noch keine Instanzen vorhanden.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 420, overflowY: 'auto' }}>
          {/* Nur freigeschaltete (gescannte) Instanzen erfassen – eine nach der anderen */}
          {samples.filter((s) => done || unlocked.includes(s.instance_id)).map((s) => {
            const key = sKey(s.instance_id, s.slot);
            const ok = sampleOk(key);
            return (
              <div key={key} style={{ border: `1px solid ${done ? (ok ? '#bbf7d0' : '#fecaca') : '#e2e8f0'}`, borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--fg-2)', flex: 1 }}>{sampleLabel(s.instance_id, s.slot)}</span>
                </div>
                {/* Nur die konfigurierten Erfassungsfelder – Bild UND Unterschrift sind eigene
                    Feldtypen (CaptureRow rendert sie). KEIN unbedingtes Foto-Feld mehr: wer nur
                    eine Unterschrift konfiguriert hat, bekommt auch NUR die Unterschrift. */}
                {fields.map((f) => (
                  <CaptureRow key={f.key} field={f} value={values[key]?.[f.key]} ok={fieldOk(f, values[key]?.[f.key])}
                    readOnly={done} onChange={(v) => setVal(key, f.key, v)} />
                ))}
              </div>
            );
          })}

          {/* Nächste Instanz scannen (Instanz-für-Instanz-Erfassung) */}
          {!done && nextInstance != null && (
            <button onClick={scanNext}
              style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '12px', borderRadius: 10, border: '1px dashed #cbd5e1', background: '#fff', color: '#2563eb', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
              <ScanLine size={16} /> {unlocked.length === 0 ? 'Erste Instanz scannen' : 'Nächste Instanz scannen'} ({unlocked.length}/{distinctInstances.length})
            </button>
          )}
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {/* Abschluss erst, wenn alle Instanzen gescannt & erfasst sind (inkl. Bild-/Unterschrift-Felder) */}
      {!done && allUnlocked && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {!mediaComplete && (
            <span style={{ fontSize: 11.5, color: 'var(--warning)' }}>
              Bitte alle Bild-/Unterschrift-Felder je Stichprobe erfassen.
            </span>
          )}
          {/* Abschliessen erst, wenn wirklich etwas erfasst wurde: ein Klick auf einen
              leeren Satz hätte die Prüfung mit lauter Nichtwerten durchfallen lassen.
              Keine Ergebnis-Vorschau mehr – das Ergebnis steht nach dem Abschluss da. */}
          <PrimaryButton icon={CheckCircle2} onClick={submit}
            disabled={saving || !mediaComplete || !anyCaptured}>
            {saving ? 'Speichert…' : 'Erfassung abschliessen'}
          </PrimaryButton>
        </div>
      )}
    </div>
  );
}

function CaptureRow({ field, value, onChange, ok, readOnly }: {
  field: CaptureField; value: Val; onChange: (v: Val) => void; ok: boolean; readOnly?: boolean;
}) {
  const filled = value != null && value !== '';
  if (field.type === 'bool') {
    return (
      <div>
        <Label>{field.label}</Label>
        <div style={{ display: 'flex', gap: 6 }}>
          {/* Daumen hoch/runter statt Wörtern: auf einen Blick erfassbar, in jeder
              Sprache verständlich – die Bedeutung steht im Hover. */}
          <Toggle icon={ThumbsUp} label="Gut" active={value === true} tone="ok" disabled={readOnly} onClick={() => onChange(true)} />
          <Toggle icon={ThumbsDown} label="Schlecht" active={value === false} tone="bad" disabled={readOnly} onClick={() => onChange(false)} />
        </div>
      </div>
    );
  }
  if (field.type === 'text') {
    return (
      <div>
        <Label>{field.label}</Label>
        <input value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} disabled={readOnly}
          className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
      </div>
    );
  }
  if (field.type === 'photo') {
    const url = (value as string) || '';
    return (
      <div>
        <Label>{field.label}</Label>
        {readOnly ? (
          url ? (
            <a href={attachmentUrl(url)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={attachmentUrl(url)} alt={field.label} style={{ height: 76, borderRadius: 8, border: '1px solid #e2e8f0', objectFit: 'cover' }} />
            </a>
          ) : <span style={{ fontSize: 12, color: '#94a3b8' }}>—</span>
        ) : (
          <PhotoCapture value={url ? [url] : []} max={1} onChange={(urls) => onChange(urls[0] ?? undefined)} />
        )}
      </div>
    );
  }
  if (field.type === 'signature') {
    const url = (value as string) || '';
    return (
      <div>
        <Label>{field.label}</Label>
        <SignaturePad value={url || null} disabled={readOnly} onChange={(u) => onChange(u ?? undefined)} />
      </div>
    );
  }
  // measure
  const soll = field.target != null ? `Soll ${field.target}${field.tolerance != null ? ` ± ${field.tolerance}` : ''}${field.unit ? ` ${field.unit}` : ''}` : 'Messwert erfassen';
  return (
    <div>
      <Label>{field.label}</Label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Messwert = Zahl: Buchstaben kommen gar nicht erst ins Feld. */}
        <input value={(value as string) ?? ''} onChange={(e) => onChange(numericOnly(e.target.value))} {...numericInputProps} disabled={readOnly} placeholder={field.unit ? `Ist (${field.unit})` : 'Ist'}
          className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          style={{ borderColor: filled && field.target != null ? (ok ? '#86efac' : '#fca5a5') : '#e2e8f0', width: 120 }} />
        <span style={{ fontSize: 12, color: '#94a3b8', flex: 1 }}>{soll}</span>
        {filled && field.target != null && (
          ok ? <CheckCircle2 size={15} style={{ color: '#16a34a' }} /> : <XCircle size={15} style={{ color: '#dc2626' }} />
        )}
      </div>
    </div>
  );
}

/** Gut/Schlecht als **Daumen**: Symbol statt Wort, Bedeutung im Hover. */
function Toggle({ icon: Icon, label, active, tone, onClick, disabled }: {
  icon: React.ElementType; label: string; active: boolean; tone: 'ok' | 'bad';
  onClick: () => void; disabled?: boolean;
}) {
  const color = tone === 'ok' ? 'var(--success)' : 'var(--danger)';
  const bg = tone === 'ok' ? 'var(--success-bg)' : 'var(--danger-bg)';
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={label} aria-label={label}
      aria-pressed={active}
      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 42, height: 34, borderRadius: 'var(--r-sm)', cursor: disabled ? 'default' : 'pointer',
        border: `1px solid ${active ? color : 'var(--border-1)'}`,
        background: active ? bg : '#fff', color: active ? color : 'var(--fg-4)' }}>
      <Icon size={17} />
    </button>
  );
}


const cardStyle: React.CSSProperties = {
  // Das Panel sitzt IN der Modul-Karte des Ablaufs – kein eigener Rahmen, kein eigener
  // Hintergrund, keine eigene Polsterung. Container-in-Container war genau die Schwere,
  // die Notiz #100 meint; die Karte drumherum ist bereits der Container.
  display: 'flex', flexDirection: 'column', gap: 12,
};
