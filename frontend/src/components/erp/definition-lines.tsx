'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Boxes, ChevronDown, GitBranch, Package, Plus, Sprout, Trash2, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleOption, UnitOption } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { IconSwitch, inputCls } from '@/components/erp/fields';
import { UnitNumber } from '@/components/erp/unit-number';
import { statusCfg, statusLabel } from '@/lib/process-status';

/**
 * **Der Definitionsbereich** – was dieser Auftrag bearbeitet, oberhalb des Start-Symbols.
 *
 * Eine Zeile beantwortet drei Fragen, und zwar **in dieser Reihenfolge**: welcher
 * Artikel, wie viele Einzelinstanzen, und woher sie kommen. Die Reihenfolge ist nicht
 * Geschmack – ohne Artikel ist die Menge nicht deutbar (Einzelserialisierung oder
 * Charge?), und ohne Menge ist die Herkunft nicht entscheidbar (welche Stücke denn?).
 * Darum ist jedes Feld gesperrt, bis das davor beantwortet ist.
 *
 * **Die Menge referenziert immer exakt Einzelinstanzen.** Menge 3 heisst: danach laufen
 * genau 3 Einzelinstanzen im Prozess. Was das an Datensätzen bedeutet, entscheidet die
 * Serialisierung des Artikels und steht als Satz unter der Zeile – geraten wird nichts.
 */

export const NEU = 'neu';
export const LAGER = 'lager';

/**
 * **Ein gewähltes Stück – und wo es lag, als es gewählt wurde.**
 *
 * Ein Entwurf lebt im Browser, die Freigabe passiert später. Dazwischen kann jemand
 * anders dasselbe Stück nehmen. `fromOrder` ist darum die **Aussage** dieser Auswahl
 * («war frei» ↔ «kam aus Auftrag N»); der Server prüft sie bei der Freigabe und bricht
 * ab, statt still etwas anderes zu tun als gewollt.
 */
export interface UnitPick {
  number: string;
  /** Objektnummer des Auftrags, in dem das Stück bei der Auswahl lief. `null` = frei. */
  fromOrder: number | null;
}

export interface DefinitionLine {
  /** Lokale Nummer – die Zeile existiert nur im Browser, bis der Auftrag freigegeben wird. */
  key: number;
  articleObjectId: number | null;
  quantity: number;
  /**
   * **Die Herkunft hat keinen dritten Wert** (Testnotiz zur Vorauswahl «Lager»).
   *
   * Sie war einmal `… | null`, angezeigt wurde aber `origin ?? LAGER`: der Regler stand
   * auf «Lager», der Zustand sagte «nichts». Alles, was an `origin === LAGER` hing –
   * die Instanz-Auswahl und damit die FIFO-Vorauswahl – lief deshalb nicht an, und die
   * Zeile fiel beim Absenden aus dem Nutzdatensatz («keine Einzelinstanz gewählt»).
   * Erreichbar wurde der Zustand nur über den Umweg *einmal umschalten und zurück*.
   *
   * Ein angezeigter Zustand, den es in den Daten nicht gibt, ist kein Vorzustand,
   * sondern ein Widerspruch. Darum ist die Vorauswahl jetzt **der Wert selbst**.
   */
  origin: typeof NEU | typeof LAGER;
  units: UnitPick[];
  /**
   * **Die Rückführung** (Abweichungsauftrag §3.3/§3.4): kehrt ein Stück, das aus einem
   * laufenden Auftrag kommt, dorthin zurück? Standard ja – das ist der Normalfall
   * (nochmal kontrollieren, nacharbeiten). Aus ist die Aussonderung.
   */
  returns: boolean;
}

export function emptyLine(key: number): DefinitionLine {
  return { key, articleObjectId: null, quantity: 1, origin: LAGER, units: [], returns: true };
}

/** Was diese Zeile an den Server schickt. Unvollständige Zeilen bleiben draussen. */
export function toPayload(lines: DefinitionLine[]) {
  return lines
    .filter((l) => l.articleObjectId !== null)
    .map((l) => ({
      article_object_id: l.articleObjectId as number,
      quantity: l.quantity,
      origin: l.origin,
      units: l.origin === LAGER
        ? l.units.map((u) => ({ number: u.number, from_order: u.fromOrder }))
        : [],
      returns: l.returns,
    }));
}

