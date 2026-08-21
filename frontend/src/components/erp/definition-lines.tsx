'use client';

import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, GitBranch, Package, Plus, ScanLine, Sprout, Trash2, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleOption, UnitChoices, UnitOption } from '@/types';
import { formatObjectId } from '@/lib/utils';
import { IconSwitch, inputCls } from '@/components/erp/fields';
import { ObjectSelect } from '@/components/erp/object-select';
import { UnitNumber } from '@/components/erp/unit-number';
import { useScan } from '@/components/scan/scan-provider';
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

/** Wie viele Stücke eine Seite trägt. Genug, um zu blättern statt zu suchen – und
 *  wenig genug, dass eine 50 000er-Charge kein Problem der Oberfläche wird (#740). */
const PAGE = 60;

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

export function DefinitionLines({ lines, setLines, onArticlesChosen, refreshKey = 0,
                                  perUnit = false }: {
  lines: DefinitionLine[];
  setLines: (l: DefinitionLine[]) => void;
  /** Meldet die Artikelliste nach oben – der Entwurf spiegelt daraus die Vorlage. */
  /** Die **gewählten** Artikel – nicht mehr alle: der Entwurf lädt keine Liste mehr,
   *  er sucht (#738). Wer den Namen des Erzeugungs-Artikels braucht, findet ihn hier. */
  onArticlesChosen?: (options: ArticleOption[]) => void;
  /**
   * **Dieselbe Zeile als Stückliste** – die Menge gilt dann **je Einzelinstanz**
   * («4× Schraube M6 pro Getriebe»), und zwei der drei Fragen entfallen:
   *
   * *Herkunft* – eine Stückliste nennt keine Erzeugung; verbaut wird, was es gibt.
   * *Welche Stücke* – **das ist keine Frage der Definition.** Ein Modul ist eine
   * Vorlage: es läuft je Auftrag und je Produkt-Stück erneut, und ein hier
   * festgenageltes Stück wäre nach dem ersten Mal verbraucht. Welche Kiste genommen
   * wird, sagt der Lagerist beim Ausführen – dort ist es eine echte Wahl (§4).
   */
  perUnit?: boolean;
  /**
   * **Die Auswahl neu gegen die Wirklichkeit halten.** Wird hochgezählt, wenn die
   * Freigabe abbricht, weil ein gewähltes Stück inzwischen woanders läuft: dann holt der
   * Picker die Stückliste neu und zieht die **beobachtete Herkunft** der gewählten Stücke
   * nach. Der Mensch sieht damit, was sich geändert hat, und entscheidet erneut – statt
   * dass die Freigabe still etwas anderes tut als gewollt.
   */
  refreshKey?: number;
}) {
  // **Nur die GEWÄHLTEN Artikel, nicht alle.** Hier stand ein Vorab-Laden von bis zu 300
  // Artikeln, aus dem ein natives Dropdown wurde: nicht durchsuchbar, und bei tausend
  // Artikeln tausend Knoten je Zeile (Testnotiz #738). Gesucht wird jetzt beim Tippen
  // (`ObjectSelect`); was hier liegt, ist, was eine Zeile bereits gewählt hat – die
  // Angaben, die «Neu» sperren und begründen (`template_steps`, `create_problem`).
  const [chosen, setChosen] = useState<Record<number, ArticleOption>>({});

  const remember = useCallback((o: ArticleOption) => {
    setChosen((prev) => (prev[o.object_id] ? prev : { ...prev, [o.object_id]: o }));
  }, []);

  useEffect(() => { onArticlesChosen?.(Object.values(chosen)); }, [chosen, onArticlesChosen]);

  const patch = useCallback((key: number, next: Partial<DefinitionLine>) => {
    setLines(lines.map((l) => (l.key === key ? { ...l, ...next } : l)));
  }, [lines, setLines]);

  const hasNew = lines.some((l) => l.origin === NEU);

  // **Kein Container um den Container** (Testnotiz zur Anlage). Hier stand eine Karte mit
  // Überschrift «Definition» und dem Satz «Was bearbeitet dieser Auftrag? Ohne Definition
  // kein Start.» – beides sagte, was die Felder darunter ohnehin zeigen, und der Rahmen
  // legte eine zweite Kante um Zeilen, die bereits Karten sind. Übrig bleibt die Sache
  // selbst: eine Zeile je Position, darunter der Knopf für die nächste.
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

      {/* **«Neu» steht für sich allein** (Testnotiz #693): ein Erzeugungsauftrag fährt die
          Vorlage genau dieses Artikels, und ihr Versionsstempel gilt nur für seine Stücke.
          Die Regel liest sich von beiden Enden gleich – darum ist hier der Knopf weg, und
          in der Zeile ist «Neu» gesperrt, sobald es eine zweite gibt. Durchgesetzt wird
          sie serverseitig (`process._assert_single_new`); dies ist die Anzeige davon. */}
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

function LineRow({ line, article, onArticle, multi, refreshKey, perUnit, onChange, onRemove }: {
  line: DefinitionLine;
  /** Der gewählte Artikel, soweit bekannt – er trägt die Angaben, aus denen «Neu» folgt. */
  article: ArticleOption | null;
  /** Ein neu aufgelöster Artikel wandert nach oben: dort liegt die eine Ablage. */
  onArticle: (o: ArticleOption) => void;
  /** Gibt es mehr als eine Zeile? Dann ist «Neu» keine Option mehr (#693). */
  multi: boolean;
  refreshKey: number;
  /** Stückliste: Menge je Einzelinstanz, keine Herkunft, keine Stück-Auswahl. */
  perUnit: boolean;
  onChange: (next: Partial<DefinitionLine>) => void;
  onRemove: () => void;
}) {
  // **Eine vorbelegte Nummer muss aufgelöst werden** – der Shortcut am Artikel öffnet den
  // Entwurf mit einer Nummer, ohne dass jemand gesucht hat. Genau einmal, und nur, wenn
  // die Angaben noch fehlen.
  useEffect(() => {
    const nr = line.articleObjectId;
    if (nr == null || article) return;
    let dead = false;
    api.getArticleOptions({ objectId: nr })
      .then((rows) => { if (!dead && rows[0]) onArticle(rows[0]); })
      .catch(() => {});
    return () => { dead = true; };
  }, [line.articleObjectId, article, onArticle]);

  const findArticles = useCallback(
    (q: string) => api.getArticleOptions({ search: q, limit: 20 }).catch(() => []),
    [],
  );

  const hasArticle = article !== null;
  const hasTemplate = (article?.template_steps ?? 0) > 0;
  // **Warum «Neu» nicht geht, sagt der Server** (`articles.may_create`) – die Oberfläche
  // formuliert den Satz nicht selbst. Zwei Formulierungen wären zwei Massstäbe, und der
  // mildere stünde an dem Knopf, der beim Klick scheitert.
  const createProblem = article?.create_problem ?? null;

  return (
    <div className="rounded-ds-lg"
      style={{ border: '1px solid var(--border-1)', background: 'var(--bg-1)', padding: 10 }}>
      <div className="flex flex-wrap items-end gap-2">
        {/* 1 — Artikel. Sperrt alles Weitere, bis er steht.
            **Dasselbe Referenzfeld wie überall** (`ObjectSelect`, #738): tippen sucht auf
            dem Server – Nummer oder Name –, und die Kamera sitzt IM Feld. */}
        <div className="flex-1" style={{ minWidth: perUnit ? 190 : 240 }}>
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>Artikel</span>
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
                // Artikelwechsel verwirft die **Auswahl** – sie gehörte zum alten Artikel.
                // Die **Herkunft** bleibt: sie ist eine Entscheidung über diese Zeile, nicht
                // über den Artikel, und sie zurückzusetzen hiesse den Regler auf einen Wert
                // zu stellen, den es nicht gibt.
                units: [],
              });
            }}
          />
        </div>

        {/* 2 — Menge. Immer exakt Einzelinstanzen – in der Stückliste **je Stück**. */}
        <label style={{ width: perUnit ? 104 : 96 }}>
          <span className="block text-[11px] mb-1" style={{ color: 'var(--fg-3)' }}>
            {perUnit ? 'Menge je Einzelinstanz' : 'Menge'}
          </span>
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
        <div style={{ display: perUnit ? 'none' : undefined }}>
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

      {/* Was die Menge an Datensätzen bedeutet – gesagt, nicht geraten. */}
      {/* **Kein Erklärtext** (#722): «Menge je Einzelinstanz» steht als Beschriftung am Feld –
          was die Zahl bedeutet, sagt sie damit selbst. Ein Rechenbeispiel darunter
          erklärt eine Beschriftung, die keiner Erklärung bedarf. */}
      {!perUnit && hasArticle && line.origin === NEU && line.quantity > 0 && (
        <p className="mt-2 text-[11px]" style={{ color: 'var(--fg-3)' }}>
          {article!.serialization === 'batch'
            ? `Eine Instanz mit ${line.quantity} Einzelinstanzen (${line.quantity === 1 ? '-1' : `-1 … -${line.quantity}`}).`
            : `${line.quantity} Instanzen mit je einer Einzelinstanz (-1).`}
        </p>
      )}

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
 * **FIFO als Vorschlag, nicht als Zwang.** Die ältesten Stücke, **die im Regal liegen**,
 * sind vorausgewählt – sichtbar und einzeln abwählbar. Eine unsichtbare Automatik wäre
 * hier das Schlimmste: man sähe erst nach der Freigabe, welche Stücke es getroffen hat.
 *
 * **Die Vorauswahl kommt vom Server** (Testnotiz #740). Sie aus der geladenen Seite zu
 * ziehen war der eigentliche Fehler: sind die ersten Stücke verbaut, findet die
 * Oberfläche **nichts**, obwohl freie da sind. FIFO ist eine Regel, keine Anzeige.
 *
 * **Zwei Fragen, nicht eine** (#739): `available` heisst «lässt sich nehmen» (ein
 * verbautes Stück ja – das Greifen IST der Ausbau), `in_stock` heisst «liegt im Regal»
 * (ein verbautes Stück nein). Vorgeschlagen wird nur, was **beides** erlaubt und in
 * keinem laufenden Auftrag steckt.
 *
 * **Gruppiert wie der Bestand** (PROCESS_CORE §10.3): eine Gruppe je vorkommendem
 * Zustand, Reihenfolge = Lebenszyklus, was zur Historie zählt startet zugeklappt. Damit
 * steht die Aussage im Bild statt in der Farbe – Verbaut bleibt grün, es hat sein Ziel
 * erreicht.
 */
function StockPicker({ articleObjectId, quantity, chosen, refreshKey, onChange }: {
  articleObjectId: number; quantity: number; chosen: UnitPick[]; refreshKey: number;
  onChange: (picks: UnitPick[]) => void;
}) {
  const [page, setPage] = useState<UnitChoices | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const scan = useScan();

  // **Eine Seite, nicht die Liste.** `preselect` bittet den Server um die FIFO-Auswahl –
  // er kennt die Ordnung und den Filter, die Seite kennt beides nicht.
  useEffect(() => {
    let dead = false;
    api.getUnitOptions({
      articleObjectId, preselect: quantity, limit: PAGE,
      offset, search: query || undefined, status: group ? [group] : undefined,
    })
      .then((p) => { if (!dead) setPage(p); })
      .catch(() => { if (!dead) setPage({ units: [], total: 0, states: [], preselect: [] }); });
    return () => { dead = true; };
  }, [articleObjectId, refreshKey, quantity, offset, query, group]);

  // Filter/Suche fangen wieder vorn an – eine Seite 3 einer anderen Menge ist keine.
  useEffect(() => { setOffset(0); }, [query, group]);

  // **Der Vorschlag hängt an seiner Grundlage, nicht an einem Ereignis.** Er entsteht nur
  // ins Leere: was der Mensch gewählt hat, wird nie überschrieben (`chosen` ist bewusst
  // keine Abhängigkeit).
  const preselect = page?.preselect;
  useEffect(() => {
    if (!preselect?.length || chosen.length) return;
    onChange(preselect.map((number) => ({ number, fromOrder: null })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselect]);

  // **Die beobachtete Herkunft wird nachgezogen, die Auswahl nicht.** Kommt die Seite neu
  // (Artikelwechsel, Freigabe-Abbruch), kann ein gewähltes Stück inzwischen woanders
  // laufen. Dann ändert sich, was der Klick bewirken WÜRDE – und das gehört vor den Klick.
  //
  // **Nur was auf dieser Seite steht**: was gerade weggefiltert ist, ist nicht
  // verschwunden. Die frühere Fassung sah die ganze Liste und durfte darum fallen lassen,
  // was fehlte; seit es Seiten gibt, wäre das ein stilles Verwerfen der Auswahl.
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
  // **Die Rückführung ist nur eine Frage, wenn es etwas zurückzugeben gibt.** Ein freies
  // Stück kommt aus keinem Auftrag – eine Wahl anzubieten, die nichts bewirkt, wäre eine
  // Behauptung, hier passiere etwas.
  const borrowed = chosen.filter((u) => u.fromOrder !== null);
  const states = page?.states ?? [];
  const total = page?.total ?? 0;

  function toggle(o: UnitOption) {
    onChange(picked.has(o.number)
      ? chosen.filter((c) => c.number !== o.number)
      : [...chosen, { number: o.number, fromOrder: o.in_order ?? null }]);
  }

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
        <div className="mt-2" style={{ borderTop: '1px solid var(--border-1)' }}>
          {/* **Suchen und scannen stehen nebeneinander** – dieselbe Haltung wie im
              Referenzfeld (`ObjectSelect`). Gescannt wird die **Instanz**: eine
              Einzelinstanz zieht bewusst keine Objektnummer, es kann für sie gar kein
              Etikett geben (PROCESS_CORE, Einzelinstanz-Regel). Der Treffer setzt die
              Suche – die Stücke der Instanz stehen dann untereinander. */}
          <div className="flex items-center gap-2 py-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Nummer suchen…"
              className={inputCls}
              style={{ flex: 1, minWidth: 0 }}
            />
            <button type="button" className="erp-idbtn" data-tip="Instanz scannen"
              aria-label="Instanz scannen"
              onClick={() => scan({
                steps: [{
                  label: 'Instanz',
                  kind: 'instance',
                  suggest: (q: string) => api.getInstances(8, 0, q)
                    .then((rows) => rows
                      .filter((i) => i.object_id != null)
                      .map((i) => ({ objectId: i.object_id as number, label: i.article_name ?? '' })))
                    .catch(() => []),
                  exists: (id: number) => api.getInstances(5, 0, String(id))
                    .then((rows) => rows.some((i) => i.object_id === id))
                    .catch(() => false),
                }],
                onComplete: (ids) => { if (ids[0] != null) setQuery(String(ids[0])); },
              })}>
              <ScanLine size={15} />
            </button>
          </div>

          {/* **Eine Gruppe je Zustand, mit der Menge aus dem Aggregat** – nicht aus der
              Seite: eine gezählte Seite zeigte «60», wo fünfzigtausend liegen. Ein Klick
              filtert; ein zweiter nimmt den Filter zurück. */}
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
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: statusCfg(s.status).color }} />
                  {statusLabel(s.status)} <span className="ix-tnum">{s.quantity}</span>
                </button>
              ))}
            </div>
          )}

          <div className="max-h-56 overflow-auto">
            {page === null && <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>Lädt …</p>}
            {page !== null && (page.units ?? []).length === 0 && (
              <p className="text-xs py-2" style={{ color: 'var(--fg-4)' }}>
                {query || group
                  ? 'Keine Treffer – Suche oder Gruppe ändern.'
                  : 'Von diesem Artikel gibt es keine Einzelinstanzen. Lege im Reiter «Bestand» des Artikels eine Instanz an – oder wähle «Neu».'}
              </p>
            )}
            {(page?.units ?? []).map((o) => {
              const taken = picked.has(o.number);
              // **Ein laufendes Stück ist wählbar** – daraus wird eine Abweichung
              // (Abweichungsauftrag §3.5). **Ein verbautes ebenso** – das Greifen IST der
              // Ausbau. Gesagt wird es trotzdem: was der Klick bewirkt, gehört vor den
              // Klick, nicht danach.
              const why = o.in_order
                ? `Läuft in Auftrag ${formatObjectId(o.in_order)} – daraus wird eine Abweichung`
                : !o.available ? `Steht auf «${statusLabel(o.status)}»`
                  : !o.in_stock ? `Steht auf «${statusLabel(o.status)}» – liegt nicht im Regal und müsste erst ausgebaut werden`
                    : undefined;
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

          {/* **Blättern statt scrollen ins Nichts** – die Gesamtzahl sagt, wie weit es geht. */}
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
