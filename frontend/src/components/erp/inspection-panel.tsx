'use client';

import { useEffect, useState } from 'react';
import { Lock, CheckCircle2, XCircle, Info, AlertTriangle, RotateCcw, ScanLine, ThumbsUp, ThumbsDown, Camera, PenLine } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';
import type { CaptureField, InspectionSampleInput, Order } from '@/types';

import { ObjId } from '@/components/erp/obj-id';
import { Label, PrimaryButton, ScrollFade, numericOnly, numericInputProps } from '@/components/erp/fields';
import { PhotoCapture } from '@/components/erp/photo-capture';
import { SignaturePad } from '@/components/erp/signature-pad';
import { useScan } from '@/components/scan/scan-provider';
import { formatObjectId } from '@/lib/utils';

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
  // **Eine Zahl, eine Quelle** (Testnotiz #643): «x von N Stück prüfen» – beide Zahlen
  // kommen aus derselben Rechnung wie der Prüfumfang (`inspection.inspected_quantity`:
  // was der Auftrag TATSÄCHLICH hält). Hier stand vorher `order.quantity`, die *deklarierte*
  // Menge: nachdem ein Abzweig ein Stück übernommen hatte, hiess es «1 von 2», obwohl nur
  // noch eines da war. Der Rückfall gilt nur für Altbestand ohne die Angabe.
  const qty = insp?.inspected_quantity
    ?? order.quantity ?? (order.order_lines ?? []).reduce((s, l) => s + l.quantity, 0);
  // **Mehrere Proben aus EINER Instanz** – der Chargen-Fall. Abgeleitet aus den Proben
  // selbst (trägt eine Instanz mehr als einen Slot?), nicht aus der Serialisierung des
  // Artikels: die Proben sind die Tatsache, der Artikeltyp nur ihre übliche Ursache. So
  // stimmt die Beschriftung auch dann, wenn ein Auftrag mehrere Chargen prüft.
  const multiSample = samples.some((s) => s.slot > 1);
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
        label: `Instanz ${formatObjectId(nextInstance)}`,
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
    // **Minimal** (Testnotiz #613): die Objektnummer ist die Aussage; «Instanz»/«Charge»
    // steht bereits am Datensatz, und die Proben-Nummer nur, wenn es mehrere gibt.
    return multiSample ? `${formatObjectId(instanceId)} · ${slot}` : formatObjectId(instanceId);
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

  // **Ein künftiger Schritt zeigt seine Planung** (Testnotiz #487) – Prüfumfang und
  // Stichproben stehen schon fest; nur ausführen lässt er sich noch nicht.
  // **Nur der Schritt, der DRAN ist, lässt sich bedienen** (Testnotiz #542). Ansehen darf
  // man jeden (#471) – aber ein Schritt, der noch nicht an der Reihe ist oder gerade ruht,
  // bietet keine Eingabe an: das Backend lehnt sie ohnehin mit 409 ab, und ein Knopf, der
  // nicht tut, was er verspricht, ist schlimmer als keiner.
  const planned = stepState !== 'active';

  return (
    <div style={cardStyle}>

      {/* **Sagen, was zu TUN ist** (Testnotiz #614): «Prüfumfang: 1 von 1 Stück (100 %
          Stichprobe)» beschreibt eine Einstellung – hier steht die Aufgabe. Woher die Zahl
          kommt (der eingestellte Prozentsatz), ist die Herkunft und gehört in den Hover. */}
      <div style={{ fontSize: 13, color: 'var(--fg-2)' }}
        data-tip={escalated ? 'Eine Stichprobe war ungenügend – hochgestuft auf 100 %'
                            : `Eingestellter Prüfumfang: ${pct} %`}>
        <b>{required}</b> von {qty} Stück prüfen
        {multiSample && <span style={{ color: 'var(--fg-4)' }}> · Proben aus der Charge</span>}
        {escalated && <span style={{ color: 'var(--warning)' }}> · hochgestuft</span>}
      </div>

      {escalated && !done && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', borderRadius: 8, background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', fontSize: 12 }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Eine Stichprobe war ungenügend – die Prüfung wurde auf <b>100 %</b> hochgestuft. Bitte alle aufgeführten Instanzen erfassen.</span>
        </div>
      )}

      {/* **Das Ergebnis steht in der Liste darunter** (Testnotiz #472) – jede Probe trägt ihre
          Farbe. Ein Banner, das dasselbe noch einmal behauptet, ist eine zweite Erzählung.
          Was die Liste NICHT sagen kann, bleibt: dass ein Folgeauftrag den Befund geklärt hat. */}
      {done && resolvedBy != null && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--fg-3)' }}
          title="Der Folgeauftrag hat den Befund geklärt – damit ist dieser Schritt erledigt.">
          <RotateCcw size={13} /> Geklärt durch <ObjId value={resolvedBy} />
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
        <ScrollFade max={300}>
          {/* Nur freigeschaltete (gescannte) Instanzen erfassen – eine nach der anderen */}
          {samples.filter((s) => done || unlocked.includes(s.instance_id)).map((s) => {
            const key = sKey(s.instance_id, s.slot);
            const ok = sampleOk(key);
            return (
              <div key={key} style={{ border: `1px solid ${done ? (ok ? 'var(--success)' : 'var(--danger)') : 'var(--border-1)'}`, borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                <span style={{ fontSize: 12.5, fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--fg-3)' }}>
                  {sampleLabel(s.instance_id, s.slot)}
                </span>
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

          {/* Nächste Instanz scannen (Instanz-für-Instanz-Erfassung) – dieselbe ruhige
              Hauptaktion wie in Bewegung und Aussondern (Notizen #125/#330): schwarz, volle
              Breite, ≥44 px. Vorher blaue Schrift auf gestricheltem Slate-Rahmen, also die
              einzige Stelle im Fenster in der alten Palette. */}
          {!done && !planned && nextInstance != null && (
            <PrimaryButton icon={ScanLine} onClick={scanNext}>
              {unlocked.length === 0 ? 'Erste Instanz scannen' : 'Nächste Instanz scannen'} ({unlocked.length}/{distinctInstances.length})
            </PrimaryButton>
          )}
        </ScrollFade>
      )}

      {/* **Wer erfasst hat, gehört zum Ergebnis** (Testnotiz #472) – das Banner darüber ist
          entfallen, die Angabe nicht. */}
      {done && insp?.inspector_name && (
        <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>
          Erfasst von {insp.inspector_name}
          {insp.checked_count != null && ` · ${insp.checked_count} geprüft`}
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

      {/* Abschluss erst, wenn alle Instanzen gescannt & erfasst sind (inkl. Bild-/Unterschrift-Felder) */}
      {!done && !planned && allUnlocked && (
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
          ok ? <CheckCircle2 size={15} style={{ color: 'var(--success)' }} /> : <XCircle size={15} style={{ color: 'var(--danger)' }} />
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