export function DefinitionLines({ lines, setLines, onArticlesLoaded, refreshKey = 0 }: {
  lines: DefinitionLine[];
  setLines: (l: DefinitionLine[]) => void;
  /** Meldet die Artikelliste nach oben – der Entwurf spiegelt daraus die Vorlage. */
  onArticlesLoaded?: (options: ArticleOption[]) => void;
  /**
   * **Die Auswahl neu gegen die Wirklichkeit halten.** Wird hochgezählt, wenn die
   * Freigabe abbricht, weil ein gewähltes Stück inzwischen woanders läuft: dann holt der
   * Picker die Stückliste neu und zieht die **beobachtete Herkunft** der gewählten Stücke
   * nach. Der Mensch sieht damit, was sich geändert hat, und entscheidet erneut – statt
   * dass die Freigabe still etwas anderes tut als gewollt.
   */
  refreshKey?: number;
}) {
  const [articles, setArticles] = useState<ArticleOption[] | null>(null);

  useEffect(() => {
    api.getArticleOptions()
      .then((a) => { setArticles(a); onArticlesLoaded?.(a); })
      .catch(() => setArticles([]));
    // Absichtlich nur beim Mounten: die Liste ändert sich während einer Anlage nicht.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const patch = useCallback((key: number, next: Partial<DefinitionLine>) => {
    setLines(lines.map((l) => (l.key === key ? { ...l, ...next } : l)));
  }, [lines, setLines]);

  const hasNew = lines.some((l) => l.origin === NEU);

  return (
    <div className="rounded-ds-lg" style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 14 }}>
      <div className="flex items-center gap-2 mb-2">
        <Boxes size={14} style={{ color: 'var(--fg-3)' }} />
        <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--fg-3)' }}>
          Definition
        </span>
      </div>
      <p className="text-xs mb-3" style={{ color: 'var(--fg-3)' }}>
        Was bearbeitet dieser Auftrag? Ohne Definition kein Start.
      </p>

      <div className="flex flex-col gap-2">
        {lines.map((line) => (
          <LineRow
            key={line.key}
            line={line}
            articles={articles}
            multi={lines.length > 1}
            refreshKey={refreshKey}
            onChange={(next) => patch(line.key, next)}
            onRemove={() => setLines(lines.filter((l) => l.key !== line.key))}
          />
        ))}
      </div>

      {/* **«Neu» steht für sich allein** (Testnotiz #693): ein Erzeugungsauftrag fährt die
          Vorlage genau dieses Artikels, und ihr Versionsstempel gilt nur für seine Stücke.
          Die Regel liest sich von beiden Enden gleich – darum ist hier der Knopf weg, und
          in der Zeile ist «Neu» gesperrt, sobald es eine zweite gibt. Durchgesetzt wird
          sie serverseitig (`process._assert_single_new`); dies ist die Anzeige davon. */}
      {!hasNew && (
        <button
          type="button"
          onClick={() => setLines([...lines, emptyLine((lines[lines.length - 1]?.key ?? 0) + 1)])}
          className="mt-2 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
          style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}
        >
          <Plus size={12} /> Zeile
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Eine Zeile
// ─────────────────────────────────────────────────────────────────────────────

function LineRow({ line, articles, multi, refreshKey, onChange, onRemove }: {
  line: DefinitionLine;
  articles: ArticleOption[] | null;
  /** Gibt es mehr als eine Zeile? Dann ist «Neu» keine Option mehr (#693). */
  multi: boolean;
  refreshKey: number;
  onChange: (next: Partial<DefinitionLine>) => void;
  onRemove: () => void;
}) {
  const article = useMemo(
    () => articles?.find((a) => a.object_id === line.articleObjectId) ?? null,
    [articles, line.articleObjectId],
  );
  const hasArticle = article !== null;
  const hasTemplate = (article?.template_steps ?? 0) > 0;

  return (
    <div className="rounded-ds-lg" style={{ border: '1px solid var(--border-1)', padding: 10 }}>
      <div className="flex flex-wrap items-end gap-2">
        {/* 1 — Artikel. Sperrt alles Weitere, bis er steht. */}
        <label className="flex-1 min-w-[190px]">
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Artikel</span>
          <select
            className={inputCls}
            value={line.articleObjectId ?? ''}
            onChange={(e) => onChange({
              articleObjectId: e.target.value ? Number(e.target.value) : null,
              // Artikelwechsel verwirft die **Auswahl** – sie gehörte zum alten Artikel.
              // Die **Herkunft** bleibt: sie ist eine Entscheidung über diese Zeile, nicht
              // über den Artikel, und sie zurückzusetzen hiesse den Regler auf einen Wert
              // zu stellen, den es nicht gibt.
              units: [],
            })}
          >
            <option value="">— wählen —</option>
            {articles?.map((a) => (
              <option key={a.object_id} value={a.object_id}>
                {formatObjectId(a.object_id)} · {a.name}
              </option>
            ))}
          </select>
        </label>

        {/* 2 — Menge. Immer exakt Einzelinstanzen. */}
        <label style={{ width: 96 }}>
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Menge</span>
          <input
            className={inputCls}
            inputMode="numeric"
            value={line.quantity}
            disabled={!hasArticle}
            data-tip={hasArticle ? undefined : 'Zuerst den Artikel wählen – ohne ihn ist die Menge nicht deutbar.'}
            onChange={(e) => {
              const raw = e.target.value.replace(/[^0-9]/g, '');
              onChange({ quantity: raw ? Number(raw) : 0, units: [] });
            }}
          />
        </label>

        {/* 3 — Herkunft. **Derselbe Schiebe-Regler wie die Mengeneinheit am Artikel**
            (Testnotiz #694): zwei sich ausschliessende Antworten, und dass sie einander
            ausschliessen, zeigt die Bewegung des Reiters statt zweier gleich aussehender
            Knöpfe. Dieselbe Komponente, nicht nachgebaut. */}
        <div>
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Herkunft</span>
          <IconSwitch<typeof NEU | typeof LAGER>
            value={line.origin}
            onChange={(v) => onChange(v === NEU
              ? { origin: NEU, units: [] }
              : { origin: LAGER })}
            options={[
              {
                value: NEU,
                // **Sprossen statt Karton** (#694): «Neu» heisst «entsteht hier», nicht
                // «wird geliefert». Ein Paket-Symbol sagte dasselbe wie «Lager».
                icon: Sprout,
                label: 'Neu',
                disabled: !hasArticle || !hasTemplate || multi,
                hint:
                  !hasArticle ? 'Zuerst den Artikel wählen.'
                    : multi
                      ? '«Neu» steht für sich allein – ein Erzeugungsauftrag fährt die Vorlage genau dieses Artikels. Für den zweiten Artikel einen eigenen Auftrag anlegen.'
                      : !hasTemplate
                        ? 'Dieser Artikel hat keinen Erzeugungsprozess. «Neu» ist erst wählbar, wenn am Artikel unter «Spezifikation» mindestens ein Modul steht.'
                        : 'Die Einzelinstanzen entstehen bei der Freigabe.',
              },
              {
                value: LAGER,
                icon: Package,
                label: 'Lager',
                disabled: !hasArticle,
                hint: hasArticle
                  ? 'Bestehende Einzelinstanzen auswählen. Hier entsteht keine neue Nummer.'
                  : 'Zuerst den Artikel wählen.',
              },
            ]}
          />
        </div>

        <button
          type="button"
          onClick={onRemove}
          className="flex items-center justify-center rounded"
          style={{ width: 30, height: 30, color: 'var(--danger)' }}
          data-tip="Zeile entfernen"
          aria-label="Zeile entfernen"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {/* Was die Menge an Datensätzen bedeutet – gesagt, nicht geraten. */}
      {hasArticle && line.origin === NEU && line.quantity > 0 && (
        <p className="mt-2 text-[11px]" style={{ color: 'var(--fg-3)' }}>
          {article!.serialization === 'batch'
            ? `Eine Instanz mit ${line.quantity} Einzelinstanzen (${line.quantity === 1 ? '-1' : `-1 … -${line.quantity}`}).`
            : `${line.quantity} Instanzen mit je einer Einzelinstanz (-1).`}
        </p>
      )}

      {hasArticle && line.origin === LAGER && (
        <StockPicker
          articleObjectId={article!.object_id}
          quantity={line.quantity}
          refreshKey={refreshKey}
          chosen={line.units}
          onChange={(units) => onChange({ units })}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Herkunft «Lager»: konkrete bestehende Einzelinstanzen
// ─────────────────────────────────────────────────────────────────────────────

/**
 * **FIFO als Vorschlag, nicht als Zwang.** Die ältesten `quantity` Stücke sind
 * vorausgewählt – sichtbar und einzeln abwählbar. Eine unsichtbare Automatik wäre hier
 * das Schlimmste: man sähe erst nach der Freigabe, welche Stücke es getroffen hat.
 *
 * Gesperrte Stücke werden **gezeigt**, nicht weggefiltert, und nennen den Grund.
 */
function StockPicker({ articleObjectId, quantity, chosen, refreshKey, onChange }: {
  articleObjectId: number; quantity: number; chosen: UnitPick[]; refreshKey: number;
  onChange: (picks: UnitPick[]) => void;
}) {
  const [options, setOptions] = useState<UnitOption[] | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let dead = false;
    setOptions(null);
    api.getUnitOptions(articleObjectId)
      .then((o) => { if (!dead) setOptions(o); })
      .catch(() => { if (!dead) setOptions([]); });
    return () => { dead = true; };
  }, [articleObjectId, refreshKey]);

  // **Der Vorschlag hängt an seiner Grundlage, nicht an einem Ereignis.**
  //
  // Er lief nur beim Eintreffen der Liste. Änderte man danach die Menge – was die
  // Auswahl verwirft, weil sie zur alten Menge gehörte –, kam kein neuer Vorschlag:
  // «0 von 3», und jedes Stück musste von Hand gewählt werden. Seine Grundlage sind
  // die vorhandenen Stücke UND die verlangte Menge; ändert sich eine davon, wird neu
  // vorgeschlagen. Was der Mensch gewählt hat, wird dabei nie überschrieben (`chosen`
  // ist bewusst keine Abhängigkeit): ein Vorschlag entsteht nur ins Leere.
  useEffect(() => {
    if (!options || chosen.length) return;
    // **Nie ein Stück, das in einem anderen Auftrag läuft.** Es zu nehmen ist eine
    // Entscheidung – daraus wird eine Abweichung, die einem laufenden Auftrag sein
    // Material entzieht. Das darf nie die Voreinstellung sein.
    const free = options.filter((o) => o.available && !o.in_order);
    const fifo = free.slice(0, quantity).map((o) => ({ number: o.number, fromOrder: null }));
    if (fifo.length) onChange(fifo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, quantity]);

  // **Die beobachtete Herkunft wird nachgezogen, die Auswahl nicht.** Kommt die Liste
  // neu (Artikelwechsel oder nach einem Freigabe-Abbruch), kann ein gewähltes Stück
  // inzwischen woanders laufen. Dann ändert sich, was der Klick bewirken WÜRDE – und das
  // gehört vor den Klick. Was der Mensch gewählt hat, bleibt; nur was es nicht mehr gibt,
  // fällt weg.
  useEffect(() => {
    if (!options || !chosen.length) return;
    const holder = new Map(options.map((o) => [o.number, o.in_order ?? null]));
    const next = chosen
      .filter((u) => holder.has(u.number))
      .map((u) => ({ number: u.number, fromOrder: holder.get(u.number) ?? null }));
    const same = next.length === chosen.length
      && next.every((u, i) => u.number === chosen[i].number && u.fromOrder === chosen[i].fromOrder);
    if (!same) onChange(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options]);

  const picked = new Set(chosen.map((u) => u.number));
  const enough = chosen.length === quantity;
  // **Die Rückführung ist nur eine Frage, wenn es etwas zurückzugeben gibt.** Ein freies
  // Stück kommt aus keinem Auftrag – eine Wahl anzubieten, die nichts bewirkt, wäre eine
  // Behauptung, hier passiere etwas.
  const borrowed = chosen.filter((u) => u.fromOrder !== null);

  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {chosen.map((u) => (
          <span key={u.number}
            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={u.fromOrder === null
              ? { background: 'var(--success-bg)', color: 'var(--success)' }
              : { background: 'var(--warning-bg)', color: 'var(--warning)' }}
            data-tip={u.fromOrder === null
              ? 'War bei der Auswahl frei'
              : `Kommt aus Auftrag ${formatObjectId(u.fromOrder)} – daraus wird eine Abweichung`}>
            <UnitNumber value={u.number} />
            <button type="button"
              onClick={() => onChange(chosen.filter((c) => c.number !== u.number))}
              style={{ opacity: 0.6 }} aria-label={`${u.number} entfernen`}>
              <X size={11} />
            </button>
          </span>
        ))}
        <button type="button" onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
          style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}>
          <ChevronDown size={12} /> Auswählen
        </button>
        <span className="text-[11px]" style={{ color: enough ? 'var(--success)' : 'var(--warning)' }}>
          {chosen.length} von {quantity}
        </span>
      </div>

      {/*
        **Ob es zurückgeht, steht am Bild – nicht hier** (Auftrag §5). Es war ein
        Knopfpaar an dieser Stelle; die Aussage stand damit woanders als ihre Wirkung,
        und man sah erst nach der Freigabe, was daraus wird. Jetzt steht der Quell-Auftrag
        selbst in der linken Spur (Vorschau, §2), mit der Rückführungslinie, die entstehen
        würde – ein Klick auf ihn schaltet sie an und aus. Hier bleibt die Tatsache, aus
        der die Frage überhaupt entsteht.
      */}
      {borrowed.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-ds-lg px-2.5 py-2"
          style={{ background: 'var(--warning-bg)' }}>
          <GitBranch size={13} style={{ color: 'var(--warning)' }} />
          <span className="text-xs" style={{ color: 'var(--fg-2)' }}>
            {borrowed.length === 1 ? 'Ein Stück läuft' : `${borrowed.length} Stücke laufen`} in
            einem anderen Auftrag – dieser hier wird eine <strong>Abweichung</strong>.
          </span>
        </div>
      )}

      {open && (
        <div className="mt-2 max-h-56 overflow-auto" style={{ borderTop: '1px solid var(--border-1)' }}>
          {options === null && <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>Lädt …</p>}
          {options?.length === 0 && (
            <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>
              Von diesem Artikel gibt es keine Einzelinstanzen. Lege im Reiter «Bestand»
              des Artikels eine Instanz an – oder wähle «Neu».
            </p>
          )}
          {options?.map((o) => {
            const taken = picked.has(o.number);
            // **Ein laufendes Stück ist wählbar** – daraus wird eine Abweichung
            // (Abweichungsauftrag §3.5). Gesagt wird es trotzdem: was der Klick bewirkt,
            // gehört vor den Klick, nicht danach.
            const why = o.in_order
              ? `Läuft in Auftrag ${formatObjectId(o.in_order)} – daraus wird eine Abweichung`
              : !o.available ? `Steht auf «${statusLabel(o.status)}»` : undefined;
            return (
              <button
                key={o.number}
                type="button"
                disabled={!o.available}
                onClick={() => onChange(taken
                  ? chosen.filter((c) => c.number !== o.number)
                  : [...chosen, { number: o.number, fromOrder: o.in_order ?? null }])}
                data-tip={why}
                className="w-full flex items-center gap-2 text-left text-xs py-1.5 px-1 disabled:opacity-45"
                style={{ borderBottom: '1px solid var(--border-1)',
                         background: taken ? 'var(--success-bg)' : undefined }}
              >
                <span style={{ minWidth: 110 }}><UnitNumber value={o.number} /></span>
                <span className="flex-1 truncate" style={{ color: 'var(--fg-3)' }}>{o.article_name}</span>
                <span style={{ color: statusCfg(o.status).color }}>{statusLabel(o.status)}</span>
                {o.in_order && (
                  <span className="inline-flex items-center gap-1 ix-tnum"
                    style={{ color: 'var(--warning)' }}>
                    <GitBranch size={11} />{formatObjectId(o.in_order)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
