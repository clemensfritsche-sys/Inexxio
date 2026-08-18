'use client';

import { useState } from 'react';
import { ArrowRight, Building2, Truck } from 'lucide-react';
import type { Award, StepHaul } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { ObjId } from '@/components/erp/obj-id';
import { AwardPanel } from '@/components/erp/award-panel';

/**
 * **Die Fuhren eines Moduls «Bewegen»** (PROCESS_CORE §9.8).
 *
 * Eine **Fuhre** ist ein Paar Ausgangsort → Ziel. Zwei Ausgangsorte sind **zwei** Fuhren,
 * weil es physisch zwei Transporte sind: zwei Preise, zwei Etiketten, zwei Ankünfte. Drei
 * Stücke am selben Ort sind **eine**.
 *
 * Sie ist **abgeleitet, nicht eingestellt**: das Modul hat genau eine Einstellung, das
 * Ziel. Wer die Fuhre einstellen liesse, böte eine Entscheidung an, deren richtige
 * Antwort die Physik längst getroffen hat.
 *
 * **Innerbetrieblich oder Versand entscheidet die Adresse**, nicht ein gespeichertes
 * Feld (§15.4). Der Vorgänger hat diese Klassifikation gespeichert und zwei Migrationen
 * gebraucht, um die Werte wieder loszuwerden – hier steht sie nur da, weil sie gerechnet
 * wurde.
 *
 * **Und sie ist eine Vorschau.** Massgeblich für die Ausführung ist der Kontext-Scan:
 * eine Beobachtung kann veraltet sein, ein Scan ist die Gegenwart.
 */
export function HaulList({ hauls, busy }: {
  hauls: StepHaul[];
  busy?: boolean;
}) {
  /**
   * Die Vergabe wird hier **überschrieben**, nicht neu geladen: eine Handlung gibt den
   * neuen Stand zurück, und der gilt. Ein Nachladen des ganzen Auftrags wäre dieselbe
   * Aussage ein zweites Mal – und für einen Moment zwei verschiedene.
   */
  const [fresh, setFresh] = useState<Record<number, Award>>({});

  if (!hauls.length) return null;
  return (
    <div className="flex flex-col">
      {hauls.map((h, i) => (
        <HaulRow key={`${h.from_holder?.object_id ?? 'offen'}-${i}`} haul={h}
          award={h.from_holder ? fresh[h.from_holder.object_id] ?? h.award ?? null : null}
          busy={busy} first={i === 0}
          onAward={(a) => h.from_holder
            && setFresh((s) => ({ ...s, [h.from_holder!.object_id]: a }))} />
      ))}
    </div>
  );
}

function HaulRow({ haul, award, busy, first, onAward }: {
  haul: StepHaul;
  award: Award | null;
  busy?: boolean;
  first: boolean;
  onAward: (a: Award) => void;
}) {
  const external = !haul.internal && !!haul.from_holder;
  return (
    <div className="flex flex-col gap-1 py-1.5"
      style={{ borderTop: first ? undefined : '1px solid var(--border-1)' }}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {external
          ? <Truck size={13} style={{ flex: 'none', color: 'var(--warning)' }} />
          : <Building2 size={13} style={{ flex: 'none', color: 'var(--fg-4)' }} />}
        <span className="text-xs" style={{ color: 'var(--fg-2)', fontWeight: 600,
          fontVariantNumeric: 'tabular-nums' }}>
          {haul.pieces}×
        </span>
        {/* **Der Ausgangsort ist eine Beobachtung, keine Behauptung**: ohne Ablage steht
            hier nichts – der Kontext-Scan stellt ihn beim Ausführen fest (§15.3). */}
        <Holder holder={haul.from_holder} />
        <ArrowRight size={12} style={{ flex: 'none', color: 'var(--fg-4)' }} />
        <Holder holder={haul.to_holder} />
        {external && (
          <span className="text-[10.5px] px-1.5 py-0.5 rounded-full ml-auto"
            data-tip="Andere Anschrift – das ist ein Versand. Gerechnet, nie gespeichert."
            style={{ color: 'var(--warning)', background: 'var(--warning-bg)' }}>
            Versand
          </span>
        )}
      </div>

      {/* **Die Vergabe hängt an der externen Fuhre** – und nur dort. Innerbetrieblich
          bewegt jemand etwas zwanzig Meter durch die Halle; dafür braucht es keinen
          Dritten und kein Formular. */}
      {external && haul.from_holder && (
        <div className="pl-5">
          <AwardPanel award={award} subjectObjectId={haul.from_holder.object_id}
            targetObjectId={haul.to_holder.object_id} busy={busy}
            onChanged={onAward} />
        </div>
      )}
    </div>
  );
}

/**
 * Ein Halter – **eine Objektnummer, mehr nicht** (§15.2).
 *
 * Regal, Behälter, Palette und LKW sind Instanzen, ein Werk ist ein Unternehmen, ein
 * Mitarbeiter ist ein Benutzer. Es gibt keinen Typ daneben und keine Whitelist; lässt
 * sich der Name nicht auflösen, steht die Nummer da – nicht «kein Ort».
 */
function Holder({ holder }: { holder?: StepHaul['from_holder'] }) {
  if (!holder) {
    return (
      <span className="text-[11.5px]" style={{ color: 'var(--fg-4)' }}
        data-tip="Noch keine Beobachtung – der Kontext-Scan stellt den Ausgangsort fest.">
        noch nicht bekannt
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 min-w-0">
      <ObjId value={holder.object_id} />
      {holder.name && (
        <span className="text-[11.5px] truncate" style={{ color: 'var(--fg-3)' }}>
          {holder.name}
        </span>
      )}
      {!holder.name && !holder.type && (
        <span className="text-[10.5px]" style={{ color: 'var(--danger)' }}
          data-tip={`Objekt ${formatObjectId(holder.object_id)} lässt sich nicht auflösen.`}>
          unbekannt
        </span>
      )}
    </span>
  );
}
