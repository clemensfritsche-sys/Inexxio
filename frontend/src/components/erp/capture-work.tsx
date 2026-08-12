'use client';

import { useState } from 'react';
import { AlertTriangle, GitBranch, ScanLine } from 'lucide-react';
import { api } from '@/lib/api';
import type { CapturePoint, StepWork } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { useScan } from '@/components/scan/scan-provider';
import { CaptureForm } from '@/components/erp/capture-form';
import type { OrderSeed } from '@/components/erp/order-detail';

/**
 * **Die Arbeit an einem aktiven Modul — eine Zeile je Instanz.**
 *
 * Ein Vorgang ist **eine Instanz**, und das ist keine Gestaltungsentscheidung: das
 * Etikett klebt am physischen Ding, und das Ding ist die Instanz – eine Einzelinstanz
 * zieht bewusst keine Objektnummer. Daraus fällt der Unterschied von selbst heraus:
 * eine Charge ist **ein** Scan (auch wenn zwölf ihrer Stücke erfasst werden),
 * Einzelserialisierung sind **n** Scans.
 *
 * ## Drei Ebenen, und nur drei (Testnotiz #715)
 *
 * Vorher standen Zustandsmeldung, Zählung und Optionen gleichrangig nebeneinander, jede
 * in ihrem eigenen Kasten – Karte im Modul in der Spalte. Jetzt gibt es eine Rangfolge,
 * und sie ist an der Schriftgrösse ablesbar:
 *
 * 1. **Die Handlung** – Nummer und Scan. Das ist, was jetzt zu tun ist.
 * 2. **Der Auftrag an diese Instanz** – eine leise Zeile: wie viele Stücke, welche
 *    Punkte. Nach dem Scan tritt an ihre Stelle das Formular.
 * 3. **Der Halt** – nur wenn es ihn gibt, in einer Zeile, mit **einer** Entscheidung.
 *
 * Kein Rahmen um die Zeilen: was sie trennt, ist eine Haarlinie. Ein Kasten in einem
 * Kasten in einer Spalte sagt dreimal dasselbe («das gehört zusammen»).
 *
 * **Ohne Bestätigung keine Eingabe.** Der Scan ist der Regelweg, die Tastatur die
 * Alternative – beides ist eine Bestätigung, beides wird geloggt, und keines ist eine
 * Umgehung. Durchgesetzt wird es serverseitig (`process.confirm_step`).
 *
 * **Nicht bestanden ⇒ hier steht alles still**, bis ein Mensch entscheidet. Das System
 * legt nichts an: ein automatischer Folgeauftrag wäre ein leerer Entwurf, den niemand
 * bestellt hat – und er zöge Stücke aus dem Auftrag, ohne dass jemand zugestimmt hätte.
 */
