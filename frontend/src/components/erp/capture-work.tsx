'use client';

import { useState } from 'react';
import { AlertTriangle, Boxes, GitBranch, PackagePlus, ScanLine, Truck } from 'lucide-react';
import { absentOn404, api } from '@/lib/api';
import { tell } from '@/lib/notice';
import { useAction } from '@/lib/use-action';
import type { CapturePoint, PlaceRef, StepNeed, StepWork } from '@/types';
import { MOVE_MODULE } from '@/lib/modules';
import { formatObjectId } from '@/lib/utils';
import { ObjId } from '@/components/erp/obj-id';
import { useScan } from '@/components/scan/scan-provider';
import { CaptureForm } from '@/components/erp/capture-form';
import type { OrderSeed } from '@/components/erp/order-detail';

/**
 * **Die Arbeit an einem aktiven Modul — eine Zeile je Instanz.**
 *
 * Ein Vorgang ist eine Instanz: das Etikett klebt an ihr (eine Einzelinstanz hat keine
 * Objektnummer). Eine Charge ist ein Scan, Einzelserialisierung sind n Scans.
 *
 * Drei Ebenen, an der Schriftgrösse ablesbar: 1. die Handlung (Nummer und Scan), 2. der
 * Auftrag an diese Instanz (nach dem Scan das Formular), 3. der Halt – nur wenn es ihn gibt.
 * Zeilen trennt eine Haarlinie, kein Rahmen.
 *
 * Ohne Bestätigung keine Eingabe (Scan oder Tastatur, beides geloggt; serverseitig in
 * `process.confirm_step`). Nicht bestanden ⇒ Stillstand, bis ein Mensch entscheidet; das
 * System legt nichts an.
 */
