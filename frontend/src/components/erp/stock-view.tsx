'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Boxes, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleStock, Instance, InstanceSummary, StockState } from '@/types';
import { statusCfg } from '@/lib/process-status';
import { SPEC, SpecHead } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { StockBar } from '@/components/erp/stock-bar';
import { UnitNumbers } from '@/components/erp/unit-numbers';

const PAGE = 50;

/**
 * **Was habe ich, in welchem Zustand, unter welcher Nummer?**
 *
 * EIN Modul, zwei Aufrufe. Der Unterschied ist ausschliesslich der **Umfang der Daten**,
 * nie die Darstellung:
 *
 *   - am **Artikel**  → alles davon; die Zeilen sind seine Instanzen, aufklappbar zu den
 *     Nummern ihrer Einzelinstanzen
 *   - an der **Instanz** → diese eine Gruppe; die Zeilen sind direkt ihre Einzelinstanzen
 *
 * Die Ansicht an der Instanz ist damit exakt der Teilbaum, den man am Artikel aufklappt –
 * dieselbe Leiste, dieselben Beschriftungen, dasselbe Verhalten beim Klick auf ein
 * Segment. Eine zweite Fassung «nur für die Instanz» hätte beim ersten neuen Zustand
 * anders ausgesehen.
 *
 * **Kein Filter.** Ein Filter versteckt, was er nicht zeigt; hier ist die Aufteilung
 * selbst das Bedienelement – ein Segment anklicken heisst «zeig mir diese Nummern», der
 * Rest bleibt in der Leiste sichtbar.
 *
 * **Niemals alles auf einmal.** Instanzen kommen seitenweise, Nummern erst auf Klick und
 * auch dann seitenweise. Die Leiste oben gilt trotzdem für den **ganzen** Umfang: sie
 * kommt aus einer eigenen Aggregation und ändert ihre Länge nicht, wenn man blättert.
 *
 * **Ein Sonderfall für Einzelserialisierung existiert nicht** (PROCESS_CORE.md §2): eine
 * Einzelinstanz ist eine Instanz mit Menge 1 – dieselbe Zeile, dieselbe Leiste.
 */
export type StockScope =
  /** Alles von diesem Artikel – die Aggregation holt der Endpunkt. */
  | { kind: 'article'; objectId: number }
  /**
   * Diese eine Gruppe. Der Datensatz **liegt schon vor** (das Fenster zeigt ihn ja) und
   * trägt seine Aufstellung mit – ihn hier ein zweites Mal zu holen wäre dieselbe Frage
   * an dieselbe Stelle.
   */
  | { kind: 'instance'; record: Instance };

