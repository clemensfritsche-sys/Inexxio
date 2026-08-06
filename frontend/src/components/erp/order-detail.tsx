'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Boxes, ClipboardList, History, Plus, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, UnitOption } from '@/types';
import { TYPE_META } from '@/lib/erp-record';
import { orderName } from '@/lib/record-name';
import { orderStatus } from '@/lib/record-status';
import { formatObjectId, localDateTime } from '@/lib/utils';
import { DetailHeader, HeaderAction, Card, inputCls } from '@/components/erp/fields';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { ProcessDiagram, type DiagramStep } from '@/components/erp/process-diagram';
import {
  END_BEFORE, START_AFTER, STATUS_VALUES, statusCfg, statusLabel,
} from '@/lib/process-status';

// Genau EIN Reiter. Er steht hier oben, weil es dabei bleibt: der Auftrag bekommt
// keine weiteren – auch keine leeren oder deaktivierten.
const TABS = [{ key: 'auftrag' as const, label: 'Auftrag', icon: ClipboardList }];

const TESTMODUL = 'testmodul';

/** Ein Modul im Entwurf. Die `id` ist eine lokale Nummer – der Auftrag existiert ja noch nicht. */
interface DraftStep extends DiagramStep {}

/**
 * Auftrag – Detailfenster.
 *
 * **Der Entwurf lebt nur hier.** `record === null` heisst: in der Datenbank steht nichts,
 * keine Entwurfs-Zeile, keine vorreservierte Objektnummer, kein Autosave. Wer das Fenster
 * verlässt, lässt keine Spur.
 *
 * **Anlegen ist Freigeben.** Es gibt keinen «Speichern»-Zwischenschritt: der Klick auf
 * «Freigeben» legt den Auftrag an, vergibt die Objektnummer, prüft die Exklusivität,
 * schickt die Stücke durch das Start-Objekt und loggt – alles in einer Transaktion
 * (PROCESS_CORE.md §6.3). Danach ist die Struktur eingefroren.
 *
 * Ob freigegeben werden darf, entscheidet der Server (`POST /erp/orders/validate` →
 * `services/orders.validate_draft`). Die Oberfläche formuliert die Regel nicht nach,
 * sie fragt sie ab: sonst gäbe es zwei Massstäbe für dieselbe Frage.
 */
