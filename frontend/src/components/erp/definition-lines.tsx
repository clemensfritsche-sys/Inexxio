'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, GitBranch, Package, Plus, ScanLine, Sprout, Trash2, X } from 'lucide-react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { qk, useSettled } from '@/lib/queries';
import { useOutside } from '@/lib/use-outside';
import type { ArticleOption, UnitChoices, UnitOption } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { FieldAction, IconSwitch, inputCls } from '@/components/erp/controls';
import { Input } from '@/components/form/field';
import { StatusDot } from '@/components/erp/fields';
import { ObjectSelect } from '@/components/erp/object-select';
import { UnitNumber } from '@/components/erp/unit-number';
import { useScan } from '@/components/scan/scan-provider';
import { statusCfg, statusLabel } from '@/lib/process-status';
import { VERBAUT, VERKAUFT } from '@/lib/status-catalog';
import { Skeleton } from './skeleton';

/**
 * **Der Definitionsbereich** – was dieser Auftrag bearbeitet, oberhalb des Start-Symbols.
 * Eine Zeile fragt **in dieser Reihenfolge**: Artikel → Menge → Herkunft; jedes Feld ist
 * gesperrt, bis das davor beantwortet ist. Die Menge zählt immer exakt Einzelinstanzen.
 */

/** Wie viele Stücke eine Seite trägt. */
const PAGE = 60;

export const NEU = 'neu';
export const LAGER = 'lager';

/**
 * **Ein gewähltes Stück – und wo es lag, als es gewählt wurde.** `fromOrder` ist die
 * Aussage der Auswahl; der Server prüft sie bei der Freigabe und bricht sonst ab.
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
  /** **Die Herkunft hat keinen dritten Wert** – die Vorauswahl ist der Wert selbst. */
  origin: typeof NEU | typeof LAGER;
  units: UnitPick[];
  /** **Die Rückführung** (Abweichungsauftrag §3.3/§3.4): kehrt ein geliehenes Stück zurück? Standard ja. */
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

