'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Boxes, ChevronDown, GitBranch, Package, PackagePlus, Plus, Trash2, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleOption, UnitOption } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { inputCls } from '@/components/erp/fields';
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

export interface DefinitionLine {
  /** Lokale Nummer – die Zeile existiert nur im Browser, bis der Auftrag freigegeben wird. */
  key: number;
  articleObjectId: number | null;
  quantity: number;
  origin: typeof NEU | typeof LAGER | null;
  unitNumbers: string[];
  /**
   * **Die Rückführung** (Abweichungsauftrag §3.3/§3.4): kehrt ein Stück, das aus einem
   * laufenden Auftrag kommt, dorthin zurück? Standard ja – das ist der Normalfall
   * (nochmal kontrollieren, nacharbeiten). Aus ist die Aussonderung.
   */
  returns: boolean;
}

export function emptyLine(key: number): DefinitionLine {
  return { key, articleObjectId: null, quantity: 1, origin: null, unitNumbers: [], returns: true };
}

/** Was diese Zeile an den Server schickt. Unvollständige Zeilen bleiben draussen. */
export function toPayload(lines: DefinitionLine[]) {
  return lines
    .filter((l) => l.articleObjectId !== null && l.origin !== null)
    .map((l) => ({
      article_object_id: l.articleObjectId as number,
      quantity: l.quantity,
      origin: l.origin as string,
      unit_numbers: l.origin === LAGER ? l.unitNumbers : [],
      returns: l.returns,
    }));
}

export function DefinitionLines({ lines, setLines, onArticlesLoaded }: {
  lines: DefinitionLine[];
  setLines: (l: DefinitionLine[]) => void;
  /** Meldet die Artikelliste nach oben – der Entwurf spiegelt daraus die Vorlage. */
  onArticlesLoaded?: (options: ArticleOption[]) => void;
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
            onChange={(next) => patch(line.key, next)}
            onRemove={() => setLines(lines.filter((l) => l.key !== line.key))}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={() => setLines([...lines, emptyLine((lines[lines.length - 1]?.key ?? 0) + 1)])}
        className="mt-2 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
        style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}
      >
        <Plus size={12} /> Zeile
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Eine Zeile
// ─────────────────────────────────────────────────────────────────────────────

function LineRow({ line, articles, onChange, onRemove }: {
  line: DefinitionLine;
  articles: ArticleOption[] | null;
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
              // Artikelwechsel verwirft die Auswahl: sie gehörte zum alten Artikel.
              origin: null, unitNumbers: [],
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
              onChange({ quantity: raw ? Number(raw) : 0, unitNumbers: [] });
            }}
          />
        </label>

        {/* 3 — Herkunft. */}
        <div>
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Herkunft</span>
          <div className="flex gap-1">
            <OriginBtn
              icon={PackagePlus}
              label="Neu"
              active={line.origin === NEU}
              disabled={!hasArticle || !hasTemplate}
              hint={
                !hasArticle ? 'Zuerst den Artikel wählen.'
                  : !hasTemplate
                    ? 'Dieser Artikel hat keinen Erzeugungsprozess. «Neu» ist erst wählbar, wenn am Artikel unter «Spezifikation» mindestens ein Modul steht.'
                    : 'Die Einzelinstanzen entstehen bei der Freigabe.'
              }
              onClick={() => onChange({ origin: NEU, unitNumbers: [] })}
            />
            <OriginBtn
              icon={Package}
              label="Lager"
              active={line.origin === LAGER}
              disabled={!hasArticle}
              hint={hasArticle
                ? 'Bestehende Einzelinstanzen auswählen. Hier entsteht keine neue Nummer.'
                : 'Zuerst den Artikel wählen.'}
              onClick={() => onChange({ origin: LAGER })}
            />
          </div>
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
          chosen={line.unitNumbers}
          onChange={(unitNumbers) => onChange({ unitNumbers })}
          returns={line.returns}
          onReturns={(returns) => onChange({ returns })}
        />
      )}
    </div>
  );
}

