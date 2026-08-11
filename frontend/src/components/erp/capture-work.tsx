'use client';

import { useState } from 'react';
import { AlertTriangle, GitBranch, ScanLine, ShieldCheck } from 'lucide-react';
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
 * Einzelserialisierung sind **n** Scans. Es gibt hier keine Abfrage nach der
 * Serialisierung.
 *
 * **Ohne Bestätigung keine Eingabe.** Der Scan ist der Regelweg, die Tastatur die
 * Alternative – beides ist eine Bestätigung, beides wird geloggt, und keines ist eine
 * Umgehung. Durchgesetzt wird es serverseitig (`process.confirm_step`); was hier steht,
 * ist die Bedienung, nicht die Regel.
 *
 * **Nicht bestanden ⇒ hier steht alles still**, bis ein Mensch entscheidet. Das System
 * legt nichts an: ein automatischer Folgeauftrag wäre ein leerer Entwurf, den niemand
 * bestellt hat – und er zöge Stücke aus dem Auftrag, ohne dass jemand zugestimmt hätte.
 */
export function CaptureWork({ orderObjectId, stepId, points, work, busy, onConfirm, onDeviate, onDirty }: {
  orderObjectId: number;
  stepId: number;
  points: CapturePoint[];
  work: StepWork[];
  busy?: boolean;
  onConfirm: (instanceObjectId: number, verification: string,
              values: Record<string, unknown>) => void;
  /** Die Entscheidung öffnet einen **ganz gewöhnlichen** Auftragsentwurf (§4/§4.1). */
  onDeviate?: (seed: OrderSeed) => void;
  onDirty?: (dirty: boolean) => void;
}) {
  if (work.length === 0) {
    return <p className="text-xs" style={{ color: 'var(--fg-3)' }}>Hier steht gerade nichts.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {work.map((w) => (
        <InstanceWork
          key={w.instance_object_id}
          orderObjectId={orderObjectId}
          stepId={stepId}
          work={w}
          points={points}
          busy={busy}
          onConfirm={onConfirm}
          onDeviate={onDeviate}
          onDirty={onDirty}
        />
      ))}
    </div>
  );
}

