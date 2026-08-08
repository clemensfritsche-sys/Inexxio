'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ClipboardList, History } from 'lucide-react';
import { api, type ApiError } from '@/lib/api';
import type { ArticleOption, ArticleProcess, CapturePoint, Order, OrderSummary } from '@/types';
import { orderStatus } from '@/lib/record-status';
import { localDateTime } from '@/lib/utils';
import { DetailHeader, HeaderAction, Card } from '@/components/erp/fields';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { ProcessDiagram, PROCESS_MAXW, type DiagramStep } from '@/components/erp/process-diagram';
import { ProcessColumns } from '@/components/erp/process-columns';
import { ProcessDesigner } from '@/components/erp/process-designer';
import {
  DefinitionLines, LAGER, NEU, emptyLine, toPayload, type DefinitionLine,
} from '@/components/erp/definition-lines';
import { END_BEFORE, statusCfg, statusLabel } from '@/lib/process-status';
import { CaptureForm } from '@/components/erp/capture-form';
import { UnitNumber } from '@/components/erp/unit-number';
import { CAPTURE_ICON, toModulePayload, type ModuleDraft } from '@/lib/modules';

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
/**
 * **Ein Entwurf mit bereits gewählter Einzelinstanz** (Abweichungsauftrag §3.1).
 *
 * Mehr ist eine «Abweichung» nicht: derselbe Entwurf, derselbe Editor, dieselbe Freigabe –
 * das Stück steht nur schon drin. Ob daraus eine Abweichung wird, entscheidet sich beim
 * Freigeben und ergibt sich aus dem Zustand des Stücks, nicht aus diesem Seed.
 */
export interface OrderSeed {
  articleObjectId: number;
  /**
   * **Nur beim Auslöser am Stück** (§3.1). Der Shortcut am Artikel (#690) merkt bewusst
   * nur den Artikel vor: wie viel, woher und mit welchem Ablauf ist die Entscheidung,
   * und die trifft der Mensch. Ein reiner Shortcut, kein zweiter Anlagepfad.
   */
  unitNumber?: string;
  /**
   * In welchem Auftrag das Stück lief, als der Shortcut es griff. Das ist keine
   * Zusatzinfo, sondern die **Absicht**: «ich hole es aus diesem Auftrag». Der Server
   * prüft sie bei der Freigabe – wechselt das Stück vorher den Auftrag, bricht sie ab,
   * statt still etwas anderes zu tun (`UnitPick.from_order`).
   */
  fromOrder?: number | null;
}