export function OrderDetail({ record, onSaved, onBack }: {
  record: Order | null;              // null ⇒ Entwurf (existiert nur im Browser)
  onSaved: (o: Order) => void;
  onBack?: () => void;
}) {
  const isDraft = record === null;
  const meta = TYPE_META.order;

  const [units, setUnits] = useState<string[]>([]);
  const [steps, setSteps] = useState<DraftStep[]>([]);
  const [missing, setMissing] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<Order | null>(record);

  useEffect(() => { setLive(record); }, [record]);

  const draft = useMemo(() => ({
    unit_numbers: units,
    steps: steps.map((s) => ({
      module_type: s.moduleType, name: s.name,
      status_before: s.statusBefore, status_after: s.statusAfter,
    })),
  }), [units, steps]);

  // Freigebbarkeit beim Server erfragen, nicht selbst behaupten.
  useEffect(() => {
    if (!isDraft) { setMissing(null); return; }
    let dead = false;
    api.validateOrder(draft)
      .then((v) => { if (!dead) setMissing(v.missing ?? []); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [isDraft, draft]);

  async function release() {
    setBusy(true); setError(null);
    try {
      onSaved(await api.createOrder(draft));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const confirmStep = useCallback(async (stepId: number) => {
    if (!live) return;
    setBusy(true); setError(null);
    try {
      setLive(await api.confirmStep(live.object_id, stepId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [live]);

  const blocked = missing != null && missing.length > 0;
  const shown = live ?? record;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        icon={meta.icon}
        iconBg={meta.bg}
        iconFg={meta.fg}
        eyebrow={meta.label}
        title={orderName()}
        objectId={shown?.object_id ?? null}
        objectIdText={isDraft ? '—' : undefined}
        objectIdHint={isDraft
          ? 'Die Objektnummer entsteht erst mit der Freigabe. Bis dahin existiert dieser Auftrag nur in diesem Fenster.'
          : undefined}
        status={shown ? orderStatus(shown) : undefined}
        actions={isDraft ? (
          <HeaderAction
            label="Freigeben"
            // Kein stummes Nichts-Passiert: der Knopf sagt, was noch fehlt.
            hint={blocked ? `Es fehlt: ${missing!.join(' und ')}` : 'Legt den Auftrag an und startet den Prozess'}
            disabled={busy || blocked || missing == null}
            onClick={release}
          />
        ) : undefined}
        onBack={onBack}
        tabs={<DetailTabs tabs={TABS} active="auftrag" onChange={() => {}} />}
      />

      <div className="flex-1 p-5" style={{ background: 'var(--bg-2)' }}>
        {error && (
          <p className="mb-3 text-sm max-w-[880px] mx-auto px-3 py-2 rounded-ds-lg"
            style={{ color: 'var(--danger)', background: 'var(--danger-bg)' }}>
            {error}
          </p>
        )}

        <div className="mx-auto" style={{ maxWidth: 620 }}>
          {isDraft ? (
            <DraftView
              units={units} setUnits={setUnits}
              steps={steps} setSteps={setSteps}
            />
          ) : (
            <RunView order={shown!} busy={busy} onConfirm={confirmStep} />
          )}
        </div>

        {!isDraft && shown && <EventLog order={shown} />}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Entwurf — Modus «definition»
// ─────────────────────────────────────────────────────────────────────────────

function DraftView({ units, setUnits, steps, setSteps }: {
  units: string[]; setUnits: (u: string[]) => void;
  steps: DraftStep[]; setSteps: (s: DraftStep[]) => void;
}) {
  const [options, setOptions] = useState<UnitOption[] | null>(null);
  useEffect(() => {
    api.getUnitOptions().then(setOptions).catch(() => setOptions([]));
  }, []);

  return (
    <>
      <ProcessDiagram
        mode="definition"
        steps={steps}
        endStatus={END_BEFORE}
        head={<DefinitionCard units={units} setUnits={setUnits} options={options} />}
        onDelete={(id) => setSteps(steps.filter((s) => s.id !== id))}
      />
      <div className="mt-3">
        <AddStep
          onAdd={(name, before, after) =>
            setSteps([...steps, {
              id: (steps[steps.length - 1]?.id ?? 0) + 1,
              name, moduleType: TESTMODUL, statusBefore: before, statusAfter: after,
            }])}
          suggestedBefore={steps.length ? steps[steps.length - 1].statusAfter : START_AFTER}
        />
      </div>
    </>
  );
}

/** Die Definition: mit welchen Einzelinstanzen arbeitet dieser Auftrag (§2.1). */
function DefinitionCard({ units, setUnits, options }: {
  units: string[]; setUnits: (u: string[]) => void; options: UnitOption[] | null;
}) {
  const [open, setOpen] = useState(false);
  const chosen = new Set(units);
  return (
    <div className="rounded-ds-lg" style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 14 }}>
      <div className="flex items-center gap-2 mb-2">
        <Boxes size={14} style={{ color: 'var(--fg-3)' }} />
        <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
          Definition
        </span>
      </div>
      <p className="text-xs mb-3" style={{ color: 'var(--fg-3)' }}>
        Mit welchen Einzelinstanzen arbeitet dieser Auftrag? Ohne Definition kein Start.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {units.map((n) => (
          <span key={n} className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
            {n}
            <button type="button" onClick={() => setUnits(units.filter((u) => u !== n))}
              style={{ opacity: 0.6 }} aria-label={`${n} entfernen`}>
              <X size={11} />
            </button>
          </span>
        ))}
        <button type="button" onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
          style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}>
          <Plus size={12} /> Einzelinstanz
        </button>
      </div>

      {open && (
        <div className="mt-3 max-h-64 overflow-auto" style={{ borderTop: '1px solid var(--border-1)' }}>
          {options === null && <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>Lädt …</p>}
          {options?.length === 0 && (
            <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>
              Es gibt keine Einzelinstanzen. Lege zuerst eine Instanz an.
            </p>
          )}
          {options?.map((o) => {
            const taken = chosen.has(o.number);
            // Gesperrte Zeilen werden gezeigt, nicht weggefiltert – mit Grund.
            const why = o.blocked_by
              ? `Aktiv in Auftrag ${formatObjectId(o.blocked_by)}`
              : !o.available ? `Steht auf «${statusLabel(o.status)}»` : undefined;
            return (
              <button
                key={o.number}
                type="button"
                disabled={!o.available || taken}
                onClick={() => setUnits([...units, o.number])}
                data-tip={why}
                className="w-full flex items-center gap-2 text-left text-xs py-1.5 px-1 disabled:opacity-45"
                style={{ borderBottom: '1px solid var(--border-1)' }}
              >
                <span className="ix-tnum" style={{ minWidth: 110 }}>{o.number}</span>
                <span className="flex-1 truncate" style={{ color: 'var(--fg-3)' }}>{o.article_name}</span>
                <span style={{ color: statusCfg(o.status).color }}>{why ?? statusLabel(o.status)}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Ein Modul anlegen. Vorher- und Nachher-Status sind **Pflicht** – ohne sie ist das Modul
 * nicht anlegbar (§4). Die Werte kommen aus der geschlossenen Liste; erfinden geht nicht.
 *
 * Bewusst ein «Hinzufügen»-Knopf statt Auto-Save: ein halb konfiguriertes Modul wäre
 * genau das, was die Pflichtangabe verhindern soll.
 */
function AddStep({ onAdd, suggestedBefore }: {
  onAdd: (name: string, before: string, after: string) => void;
  suggestedBefore: string;
}) {
  const [name, setName] = useState('');
  const [before, setBefore] = useState(suggestedBefore);
  const [after, setAfter] = useState(END_BEFORE);
  useEffect(() => { setBefore(suggestedBefore); }, [suggestedBefore]);

  const ready = name.trim().length > 0;
  return (
    <Card icon={Plus} title="Testmodul hinzufügen">
      <p className="text-xs mb-2.5" style={{ color: 'var(--fg-3)' }}>
        Platzhalter-Modul: es prüft den Vorher-Status, setzt den Nachher-Status und rückt
        die Stücke vor. Keine Felder, keine Fachlogik.
      </p>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="flex-1 min-w-[160px]">
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Name</span>
          <input className={inputCls} value={name} maxLength={120}
            onChange={(e) => setName(e.target.value)} placeholder="z. B. Zuschnitt" />
        </label>
        <StatusPick label="Vorher" value={before} onChange={setBefore} />
        <StatusPick label="Nachher" value={after} onChange={setAfter} />
        <button
          type="button"
          className="erp-actbtn erp-actbtn-primary"
          style={{ height: 32, padding: '0 14px' }}
          disabled={!ready}
          data-tip={ready ? undefined : 'Ein Modul braucht einen Namen.'}
          onClick={() => { onAdd(name.trim(), before, after); setName(''); }}
        >
          Hinzufügen
        </button>
      </div>
    </Card>
  );
}

function StatusPick({ label, value, onChange }: {
  label: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <label>
      <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>{label}</span>
      <select className={inputCls} style={{ width: 150 }} value={value}
        onChange={(e) => onChange(e.target.value)}>
        {STATUS_VALUES.map((s) => (
          <option key={s} value={s}>{statusLabel(s)}</option>
        ))}
      </select>
    </label>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Freigegeben — Modus «ausfuehrung»
// ─────────────────────────────────────────────────────────────────────────────

function RunView({ order, busy, onConfirm }: {
  order: Order; busy: boolean; onConfirm: (stepId: number) => void;
}) {
  const steps: DiagramStep[] = (order.steps ?? []).map((s) => ({
    id: s.id, name: s.name, moduleType: s.module_type,
    statusBefore: s.status_before, statusAfter: s.status_after,
  }));
  const units = (order.units ?? []).map((u) => ({
    number: u.number, status: u.status,
    currentStepId: u.current_step_id ?? null, active: u.active,
  }));

  return (
    <ProcessDiagram
      mode="ausfuehrung"
      steps={steps}
      units={units}
      activeStepId={order.active_step_id ?? null}
      endStatus={order.end_status}
      renderStep={(step, isActive) => (isActive ? (
        <button
          type="button"
          className="erp-actbtn erp-actbtn-primary w-full"
          style={{ height: 38 }}
          disabled={busy}
          onClick={() => onConfirm(step.id)}
        >
          Schritt bestätigen
        </button>
      ) : null)}
    />
  );
}

/**
 * Die Historie. **Append-only** – es gibt keinen Bearbeiten- und keinen Löschen-Knopf,
 * weil es dafür keinen Endpunkt gibt (§7.2). Eine Korrektur wäre ein neuer Eintrag.
 */
function EventLog({ order }: { order: Order }) {
  const events = order.events ?? [];
  if (!events.length) return null;
  const KIND: Record<string, string> = { start: 'Start', step: 'Modul', end: 'Ende' };
  const names = new Map((order.steps ?? []).map((s) => [s.id, s.name]));
  return (
    <div className="mx-auto mt-5" style={{ maxWidth: 620 }}>
      <Card icon={History} title="Historie">
        <p className="text-xs mb-2.5" style={{ color: 'var(--fg-3)' }}>
          Eingefroren. Was hier steht, wird nicht mehr geändert – eine Korrektur wäre ein
          neuer Eintrag.
        </p>
        <div className="flex flex-col">
          {events.map((e) => (
            <div key={e.id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs py-1.5"
              style={{ borderTop: '1px solid var(--border-1)' }}>
              <span className="ix-tnum" style={{ minWidth: 104 }}>{e.unit_number}</span>
              <span style={{ color: 'var(--fg-3)', minWidth: 92 }}>
                {e.step_id ? names.get(e.step_id) ?? KIND[e.kind] : KIND[e.kind]}
              </span>
              <span style={{ color: statusCfg(e.status_before).color }}>{statusLabel(e.status_before)}</span>
              <span style={{ color: 'var(--fg-4)' }}>→</span>
              <span style={{ color: statusCfg(e.status_after).color }}>{statusLabel(e.status_after)}</span>
              <span className="flex-1" />
              <span style={{ color: 'var(--fg-4)' }}>
                {e.actor ? `${e.actor} · ` : ''}{localDateTime(e.created_at)}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
