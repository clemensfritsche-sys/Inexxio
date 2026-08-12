'use client';

import { useState } from 'react';
import { AlertTriangle, GitBranch, ScanLine, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import type { CapturePoint, StepWork } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { useScan } from '@/components/scan/scan-provider';
import { CAPTURE_ICON } from '@/lib/modules';
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
          action={action}
          busy={busy}
          onConfirm={onConfirm}
          onDeviate={onDeviate}
          onDirty={onDirty}
        />
      ))}
    </div>
  );
}

function InstanceWork({ orderObjectId, stepId, work, points, action, busy, onConfirm, onDeviate, onDirty }: {
  orderObjectId: number;
  stepId: number;
  work: StepWork;
  points: CapturePoint[];
  action: string;
  busy?: boolean;
  onConfirm: (instanceObjectId: number, verification: string,
              values: Record<string, Record<string, unknown>>) => void;
  onDeviate?: (seed: OrderSeed) => void;
  onDirty?: (dirty: boolean) => void;
}) {
  const scan = useScan();
  const [verified, setVerified] = useState<string | null>(null);
  const [numbers, setNumbers] = useState<string[] | null>(null);

  const nr = formatObjectId(work.instance_object_id);

  /**
   * **Der Verifikationsschritt ist genau der Fall, für den die Sequenz gebaut ist**:
   * `expected` = diese Objektnummer. Kein eigener Dialog, keine zweite Kamera-Logik.
   *
   * **Und kein zweiter Weg daneben.** Es gab einmal einen Knopf «Von Hand bestätigen»,
   * der das Formular ohne den Dialog öffnete – zwei Wege zu demselben Ziel, und der
   * zweite nur deshalb, weil das Tippen im Dialog praktisch unmöglich war (er verlangte
   * die volle neunstellige Nummer). Das ist behoben: die Tastatur wohnt in der Leiste im
   * Bild, eine Teileingabe genügt, und **wie** bestätigt wurde, sagt der Dialog selbst –
   * `scan` oder `manual`, so wie es der Server verlangt und protokolliert.
   *
   * **Erst nach dem Scan holt die Ansicht die Nummern** der gezogenen Stücke – erst dann
   * werden sie gebraucht, und bei einer grossen Charge sind es viele. Die Vorschau
   * davor kommt mit den Zahlen aus, die ohnehin mitreisen.
   */
  function verify() {
    scan({
      steps: [{ label: 'Instanz', kind: 'instance', expected: work.instance_object_id }],
      onComplete: (_ids, how) => {
        setVerified(how);
        if (!points.length) { setNumbers([]); return; }
        void api.stepHold(orderObjectId, stepId, work.instance_object_id, 'sample')
          .then((r) => setNumbers(r.numbers));
      },
    });
  }

  return (
    <div className="rounded-ds-md" style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)' }}>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 px-2.5 py-2">
        <span style={{ font: '600 12.5px var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>{nr}</span>
        {work.article_name && (
          <span className="text-xs truncate" style={{ color: 'var(--fg-3)' }}>{work.article_name}</span>
        )}
        {/* **Der eigene Scan-Knopf je Instanz** – klein, neben ihrer Nummer. Der grosse
            Sammel-Knopf unten bleibt; er geht dieselbe Liste der Reihe nach durch. */}
        {!verified && (
          <button type="button" onClick={verify} disabled={busy}
            className="ml-auto flex items-center gap-1 text-[11.5px] disabled:opacity-40"
            style={{ color: 'var(--accent)' }}
            aria-label={`Instanz ${nr} scannen`} data-tip="Diese Instanz scannen">
            <ScanLine size={13} /> scannen
          </button>
        )}
      </div>

      {/* ►►► **Der Halt steht NEBEN dem Weg nach vorn, nicht anstelle davon.** ◄◄◄
          Er zeigte einmal ausschliesslich die Entscheidung – und war damit eine
          Sackgasse: nach einer Abweichung kam das Stück zurück, der letzte Befund war
          weiterhin negativ, und die einzige angebotene Handlung legte die nächste
          Abweichung an. Aufgehoben wird ein Halt durch einen **neuen Befund** (die
          Wiederholungsprüfung); die Entscheidung ist ein Angebot daneben, keine
          Bedingung. Der Dienst hat das nie anders gesehen. */}
      {work.held && (
        <Decision work={work} orderObjectId={orderObjectId} stepId={stepId} onDeviate={onDeviate} />
      )}
      {verified ? (
        <div className="px-2.5 pb-2.5">
          <CaptureForm
            points={points}
            action={action}
            numbers={numbers}
            busy={busy}
            onDirty={onDirty}
            onConfirm={(values) => {
              setVerified(null);
              setNumbers(null);
              onConfirm(work.instance_object_id, verified, values);
            }}
          />
        </div>
      ) : (
        <Preview points={points} work={work} />
      )}
    </div>
  );
}

/**
 * ►►► **Was hier zu tun ist — bevor irgendetwas gescannt wurde.** ◄◄◄
 *
 * Der Scan bleibt die Voraussetzung für die **Eingabe**; er war aber auch die
 * Voraussetzung für die **Auskunft**, und das war zu viel. Vorher stand hier nur «Instanz
 * scannen» – man wusste nicht, was einen erwartet, und musste scannen, um es zu erfahren.
 *
 * Die Vorschau beantwortet zwei Fragen, und beide sind da, bevor man etwas tut:
 *
 *   *wie viele*  Einzelinstanzen erfasst werden (und wie viele ohne Erfassung durchlaufen)
 *   *was*        an jeder erfasst wird – die Punkte des Moduls, mit ihrer Einheit
 *
 * **Sie steht bewusst hier und nicht in einem Modul**: `points` und `work` hat jedes
 * Modul, das über diese Ausführungsstelle läuft. Ein Modul ohne Erfassungspunkte
 * (Aussondern) zeigt nur die Menge – bei ihm gibt es nichts zu erfassen, und genau das
 * ist dann die Auskunft.
 */
function Preview({ points, work }: { points: CapturePoint[]; work: StepWork }) {
  return (
    <div className="flex flex-col gap-1.5 px-2.5 pb-2.5">
      <p className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>
        {points.length === 0
          ? `${work.waiting} Stück · nichts zu erfassen, der Scan bestätigt`
          : work.rest > 0
            ? `${work.sample} von ${work.waiting} Stück erfassen · ${work.rest} laufen ohne Erfassung durch`
            : `${work.waiting} Stück erfassen`}
      </p>
      {points.length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1">
          {points.map((p) => {
            const Icon = CAPTURE_ICON[p.type];
            return (
              <li key={p.key} className="flex items-center gap-1 text-[11.5px]"
                  style={{ color: 'var(--fg-4)' }}>
                {Icon && <Icon size={11} />}
                {p.label}
                {p.target != null && (
                  <span className="ix-tnum">
                    {' '}{p.target}{p.tolerance ? ` ±${p.tolerance}` : ''}{p.unit ? ` ${p.unit}` : ''}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
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
          Nicht bestanden: {failed.join(', ')}. Nichts ist vorgerückt
          {/* **Den Rest nur nennen, wenn es ihn gibt.** «auch die 0 ungeprüften Stück»
              stand als Satz da, sobald die Stichprobe «alle» war – eine Aussage über
              eine Menge, die es nicht gibt. */}
          {work.rest > 0 && <> – auch nicht die {work.rest} ungeprüften Stück dieser Instanz</>}.
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