export function StockView({ scope }: { scope: StockScope }) {
  const articleId = scope.kind === 'article' ? scope.objectId : null;
  const [stock, setStock] = useState<ArticleStock | null>(null);
  const [rows, setRows] = useState<InstanceSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  /**
   * **Welcher Zustand offen ist – genau einer, und keiner zu Beginn** (#716/#789). Eine
   * Gruppe, die von selbst offensteht, entscheidet für den Betrachter, was ihn
   * interessiert; die Mengen in der Leiste sagen ihm, ob sich das Öffnen lohnt. Ein
   * zweiter Klick schliesst wieder – dasselbe Bedienelement, beide Richtungen.
   */
  const [picked, setPicked] = useState<string | null>(null);
  const toggle = (status: string) =>
    setPicked((cur) => (cur === status ? null : status));

  const load = useCallback((offset: number) => {
    if (articleId == null) return;
    setBusy(true);
    api.getArticleStock(articleId, PAGE, offset)
      .then((s) => {
        setStock(s);
        setRows((prev) => (offset === 0 ? s.instances : [...prev, ...s.instances]));
        setErr(null);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  }, [articleId]);

  useEffect(() => { setRows([]); load(0); }, [load]);

  const states = scope.kind === 'article' ? stock?.states : scope.record.states;
  const total = scope.kind === 'article' ? stock?.total : scope.record.quantity;

  if (err) {
    return (
      <Card>
        <p className="text-sm" style={{ color: 'var(--danger)' }}>{err}</p>
      </Card>
    );
  }
  if (states == null || total == null) return null;

  if (total === 0) {
    return (
      <Card>
        <p className="text-sm text-fg-3">
          Noch kein Bestand – Einzelinstanzen entstehen mit der Freigabe eines Auftrags.
        </p>
      </Card>
    );
  }

  // **Ein Zustand ohne Zuordnung ist ein Fehler** und wird gemeldet, nicht einsortiert.
  const unknown = states.filter((s) => s.stock !== 'live' && s.stock !== 'history');
  const open = states.find((s) => s.status === picked) ?? null;

  return (
    <Card>
      {/* ►►► **Die Leiste IST das Bedienelement** (Testnotiz #789). ◄◄◄

          Darunter stand eine aufklappbare Sektion je Zustand – jede mit Chevron, Punkt,
          Wort und Menge im Kopf, also Zeile für Zeile das, was die Leiste eine Zeile
          höher schon zeigte, nur zwanzigmal höher. Bei vier Zuständen war der halbe
          Bildschirm Kopfzeilen ohne Inhalt.

          Geblieben ist **eine** Fassung: die Leiste mit ihren Beschriftungen (die die
          Farbe allein nicht leisten kann – drei Ampeltöne für sechs Zustände), und genau
          **ein** Ausschnitt darunter. Kein Filter: was man nicht anklickt, steht
          weiterhin in der Leiste. */}
      <StockBar states={states} height={10} onPick={toggle} active={picked} />

      {unknown.length > 0 && (
        <div className="pt-3"><UnknownStates states={unknown} /></div>
      )}

      {open && (
        <section className="mt-3 flex flex-col border-t border-border-1 pt-1">
          {scope.kind === 'instance' ? (
            // An der Instanz sind die Zeilen direkt die Einzelinstanzen – dieselbe
            // Komponente, die am Artikel eine Instanz-Zeile aufklappt.
            <UnitNumbers
              objectId={scope.record.object_id}
              statuses={[open.status]}
              quantity={open.quantity}
            />
          ) : (
            <>
              {rows
                .filter((r) => r.states.some((x) => x.status === open.status))
                .map((r) => <InstanceRow key={r.id} row={r} status={open.status} />)}
              {stock != null && rows.length < stock.instance_total && (
                <button
                  type="button"
                  onClick={() => load(rows.length)}
                  disabled={busy}
                  className="mt-2 self-start text-[12.5px] text-fg-3 hover:text-fg-1 disabled:opacity-50"
                >
                  {busy ? 'lädt …' : `weitere ${stock.instance_total - rows.length} Instanzen`}
                </button>
              )}
            </>
          )}
        </section>
      )}
    </Card>
  );
}

const sum = (states: StockState[]) => states.reduce((n, s) => n + s.quantity, 0);

/**
 * Die Karte – dieselbe Anatomie wie die Spezifikation (Karte + Kopf + Inhalt).
 *
 * **Ohne die eine grosse Zahl.** Sie stand rechts im Kopf und summierte alles – auch
 * Verschrottetes. Damit war sie zugleich irreführend (das ist kein Bestand) und
 * uninformativ (sie sagte nicht, wovon). Was sie beantworten sollte, beantworten jetzt
 * die Leiste und die Gruppen darunter: je Zustand eine Zahl, in der Reihenfolge des
 * Lebenszyklus.
 */
function Card({ children }: { children: React.ReactNode }) {
  return (
    <div style={SPEC.card}>
      <SpecHead icon={Boxes} title="Bestand" />
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

/**
 * **Ein Zustand ohne Zuordnung ist ein Fehler, kein Sonderfall.** Er dürfte nicht
 * existieren: `domain/statuses.py` weist beim Import jeden Einzelinstanz-Zustand ab, der
 * nicht sagt, ob er zum Bestand oder zur Historie zählt. Taucht er trotzdem auf (Altdaten,
 * ein von Hand geschriebener Wert), wird er **benannt** – ihn in einen Block zu raten
 * wäre eine Behauptung, ihn wegzulassen ein stiller Verlust.
 */
function UnknownStates({ states }: { states: StockState[] }) {
  return (
    <div
      className="flex items-start gap-2 rounded-ds-md px-3 py-2.5 text-[12.5px]"
      style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}
    >
      <AlertTriangle size={14} style={{ flex: 'none', marginTop: 1 }} />
      <span>
        Nicht zugeordnet ({states.map((s) => `${statusCfg(s.status).label} · ${s.quantity}`).join(', ')}) –
        dieser Zustand sagt nicht, ob er zum Bestand oder zur Historie zählt.
      </span>
    </div>
  );
}

/*
 * **Es gibt hier keine Gruppen-Sektionen mehr** (Testnotiz #789).
 *
 * Sie standen untereinander – je Zustand ein Kopf mit Chevron, Punkt, Wort und Menge,
 * darunter der aufgeklappte Inhalt. Der Kopf sagte damit dasselbe wie das Segment der
 * Leiste eine Zeile höher, nur zwanzigmal höher; bei vier Zuständen war der halbe
 * Bildschirm Kopfzeilen ohne Inhalt.
 *
 * Was sie konnten, kann jetzt die Leiste selbst: sie **nennt** ihre Zustände (Punkt,
 * Wort, Menge – die Farbe allein kann es nicht, drei Ampeltöne tragen sechs Zustände)
 * und ist zugleich die Auswahl. Was sie **nicht** konnte und weiterhin niemand kann:
 * zwei Zustände gleichzeitig offen halten – das war der Grund, warum es Sektionen gab,
 * und es war nie eine Frage, die jemand hatte.
 *
 * **Kein Status wird dabei aufgezählt.** Welche Zustände es gibt, sagt `states` vom
 * Server; die Reihenfolge ist die des `CATALOG` (= Lebenszyklus), die Farbe der
 * Ampelton. Ein neuer Zustand erscheint ohne eine Zeile Code an seiner Stelle.
 */

/**
 * Eine Zeile je Instanz **innerhalb einer Zustands-Gruppe**: Objektnummer, Menge.
 *
 * Sie zeigt nur, was sie in **diesem** Zustand hat – eine Charge mit drei freigegebenen
 * und einem verschrotteten Stück steht darum in zwei Gruppen, jedes Mal mit ihrer
 * dortigen Menge. Das ist die Auskunft, die eine Gruppe je Zustand überhaupt erst
 * möglich macht: die Instanz hat keinen Zustand, ihre Stücke haben einen.
 *
 * Aufklappen zeigt die **Nummern dieses Zustands** – eine Leiste braucht es dafür nicht
 * mehr: die Gruppe darüber IST die Auswahl.
 *
 * **Die Objektnummer führt zum Datensatz** (bestehende Navigation, kein eigener Weg) –
 * und weil `ObjId` den Klick abfängt, kollidiert das nicht mit dem Aufklappen.
 */
function InstanceRow({ row, status }: { row: InstanceSummary; status: string }) {
  const [shown, setShown] = useState(false);
  const states = row.states.filter((s) => s.status === status);

  const toggle = () => setShown((v) => !v);

  // **Die Trennlinie schliesst die Zeile ab, sie eröffnet sie nicht** – die eröffnende
  // gehört dem Ausschnitt selbst (`section`). Mit `border-t` an der Zeile stünden am
  // Anfang der Liste zwei Haarlinien 4 px übereinander; solange darüber noch ein
  // Gruppen-Kopf stand, fiel das nicht auf.
  return (
    <div className="border-b border-border-1">
      <div
        role="button"
        tabIndex={0}
        onClick={toggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
        className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2 cursor-pointer"
      >
        <ChevronRight
          size={13}
          className="text-fg-4 transition-transform"
          style={{ transform: shown ? 'rotate(90deg)' : 'none', flex: 'none' }}
        />
        <ObjId value={row.object_id} />
        <span className="ix-tnum text-[13px] whitespace-nowrap">{sum(states)}</span>
      </div>

      {shown && (
        <div className="pb-3 pl-6">
          {/* Genau der Zustand dieser Gruppe – nie «alle»: die Nummern der anderen
              stehen in ihrer eigenen Gruppe, und zweimal dieselbe Nummer zu zeigen
              hiesse, die Aufteilung wieder aufzuheben. */}
          <UnitNumbers
            objectId={row.object_id}
            statuses={[status]}
            quantity={sum(states)}
            dense
          />
        </div>
      )}
    </div>
  );
}