export function OrderDetail({ record, seed, onSaved, onDeviate, onBack }: {
  /** ``null`` ⇒ Entwurf (existiert nur im Browser). Sonst genügt die **Feed-Zeile** –
   *  das Detail lädt sich selbst nach (siehe unten). */
  record: OrderSummary | Order | null;
  /** Nur beim Entwurf: eine vorgewählte Einzelinstanz. */
  seed?: OrderSeed | null;
  onSaved: (o: Order) => void;
  /** Ein Stück im Prozess soll eine Abweichung bekommen – die Seite öffnet den Entwurf. */
  onDeviate?: (seed: OrderSeed) => void;
  onBack?: () => void;
}) {
  const isDraft = record === null;

  const [lines, setLines] = useState<DefinitionLine[]>(() => {
    if (!seed) return [emptyLine(1)];
    // Mit Stück: es steht schon in der Definition, Herkunft «Lager» folgt daraus.
    // Ohne Stück (Artikel-Shortcut): nur der Artikel – Menge und Herkunft bleiben offen.
    return seed.unitNumber
      ? [{ key: 1, articleObjectId: seed.articleObjectId, quantity: 1, origin: LAGER,
           units: [{ number: seed.unitNumber, fromOrder: seed.fromOrder ?? null }],
           returns: true }]
      : [{ ...emptyLine(1), articleObjectId: seed.articleObjectId }];
  });
  const [steps, setSteps] = useState<ModuleDraft[]>([]);
  const [missing, setMissing] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<Order | null>(null);
  // Zählt hoch, wenn die Freigabe an einer veralteten Auswahl scheitert – der Picker holt
  // die Stückliste dann neu und zeigt, wo die Stücke jetzt liegen.
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(false);

  /**
   * **Das Detail lädt seinen Auftrag selbst.**
   *
   * Der Feed liefert bewusst nur eine Zusammenfassung (`OrderSummary`) – ohne Schritte,
   * Stücke und Historie; bei 5000 Stück ist das der Unterschied zwischen einer Liste und
   * einem Megabyte. Wer die Feed-Zeile als Detail rendert, zeigt darum einen laufenden
   * Prozess als leer: kein Modul, keine Einzelinstanzen, «nicht gestartet». Genau das
   * war zu sehen – die Erzeugung lief pünktlich, die Ansicht wusste nur nichts davon.
   *
   * Die Zeile aus dem Feed dient nur noch als Adresse (`object_id`).
   */
  const objectId = record?.object_id ?? null;
  useEffect(() => {
    if (objectId == null) { setLive(null); return; }
    let dead = false;
    setLoading(true);
    api.getOrder(objectId)
      .then((o) => { if (!dead) setLive(o); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [objectId]);

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
      // **Ein veralteter Pick ist kein blosser Fehler, sondern eine neue Lage.** Der
      // Server nennt sie mit einem Code (nicht mit einem Satz, den jemand umformulieren
      // könnte); die Auswahl wird daraufhin gegen die Wirklichkeit nachgezogen.
      const detail = (e as ApiError)?.detail as { code?: string } | undefined;
      if (detail?.code === 'pick_stale') setRefreshKey((n) => n + 1);
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
  const shown = live;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        type="order"
        // **Die Abweichung ist ein Zeichen am Symbol** (#699) – dieselbe Komponente wie
        // im Feed. Zwei Implementierungen driften garantiert auseinander (#688).
        deviation={shown?.is_deviation ?? false}
        title={shown?.name ?? null}
        placeholder="Neuer Auftrag"
        objectId={shown?.object_id ?? record?.object_id ?? null}
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

        {/* **Kein Mass von hier.** Jedes Prozessbild bringt seines mit (#684) – der
            Entwurf ist eine Spalte, der laufende Auftrag sind bis zu drei. Eine Zahl an
            dieser Stelle wäre der zweite Stand, aus dem der gemeldete Breitenunterschied
            entstanden ist. */}
        {isDraft ? (
          <DraftView lines={lines} setLines={setLines} steps={steps} setSteps={setSteps}
            refreshKey={refreshKey} />
        ) : shown ? (
          <RunView order={shown} busy={busy} onConfirm={confirmStep} onDeviate={onDeviate} />
        ) : (
          <p className="text-sm text-center" style={{ color: 'var(--fg-4)' }}>
            {loading ? 'Lädt …' : null}
          </p>
        )}

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
 * Ändern geht am Artikel, unter «Spezifikation».
 *
 * Ein reiner «Lager»-Auftrag greift auf Vorhandenes zu – was damit geschehen soll, weiss
 * nur dieser eine Auftrag. Dort wird frei modelliert.
 */
function DraftView({ lines, setLines, steps, setSteps, refreshKey }: {
  lines: DefinitionLine[]; setLines: (l: DefinitionLine[]) => void;
  steps: ModuleDraft[]; setSteps: (s: ModuleDraft[]) => void;
  /** Hochgezählt, wenn die Freigabe an einer veralteten Auswahl scheitert. */
  refreshKey: number;
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
      id: s.id, moduleType: s.module_type, label: s.label,
    }));
  }, [template]);

  const isMake = sourceArticle !== null;
  const articleName = articles.find((a) => a.object_id === sourceArticle)?.name;

  // Bringt eine Zeile «Neu» mit, ist der Prozess die **Vorlage des Artikels** – dann nur
  // ansehen. Sonst wird hier modelliert, mit demselben Editor wie am Artikel.
  return (
    <>
      {isMake ? (
        <ProcessDiagram
          mode="definition"
          steps={mirrored ?? []}
          endStatus={END_BEFORE}
          head={<DefinitionLines lines={lines} setLines={setLines} refreshKey={refreshKey} onArticlesLoaded={setArticles} />}
        />
      ) : (
        <ProcessDesigner
          modules={steps}
          onChange={setSteps}
          head={<DefinitionLines lines={lines} setLines={setLines} refreshKey={refreshKey} onArticlesLoaded={setArticles} />}
        />
      )}

      {isMake ? (
        <p className="mt-3 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
          {mirrored?.length
            ? <>Erzeugungsprozess von <strong>{articleName}</strong> (Stand {template?.version}).
              Er wird bei der Freigabe als Kopie übernommen – geändert wird er am Artikel.</>
            : 'Lädt den Erzeugungsprozess …'}
        </p>
      ) : null}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Freigegeben — Modus «ausfuehrung»
// ─────────────────────────────────────────────────────────────────────────────

function RunView({ order, busy, onConfirm, onDeviate }: {
  order: Order; busy: boolean;
  onConfirm: (stepId: number, values: Record<string, unknown>) => void;
  onDeviate?: (seed: OrderSeed) => void;
}) {
  const steps: DiagramStep[] = (order.steps ?? []).map((s) => ({
    id: s.id, moduleType: s.module_type, label: s.label,
  }));
  const groups = (order.unit_groups ?? []).map((g) => ({
    currentStepId: g.current_step_id ?? null, status: g.status,
    active: g.active, count: g.count,
  }));

  // Die einzelnen Nummern kommen erst beim Aufklappen – bei 5000 Stück ist das der
  // Unterschied zwischen einer Antwort und einem Megabyte.
  /**
   * ►►► Die **restriktivere Variante** zur offenen Frage (Abweichungsauftrag §5) ◄◄◄
   *
   * Solange im aktiven Modul erfasst wird, lässt sich keine Abweichung auslösen. Der
   * Server kann das nicht prüfen: eine begonnene Erfassung ist nirgends gespeichert (sie
   * entsteht erst beim Bestätigen). Diese Sperre ist darum **hier** – und sie ist
   * bewusst die strengere von zwei möglichen Antworten, bis die Frage entschieden ist.
   * Die dauerhafte Regel gehört an den Modultyp (`domain/modules.units_may_leave`).
   */
  const [entryStarted, setEntryStarted] = useState(false);

  const expand = useCallback(async (stepId: number | null, active: boolean) => {
    const page = await api.getOrderUnits(order.object_id, stepId, active, 100, 0);
    return (page.units ?? []).map((u) => ({ number: u.number, startedAt: u.started_at }));
  }, [order.object_id]);

  return (
    <>
      <DefinitionSummary order={order} />
      <ProcessColumns
        order={order}
        onExpand={expand}
        onDeviate={onDeviate
          ? (unitNumber) => { void startDeviation(unitNumber, order.object_id, onDeviate); }
          : undefined}
        deviateBlocked={entryStarted
          ? 'Im aktiven Modul wurde bereits erfasst. Erst bestätigen – oder das Fenster neu laden, dann ist die Eingabe verworfen.'
          : undefined}
        journeyIn={order.journey_in ?? []}
        journeyOut={order.journey_out ?? []}
        // **Jedes Modul zeigt, was es tut** (Testnotiz #696) – das aktive als Formular,
        // die übrigen als das, was in ihnen definiert ist. Ob die Karte auf- oder
        // zugeklappt startet und ob sie gesperrt ist, entscheidet das Diagramm; hier
        // steht nur der Inhalt.
        renderStep={(step, isActive) => (isActive ? (
          <CaptureForm
            points={pointsOf(order, step.id)}
            count={waitingAt(order, step.id)}
            busy={busy}
            onDirty={setEntryStarted}
            onConfirm={(values) => onConfirm(step.id, values)}
          />
        ) : (
          <PointList points={pointsOf(order, step.id)} />
        ))}
      />
    </>
  );
}

/**
 * Was dieses Modul erfassen wird – seine eingefrorene Definition.
 *
 * Für ein Modul, das nicht an der Reihe ist: es soll zeigen, **was** es tut, ohne es tun
 * zu lassen. Die erfassten *Werte* eines erledigten Moduls stehen nicht hier, sondern in
 * der Historie – sie sind ein Ereignis, keine Eigenschaft des Moduls.
 */
function PointList({ points }: { points: CapturePoint[] }) {
  if (!points.length) return null;
  return (
    <div className="flex flex-col gap-1">
      {points.map((p) => {
        const Icon = CAPTURE_ICON[p.type] ?? CAPTURE_ICON.text;
        return (
          <div key={p.key} className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
            <Icon size={13} style={{ color: 'var(--fg-4)' }} />
            <span className="flex-1 min-w-0 truncate" style={{ color: 'var(--fg-2)' }}>{p.label}</span>
            {p.target != null && (
              <span className="ix-tnum">
                Soll {p.target}{p.tolerance ? ` ± ${p.tolerance}` : ''}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * **Wartet dieser Auftrag auf eine Rückführung?** Abgeleitet, nicht gespeichert – es
 * wartet, wer noch eine offene rückführende Verbindung hat. Steht hier nichts, wartet er
 * auf nichts; ein Platzhalter «wartet auf 0» wäre eine Zeile ohne Aussage.
 */

/**
 * **Welcher Artikel gehört zu diesem Stück?** Die Nummer sagt es zur Hälfte: ihr vorderer
 * Teil ist die Objektnummer der Instanz, und die Instanz kennt ihren Artikel. Gefragt wird
 * darum der bestehende Endpunkt – ein zweites Feld an der Stück-Antwort wäre eine Kopie,
 * die auseinanderlaufen kann.
 */
async function startDeviation(
  unitNumber: string, fromOrder: number, open: (seed: OrderSeed) => void,
) {
  const instanceId = Number(unitNumber.split('-')[0]);
  if (!Number.isInteger(instanceId)) return;
  const instance = await api.getInstance(instanceId);
  if (instance.article_object_id == null) return;
  // Woher das Stück kommt, weiss diese Stelle sicher: aus dem Auftrag, dessen Prozess
  // gerade offen ist. Genau das ist die Aussage, die der Server bei der Freigabe prüft.
  open({ articleObjectId: instance.article_object_id, unitNumber, fromOrder });
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
    <div className="rounded-ds-lg mb-3 mx-auto"
      style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)',
               padding: 12, maxWidth: PROCESS_MAXW }}>
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
  // **Referenziert wird die id, beschriftet der Typ** (#687): ein Name wäre eine
  // Eingabe, und die Historie darf nicht auf eine Eingabe zeigen.
  const labels = new Map((order.steps ?? []).map((s) => [s.id, s.label]));
  const total = order.event_count ?? events.length;
  return (
    <div className="mx-auto mt-5" style={{ maxWidth: PROCESS_MAXW }}>
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
              <span style={{ minWidth: 104 }}><UnitNumber value={e.unit_number} /></span>
              <span style={{ color: 'var(--fg-3)', minWidth: 92 }}>
                {e.step_id ? labels.get(e.step_id) ?? KIND[e.kind] : KIND[e.kind]}
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