function InstanceWork({ orderObjectId, stepId, work, points, busy, onConfirm, onDeviate, onDirty }: {
  orderObjectId: number;
  stepId: number;
  work: StepWork;
  points: CapturePoint[];
  busy?: boolean;
  onConfirm: (instanceObjectId: number, verification: string,
              values: Record<string, unknown>) => void;
  onDeviate?: (seed: OrderSeed) => void;
  onDirty?: (dirty: boolean) => void;
}) {
  const scan = useScan();
  const [verified, setVerified] = useState<string | null>(null);

  const nr = formatObjectId(work.instance_object_id);
  const scope = work.rest > 0
    ? `${work.sample} von ${work.waiting} Stück werden erfasst · ${work.rest} laufen ohne Erfassung durch`
    : `${work.waiting} Stück`;

  /**
   * **Der Verifikationsschritt ist genau der Fall, für den die Sequenz gebaut ist**:
   * `expected` = diese Objektnummer. Kein eigener Dialog, keine zweite Kamera-Logik –
   * und die manuelle Eingabe steckt bereits darin (dieselbe Leiste im Bild).
   */
  function verify() {
    scan({
      steps: [{ label: 'Instanz', kind: 'instance', expected: work.instance_object_id }],
      onComplete: () => setVerified('scan'),
    });
  }

  return (
    <div className="rounded-ds-md" style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)' }}>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 px-2.5 py-2">
        <span style={{ font: '600 12.5px var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>{nr}</span>
        {work.article_name && (
          <span className="text-xs truncate" style={{ color: 'var(--fg-3)' }}>{work.article_name}</span>
        )}
        <span className="ml-auto text-[11.5px]" style={{ color: 'var(--fg-4)' }}>{scope}</span>
      </div>

      {work.held ? (
        <Decision work={work} orderObjectId={orderObjectId} stepId={stepId} onDeviate={onDeviate} />
      ) : verified ? (
        <div className="px-2.5 pb-2.5">
          <CaptureForm
            points={points}
            count={work.sample}
            busy={busy}
            onDirty={onDirty}
            onConfirm={(values) => {
              setVerified(null);
              onConfirm(work.instance_object_id, verified, values);
            }}
          />
        </div>
      ) : (
        // **Ohne Bestätigung keine Eingabe.** Der Scan ist der Regelweg; wer die Kamera
        // nicht nutzen kann, tippt die Nummer – im selben Dialog, und ebenso geloggt.
        <div className="flex flex-wrap items-center gap-2 px-2.5 pb-2.5">
          <button type="button" className="erp-actbtn erp-actbtn-primary flex-1"
            style={{ height: 36, minWidth: 180 }} disabled={busy} onClick={verify}>
            <ScanLine size={15} /> Instanz scannen
          </button>
          <button type="button" className="erp-actbtn" style={{ height: 36 }}
            disabled={busy} onClick={() => setVerified('manual')}
            data-tip="Alternative zum Scan – wird ebenso als Bestätigung festgehalten">
            <ShieldCheck size={15} /> Von Hand bestätigen
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * **Die Entscheidung nach einem «nicht bestanden»** (§4 / §4.1).
 *
 * Zwei Wege, und beide sind **derselbe Mechanismus**: ein ganz gewöhnlicher
 * Auftragsentwurf mit vorgewählten Stücken. Die 100 %-Kontrolle ist kein neues Konzept –
 * nur eine andere Vorbelegung. Wer beides braucht, klickt beides nacheinander.
 *
 * **Der «Rest» sind die ungeprüften Stücke dieser Instanz an diesem Modul** – nicht die
 * übrige Charge. Stücke, die anderswo laufen oder längst am Lager liegen, hat dieses
 * Modul nie behandelt; eine 100 %-Kontrolle über sie wäre eine Aussage über Material,
 * das hier nie war.
 */
function Decision({ work, orderObjectId, stepId, onDeviate }: {
  work: StepWork; orderObjectId: number; stepId: number;
  onDeviate?: (seed: OrderSeed) => void;
}) {
  const [busy, setBusy] = useState(false);
  const failed = work.failed_numbers ?? [];

  async function open(group: 'failed' | 'rest') {
    if (!onDeviate) return;
    setBusy(true);
    try {
      const [{ numbers }, instance] = await Promise.all([
        api.stepHold(orderObjectId, stepId, work.instance_object_id, group),
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
    <div className="px-2.5 pb-2.5 flex flex-col gap-2">
      <p className="flex items-start gap-1.5 text-xs" style={{ color: 'var(--danger)' }}>
        <AlertTriangle size={13} style={{ flex: 'none', marginTop: 1 }} />
        <span>
          Nicht bestanden: {failed.join(', ')}. Hier steht alles still, bis
          entschieden ist – auch die {work.rest} ungeprüften Stück dieser Instanz.
        </span>
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="erp-actbtn" style={{ height: 34 }}
          disabled={busy || !onDeviate} onClick={() => void open('failed')}
          data-tip="Auftrag über die durchgefallenen Stücke – Prozess definieren und freigeben">
          <GitBranch size={14} /> Abweichung ({failed.length})
        </button>
        {work.rest > 0 && (
          <button type="button" className="erp-actbtn" style={{ height: 34 }}
            disabled={busy || !onDeviate} onClick={() => void open('rest')}
            data-tip="Die Stichprobe ist nicht mehr repräsentativ – der ungeprüfte Rest dieser Instanz wird vollständig kontrolliert">
            <ShieldCheck size={14} /> 100 %-Kontrolle ({work.rest})
          </button>
        )}
      </div>
    </div>
  );
}