export function CaptureWork({ orderObjectId, stepId, points, action, work, needs = [],
                              target = null, moves = false,
                              busy, onConfirm, onDeviate, onDirty }: {
  orderObjectId: number;
  stepId: number;
  points: CapturePoint[];
  /** Das Verb des Moduls – vom Server, siehe `CaptureForm`. */
  action: string;
  work: StepWork[];
  /** **Die Stückliste dieses Moduls**, gegen den Bestand gehalten. Leer = keine. */
  needs?: StepNeed[];
  /**
   * **Wohin dieses Modul bringt** – aus der Definition, bereits aufgelöst. `null` heisst
   * bei einem Bewegungsmodul «beim Ausführen wählen», nicht «keines».
   */
  target?: PlaceRef | null;
  /**
   * **Womit bewegt werden kann** – und was davon heute geht (`available`). Leer bei jedem
   * anderen Modultyp: die Liste ist zugleich das Bit, ob dieses Modul bewegt.
   */
  moves?: boolean;
  busy?: boolean;
  onConfirm: (instanceObjectId: number, verification: string,
              values: Record<string, Record<string, unknown>>,
              sources: number[], place: number | null) => void;
  /** Die Entscheidung öffnet einen **ganz gewöhnlichen** Auftragsentwurf (§4/§4.1). */
  onDeviate?: (seed: OrderSeed) => void;
  onDirty?: (dirty: boolean) => void;
}) {
  const scan = useScan();
  /**
   * Wie eine Instanz bestätigt wurde (`scan` ↔ `manual`) und welche Stücke zu erfassen sind –
   * hier oben, weil der Sammel-Scan mehrere Zeilen auf einmal bestätigt.
   */
  const [verified, setVerified] = useState<Record<number, string>>({});
  const [numbers, setNumbers] = useState<Record<number, string[]>>({});
  /**
   * Aus welchen Kisten genommen wird – je Artikel. Leer heisst «nach Plan» (`planBoxes`); der
   * Server prüft die Wahl, er rät nicht.
   */
  const [boxes, setBoxes] = useState<Record<number, number[]>>({});
  /**
   * Wohin es geht (je Instanz die gescannte Ziel-Objektnummer) und womit – am Vorgang, weil der
   * Sammel-Scan alles an denselben Ort bringt. Ein definiertes Ziel wird per Scan verifiziert.
   */
  const [placed, setPlaced] = useState<Record<number, number>>({});

  if (work.length === 0) {
    return <p className="text-xs" style={{ color: 'var(--fg-3)' }}>Hier steht gerade nichts.</p>;
  }

  /**
   * **Was zu scannen ist, ergibt sich aus der Stichprobe**: gezogene Einzelinstanzen → ihre
   * Instanzen. Eine Instanz ohne gezogenes Stück läuft durch, sobald die Stichprobe bestanden
   * ist (`process._run_through`).
   */
  const needsScan = (w: StepWork) =>
    (points.length === 0 || w.sample > 0) && verified[w.instance_object_id] == null;
  const open = work.filter(needsScan);

  /**
   * Welche Kisten dieser Vorgang anfasst: der Plan (älteste zuerst) ist die Vorgabe, die Wahl
   * des Menschen sticht ihn. Dieselbe Liste wird gescannt und mitgeschickt.
   */
  const boxesFor = (w: StepWork): number[] => {
    const out = needs.flatMap((n) =>
      boxes[n.article_object_id]?.length
        ? boxes[n.article_object_id]
        : planBoxes(n, n.per_unit * w.waiting));
    return [...new Set(out)];
  };

  /** Die Nummern der gezogenen Stücke – **erst nach dem Scan**, denn erst dann gebraucht. */
  function accept(w: StepWork, how: string, place: number | null) {
    setVerified((s) => ({ ...s, [w.instance_object_id]: how }));
    if (place) setPlaced((s) => ({ ...s, [w.instance_object_id]: place }));
    if (!points.length) { setNumbers((s) => ({ ...s, [w.instance_object_id]: [] })); return; }
    void api.stepHold(orderObjectId, stepId, w.instance_object_id, 'sample')
      .then((r) => setNumbers((s) => ({ ...s, [w.instance_object_id]: r.numbers })));
  }

  /** Was ein Vorgang an der Ware scannt: die Instanz, danach jede Kiste, aus der er nimmt.
   *  Das Label nennt die Sorte, die Nummer hängt der Scanner an (`objectCodes.prompt`). */
  const goodsSteps = (w: StepWork) => [
    // Ohne `label`: die Sorte kommt aus dem Typ, nicht aus einem hingeschriebenen Wort.
    { kind: 'instance' as const, expected: w.instance_object_id },
    ...boxesFor(w).map((id) => ({
      label: 'Material', kind: 'instance' as const, expected: id,
    })),
  ];

  /**
   * **Der Zielort – zuletzt**: der Ziel-Scan ist die Quittung der Ablage (erst die Ware, dann
   * der Platz). Steht das Ziel in der Definition, ist er eine Verifikation (`expected`); sonst
   * ein freier Lookup mit Existenzprüfung.
   */
  const placeStep = () => (target
    ? { label: 'Zielort', expected: target.object_id }
    : {
      label: 'Zielort',
      exists: (id: number) => api.getPlace(id).then(() => true, absentOn404),
      // Ein freier Schritt bringt seine Vorschlagsquelle mit – dieselbe Suche wie das Zielfeld
      // im Editor.
      suggest: (q: string) => api.searchPlaces(q)
        .then((rows) => rows.map((p) => ({ objectId: p.object_id, label: p.label }))),
    });

  const scanSteps = (w: StepWork) => [
    ...goodsSteps(w), ...(moves ? [placeStep()] : []),
  ];

  /**
   * **Der Sammel-Scan ist die Scan-Sequenz**: ein Dialog, ein Schritt je Instanz. Kein zweiter
   * Mechanismus.
   */
  function scanAll() {
    if (!open.length) return;
    // Der Zielort wird EINMAL gescannt, nicht je Instanz – eine Fuhre geht an einen Ort.
    // Verschiedene Ziele: Zeilen einzeln bestätigen.
    scan({
      steps: [...open.flatMap(goodsSteps), ...(moves ? [placeStep()] : [])],
      onComplete: (ids, how) => {
        const to = moves ? Number(ids[ids.length - 1]) || null : null;
        open.forEach((w) => accept(w, how, to));
      },
    });
  }

  return (
    <div className="flex flex-col">
      {work.map((w, i) => (
        <InstanceRow
          key={w.instance_object_id}
          work={w}
          points={points}
          action={action}
          // Die Stückliste steht unter ihrer Einzelinstanz: erst wohin, dann was.
          needs={needs}
          boxes={boxes}
          onChoose={(article, ids) => setBoxes((s) => ({ ...s, [article]: ids }))}
          onSupply={onDeviate && ((article: number) => onDeviate({ articleObjectId: article }))}
          // «Holen lassen» ist kein zweiter Anlagepfad – derselbe Entwurf wie «Nachschub», mit
          // Menge und einem Bewegen-Modul auf den Arbeitsort.
          onHaul={onDeviate && ((need, quantity) => onDeviate({
            articleObjectId: need.article_object_id,
            quantity,
            steps: [{ moduleType: MOVE_MODULE, target: need.place?.object_id }],
          }))}
          busy={busy}
          first={i === 0}
          via={verified[w.instance_object_id] ?? null}
          numbers={numbers[w.instance_object_id] ?? null}
          onScan={() => scan({
            steps: scanSteps(w),
            onComplete: (ids, how) =>
              accept(w, how, moves ? Number(ids[ids.length - 1]) || null : null),
          })}
          onDirty={onDirty}
          onDeviate={onDeviate}
          orderObjectId={orderObjectId}
          stepId={stepId}
          onConfirm={(values) => {
            setVerified(({ [w.instance_object_id]: _gone, ...rest }) => rest);
            setNumbers(({ [w.instance_object_id]: _also, ...rest }) => rest);
            onConfirm(w.instance_object_id, verified[w.instance_object_id] ?? 'manual',
                      values, boxesFor(w),
                      placed[w.instance_object_id] ?? null);
          }}
        />
      ))}

      {/* Der grosse Knopf nur, wenn er mehr kann als der kleine (mehr als eine offene Instanz). */}
      {open.length > 1 && (
        <button type="button" onClick={scanAll} disabled={busy}
          className="erp-actbtn mt-2.5 w-full" style={{ height: 38 }}
          data-tip="Der Reihe nach durch alle Instanzen – ein Schritt je Instanz">
          <ScanLine size={15} /> Alle scannen ({open.length})
        </button>
      )}
    </div>
  );
}