function OriginBtn({ icon: Icon, label, active, disabled, hint, onClick }: {
  icon: React.ElementType; label: string; active: boolean; disabled: boolean;
  hint: string; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-tip={hint}
      // Der Tooltip läuft über CSS-generierten Inhalt (`content: attr(data-tip)`), und
      // den zählt Chromium in den Accessible Name. Ohne diese Zeile hiesse der Knopf für
      // einen Screenreader «Neu Dieser Artikel hat keinen Erzeugungsprozess …» – die
      // Erklärung wäre der Name. Sie gehört in die Beschreibung, nicht in den Namen.
      aria-label={label}
      className="inline-flex items-center gap-1.5 text-xs rounded-ds-lg disabled:opacity-45"
      style={{
        height: 32, padding: '0 10px',
        border: `1px solid ${active ? 'var(--accent-ink)' : 'var(--border-2)'}`,
        background: active ? 'var(--accent-soft)' : 'var(--bg-1)',
        color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
      }}
    >
      <Icon size={13} />
      {label}
    </button>
  );
}

/** Die zwei Wege der Rückführung. Dieselbe Form wie die Herkunft – es ist dieselbe Art
 *  Entscheidung: zwei sich ausschliessende Antworten, beide mit Grund im Hover. */
function ReturnBtn({ active, label, hint, onClick }: {
  active: boolean; label: string; hint: string; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-tip={hint}
      aria-label={label}
      className="inline-flex items-center gap-1.5 text-xs rounded-ds-lg"
      style={{
        height: 28, padding: '0 9px',
        border: `1px solid ${active ? 'var(--accent-ink)' : 'var(--border-2)'}`,
        background: active ? 'var(--accent-soft)' : 'var(--bg-1)',
        color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
      }}
    >
      {label}
    </button>
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
function StockPicker({ articleObjectId, quantity, chosen, onChange, returns, onReturns }: {
  articleObjectId: number; quantity: number; chosen: string[];
  onChange: (numbers: string[]) => void;
  returns: boolean;
  onReturns: (value: boolean) => void;
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
  }, [articleObjectId]);

  // FIFO-Vorauswahl: die ältesten verfügbaren Stücke, sobald die Liste da ist.
  useEffect(() => {
    if (!options || chosen.length) return;
    const fifo = options.filter((o) => o.available).slice(0, quantity).map((o) => o.number);
    if (fifo.length) onChange(fifo);
    // Nur beim ersten Eintreffen der Liste – danach entscheidet der Mensch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options]);

  const picked = new Set(chosen);
  const enough = chosen.length === quantity;
  // **Die Rückführung ist nur eine Frage, wenn es etwas zurückzugeben gibt.** Ein freies
  // Stück kommt aus keinem Auftrag – eine Wahl anzubieten, die nichts bewirkt, wäre eine
  // Behauptung, hier passiere etwas.
  const borrowed = (options ?? []).filter((o) => picked.has(o.number) && o.in_order);

  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {chosen.map((n) => (
          <span key={n} className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ix-tnum"
            style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
            {n}
            <button type="button" onClick={() => onChange(chosen.filter((c) => c !== n))}
              style={{ opacity: 0.6 }} aria-label={`${n} entfernen`}>
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

      {borrowed.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-ds-lg px-2.5 py-2"
          style={{ background: 'var(--warning-bg)' }}>
          <GitBranch size={13} style={{ color: 'var(--warning)' }} />
          <span className="text-xs flex-1 min-w-[180px]" style={{ color: 'var(--fg-2)' }}>
            {borrowed.length === 1 ? 'Ein Stück läuft' : `${borrowed.length} Stücke laufen`} in
            einem anderen Auftrag – dieser hier wird eine <strong>Abweichung</strong>.
          </span>
          <div className="flex gap-1">
            <ReturnBtn active={returns} onClick={() => onReturns(true)}
              label="kehrt zurück"
              hint="Nach dem Durchlauf geht das Stück an genau die Stelle zurück, an der es ausgeschert ist. Der andere Auftrag wartet solange." />
            <ReturnBtn active={!returns} onClick={() => onReturns(false)}
              label="bleibt hier"
              hint="Das Stück kehrt nicht zurück (z. B. Aussonderung). Der andere Auftrag läuft mit weniger Stücken weiter und wartet nicht." />
          </div>
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
                onClick={() => onChange(taken ? chosen.filter((c) => c !== o.number) : [...chosen, o.number])}
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
