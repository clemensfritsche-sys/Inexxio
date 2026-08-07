'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ClipboardList, History } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleOption, ArticleProcess, CapturePoint, Order } from '@/types';
import { TYPE_META } from '@/lib/erp-record';
import { orderName } from '@/lib/record-name';
import { orderStatus } from '@/lib/record-status';
import { localDateTime } from '@/lib/utils';
import { DetailHeader, HeaderAction, Card } from '@/components/erp/fields';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { ProcessDiagram, type DiagramStep } from '@/components/erp/process-diagram';
import {
  DefinitionLines, LAGER, NEU, emptyLine, toPayload, type DefinitionLine,
} from '@/components/erp/definition-lines';
import { END_BEFORE, statusCfg, statusLabel } from '@/lib/process-status';
import { AddModule } from '@/components/erp/module-editor';
import { CaptureForm } from '@/components/erp/capture-form';
import { toModulePayload, type ModuleDraft } from '@/lib/modules';

// Genau EIN Reiter. Er steht hier oben, weil es dabei bleibt: der Auftrag bekommt
// keine weiteren – auch keine leeren oder deaktivierten.
const TABS = [{ key: 'auftrag' as const, label: 'Auftrag', icon: ClipboardList }];

/**
 * Auftrag – Detailfenster.
 *
 * **Der Entwurf lebt nur hier.** `record === null` heisst: in der Datenbank steht nichts,
 * keine Entwurfs-Zeile, keine vorreservierte Objektnummer, kein Autosave. Wer das Fenster
 * verlässt, lässt keine Spur.
 *
 * **Anlegen ist Freigeben.** Es gibt keinen «Speichern»-Zwischenschritt: der Klick auf
 * «Freigeben» legt den Auftrag an, vergibt die Objektnummer, prüft die Exklusivität,
 * **erzeugt die neuen Einzelinstanzen**, schickt die Stücke durch das Start-Objekt und
 * loggt – alles in einer Transaktion (PROCESS_CORE.md §6.3). Danach ist die Struktur
 * eingefroren.
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

  const [lines, setLines] = useState<DefinitionLine[]>([emptyLine(1)]);
  const [steps, setSteps] = useState<ModuleDraft[]>([]);
  const [missing, setMissing] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<Order | null>(record);

  useEffect(() => { setLive(record); }, [record]);

  const draft = useMemo(() => ({
    lines: toPayload(lines),
    steps: steps.map(toModulePayload),
  }), [lines, steps]);

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

  const confirmStep = useCallback(async (stepId: number, values: Record<string, unknown>) => {
    if (!live) return;
    setBusy(true); setError(null);
    try {
      setLive(await api.confirmStep(live.object_id, stepId, values));
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
            hint={blocked ? `Es fehlt: ${missing!.join(' · ')}` : 'Legt den Auftrag an und startet den Prozess'}
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
            <DraftView lines={lines} setLines={setLines} steps={steps} setSteps={setSteps} />
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

/**
 * **Der Prozess folgt aus der Herkunft.**
 *
 * Sobald eine Zeile «Neu» trägt, ist der Prozess die **Vorlage des Artikels** – als
 * Kopie, mit Versionsstempel, und hier nur zu sehen, nicht zu ändern. Sie zu bearbeiten
 * hiesse, einen Stempel auf etwas zu setzen, das danach nicht mehr die Vorlage ist.
 * Ändern geht am Artikel, im Reiter «Erzeugungsprozess».
 *
 * Ein reiner «Lager»-Auftrag greift auf Vorhandenes zu – was damit geschehen soll, weiss
 * nur dieser eine Auftrag. Dort wird frei modelliert.
 */