/**
 * **Der Plan: aus welchen Kisten die Menge kommt** – dieselbe Reihenfolge wie der Server
 * (`consumption._free`), damit man vor dem Scan weiss, was zu holen ist.
 */
/**
 * Welche Kisten der Server nehmen würde. Was am Arbeitsort liegt, kommt zuerst (§9.6); ob
 * eine Kiste «hier» ist, sagt der Server je Quelle (``NeedSource.here``).
 */
function planBoxes(need: StepNeed, want: number): number[] {
  const out: number[] = [];
  let left = want;
  const byPlace = [...(need.sources ?? [])].sort((a, b) => (b.here ?? 0) - (a.here ?? 0));
  for (const s of byPlace) {
    if (left <= 0) break;
    const usable = need.place ? (s.here ?? 0) : s.free;
    if (usable <= 0) continue;
    out.push(s.instance_object_id);
    left -= usable;
  }
  return out;
}

/**
 * **Eine Zeile der Stückliste — was gebraucht wird, und ob es da ist.**
 *
 * Nichtverfügbarkeit ist kein Zustand (§4): hier steht in Klartext, woran es liegt. Drei Wege:
 * eine andere Kiste nehmen · holen lassen (Auftrag mit Bewegen-Modul auf den Arbeitsort) ·
 * Nachschub anlegen. Angeboten wird nur, was gerade Sinn ergibt; ein automatisches Ausweichen
 * gibt es nicht.
 */
