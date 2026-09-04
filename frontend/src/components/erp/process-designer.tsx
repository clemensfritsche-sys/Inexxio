'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Columns2, Grid2x2, Layers, Lock, LockOpen, Percent, Trash2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { DealParty, ModuleCatalog } from '@/types';
import {
  CAPTURE_ICON, DEAL_DIRECTION, DEAL_PARTY, DEAL_TASK, DEAL_TASK_HINT,
  DISPOSAL_MODES, moduleIcon, NEEDS_TARGET,
  SAMPLE_PRESETS, blankModule, moduleTone,
  type DisposalMode, type ModuleDraft, type PointDraft, type SampleDraft, type SampleMode,
} from '@/lib/modules';

/** Symbol je Kurzweg. Die Wörter stehen daneben – ein Anteil hat kein Bild (#636). */
const SAMPLE_ICON: Record<SampleMode, LucideIcon> = {
  all: Layers, half: Columns2, quarter: Grid2x2, free: Percent,
};
import {
  DRAFT_OBJECT_ID, definitionGraph, type DiagramStep,
} from '@/components/erp/process-diagram';
import { ProcessColumns } from '@/components/erp/process-columns';
import { ObjId } from '@/components/erp/obj-id';
import { END_BEFORE } from '@/lib/process-status';
import type { RelatedOrder } from '@/types';
import { IconSwitch, inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';
import { DefinitionLines, emptyLine } from '@/components/erp/definition-lines';
import { ObjectSelect } from '@/components/erp/object-select';
import type { PlaceRef } from '@/types';
import { RUNTIME_CHOICE } from '@/lib/scan';

/**
 * **Den Prozess definieren — dieselbe Komponente am Artikel wie im Auftrag.**
 *
 * Beide Orte definieren denselben Prozess (PROCESS_CORE.md §8): am Artikel als Vorlage,
 * im Auftrag als das, was gleich läuft. Zwei Editoren dafür wären zwei Stände, und sie
 * liefen garantiert auseinander.
 *
 * **Kein «Hinzufügen»-Knopf und kein Bearbeiten-Modus.** Ein Klick auf die Palette legt
 * das Modul an; es steht ab dem ersten Moment im Fluss und füllt sich, während man tippt
 * (Autosave). Vollständig ist es, wenn seine Pflichtangaben stehen – bis dahin sagt die
 * Karte, was fehlt, und die Freigabe verweigert. Ändern heisst löschen und neu anlegen;
 * dafür gibt es den Mülleimer, keinen zweiten Weg.
 *
 * **Nach der Freigabe ist die Struktur eingefroren** (`frozen`): keine Palette, kein
 * Mülleimer, kein Ziehen. Das ist keine bewachte Regel, sondern ein fehlendes Bedienelement –
 * einen Endpunkt, der eine freigegebene Definition ändert, gibt es ohnehin nicht.
 */
export function ProcessDesigner({ modules, onChange, frozen, readOnlySteps, head,
  parents, onToggleReturn }: {
  modules: ModuleDraft[];
  onChange: (m: ModuleDraft[]) => void;
  frozen?: boolean;
  /** Eingefrorener Stand (freigegebener Artikel/Auftrag) – dann wird nur gezeigt. */
  readOnlySteps?: DiagramStep[];
  /** Slot über dem Start – beim Auftrag die Definition der Einzelinstanzen. Der Artikel
   *  hat keine, und ein Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar. */
  head?: React.ReactNode;
  /**
   * **Die Quell-Aufträge des Entwurfs** (Auftrag §2) – vom Server vorausberechnet, mit
   * der Abzweigung, die entstehen würde. Ein Artikel hat keine; dann steht hier nur der
   * Prozess, wie bisher.
   */
  parents?: RelatedOrder[];
  /** Ein Klick auf den Quell-Auftrag schaltet seine Rückführung an und aus (§5). */
  onToggleReturn?: (parentObjectId: number) => void;
}) {
  const [catalog, setCatalog] = useState<ModuleCatalog | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  // **Das zuletzt angelegte Modul startet aufgeklappt** (#696): es ist das, woran gerade
  // gearbeitet wird – die Entsprechung zum «aktiven» Modul im laufenden Auftrag. Alle
  // übrigen sind zu; ihr Kopf klappt sie auf.
  const [justAdded, setJustAdded] = useState<number | null>(null);

  // **Auch der eingefrorene Stand braucht ihn** (Testnotiz #771): die Felder eines Moduls
  // nennen ihre Erfassungspunkte beim Namen, und die Namen stehen im Katalog. Er wurde
  // hier übersprungen, solange ein freigegebener Prozess gar keinen Feldsatz zeigte; die
  // Palette bleibt trotzdem weg – die hängt an `frozen`, nicht am Katalog.
  useEffect(() => {
    let dead = false;
    api.getModuleCatalog()
      .then((c) => { if (!dead) setCatalog(c); })
      .catch(() => { /* ohne Katalog bleibt die Palette leer – kein erfundener Typ */ });
    return () => { dead = true; };
  }, []);

  // **Was ein Modul ist, sagt sein Typ** – im Entwurf über den Katalog, gespeichert über
  // die Antwort des Servers. Beides dieselbe Registry, nur zwei Wege dorthin; **beide**
  // bringen Beschriftung, Farbfamilie und «Ausgang?» mit, damit keine Ansicht sie
  // nachschlagen muss und keine sie vergessen kann.
  const steps: DiagramStep[] = readOnlySteps
    ?? modules.map((m) => {
      const type = catalog?.modules?.find((x) => x.key === m.moduleType);
      return {
        id: m.id,
        moduleType: m.moduleType,
        label: type?.label ?? m.moduleType,
        tone: type?.tone ?? null,
        terminal: !!type?.terminal,
      };
    });

  function add(moduleType: string) {
    const id = (modules[modules.length - 1]?.id ?? 0) + 1;
    setJustAdded(id);
    onChange([...modules, blankModule(id, moduleType)]);
  }
  function patch(id: number, next: Partial<ModuleDraft>) {
    onChange(modules.map((m) => (m.id === id ? { ...m, ...next } : m)));
  }

  /** Ein Modul an eine andere Stelle ziehen. Die Reihenfolge IST der Prozess. */
  function move(from: number, to: number) {
    if (from === to) return;
    const next = [...modules];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    onChange(next);
  }

  return (
    <ProcessColumns
      mid={{
        objectId: DRAFT_OBJECT_ID,
        // **Der Graph eines Entwurfs ist seine Definition** – hier steht keine
        // Prozesslogik, sondern die Liste, die daneben bearbeitet wird.
        graph: definitionGraph(steps),
        steps,
        mode: 'definition',
        expandedStepId: justAdded,
        endStatus: END_BEFORE,
        head,
        onDelete: frozen ? undefined : (id) => onChange(modules.filter((m) => m.id !== id)),
        onReorder: frozen ? undefined : move,
        dragging: drag,
        onDragState: setDrag,
        // ►► **Ein Modul zeigt seine Sache in JEDEM Zustand** (Testnotiz #771). ◄◄
        //
        // Hier stand `frozen ? undefined : …` – im **freigegebenen** Artikel bekam ein
        // Modul damit gar keinen Körper: der Kopf klappte auf, und darin war nichts.
        // Genau so wurde es gemeldet («überall sonst funktioniert es, nur hier nicht»),
        // und «überall sonst» stimmt: der laufende Auftrag zeigt seine Module längst in
        // jedem Zustand (#749).
        //
        // Es ist **derselbe Feldsatz**, nicht ein zweiter zum Lesen – gesperrt über
        // `fieldset[disabled]`, dieselbe eine Zeile, mit der auch eine wartende Modul-
        // Karte stillgelegt wird (#698). Ein eigener Lese-Feldsatz daneben wäre die
        // Stelle, an der die (n+1)-te Angabe fehlt.
        renderStep: (step) => {
          const m = modules.find((x) => x.id === step.id);
          if (!m) return null;
          // **Welche Felder ein Modul hat, sagt sein Typ** – die Zuordnung steht hier,
          // nicht als Bedingung im Rumpf. Ein neuer Typ ist ein Eintrag, kein Eingriff.
          const known = m.moduleType in MODULE_FIELDS;
          const Fields = MODULE_FIELDS[m.moduleType];
          if (!known) {
            return (
              <p className="text-xs" style={{ color: 'var(--danger)' }}>
                Modultyp «{m.moduleType}» ist dieser Oberfläche unbekannt.
              </p>
            );
          }
          return (
            <fieldset disabled={frozen}
              style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
              <div className="flex flex-col gap-3">
                {Fields && (
                  <Fields module={m} types={catalog?.capture_types ?? []}
                    onChange={(next) => patch(m.id, next)} />
                )}
              </div>
            </fieldset>
          );
        },
        // ►► **Hinter einem Ausgang gibt es nichts mehr anzubieten.** ◄◄
        //
        // Dieselbe Eigenschaft (`Module.terminal`), aus der die Freigabe ihren Fehler
        // zieht und das Bild sein Ende: was an einem terminalen Modul ankommt, verlässt
        // den Auftrag – ein Modul dahinter bekäme nie eine Einzelinstanz. Es hier gar
        // nicht erst anzubieten ist die freundlichere Hälfte derselben Regel; die
        // Prüfung bei der Freigabe bleibt das Netz (eine fehlende Schaltfläche ist keine
        // Absicherung, sondern eine Bitte).
        tail: frozen || steps.some((s) => s.terminal)
          ? undefined
          : <Palette catalog={catalog} onPick={add} />,
      }}
      parents={parents}
      onToggleReturn={onToggleReturn}
    />
  );
}

/**
 * **Die Modulauswahl — dort, wo das nächste Modul hinkäme.**
 *
 * Ein Symbol je Modultyp, in seiner Farbe; der Name klappt beim Hovern daneben auf.
 * Dieselbe Interaktion wie die Mengeneinheit am Artikel (`IconSwitch labelActiveOnly`):
 * man sieht die Auswahl auf einen Blick, ohne dass Wörter um Aufmerksamkeit ringen –
 * nur ist dies keine Wahl zwischen Werten, sondern ein Griff in den Baukasten.
 */
function Palette({ catalog, onPick }: {
  catalog: ModuleCatalog | null; onPick: (key: string) => void;
}) {
  const mods = catalog?.modules ?? [];
  if (!mods.length) return null;
  return (
    <div className="flex flex-wrap justify-center gap-1.5">
      {mods.map((m) => {
        const Icon = moduleIcon(m.key);
        const tone = moduleTone(m.tone);
        return (
          <button
            key={m.key}
            type="button"
            className="ix-palette"
            style={{ background: tone.bg, color: tone.fg, borderColor: tone.border }}
            aria-label={`${m.label} hinzufügen`}
            onClick={() => onPick(m.key)}
          >
            <Icon size={17} />
            <span className="ix-palette-name">{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * **Aussondern — eine Entscheidung, sonst nichts.**
 *
 * Verschrotten und Sperren tun dasselbe: das Stück verlässt den Auftrag. Der einzige
 * Unterschied ist, **ob es einen Weg zurück gibt** – und genau das steht hier. Es ist
 * kein Status-Dropdown: der Anwender wählt, was passieren soll, den Zustand leitet das
 * Modul ab (`Aussondern.status_after_for`).
 *
 * Keine Erfassungspunkte, keine Stichprobe: was ankommt, wird ausgesondert.
 *
 * **Der Grund gehört hierher, nicht ans Band.** Warum an dieser Stelle ausgesondert wird,
 * ist eine Eigenschaft des Ablaufs und lautet bei jedem Stück gleich – am Band wäre es
 * ein Feld, das immer dasselbe aufnimmt. Ohne ihn lässt sich das Modul nicht anlegen
 * (`Aussondern.clean_config`); die Meldung hier ist die Bedienung, die Regel steht dort.
 */
function DisposalFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <IconSwitch
        value={m.mode}
        onChange={(mode: DisposalMode) => onChange({ mode })}
        options={DISPOSAL_MODES.map((o) => ({
          value: o.value, icon: o.value === 'scrap' ? Trash2 : Lock,
          label: o.label, hint: o.hint,
        }))}
      />
      <input className={inputCls} value={m.reason} maxLength={200}
        placeholder="Grund, z. B. Ausschuss aus der Sichtprüfung"
        aria-label="Grund der Aussonderung"
        onChange={(e) => onChange({ reason: e.target.value })} />
    </div>
  );
}

/**
 * **Bewegen — eine Frage: wohin?**
 *
 * Und sie darf **offen bleiben**. Das ist der einzige Unterschied zu jedem anderen
 * Pflichtfeld im Editor, und er ist fachlich: beim Modellieren steht oft nicht fest, wo
 * in drei Wochen Platz sein wird. Eine Vorlage, die dann trotzdem ein Regal nennt, ist
 * beim zweiten Durchlauf falsch — und zwar stillschweigend.
 *
 * Damit «leer» nicht wie «vergessen» aussieht, sagt das Feld selbst, was dann passiert.
 * Steht eine Nummer da, wird sie **aufgelöst**: man sieht den Namen des Halters, nicht
 * nur seine Ziffern — sonst prüft niemand nach, ob es das richtige Regal ist.
 *
 * Der Scan-Knopf ist die Abkürzung dafür: am Regal steht man ohnehin, und sein Etikett
 * trägt die Nummer. Er nutzt denselben Dialog wie die Ausführung, nur mit einem freien
 * Lookup statt einer Verifikation.
 */
function MoveFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const [place, setPlace] = useState<PlaceRef | null>(null);
  const target = m.target.trim();

  // Den **gewählten** Halter benennen, damit im Feld sein Name steht und nicht seine
  // Ziffern. Nur diesen einen – die Vorschläge holt die Suche, wenn getippt wird.
  useEffect(() => {
    if (target === '') { setPlace(null); return; }
    let stale = false;
    api.getPlace(Number(target))
      .then((p) => { if (!stale) setPlace(p); })
      .catch(() => { if (!stale) setPlace(null); });
    return () => { stale = true; };
  }, [target]);

  // `PlaceRef` nennt sein Namensfeld `label`; hier wird es zu `name` – ein Mapping an der
  // Stelle, an der der Unterschied entsteht, statt einer zweiten Feld-Konvention.
  const findPlaces = useCallback(
    (q: string) => api.searchPlaces(q)
      .then((rows) => rows.map((p) => ({ ...p, name: p.label })))
      .catch(() => []),
    [],
  );

  return (
    <ObjectSelect<PlaceRef & { name: string }>
      // **Das Feld nennt seine Sorte, der Scanner nennt dieselbe** – im Feld als
      // Beschriftung, im Dialog als Zeile über der Suchleiste. Ohne sie stünde nur
      // «Nummer oder Name» da, und im Vollbild-Dialog bliebe nach dem ersten Zeichen
      // gar nichts mehr, das sagt, wonach gesucht wird. `scanLabel` ist damit
      // überflüssig geworden: die Beschriftung IST die Sorte.
      label="Zielort"
      value={target === '' ? null : Number(target)}
      selected={place ? { ...place, name: place.label } : null}
      find={findPlaces}
      onChange={(nr) => onChange({ target: nr == null ? '' : String(nr) })}
      // **«Kein Ziel» ist eine Wahl, keine Lücke** (#734–#736): sie steht als erste Zeile
      // in derselben Liste und im Feld, sobald sie gilt. Vorher stand dieselbe Aussage an
      // drei Stellen – im Platzhalter, in einem Erklärsatz darunter und in einem X-Knopf
      // daneben – und an keiner davon konnte man sie wählen.
      emptyOption={RUNTIME_CHOICE}
    />
  );
}

/**
 * **Was ein Modultyp ZUSÄTZLICH hat.** Eine Zuordnung, keine Bedingung – und jeder Typ
 * steht darin, auch der mit `null`: die Liste beantwortet «kennt die Oberfläche diesen
 * Typ?», und ein fehlender Schlüssel ist die Antwort «nein».
 *
 * **`null` heisst «kennt ihn, hat aber nichts zu fragen».** Es gibt heute keinen solchen
 * Typ mehr – der Wert bleibt trotzdem erlaubt: ein **fehlender** Schlüssel wäre die
 * Antwort «diesen Typ kenne ich nicht», und die Karte sagte das dann auch. Ein Wächter
 * hält die Schlüssel mit dem Backend deckungsgleich.
 */
const MODULE_FIELDS: Record<string, React.ComponentType<{
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}> | null> = {
  datenerfassung: ModuleFields,
  aussondern: DisposalFields,
  verbrauch: ConsumptionFields,
  bewegen: MoveFields,
  zahlung: MoneyFields,
};

/**
 * ►►► **Eine Zeile entfernen — dasselbe Zeichen wie am Modul selbst** (Testnotiz #844). ◄◄◄
 *
 * Der Knopf an der Partner-Zeile trug `.erp-actbtn-neutral`: ein Kasten mit Rahmen und
 * Fläche, mitten in einer Zeile aus Nummer, Name und Eingabefeld – und damit lauter als
 * das Eingabefeld daneben, obwohl er die seltenere Handlung ist. Der Knopf, mit dem man
 * ein **ganzes Modul** entfernt, sieht dagegen so aus: ein 26-px-Quadrat, kein Rahmen,
 * keine Fläche, allein die Warnfarbe.
 *
 * Beides ist «diese Sache hier wegnehmen», also sieht beides gleich aus – und weil es
 * schon **zwei** handgeschriebene Fassungen davon gab (Partner-Zeile, Erfassungspunkt),
 * steht es jetzt einmal da statt dreimal. Was sie unterscheidet, ist der Satz im Hover.
 */
function RowDelete({ label, hint, reveal, onClick }: {
  label: string; hint?: string;
  /**
   * **Erst beim Hovern** (#832) – für Zeilen, die man häufig liest und selten löscht.
   * Die Regel steht in `globals.css` (`.erp-rowaction`, mit `@media (hover: none)` für
   * Touch); hier wird sie nur **gewählt**, nicht formuliert. Ohne die Angabe steht der
   * Knopf durchgehend da – so, wie der Erfassungspunkt ihn immer schon hatte.
   */
  reveal?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" aria-label={label} data-tip={hint}
      className={`flex items-center justify-center rounded flex-none${reveal ? ' erp-rowaction' : ''}`}
      style={{ width: 26, height: 26, color: 'var(--danger)' }}
      onClick={onClick}>
      <Trash2 size={14} />
    </button>
  );
}

/**
 * ►►► **Zahlung — vier Angaben, und die erste entscheidet alles.** ◄◄◄
 *
 * *Kommt Geld herein oder geht es hinaus?* Daraus folgt jedes Wort des Moduls: wie die
 * Stufen heissen, wie die Gegenpartei heisst, wer die Rechnung stellt. Als **Schieber**
 * und nicht als zwei Kacheln in der Palette – es ist EIN Modul, und die Richtung ist
 * seine Einstellung; zwei Kacheln wären wieder die Trennung, die es gerade aufhebt.
 *
 * **Worum es geht** ist Pflicht (`subject`): ohne den Satz steht auf dem Beleg ein Betrag
 * und sonst nichts. Er gehört an das **Modul** und nicht an den Artikel – «Härten auf 58
 * HRC» ist eine Eigenschaft dieses Schritts, und ein Artikel hat mehrere.
 *
 * **Keine Menge, kein Artikel, kein Termin**: die Menge ist die Zahl der Einzelinstanzen
 * vor dem Modul, den Artikel tragen sie selbst, und der Termin ist ableitbar. Und **kein
 * Betrag**: der steht beim Modellieren nicht fest – ein hier getippter wäre bei der
 * zweiten Ausführung falsch, und zwar stillschweigend.
 *
 * **Der einzige Schalter ist die Sperre** (`prepaid`). Er schreibt keine Reihenfolge vor:
 * Vorauszahlung, Zahlungsziel, Anzahlung und Nachnahme sind dieselbe Mechanik in anderer
 * Folge. Er sagt nur, dass dieses Modul nicht abschliesst, bevor das Geld da ist.
 */
function MoneyFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const [known, setKnown] = useState<Record<number, string>>({});

  // Die gewählten Gegenparteien benennen – sonst stünden dort nur Ziffern. Eine Abfrage
  // je fehlender Nummer, nicht je Rendern.
  useEffect(() => {
    const missing = m.parties.map((r) => r.party).filter((n) => !(n in known));
    if (missing.length === 0) return;
    let stale = false;
    void Promise.all(missing.map((n) => api.searchDealParties(String(n), 1)))
      .then((groups) => {
        if (stale) return;
        const found: Record<number, string> = {};
        groups.flat().forEach((o) => { found[o.object_id] = o.name; });
        setKnown((k) => ({ ...k, ...found }));
      })
      .catch(() => {});
    return () => { stale = true; };
  }, [m.parties, known]);

  const find = useCallback((q: string) => api.searchDealParties(q).catch(() => []), []);

  return (
    <div className="flex flex-col gap-3">
      <div>
        {/* ►►► **Kein Label darüber** (#816). ◄◄◄
            Die beiden Werte heissen «Verkauf» und «Einkauf» und tragen ihre Symbole –
            eine Zeile «Geschäft *» darüber sagt nichts, was der Schalter nicht selbst
            sagt. Ein Bedienelement, das spricht, braucht keine Ansage; die Pflicht ist
            ohnehin erfüllt, weil immer einer der beiden Werte steht. */}
        <IconSwitch
          value={m.direction === 'in' ? 'in' : 'out'}
          onChange={(v) => onChange({ direction: v })}
          options={[
            { value: 'in', icon: DEAL_DIRECTION.in.icon,
              label: DEAL_DIRECTION.in.label, hint: DEAL_DIRECTION.in.hint },
            { value: 'out', icon: DEAL_DIRECTION.out.icon,
              label: DEAL_DIRECTION.out.label, hint: DEAL_DIRECTION.out.hint },
          ]}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        {/* **«Leer heisst frei» steht in der LISTE, nicht als Satz darunter** (#786) –
            und nur, solange sie gilt: sobald jemand zugelassen ist, wäre «Beim Ausführen
            definieren» eine Behauptung, die die Zeilen darunter widerlegen.

            **Ein Wort für beide Richtungen** (#802): «Kunde» ↔ «Lieferant» ist dieselbe
            Rolle – der andere im Geschäft. Und Singular = Plural, damit es keine Beugung
            gibt, die jemand rechnen könnte. */}
        {/* **Ein Hinzufüger, kein Auswahlfeld**: `value`/`selected` sind immer `null`,
            was man wählt, wandert in die Liste darunter – und das Feld ist danach leer
            (gemessen in Chromium: nach zwei Klicks beide Male `""`). Genau darum steht
            hier auch kein Zurücksetzen: `SearchSelect.pick` räumt seine Suche selbst auf.
            Die Stelle, an der ein Name stehen blieb, ist die **Laufzeit** (#820) –
            `deal-work.Offer`, wo die frische Wahl gehalten wird, bis der Server sie als
            Zeile zurückgibt. */}
        {/* ►►► **«Partner» steht IM Feld, nicht darüber** (Testnotiz #843). ◄◄◄

            Die Beschriftung kostete eine eigene Zeile, um ein einziges Wort zu sagen –
            und darunter stand ein Platzhalter «Nummer oder Name», der dasselbe Feld ein
            zweites Mal erklärte. Zusammengelegt sagt der Platzhalter beides: **wen** man
            sucht und **womit**. Er verschwindet beim ersten Zeichen, und das ist hier
            genau richtig: dann steht die Liste der Treffer da, und die beantwortet die
            Frage besser als jede Beschriftung.

            Dieselbe Regel wie im Scan-Dialog (#758). Im **Vollbild** des Scanners bleibt
            die Sorte als Beschriftung stehen (`scanLabel`) – dort liegt Text auf einem
            Foto, und der Platzhalter allein trüge sie nicht. */}
        <ObjectSelect<DealParty>
          value={null}
          selected={null}
          find={find}
          scanLabel={DEAL_PARTY}
          emptyOption={m.parties.length === 0 ? RUNTIME_CHOICE : undefined}
          placeholder={`${DEAL_PARTY} – Nummer oder Name`}
          onChange={(nr, opt) => {
            if (nr === null || m.parties.some((r) => r.party === nr)) return;
            if (opt) setKnown((k) => ({ ...k, [nr]: opt.name }));
            onChange({ parties: [...m.parties, { party: nr, ref: '' }] });
          }}
        />
        {m.parties.map((row) => (
          /* ►►► **Alles zu EINEM Partner steht auf EINER Zeile** (Testnotiz #833). ◄◄◄

             Nummer, Name und «Was ist zu tun?» gehören zusammen – und bei mehreren
             Partnern ist die Zeile die **einzige** Stelle, an der die Zugehörigkeit
             steht. Untereinander sah es aus wie zwei Angaben, von denen die zweite zu
             keiner bestimmten gehört.

             ►►► **Und der Löschen-Knopf erscheint beim Hovern** (#832) – aber er
             **verschwindet nie auf Touch**: `@media (hover: none)` hält ihn dort
             sichtbar. Eine Funktion, die nur ein Zeiger findet, gibt es am Telefon
             nicht. `focus-within` deckt den Tastaturweg. */
          <div key={row.party}
            className="erp-partyrow flex items-center gap-2 py-1.5 flex-wrap"
            style={{ borderTop: '1px solid var(--border-1)' }}>
            <ObjId value={row.party} />
            <span className="text-[12.5px] truncate" style={{
              color: 'var(--fg-3)', maxWidth: 180, flex: 'none',
            }}>{known[row.party] ?? ''}</span>
            <input className={inputCls} value={row.ref} maxLength={200} required
              aria-label={DEAL_TASK} placeholder={DEAL_TASK_HINT}
              style={{ flex: '1 1 160px', minWidth: 0 }}
              onChange={(e) => onChange({
                parties: m.parties.map((x) => (x.party === row.party
                  ? { ...x, ref: e.target.value } : x)),
              })} />
            <RowDelete label="Entfernen" hint="Aus der Freigabe nehmen" reveal
              onClick={() => onChange({
                parties: m.parties.filter((x) => x.party !== row.party),
              })} />
          </div>
        ))}
      </div>
      <div>
        {/* ►►► **Die Werte benennen die ENTSCHEIDUNG** (#818/#819/#834). ◄◄◄

            Das Label darüber ist entfallen (#819) – richtig, aber die Werte trugen die
            Frage danach nicht: «Nach Zusage» ↔ «Nach Zahlung» sagt nicht, worauf es sich
            bezieht, und ohne die Zeile darüber fehlte der Bezug ganz (#834).

            Jetzt steht die Entscheidung **im Wert**: warte ich auf das Geld, bevor das
            Modul abschliesst – ja oder nein. Beide Sätze stehen für sich, ohne Kontext
            und ohne Hover; das Schloss trägt die Metapher, der Hover das Detail.

            Dieselbe Regel wie beim Schalter darüber: was ein Bedienelement selbst sagt,
            sagt man nicht noch einmal daneben – **aber es muss es dann auch sagen.** */}
        <IconSwitch
          value={m.prepaid ? 'prepaid' : 'open'}
          onChange={(v) => onChange({ prepaid: v === 'prepaid' })}
          options={[
            { value: 'open', icon: LockOpen, label: 'Zahlung nicht abwarten',
              hint: 'Das Modul schliesst ab, sobald zugesagt ist – gezahlt wird nach '
                + 'Vereinbarung.' },
            { value: 'prepaid', icon: Lock, label: 'Zahlung abwarten',
              hint: 'Das Modul schliesst erst ab, wenn der zugesagte Betrag bezahlt ist '
                + '(Vorauszahlung).' },
          ]}
        />
      </div>
      {/* ►►► **Der Steuersatz steht hier NICHT** (Testnotiz #851). ◄◄◄

          Er stand als «Vorgabe jeder neuen Position» in der Definition und war damit
          eine Eigenschaft des **Moduls**: eine Vorlage, die für jeden künftigen Auftrag
          denselben Satz behauptet. Er hängt aber an der **Sache** – sechs Wellen zu
          8.1 % und eine Ausfuhr zu 0 % stehen auf demselben Papier –, und die steht erst
          fest, wenn ein Auftrag läuft. Gefragt wird er darum **je Position an der
          Ausführungsstelle** (`OurOffer`), wo der Katalog mit dem Vorgang mitreist.

          Ein Vorgabewert, der bei der Hälfte der Aufträge überschrieben werden muss, ist
          kein Komfort: er ist die Zahl, die stehenbleibt, wenn es niemand tut. */}
      {/* **Kein Erklärtext** (#792). Was die Richtung bedeutet, sagt der Hover am
          Schieber; was hier nicht gefragt wird (Betrag, Artikel, Termin), muss niemand
          erklärt bekommen – man vermisst kein Feld, das nie dastand. Ein Absatz, der
          begründet, warum etwas fehlt, ist die Form, in der Dokumentation in die
          Oberfläche rutscht. */}
    </div>
  );
}

/**
 * **Verbrauch — die Stückliste: Artikel und Menge JE Einzelinstanz.**
 *
 * Es ist **dieselbe Komponente wie der Bedarf am Auftragsanfang** (`DefinitionLines`),
 * nur als Stückliste: die Menge gilt je Stück, und zwei der drei Fragen entfallen. Die
 * *Herkunft* – eine Stückliste erzeugt nichts. Und die *konkreten Stücke*: ein Modul ist
 * eine Vorlage, es läuft je Auftrag und je Produkt-Stück erneut, und ein hier
 * festgenageltes Stück wäre nach dem ersten Mal verbraucht. Welche Kiste genommen wird,
 * sagt der Lagerist beim Ausführen – dort ist es eine echte Wahl.
 *
 * **Artikel, nicht Definitionszeilen.** Dasselbe Modul wird auch in der Artikel-Vorlage
 * definiert – der Erzeugungsprozess IST der Montageplan –, und dort gibt es noch keine
 * Zeilen. Eine Vorlage kann «4× Schraube M6» meinen, aber nicht «Zeile 2».
 *
 * **Gerechnet wird beim Erreichen**, nicht hier: wie viele Erzeugnisse ankommen, steht
 * beim Modellieren nicht fest. Ob der Bestand dann reicht, sagt das Modul im Auftrag.
 */
function ConsumptionFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  return (
    <DefinitionLines
      perUnit
      lines={m.lines.length ? m.lines : [emptyLine(1)]}
      setLines={(lines) => onChange({ lines })}
    />
  );
}


/**
 * **Die Stichprobe — eine Zeile, keine Maske.**
 *
 * Drei Formen und **eine** Zahl: alle (Vorgabe) · Anzahl · Prozent. Mehr braucht die
 * Frage nicht, und ein Formular mit fünf Feldern wäre die falsche Antwort auf etwas,
 * das sich in einem Satz stellen lässt.
 *
 * **Die Wörter stehen ausgeschrieben da.** Ein Anteil hat kein Bild, das man ohne
 * Vorwissen liest – ein Symbol, das man raten muss, ist keines (Testnotizen #618/#636).
 *
 * **«je Instanz» ist keine Beschriftungs-Kosmetik, sondern die Regel**: eine Stichprobe
 * wird aus einem Los gezogen (ISO 2859-1), und das Los ist die Instanz. «10 %» heisst
 * 10 % **aus jeder** Charge, nicht 10 % aus dem Haufen; sonst bliebe eine ganze Charge
 * womöglich ungeprüft.
 */
function SampleRow({ value, onChange }: {
  value: SampleDraft; onChange: (next: SampleDraft) => void;
}) {
  return (
    // **Die Beschriftung steht ÜBER den Knöpfen**, nicht neben ihnen: daneben stand sie
    // auf gleicher Höhe wie die Auswahl und las sich wie deren erste Option.
    <div className="flex flex-col gap-1">
      <span style={{
        font: '700 11px var(--font-body)', textTransform: 'uppercase',
        letterSpacing: '.07em', color: 'var(--fg-4)',
      }}>Stichprobe</span>
      <div className="flex flex-wrap items-center gap-2">
        <IconSwitch
          value={value.mode}
          onChange={(mode: SampleMode) => onChange({ mode, value: mode === 'free' ? value.value : '' })}
          options={SAMPLE_PRESETS.map((p) => ({
            value: p.value,
            icon: SAMPLE_ICON[p.value],
            label: p.label,
            hint: p.percent
              ? `${p.percent} % aller wartenden Einzelinstanzen`
              : 'Ein frei gewählter Anteil, aufgerundet',
          }))}
        />
        {value.mode === 'free' && (
          <>
            <input className={inputCls} style={{ width: 80 }} value={value.value}
              {...numericInputProps} placeholder="z. B. 10"
              onChange={(e) => onChange({ ...value, value: numericOnly(e.target.value) })} />
            <span className="text-xs" style={{ color: 'var(--fg-4)' }}>%</span>
          </>
        )}
      </div>
    </div>
  );
}

/** Die Art eines Erfassungspunktes – Symbol mit dem Namen im Hover. */
function PointIcon({ type, types }: { type: string; types: { key: string; label: string }[] }) {
  const Icon = CAPTURE_ICON[type] ?? CAPTURE_ICON.text;
  return (
    <span className="flex items-center justify-center flex-none rounded"
      style={{ width: 26, height: 26, color: 'var(--fg-3)' }}
      data-tip={types.find((t) => t.key === type)?.label ?? type}>
      <Icon size={14} />
    </span>
  );
}

/**
 * Der Inhalt eines Moduls im Entwurf: seine Erfassungspunkte.
 *
 * Es gibt **kein** «Pflicht ja/nein» mehr: alles, was angelegt ist, ist Pflicht. Ein
 * Schalter dafür wäre die Frage, warum man einen Erfassungspunkt anlegt, den niemand
 * ausfüllen muss – und jeder ausgeschaltete Punkt eine Lücke, die erst später auffällt.
 */
function ModuleFields({ module: m, types, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const defaultType = types[0]?.key ?? 'text';
  function setPoint(i: number, p: Partial<PointDraft>) {
    onChange({ points: m.points.map((row, n) => (n === i ? { ...row, ...p } : row)) });
  }

  return (
    <div className="flex flex-col gap-2">
      <SampleRow value={m.sample} onChange={(sample) => onChange({ sample })} />

      <div className="flex flex-col gap-1.5">
        {m.points.map((p, i) => (
          <div key={i} className="flex flex-wrap gap-1.5 items-center">
            {/* **Die Art ist das Symbol der Zeile, kein Feld** (Testnotiz #683). Gewählt
                wird sie unten mit der Palette – ein Auswahlfeld daneben wäre der zweite
                Weg zur selben Entscheidung. Umentscheiden heisst löschen und neu
                anlegen, wie beim Modul selbst. */}
            <PointIcon type={p.type} types={types} />
            <input className={inputCls} style={{ flex: 1, minWidth: 120 }} value={p.label}
              maxLength={120} placeholder="Erfassungspunkt, z. B. Gratfrei"
              onChange={(e) => setPoint(i, { label: e.target.value })} />
            {p.type === NEEDS_TARGET && (
              <>
                <input className={inputCls} style={{ width: 76 }} value={p.target ?? ''}
                  {...numericInputProps} placeholder="Soll"
                  onChange={(e) => setPoint(i, { target: numericOnly(e.target.value, { decimals: true }) })} />
                <input className={inputCls} style={{ width: 76 }} value={p.tolerance ?? ''}
                  {...numericInputProps} placeholder="± Tol."
                  onChange={(e) => setPoint(i, { tolerance: numericOnly(e.target.value, { decimals: true }) })} />
                {/* **Worin gemessen wird** – ein freies, kurzes Wort (Testnotiz #707).
                    Bewusst keine Liste: die Mengeneinheiten des Artikels beantworten
                    eine andere Frage («worin wird die Menge geführt») und kennen weder
                    °C noch bar; eine zweite Liste wäre endlos, und das System rechnet
                    nie mit der Einheit – es zeigt sie an. */}
                <input className={inputCls} style={{ width: 62 }} value={p.unit ?? ''}
                  maxLength={8} placeholder="Einheit" data-tip="mm · kg · °C …"
                  onChange={(e) => setPoint(i, { unit: e.target.value })} />
              </>
            )}
            <RowDelete label="Erfassungspunkt entfernen"
              onClick={() => onChange({ points: m.points.filter((_, n) => n !== i) })} />
          </div>
        ))}
      </div>

      {/* Ein Symbol je Erfassungstyp – dieselbe Geste wie die Modulauswahl, eine Ebene
          tiefer. Klick legt den Punkt an; ausgefüllt wird er dort, wo er steht. */}
      <div className="flex flex-wrap gap-1.5">
        {types.map((t) => {
          const Icon = CAPTURE_ICON[t.key] ?? CAPTURE_ICON.text;
          return (
            <button key={t.key} type="button" className="ix-palette ix-palette-sm"
              aria-label={`${t.label} hinzufügen`}
              onClick={() => onChange({
                points: [...m.points, { label: '', type: t.key || defaultType, target: '',
                                        tolerance: '', unit: '' }],
              })}>
              <Icon size={14} />
              <span className="ix-palette-name">{t.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