export function DefinitionLines({ lines, setLines, refreshKey = 0,
                                  perUnit = false }: {
  lines: DefinitionLine[];
  setLines: (l: DefinitionLine[]) => void;
  /**
   * **Dieselbe Zeile als Stückliste** – Menge **je Einzelinstanz**, ohne Herkunft und ohne
   * Stück-Auswahl: welche Stücke verbaut werden, wählt der Lagerist beim Ausführen (§4).
   */
  perUnit?: boolean;
  /** Hochgezählt, wenn die Freigabe abbricht: der Picker lädt neu und zieht die
   *  beobachtete Herkunft der gewählten Stücke nach. */
  refreshKey?: number;
}) {
  // Nur die gewählten Artikel – ihre Angaben sperren und begründen «Neu».
  const [chosen, setChosen] = useState<Record<number, ArticleOption>>({});

  const remember = useCallback((o: ArticleOption) => {
    setChosen((prev) => (prev[o.object_id] ? prev : { ...prev, [o.object_id]: o }));
  }, []);

  const patch = useCallback((key: number, next: Partial<DefinitionLine>) => {
    setLines(lines.map((l) => (l.key === key ? { ...l, ...next } : l)));
  }, [lines, setLines]);

  const hasNew = lines.some((l) => l.origin === NEU);

  return (
    <div className="flex flex-col gap-2">
      {lines.map((line) => (
        <LineRow
          key={line.key}
          line={line}
          article={line.articleObjectId != null ? chosen[line.articleObjectId] ?? null : null}
          onArticle={remember}
          multi={lines.length > 1}
          refreshKey={refreshKey}
          perUnit={perUnit}
          onChange={(next) => patch(line.key, next)}
          onRemove={() => setLines(lines.filter((l) => l.key !== line.key))}
        />
      ))}

      {/* **«Neu» steht für sich allein** (`process._assert_single_new`): kein Knopf für eine
          zweite Zeile, und «Neu» ist gesperrt, sobald es eine zweite gibt. */}
      {(perUnit || !hasNew) && (
        <button
          type="button"
          onClick={() => setLines([...lines, emptyLine((lines[lines.length - 1]?.key ?? 0) + 1)])}
          className="self-center inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
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

/**
 * **Eine Menge, die nicht null werden kann**: während des Tippens lebt die Eingabe lokal
 * (leer erlaubt), übernommen wird beim Verlassen mit Untergrenze 1. Die Obergrenze nennt
 * der Server (`Verbrauch.MAX_PER_UNIT`).
 */
function QuantityInput({ value, disabled, onChange }: {
  value: number; disabled: boolean; onChange: (n: number) => void;
}) {
  const [text, setText] = useState(String(value));
  // Der Aufrufer ist die Wahrheit: ändert sich die Zeile von aussen, folgt die Anzeige.
  useEffect(() => { setText(String(value)); }, [value]);

  function commit() {
    const n = Math.max(1, Number(text.replace(/[^0-9]/g, '')) || 0);
    setText(String(n));
    if (n !== value) onChange(n);
  }

  return (
    <Input
      name="quantity"
      className={inputCls}
      inputMode="numeric"
      value={text}
      disabled={disabled}
      data-tip={disabled ? 'Zuerst den Artikel wählen – ohne ihn ist die Menge nicht deutbar.' : undefined}
      onChange={(v) => setText(v.replace(/[^0-9]/g, ''))}
      onBlur={commit}
      onEnter={commit}
    />
  );
}

function LineRow({ line, article, onArticle, multi, refreshKey, perUnit, onChange, onRemove }: {
  line: DefinitionLine;
  /** Der gewählte Artikel, soweit bekannt – er trägt die Angaben, aus denen «Neu» folgt. */
  article: ArticleOption | null;
  /** Ein neu aufgelöster Artikel wandert nach oben: dort liegt die eine Ablage. */
  onArticle: (o: ArticleOption) => void;
  /** Gibt es mehr als eine Zeile? Dann ist «Neu» keine Option mehr. */
  multi: boolean;
  refreshKey: number;
  /** Stückliste: Menge je Einzelinstanz, keine Herkunft, keine Stück-Auswahl. */
  perUnit: boolean;
  onChange: (next: Partial<DefinitionLine>) => void;
  onRemove: () => void;
}) {
  // Eine vorbelegte Nummer (Shortcut am Artikel) wird einmal aufgelöst – als Query; die
  // Antwort geht einmal in den Entwurf (Query-Daten treiben nie ein Formular).
  const nr = line.articleObjectId;
  const preset = useQuery({
    queryKey: qk.catalog('article', nr),
    queryFn: ({ signal }) => api.getArticleOptions({ objectId: nr! }, { signal }),
    enabled: nr != null && !article,
    meta: { what: 'Artikel' },
  }).data?.[0];
  useEffect(() => {
    if (preset && !article) onArticle(preset);
  }, [preset, article, onArticle]);

  const findArticles = useCallback(
    (q: string) => api.getArticleOptions({ search: q, limit: 20 }),
    [],
  );

  const hasArticle = article !== null;
  const hasTemplate = (article?.template_steps ?? 0) > 0;
  // **Warum «Neu» nicht geht, sagt der Server** (`articles.may_create`).
  const createProblem = article?.create_problem ?? null;

  return (
    <div className="rounded-ds-lg"
      style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 10 }}>
      <div className="flex flex-wrap items-end gap-2">
        {/* 1 — Artikel (`ObjectSelect`); sperrt alles Weitere. Keine Beschriftung: das
            Feld sagt selbst, wonach es fragt. */}
        <div className="flex-1" style={{ minWidth: perUnit ? 190 : 240 }}>
          <ObjectSelect<ArticleOption>
            value={line.articleObjectId}
            selected={article}
            find={findArticles}
            kind="article"
            scanLabel="Artikel"
            onChange={(nr, opt) => {
              if (opt) onArticle(opt);
              onChange({
                articleObjectId: nr,
                // Artikelwechsel verwirft die Auswahl; die Herkunft gehört der Zeile und bleibt.
                units: [],
              });
            }}
          />
        </div>

        {/* 2 — Menge (in der Stückliste je Stück); was sie zählt, steht im Hover. */}
        <label style={{ width: perUnit ? 104 : 96 }}
          data-tip={perUnit
            ? 'Menge je Einzelinstanz – «4» heisst vier Stück je Erzeugnis'
            : 'Menge – wie viele Einzelinstanzen dieser Auftrag bearbeitet'}>
          <QuantityInput
            value={line.quantity}
            disabled={!hasArticle}
            onChange={(n) => onChange({ quantity: n, units: [] })}
          />
        </label>

        {/* 3 — Herkunft: derselbe Schiebe-Regler (`IconSwitch`) wie überall. */}
        <div style={{ display: perUnit ? 'none' : undefined }}>
          <IconSwitch<typeof NEU | typeof LAGER>
            value={line.origin}
            onChange={(v) => onChange(v === NEU
              ? { origin: NEU, units: [] }
              : { origin: LAGER })}
            options={[
              {
                value: NEU,
                // Sprossen: «Neu» heisst «entsteht hier».
                icon: Sprout,
                label: 'Neu',
                disabled: !hasArticle || !hasTemplate || multi || createProblem !== null,
                hint:
                  !hasArticle ? 'Zuerst den Artikel wählen.'
                    : multi
                      ? '«Neu» steht für sich allein – ein Erzeugungsauftrag fährt die Vorlage genau dieses Artikels. Für den zweiten Artikel einen eigenen Auftrag anlegen.'
                      : createProblem
                        ? createProblem
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

      {!perUnit && hasArticle && line.origin === LAGER && (
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
 * **FIFO als Vorschlag, nicht als Zwang**: die ältesten Stücke im Regal sind vorausgewählt,
 * sichtbar und einzeln abwählbar; die Vorauswahl rechnet der Server. `available` = lässt
 * sich nehmen, `in_stock` = liegt im Regal – vorgeschlagen wird nur, was beides ist und in
 * keinem laufenden Auftrag steckt. Gruppiert wie der Bestand (PROCESS_CORE §10.3).
 */
function StockPicker({ articleObjectId, quantity, chosen, refreshKey, onChange }: {
  articleObjectId: number; quantity: number; chosen: UnitPick[]; refreshKey: number;
  onChange: (picks: UnitPick[]) => void;
}) {
  const [query, setQueryText] = useState('');
  const [group, setGroupKey] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  // Filter/Suche fangen wieder vorn an – im selben Schritt, damit es EINE Frage ist.
  const setQuery = (q: string) => { setQueryText(q); setOffset(0); };
  const setGroup = (g: string | null) => { setGroupKey(g); setOffset(0); };
  const scan = useScan();

  // Eine Seite, nicht die Liste; die Suche ist entprellt, die alte Seite steht bis zur neuen.
  const search = useSettled(query.trim());
  const opts = {
    articleObjectId, preselect: quantity, limit: PAGE, offset,
    search: search || undefined, status: group ? [group] : undefined,
  };
  const page: UnitChoices | null = useQuery({
    queryKey: [...qk.unitOptions(opts), refreshKey],
    queryFn: ({ signal }) => api.getUnitOptions(opts, { signal }),
    placeholderData: keepPreviousData,
    meta: { what: 'Stücke im Lager' },
  }).data ?? null;

  // Der Vorschlag füllt nur eine leere Auswahl (`chosen` ist bewusst keine Abhängigkeit).
  const preselect = page?.preselect;
  useEffect(() => {
    if (!preselect?.length || chosen.length) return;
    onChange(preselect.map((number) => ({ number, fromOrder: null })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselect]);

  // **Die beobachtete Herkunft wird nachgezogen, die Auswahl nicht** – nur für Stücke auf
  // dieser Seite (weggefiltert ist nicht verschwunden).
  const units = page?.units;
  useEffect(() => {
    if (!units || !chosen.length) return;
    const here = new Map(units.map((o) => [o.number, o]));
    const next = chosen
      .filter((u) => !here.has(u.number) || here.get(u.number)!.available)
      .map((u) => (here.has(u.number)
        ? { number: u.number, fromOrder: here.get(u.number)!.in_order ?? null }
        : u));
    const same = next.length === chosen.length
      && next.every((u, i) => u.number === chosen[i].number && u.fromOrder === chosen[i].fromOrder);
    if (!same) onChange(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [units]);

  const picked = new Set(chosen.map((u) => u.number));
  const enough = chosen.length === quantity;

  /**
   * ►►► **Offen ist, was noch nicht entschieden ist** ◄◄◄ – abgeleitet (unvollständig = offen),
   * weil der Baum beim ersten geliehenen Stück neu aufgebaut wird (`ProcessColumns`, §8.1c).
   * `touched` ist nur die Übersteuerung von Hand.
   */
  const [touched, setTouched] = useState<boolean | null>(null);
  const open = touched ?? (page !== null && !enough && (page.total ?? 0) > 0);
  // Die Rückführung ist nur eine Frage, wenn es etwas zurückzugeben gibt.
  const borrowed = chosen.filter((u) => u.fromOrder !== null);
  const states = page?.states ?? [];
  const total = page?.total ?? 0;

  function toggle(o: UnitOption) {
    // Wer wählt, will weiterwählen – die Liste bleibt offen.
    setTouched(true);
    // Mehr als verlangt gibt es nicht: ist die Auswahl voll, ersetzt der Klick das zuletzt gewählte.
    const keep = picked.has(o.number) ? chosen
      : chosen.length >= quantity ? chosen.slice(0, Math.max(0, quantity - 1)) : chosen;
    onChange(picked.has(o.number)
      ? chosen.filter((c) => c.number !== o.number)
      : [...keep, { number: o.number, fromOrder: o.in_order ?? null }]);
  }

  // **Ein Klick daneben schliesst die Liste** – wie jede andere Auswahl im Haus.
  // Der Scan-Dialog liegt über der Seite, gehört aber zur Liste (er setzt die Suche).
  const box = useRef<HTMLDivElement>(null);
  useOutside(open, () => setTouched(false), [box], '[role="dialog"]');

  return (
    <div className="mt-2" ref={box}>
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
        <button type="button" onClick={() => setTouched(!open)}
          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
          style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}>
          <ChevronDown size={12} /> Auswählen
        </button>
        <span className="text-[11px]" style={{ color: enough ? 'var(--success)' : 'var(--warning)' }}>
          {chosen.length} von {quantity}
        </span>
      </div>

      {/* Ob es zurückgeht, schaltet man am Bild (Rückführungslinie); hier steht nur die Tatsache. */}
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
        <div className="mt-2" style={{ borderTop: '1px solid var(--border-1)' }}>
          {/* ►►► **Die Kamera sitzt IM Feld** (wie `ObjectSelect`) ◄◄◄ – gescannt wird die
              **Instanz** (Einzelinstanz-Regel); der Treffer setzt die Suche. */}
          <div className="py-2" style={{ position: 'relative' }}>
            {/* eslint-disable-next-line no-restricted-syntax -- Suchfeld: die Eingabe sucht eine Instanz, sie ist kein Wert des Datensatzes. */}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Nummer suchen"
              className={inputCls}
              style={{ width: '100%', paddingRight: 34 }}
            />
            <FieldAction icon={<ScanLine size={15} />} label="Instanz scannen"
              onClick={() => scan({
                steps: [{
                  // Kein `label`: die Sorte kommt aus dem Typ (`TYPE_META`).
                  kind: 'instance',
                  suggest: (q: string) => api.getInstances(8, 0, q)
                    .then((rows) => rows
                      .filter((i) => i.object_id != null)
                      .map((i) => ({ objectId: i.object_id as number, label: i.article_name ?? '' }))),
                  exists: (id: number) => api.getInstances(5, 0, String(id))
                    .then((rows) => rows.some((i) => i.object_id === id)),
                }],
                onComplete: (ids) => { if (ids[0] != null) setQuery(String(ids[0])); },
              })} />
          </div>

          {/* Eine Gruppe je Zustand, Menge aus dem Aggregat (nicht der Seite); Klick filtert. */}
          {states.length > 1 && (
            <div className="flex flex-wrap gap-1.5 pb-2">
              {states.map((s) => (
                <button key={s.status} type="button"
                  onClick={() => setGroup(group === s.status ? null : s.status)}
                  className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full"
                  style={{
                    border: `1px solid ${group === s.status ? statusCfg(s.status).color : 'var(--border-2)'}`,
                    background: group === s.status ? statusCfg(s.status).bg : 'transparent',
                    color: statusCfg(s.status).color,
                  }}>
                  <StatusDot color={statusCfg(s.status).color} />
                  {statusLabel(s.status)} <span className="ix-tnum">{s.quantity}</span>
                </button>
              ))}
            </div>
          )}

          <div className="max-h-56 overflow-auto">
            {page === null && <Skeleton rows={3} label="Stücke werden geladen" style={{ padding: '8px 0' }} />}
            {page !== null && (page.units ?? []).length === 0 && (
              <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>
                {query || group
                  ? 'Keine Treffer – Suche oder Gruppe ändern.'
                  : 'Von diesem Artikel gibt es keine Einzelinstanzen. Lege im Reiter «Bestand» des Artikels eine Instanz an – oder wähle «Neu».'}
              </p>
            )}
            {(page?.units ?? []).map((o) => {
              const taken = picked.has(o.number);
              // Laufende und verbaute Stücke sind wählbar (Abweichung, §3.5) – der Hover sagt es vorher.
              const why = o.in_order
                ? `Läuft in Auftrag ${formatObjectId(o.in_order)} – daraus wird eine Abweichung`
                : !o.available ? `Steht auf «${statusLabel(o.status)}»`
                  : o.in_stock ? undefined
                    : o.status === VERBAUT
                      ? 'Verbaut – steckt in einem anderen Stück; der Auftrag baut es aus (Abweichung)'
                      : o.status === VERKAUFT
                        ? 'Verkauft – gehört einer anderen Partei; ein regulärer Start, etwa für Service, Reparatur oder eine Retoure'
                        : `Steht auf «${statusLabel(o.status)}» – zählt nicht zum Bestand; daraus wird eine Abweichung`;
              return (
                <button
                  key={o.number}
                  type="button"
                  disabled={!o.available}
                  onClick={() => toggle(o)}
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

          {total > PAGE && (
            <div className="flex items-center justify-between py-1.5 text-[11px]"
              style={{ color: 'var(--fg-3)' }}>
              <button type="button" disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
                className="px-2 py-1 rounded disabled:opacity-40"
                style={{ border: '1px solid var(--border-2)' }}>Zurück</button>
              <span className="ix-tnum">{offset + 1}–{Math.min(offset + PAGE, total)} von {total}</span>
              <button type="button" disabled={offset + PAGE >= total}
                onClick={() => setOffset(offset + PAGE)}
                className="px-2 py-1 rounded disabled:opacity-40"
                style={{ border: '1px solid var(--border-2)' }}>Weiter</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