function NeedRow({ need, pieces, chosen, onChoose, onSupply, onHaul }: {
  need: StepNeed;
  /** Wie viele Stücke **dieser** Instanz vor dem Modul stehen – die Bezugsgrösse. */
  pieces: number;
  chosen: number[] | null;
  onChoose: (ids: number[]) => void;
  onSupply?: () => void;
  /** «Holen lassen» – ein Auftragsentwurf mit Bewegen-Modul auf den Arbeitsort. */
  onHaul?: (quantity: number) => void;
}) {
  const [open, setOpen] = useState(false);
  // Gerechnet wird auf **diese** Instanz: die Menge gilt je Stück.
  const mine = need.per_unit * pieces;
  const sources = need.sources ?? [];
  const plan = chosen ?? planBoxes(need, mine);

  /**
   * ►►► **Verglichen wird gegen den Bedarf des MODULS, nicht gegen den Anteil dieser
   * Zeile.** ◄◄◄
   * Zugeteilt wird erst beim Bestätigen (`consumption.plan`, FIFO, im Log `payload.into`) –
   * Reservierungen gibt es nicht. Der gemeinsame freie Bestand wird darum gegen
   * `need.required` gehalten (Menge je Stück × alle Stücke vor dem Modul), denselben Massstab,
   * gegen den `plan` prüft.
   */
  const required = need.required;
  /** Wie viele Produkt-Stücke an diesem Modul davorstehen – die Bezugsgrösse der Zahl. */
  const units = need.per_unit > 0 ? required / need.per_unit : 0;

  // ►► **Keine Option anbieten, die gerade keinen Sinn ergibt.** ◄◄
  //
  //   am Arbeitsort genug         →  nichts. Einfach scannen.
  //   genug da, liegt nur woanders →  «Holen lassen» – die Handlung ist ein Transport.
  //   reicht nicht, Bestand da    →  «Andere Instanz wählen».
  //   gar kein Bestand            →  nur «Nachschub». Wählen liesse sich nichts.
  const enough = need.available >= required;
  const empty = need.available <= 0;
  const here = need.place ? (need.here ?? 0) : need.available;
  // Die Menge ist da, nur nicht hier. Der einzige Fall, den ein Transport löst.
  const misplaced = enough && here < required;

  return (
    <div className="flex flex-col gap-1 py-1.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Boxes size={13} style={{ flex: 'none', color: 'var(--fg-4)' }} />
        {/* Die Zahl vorn gilt DIESER Instanz; die Deckung daneben gilt dem Modul. */}
        <span className="text-xs" style={{ color: 'var(--fg-2)', fontWeight: 600 }}
          data-tip={`${need.per_unit} je Einzelinstanz × ${pieces} Stück dieser Instanz`}>
          {mine}×
        </span>
        <span className="text-xs truncate" style={{ color: 'var(--fg-3)' }}>
          {need.article_name}
        </span>
        {!enough && (
          <span className="ml-auto text-[11.5px]" style={{ color: 'var(--danger)' }}
            data-tip={`Gebraucht an diesem Modul: ${need.per_unit} je Einzelinstanz × `
              + `${units} Stück`}>
            {need.available} von {required} verfügbar
          </span>
        )}
        {/* Der Ort ist das Problem, nicht die Menge: wie viel hier liegt, und wo der Rest steht. */}
        {enough && misplaced && need.place && (
          <span className="ml-auto text-[11.5px]" style={{ color: 'var(--danger)' }}
            data-tip={`Gebraucht bei ${need.place.label} · ${need.available - here} `
              + `${need.available - here === 1 ? 'liegt' : 'liegen'} woanders`}>
            {here} bei {need.place.label}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {/* Eine Objektnummer führt zu ihrem Datensatz (`ObjId`). */}
        <span className="text-[11.5px] flex flex-wrap items-center gap-x-1"
          style={{ color: 'var(--fg-4)' }}>
          {plan.length
            ? <>aus {plan.map((id, i) => (
                <span key={id} className="inline-flex items-center gap-1">
                  {i > 0 && <span aria-hidden>·</span>}
                  <ObjId value={id} />
                </span>
              ))}</>
            : 'kein Bestand'}
        </span>
        {(misplaced || (!enough && !empty)) && (
          <button type="button" onClick={() => setOpen(!open)}
            className="text-[11.5px] underline" style={{ color: 'var(--fg-3)' }}
            data-tip="Aus einer anderen Instanz nehmen – die Wahl gilt, es wird nicht ausgewichen">
            Andere Instanz wählen
          </button>
        )}
        {misplaced && onHaul && (
          <button type="button" className="erp-actbtn ml-auto" style={{ height: 28 }}
            onClick={() => onHaul(required - here)}
            data-tip={"Öffnet einen ganz gewöhnlichen Auftragsentwurf: dieses Material "
              + "holen und hierher bringen. Angelegt wird nichts."}>
            <Truck size={13} /> Holen lassen
          </button>
        )}
        {empty && onSupply && (
          <button type="button" className="erp-actbtn ml-auto" style={{ height: 28 }}
            onClick={onSupply}
            data-tip="Öffnet einen ganz gewöhnlichen Auftragsentwurf mit diesem Artikel">
            <PackagePlus size={13} /> Nachschub
          </button>
        )}
      </div>

      {open && (
        <div className="flex flex-wrap gap-1.5">
          {sources.length === 0 && (
            <span className="text-[11.5px]" style={{ color: 'var(--fg-4)' }}>
              Von diesem Artikel liegt nichts frei.
            </span>
          )}
          {sources.map((s) => {
            const on = plan.includes(s.instance_object_id);
            return (
              <button key={s.instance_object_id} type="button"
                onClick={() => onChoose(on
                  ? plan.filter((x) => x !== s.instance_object_id)
                  : [...plan, s.instance_object_id])}
                className="rounded-full px-2 py-1 text-[11.5px] ix-tnum"
                style={on
                  ? { background: 'var(--success-bg)', color: 'var(--success)' }
                  : { border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}>
                {formatObjectId(s.instance_object_id)} · {s.free}
                {need.place && s.place ? (
                  <span style={{ opacity: 0.75 }}> · {s.place.label}</span>
                ) : null}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Eine Instanz — eine Zeile, darunter höchstens zwei leise; getrennt durch eine Haarlinie. */
function InstanceRow({ work, points, action, needs, boxes, onChoose, onSupply, onHaul, busy,
                      first, via, numbers, onScan, onConfirm,
                      onDirty, onDeviate, orderObjectId, stepId }: {
  work: StepWork;
  points: CapturePoint[];
  action: string;
  /** Die Stückliste dieses Moduls – gerechnet auf **diese** Instanz. */
  needs: StepNeed[];
  boxes: Record<number, number[]>;
  onChoose: (article: number, ids: number[]) => void;
  onSupply?: (article: number) => void;
  onHaul?: (need: StepNeed, quantity: number) => void;
  busy?: boolean;
  first: boolean;
  via: string | null;
  numbers: string[] | null;
  onScan: () => void;
  onConfirm: (values: Record<string, Record<string, unknown>>) => void;
  onDirty?: (dirty: boolean) => void;
  onDeviate?: (seed: OrderSeed) => void;
  orderObjectId: number;
  stepId: number;
}) {
  const nr = formatObjectId(work.instance_object_id);
  // Hier ist nichts zu erfassen (ausserhalb der Ziehung) – der Rest läuft sichtbar durch.
  const idle = points.length > 0 && work.sample === 0;

  return (
    <div className="flex flex-col gap-1 py-2"
      style={first ? undefined : { borderTop: '1px solid var(--border-1)' }}>
      {/* ── Ebene 1 · die Handlung ─────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <span style={{ font: '600 12.5px var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
          {nr}
        </span>
        {work.article_name && (
          <span className="text-xs truncate" style={{ color: 'var(--fg-3)' }}>
            {work.article_name}
          </span>
        )}
        {/* Nur das Symbol – was es tut, sagt der Hover. */}
        {!via && !idle && (
          <button type="button" onClick={onScan} disabled={busy}
            className="ml-auto flex items-center justify-center rounded-ds-md disabled:opacity-40"
            style={{ width: 32, height: 32, border: '1px solid var(--border-2)',
                     background: 'var(--bg-1)', color: 'var(--fg-2)' }}
            aria-label={`Instanz ${nr} scannen`} data-tip="Diese Instanz scannen">
            <ScanLine size={17} />
          </button>
        )}
      </div>

      {/* ── Was hineingeht — eingerückt, denn es gehört zu diesem Stück ── */}
      {needs.length > 0 && (
        <div className="flex flex-col" style={{
          marginLeft: 10, paddingLeft: 10, borderLeft: '1px solid var(--border-1)',
        }}>
          {needs.map((n) => (
            <NeedRow key={n.article_object_id} need={n} pieces={work.waiting}
              chosen={boxes[n.article_object_id] ?? null}
              onChoose={(ids) => onChoose(n.article_object_id, ids)}
              onSupply={onSupply && (() => onSupply(n.article_object_id))}
              onHaul={onHaul && ((quantity) => onHaul(n, quantity))} />
          ))}
        </div>
      )}

      {/* ── Ebene 2 · der Auftrag an diese Instanz — oder das Formular ──────── */}
      {via ? (
        <CaptureForm points={points} action={action} numbers={numbers} busy={busy}
          onDirty={onDirty} onConfirm={onConfirm} />
      ) : (
        <p className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>
          {idle
            ? `${work.waiting} Stück · nicht gezogen, läuft ohne Erfassung durch`
            : points.length === 0
              ? `${work.waiting} Stück · der Scan bestätigt`
              : <>
                  {work.sample} von {work.waiting} Stück erfassen
                  <span data-tip={points.map(labelOf).join(' · ')}> · {points.length === 1
                    ? points[0].label
                    : `${points.length} Angaben`}</span>
                </>}
        </p>
      )}

      {/* ── Ebene 3 · der Halt, nur wenn es ihn gibt ────────────────────────── */}
      {work.held && (
        <Hold work={work} orderObjectId={orderObjectId} stepId={stepId} onDeviate={onDeviate} />
      )}
    </div>
  );
}

/** Ein Erfassungspunkt in einer Zeile – Beschriftung plus Sollwert, wo es einen gibt. */
function labelOf(p: CapturePoint): string {
  if (p.target == null) return p.label;
  return `${p.label} ${p.target}${p.tolerance ? ` ±${p.tolerance}` : ''}${p.unit ? ` ${p.unit}` : ''}`;
}

/**
 * **Der Halt — eine Zeile, eine Entscheidung** (§4.1). Die Meldung nennt die Tatsache, die
 * Folgen stehen im Hover. Eine 100 %-Kontrolle ist ein Abweichungsauftrag mit Stichprobe «alle».
 */
function Hold({ work, orderObjectId, stepId, onDeviate }: {
  work: StepWork; orderObjectId: number; stepId: number;
  onDeviate?: (seed: OrderSeed) => void;
}) {
  const { busy, run } = useAction();
  const failed = work.failed_numbers ?? [];

  const open = () => onDeviate && run(async () => {
    const [{ numbers }, instance] = await Promise.all([
      api.stepHold(orderObjectId, stepId, work.instance_object_id, 'failed'),
      api.getInstance(work.instance_object_id),
    ]);
    if (!numbers.length || instance.article_object_id == null) return;
    onDeviate({
      articleObjectId: instance.article_object_id,
      unitNumbers: numbers,
      fromOrder: orderObjectId,
    });
  }, tell('Abweichung', 'Nicht vorbereitet'));

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
      <span className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--danger)' }}
        data-tip={`Hier steht alles still, bis entschieden ist${
          work.rest > 0 ? ` – auch die ${work.rest} ungeprüften Stück dieser Instanz` : ''}.`}>
        <AlertTriangle size={13} style={{ flex: 'none' }} />
        Nicht bestanden: {failed.join(', ')}
      </span>
      <button type="button" className="erp-actbtn ml-auto" style={{ height: 30 }}
        disabled={busy || !onDeviate} onClick={() => void open()}
        data-tip="Auftrag über die durchgefallenen Stücke – Prozess definieren und freigeben">
        <GitBranch size={13} /> Abweichung ({failed.length})
      </button>
    </div>
  );
}