export function CaptureWork({ orderObjectId, stepId, points, action, work, busy, onConfirm, onDeviate, onDirty }: {
  orderObjectId: number;
  stepId: number;
  points: CapturePoint[];
  /** Das Verb des Moduls – vom Server, siehe `CaptureForm`. */
  action: string;
  work: StepWork[];
  busy?: boolean;
  onConfirm: (instanceObjectId: number, verification: string,
              values: Record<string, Record<string, unknown>>) => void;
  /** Die Entscheidung öffnet einen **ganz gewöhnlichen** Auftragsentwurf (§4/§4.1). */
  onDeviate?: (seed: OrderSeed) => void;
  onDirty?: (dirty: boolean) => void;
}) {
  const scan = useScan();
  /**
   * **Wie** eine Instanz bestätigt wurde (`scan` ↔ `manual`) und **welche** Stücke zu
   * erfassen sind. Beides steht hier oben und nicht in der Zeile, weil der Sammel-Scan
   * (#711) mehrere Zeilen auf einmal bestätigt – eine Zeile kann das nicht für die
   * anderen mitmachen.
   */
  const [verified, setVerified] = useState<Record<number, string>>({});
  const [numbers, setNumbers] = useState<Record<number, string[]>>({});

  if (work.length === 0) {
    return <p className="text-xs" style={{ color: 'var(--fg-3)' }}>Hier steht gerade nichts.</p>;
  }

  /**
   * **Was zu scannen ist, ergibt sich aus der Stichprobe** (Testnotiz #714).
   *
   * Erst wird gezogen, daraus ergeben sich die zu erfassenden Einzelinstanzen, daraus
   * die zu scannenden **Instanzen**. Eine Instanz ohne gezogenes Stück wird hier nicht
   * bestätigt – sie läuft durch, sobald die Stichprobe dieses Moduls durch und bestanden
   * ist (`process._run_through`). Ein Scan, der nichts bestätigt, ist keiner.
   */
  const needsScan = (w: StepWork) =>
    (points.length === 0 || w.sample > 0) && verified[w.instance_object_id] == null;
  const open = work.filter(needsScan);

  /** Die Nummern der gezogenen Stücke – **erst nach dem Scan**, denn erst dann gebraucht. */
  function accept(w: StepWork, how: string) {
    setVerified((s) => ({ ...s, [w.instance_object_id]: how }));
    if (!points.length) { setNumbers((s) => ({ ...s, [w.instance_object_id]: [] })); return; }
    void api.stepHold(orderObjectId, stepId, w.instance_object_id, 'sample')
      .then((r) => setNumbers((s) => ({ ...s, [w.instance_object_id]: r.numbers })));
  }

  /**
   * **Der Sammel-Scan ist die Scan-Sequenz** (#711) – genau dafür ist sie gebaut: ein
   * Dialog, ein Schritt je Instanz, der Reihe nach. Kein zweiter Mechanismus, keine
   * zweite Kamera-Logik; der Unterschied zum Knopf in der Zeile ist die Zahl der
   * Schritte.
   */
  function scanAll() {
    if (!open.length) return;
    scan({
      steps: open.map((w) => ({
        label: `Instanz ${formatObjectId(w.instance_object_id)}`,
        kind: 'instance' as const,
        expected: w.instance_object_id,
      })),
      onComplete: (_ids, how) => open.forEach((w) => accept(w, how)),
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
          busy={busy}
          first={i === 0}
          via={verified[w.instance_object_id] ?? null}
          numbers={numbers[w.instance_object_id] ?? null}
          onScan={() => scan({
            steps: [{
              label: `Instanz ${formatObjectId(w.instance_object_id)}`,
              kind: 'instance', expected: w.instance_object_id,
            }],
            onComplete: (_ids, how) => accept(w, how),
          })}
          onDirty={onDirty}
          onDeviate={onDeviate}
          orderObjectId={orderObjectId}
          stepId={stepId}
          onConfirm={(values) => {
            setVerified(({ [w.instance_object_id]: _gone, ...rest }) => rest);
            setNumbers(({ [w.instance_object_id]: _also, ...rest }) => rest);
            onConfirm(w.instance_object_id, verified[w.instance_object_id] ?? 'manual', values);
          }}
        />
      ))}

      {/* **Der grosse Knopf – aber nur, wenn er mehr kann als der kleine.** Bei einer
          einzigen offenen Instanz wäre er ein zweiter Weg zum selben Ziel. */}
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
 * Eine Instanz — **eine Zeile, darunter höchstens zwei leise**.
 *
 * Getrennt wird durch eine Haarlinie, nicht durch einen Rahmen: die Zeilen gehören
 * ohnehin zusammen, das sagt schon die Modul-Karte, in der sie stehen.
 */
function InstanceRow({ work, points, action, busy, first, via, numbers, onScan, onConfirm,
                      onDirty, onDeviate, orderObjectId, stepId }: {
  work: StepWork;
  points: CapturePoint[];
  action: string;
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
  // **Hier ist nichts zu erfassen** – die Instanz liegt ausserhalb der Ziehung (#714).
  // Sie steht trotzdem da: der ungezogene Rest läuft **sichtbar** durch, nicht heimlich.
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
        {/* **Nur das Symbol** (#712) – was es tut, sagt der Hover; wen es meint, die
            Nummer daneben. Ein Wort dazwischen wäre die dritte Aussage in einer Zeile. */}
        {!via && !idle && (
          <button type="button" onClick={onScan} disabled={busy}
            className="ml-auto flex items-center justify-center rounded-ds-md disabled:opacity-40"
            style={{ width: 32, height: 32, border: '1px solid var(--border-2)',
                     background: '#fff', color: 'var(--fg-2)' }}
            aria-label={`Instanz ${nr} scannen`} data-tip="Diese Instanz scannen">
            <ScanLine size={17} />
          </button>
        )}
      </div>

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
 * **Der Halt — eine Zeile, eine Entscheidung** (§4.1, Testnotizen #710/#713).
 *
 * Zwei Vereinfachungen gegenüber der Vorgängerfassung, beide aus demselben Grundsatz:
 *
 * * **Die Meldung nennt die Tatsache, nicht ihre Folgen.** «Hier steht alles still, bis
 *   entschieden ist – auch die 1 ungeprüften Stück dieser Instanz» erklärte in einem
 *   Satz, was der Zustand ohnehin zeigt. Was nicht zur Handlung beiträgt, steht im Hover.
 * * **Die 100 %-Kontrolle ist ersatzlos entfallen.** Sie war kein zweiter Mechanismus,
 *   sondern derselbe: ein Abweichungsauftrag über die übrigen Stücke mit der Stichprobe
 *   «alle». Zwei Wege zu demselben Ergebnis sind einer zu viel – und der zweite legte
 *   die Stichprobe der Auflösung stillschweigend fest, statt sie wählen zu lassen.
 */
function Hold({ work, orderObjectId, stepId, onDeviate }: {
  work: StepWork; orderObjectId: number; stepId: number;
  onDeviate?: (seed: OrderSeed) => void;
}) {
  const [busy, setBusy] = useState(false);
  const failed = work.failed_numbers ?? [];

  async function open() {
    if (!onDeviate) return;
    setBusy(true);
    try {
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
    } finally {
      setBusy(false);
    }
  }

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