function DraftView({ lines, setLines, steps, setSteps }: {
  lines: DefinitionLine[]; setLines: (l: DefinitionLine[]) => void;
  steps: ModuleDraft[]; setSteps: (s: ModuleDraft[]) => void;
}) {
  const [articles, setArticles] = useState<ArticleOption[]>([]);
  const [template, setTemplate] = useState<ArticleProcess | null>(null);

  // Welcher Artikel bringt den Prozess mit? Der erste mit Herkunft «Neu».
  const sourceArticle = useMemo(
    () => lines.find((l) => l.origin === NEU && l.articleObjectId !== null)?.articleObjectId ?? null,
    [lines],
  );

  useEffect(() => {
    if (sourceArticle === null) { setTemplate(null); return; }
    let dead = false;
    api.getArticleProcess(sourceArticle)
      .then((p) => { if (!dead) setTemplate(p); })
      .catch(() => { if (!dead) setTemplate(null); });
    return () => { dead = true; };
  }, [sourceArticle]);

  const mirrored: DiagramStep[] | null = useMemo(() => {
    if (!template) return null;
    return (template.steps ?? []).map((s) => ({
      id: s.id, name: s.name, moduleType: s.module_type,
    }));
  }, [template]);

  const isMake = sourceArticle !== null;
  const own: DiagramStep[] = steps.map((m) => ({ id: m.id, name: m.name, moduleType: m.moduleType }));
  const shownSteps = mirrored ?? own;
  const articleName = articles.find((a) => a.object_id === sourceArticle)?.name;

  return (
    <>
      <ProcessDiagram
        mode="definition"
        steps={shownSteps}
        endStatus={END_BEFORE}
        head={
          <DefinitionLines lines={lines} setLines={setLines} onArticlesLoaded={setArticles} />
        }
        onDelete={isMake ? undefined : (id) => setSteps(steps.filter((s) => s.id !== id))}
      />

      {isMake ? (
        <p className="mt-3 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
          {mirrored?.length
            ? <>Erzeugungsprozess von <strong>{articleName}</strong> (Stand {template?.version}).
              Er wird bei der Freigabe als Kopie übernommen – geändert wird er am Artikel.</>
            : 'Lädt den Erzeugungsprozess …'}
        </p>
      ) : (
        <div className="mt-3">
          <AddModule
            onAdd={(m) => setSteps([...steps, { ...m, id: (steps[steps.length - 1]?.id ?? 0) + 1 }])}
          />
        </div>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Freigegeben — Modus «ausfuehrung»
// ─────────────────────────────────────────────────────────────────────────────

function RunView({ order, busy, onConfirm }: {
  order: Order; busy: boolean;
  onConfirm: (stepId: number, values: Record<string, unknown>) => void;
}) {
  const steps: DiagramStep[] = (order.steps ?? []).map((s) => ({
    id: s.id, name: s.name, moduleType: s.module_type,
  }));
  const groups = (order.unit_groups ?? []).map((g) => ({
    currentStepId: g.current_step_id ?? null, status: g.status,
    active: g.active, count: g.count,
  }));

  // Die einzelnen Nummern kommen erst beim Aufklappen – bei 5000 Stück ist das der
  // Unterschied zwischen einer Antwort und einem Megabyte.
  const expand = useCallback(async (stepId: number | null, active: boolean) => {
    const page = await api.getOrderUnits(order.object_id, stepId, active, 100, 0);
    return (page.units ?? []).map((u) => u.number);
  }, [order.object_id]);

  return (
    <>
      <DefinitionSummary order={order} />
      <ProcessDiagram
        mode="ausfuehrung"
        steps={steps}
        groups={groups}
        activeStepId={order.active_step_id ?? null}
        endStatus={order.end_status}
        onExpand={expand}
        renderStep={(step, isActive) => (isActive ? (
          // Was das aktive Modul verlangt, steht in seiner Definition – die Karte des
          // Schritts ist der Ort, an dem es ausgefüllt wird.
          <CaptureForm
            points={pointsOf(order, step.id)}
            count={waitingAt(order, step.id)}
            busy={busy}
            onConfirm={(values) => onConfirm(step.id, values)}
          />
        ) : null)}
      />
    </>
  );
}

/** Die Erfassungspunkte eines Moduls – aus seiner eingefrorenen Definition. */
function pointsOf(order: Order, stepId: number): CapturePoint[] {
  const step = (order.steps ?? []).find((s) => s.id === stepId);
  const cfg = step?.config as { points?: CapturePoint[] } | null | undefined;
  return cfg?.points ?? [];
}

/** Wie viele Stücke stehen gerade davor – die Erfassung gilt für sie alle. */
function waitingAt(order: Order, stepId: number): number {
  return (order.unit_groups ?? [])
    .filter((g) => g.active && g.current_step_id === stepId)
    .reduce((n, g) => n + g.count, 0);
}

/** Was dieser Auftrag bearbeitet – festgeschrieben bei der Freigabe. */
function DefinitionSummary({ order }: { order: Order }) {
  const lines = order.lines ?? [];
  if (!lines.length) return null;
  return (
    <div className="rounded-ds-lg mb-3" style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 12 }}>
      {lines.map((ln) => (
        <div key={ln.id} className="flex flex-wrap items-center gap-x-2 text-xs py-0.5">
          <span className="ix-tnum" style={{ minWidth: 34 }}>{ln.quantity}×</span>
          <span className="flex-1 truncate">{ln.article_name}</span>
          <span style={{ color: 'var(--fg-3)' }}>
            {ln.origin === NEU ? 'neu erzeugt' : 'ab Lager'}
          </span>
        </div>
      ))}
    </div>
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
  const total = order.event_count ?? events.length;
  return (
    <div className="mx-auto mt-5" style={{ maxWidth: 620 }}>
      <Card icon={History} title="Historie">
        <p className="text-xs mb-2.5" style={{ color: 'var(--fg-3)' }}>
          Eingefroren. Was hier steht, wird nicht mehr geändert – eine Korrektur wäre ein
          neuer Eintrag.
          {total > events.length && (
            // Gekappt, aber nicht verschwiegen: eine stumme Liste sähe aus wie alles.
            <> Gezeigt sind die letzten {events.length} von {total} Einträgen.</>
          )}
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
