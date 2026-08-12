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
 * dieselbe Leiste, dieselbe Legende, dieselbe Aufteilung in Bestand/Historie, dasselbe
 * Verhalten beim Klick auf ein Segment. Eine zweite Fassung «nur für die Instanz» hätte
 * beim ersten neuen Zustand anders ausgesehen.
 *
 * **Kein Filter.** Ein Filter versteckt, was er nicht zeigt; hier ist die Aufteilung
 * selbst das Bedienelement – ein Segment anklicken heisst «zeig mir diese Nummern», der
 * Rest bleibt sichtbar.
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

  return (
    <Card>
      {/* **Die Leiste, und darunter ihre Legende — das sind die Gruppen selbst.**
          Eine eigene Legende stand einmal dazwischen: Punkt, Wort, Menge je Zustand –
          und drei Zeilen tiefer noch einmal dasselbe, nur anklickbar. Zwei Anzeigen
          derselben Zahl auf so engem Raum sind keine zwei Auskünfte (Testnotiz #716).
          Geblieben ist die, mit der man arbeitet. */}
      <div className="pb-1">
        <StockBar states={states} height={10} />
      </div>

      {unknown.length > 0 && <UnknownStates states={unknown} />}

      {states.map((s) => (
        <Block key={s.status} state={s}>
          {scope.kind === 'instance' ? (
            // An der Instanz sind die Zeilen direkt die Einzelinstanzen – dieselbe
            // Komponente, die am Artikel eine Instanz-Zeile aufklappt.
            <UnitNumbers
              objectId={scope.record.object_id}
              statuses={[s.status]}
              quantity={s.quantity}
            />
          ) : (
            <>
              {rows
                .filter((r) => r.states.some((x) => x.status === s.status))
                .map((r) => <InstanceRow key={r.id} row={r} status={s.status} />)}
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
        </Block>
      ))}
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

/**
 * **Eine Gruppe je Zustand** — Punkt, Wort, Menge; darunter, was darin liegt.
 *
 * Dieses Werkzeug **zählt keinen Status auf**, weder für die Gruppierung noch für die
 * Reihenfolge noch für die Farbe. Alles drei kommt vom Status selbst:
 *
 *   Welche Gruppen  die Zustände, die wirklich vorkommen (`states` vom Server)
 *   Reihenfolge     die Position im `CATALOG` – dieselbe, die Leiste und Legende ordnet
 *   Farbe           der Ampelton des Status (`statusCfg`)
 *   Zugeklappt      ob er zur **Historie** zählt (`stock`)
 *
 * Kommt morgen ein Zustand dazu, erscheint er hier ohne eine Zeile Code – an seiner
 * Stelle im Lebenszyklus, in seiner Farbe. Vorher waren es zwei feste Blöcke («Bestand»
 * und «Historie»); ein neuer Zustand verschwand darin, statt sich zu zeigen.
 *
 * **Die Reihenfolge ist die des Lebenszyklus**, weil der Katalog sie so führt:
 * Freigegeben → Im Prozess → Gesperrt → Verschrottet. Sie steht dort einmal und gilt für
 * jede Ansicht, die Zustände nebeneinander zeigt.
 */
function Block({ state, children }: { state: StockState; children: React.ReactNode }) {
  const cfg = statusCfg(state.status);
  // **Zugeklappt startet ALLES** (Testnotiz #716) – dieselbe Regel wie beim
  // Prozessschrittmodul. Eine Gruppe, die von selbst offensteht, entscheidet für den
  // Betrachter, was ihn interessiert; die Zahl im Kopf sagt ihm ohnehin, ob sich das
  // Aufklappen lohnt. (Vorher hing es an `stock`: der lebende Bestand stand offen, die
  // Historie zu – bei einem Artikel mit genau einem Zustand also immer offen.)
  const [shown, setShown] = useState(false);
  return (
    <section className="border-t border-border-1">
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        className="flex w-full items-center gap-2 py-2.5 text-left"
      >
        <ChevronRight
          size={14}
          className="text-fg-4 transition-transform"
          style={{ transform: shown ? 'rotate(90deg)' : 'none', flex: 'none' }}
        />
        <span aria-hidden className="rounded-full" style={{
          width: 7, height: 7, flex: 'none', background: cfg.color,
        }} />
        <span className="text-[13px] font-medium">{cfg.label}</span>
        <span className="ix-tnum text-[13px] text-fg-3">{state.quantity}</span>
      </button>
      {shown && <div className="flex flex-col pb-4">{children}</div>}
    </section>
  );
}

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

  return (
    <div className="border-t border-border-1">
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
