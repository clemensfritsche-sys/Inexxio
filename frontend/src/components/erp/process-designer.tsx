'use client';

import { useCallback, useEffect, useState } from 'react';
import { Columns2, Grid2x2, Layers, Lock, Percent, Trash2, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { ModuleCatalog, ModuleTypeInfo, SupplierOption } from '@/types';
import {
  CAPTURE_ICON, DISPOSAL_MODES, moduleIcon, NEEDS_TARGET, SAMPLE_PRESETS, blankModule,
  moduleTone,
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
import { IconSwitch, Label, inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';
import { DefinitionLines, emptyLine } from '@/components/erp/definition-lines';
import { ObjectSelect } from '@/components/erp/object-select';
import type { PlaceRef } from '@/types';

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
          const info = (catalog?.modules ?? []).find((x) => x.key === m.moduleType);
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
                {/* ►► **Wer einkaufen kann, definiert seinen Beleg – hier, wie jeder
                    andere auch.** ◄◄
                    Der Block hängt an `buys` und nicht an einer Liste von Modultypen in
                    dieser Datei: ein neuer einkaufender Typ bekommt ihn, ohne dass
                    jemand das Frontend anfasst. Ob die Angaben Pflicht sind und ob
                    daneben etwas Abgeleitetes steht, sagt derselbe Eintrag – die
                    Oberfläche fragt nie nach dem Modultyp (#777). */}
                {info?.buys && (
                  <ProcurementFields module={m} info={info}
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
      emptyOption="Beim Ausführen scannen"
    />
  );
}

/**
 * **Beschaffen: bei wem — und was zu tun ist.** Zwei Angaben, mehr braucht ein Einkauf nicht.
 *
 * **Kein Artikelfeld.** *Was* beschafft wird, sagt der Prozess: die Einzelinstanzen, die
 * vor dem Modul stehen, tragen ihren Artikel. Es daneben zu tippen wäre eine zweite
 * Aussage über dieselbe Sache – und die getippte gewinnt auch dann, wenn sie falsch ist.
 * Stehen Stücke zweier Artikel davor, hat der Beleg zwei Zeilen: EINE Bestellung mit
 * zwei Positionen, wie im echten Leben.
 *
 * **Dafür der Auftrag an den Lieferanten.** Die Artikel-Spezifikation beschreibt die
 * Sache und reist mit dem Beleg; was mit ihr geschehen soll, steht dort nicht – «Härten
 * auf 58 HRC» ist eine Eigenschaft *dieses* Schritts, und ein Artikel hat mehrere.
 *
 * Die Lieferanten sind eine **Liste**, auch wenn fast immer einer drinsteht: wer
 * vergleichen will, nennt drei, und der Angebotsvergleich ist damit kein zweiter
 * Mechanismus, sondern dieselbe Liste eine Zeile länger. Fachlich die Lieferantenfreigabe.
 *
 * **Keine Menge und kein «Webshop»-Modus**: die Menge ist die Zahl der Stücke vor dem
 * Modul, und wo jemand seinen Shop hat, ist eine Eigenschaft des Lieferanten – nicht
 * dieser Bestellung.
 */
function ProcurementFields({ module: m, info, onChange }: {
  module: ModuleDraft;
  info: ModuleTypeInfo;
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const [known, setKnown] = useState<Record<number, string>>({});

  // **Mit wem gehandelt wird, sagt der Katalog** (`party_role`) – ein Lieferant beim
  // Einkauf, ein Kunde beim Verkauf. Die Oberfläche fragt nie nach dem Modultyp: ein
  // `if` hier wäre die zweite Stelle für dieselbe Regel, und der Dienst wiese danach ab.
  const role = info.party_role;
  // **Und wie sie im Satz heisst, kommt aus derselben Quelle.** «Auftrag an den
  // Lieferanten» wäre am Verkaufs-Modul falsch; ein zweiter Text daneben, gewählt über
  // den Modultyp, wäre die dritte Stelle für dieselbe Angabe.
  const orderLabel = info.derived_instruction
    ? 'Ergänzung zum Auftrag' : `Auftrag an den ${info.party_word}en`;

  // Die gewählten Gegenparteien benennen – sonst stünden dort nur Ziffern. Eine Abfrage
  // je Modul, nicht je Zeile.
  useEffect(() => {
    const missing = m.suppliers.filter((r) => !(r.supplier in known));
    if (missing.length === 0) return;
    let stale = false;
    void Promise.all(missing.map((r) => api.searchParties(role, String(r.supplier), 1)))
      .then((groups) => {
        if (stale) return;
        const found: Record<number, string> = {};
        groups.flat().forEach((o) => { found[o.object_id] = o.name; });
        setKnown((k) => ({ ...k, ...found }));
      })
      .catch(() => {});
    return () => { stale = true; };
  }, [m.suppliers, known, role]);

  const findSuppliers = useCallback(
    (q: string) => api.searchParties(role, q).catch(() => []), [role]);

  return (
    <div className="flex flex-col gap-3">
      {/* ►►► **Ein Feld gibt es genau dann, wenn das Modul es DEKLARIERT.** ◄◄◄
          `off` · `optional` · `required` (`ModuleTypeInfo.parties` / `.instruction`).
          Vorher waren es zwei Booleans, und der Zustand «gibt es hier gar nicht» fehlte
          darin – daraus wurde ein Feld, das freiwillig dastand, weil man es *vielleicht*
          braucht, mit einer Beschriftung, die nirgends passt («Auftrag an den Kundeen»,
          #780/#781). Ein Feld als Vielleicht ist schlimmer als keines. */}
      {info.instruction !== 'off' && (
      <div className="flex flex-col gap-1.5">
        <Label>{orderLabel}</Label>
        {/* **Was abgeleitet ist, steht als Wert da – nicht als Vorschlag im Feld.**
            «Transport von A nach B» kennt der Vorgang selbst; ihn hier eintippbar zu
            machen wäre die zweite Aussage über dieselbe Sache, und die getippte gewänne
            auch falsch. Die Eingabe daneben ist das, was NUR ein Mensch weiss
            («Hebebühne nötig») – darum heisst sie dort «Ergänzung» (#777). */}
        {info.derived_instruction && (
          <p className="text-[12px]" style={{ color: 'var(--fg-3)' }}>
            Steht bereits im Auftrag: «{info.derived_instruction} …» – abgeleitet aus
            Herkunft und Ziel.
          </p>
        )}
        <textarea
          className={inputCls}
          rows={2}
          maxLength={400}
          value={m.instruction}
          required={info.instruction === 'required'}
          placeholder={info.derived_instruction
            ? 'z. B. Hebebühne nötig · nur werktags · Gefahrgut'
            : 'z. B. Härten auf 58 HRC · gemäss Zeichnung fertigen · liefern'}
          aria-label={orderLabel}
          onChange={(e) => onChange({ instruction: e.target.value })}
          style={{ resize: 'vertical', minHeight: 54 }}
        />
      </div>
      )}
      {info.parties !== 'off' && (
      <div className="flex flex-col gap-1.5">
        <ObjectSelect<SupplierOption>
          label={`Zugelassene ${info.party_word}en`}
          required={info.parties === 'required'}
          value={null}
          selected={null}
          find={findSuppliers}
          scanLabel={info.party_word}
          placeholder="Nummer oder Name"
          onChange={(nr, opt) => {
            if (nr === null || m.suppliers.some((r) => r.supplier === nr)) return;
            if (opt) setKnown((k) => ({ ...k, [nr]: opt.name }));
            onChange({ suppliers: [...m.suppliers, { supplier: nr, ref: '' }] });
          }}
        />
        {/* **Leer heisst frei, nicht «niemand»** – dieselbe Regel wie im Dienst
            (`Module.suppliers_of`). Wo der Einkauf nur eine Möglichkeit ist, entscheidet
            sich erst zur Laufzeit, wer fährt; eine Pflichtliste wäre dort eine Hürde
            ohne Gegenwert. Dass man sie trotzdem füllen KANN, ist der Punkt: «wir fahren
            nur mit diesen drei» ist eine echte Hausregel. */}
        {info.parties !== 'required' && m.suppliers.length === 0 && (
          <p className="text-[12px]" style={{ color: 'var(--fg-3)' }}>
            Leer: freie Wahl beim Ausführen.
          </p>
        )}
        {/* **Wer liefern darf – und wie man bei ihm bestellt.** Die Bestellangabe steht
            hier und nicht am Beleg: sie ist eine Eigenschaft der Paarung Modul ×
            Lieferant («seine Artikelnummer», «sein Shop-Link») und ändert sich nicht je
            Bestellung. Am Beleg wäre sie eine Angabe, die man jedes Mal neu abschreibt
            – genau das war das alte Referenz-Feld (#753). */}
        {m.suppliers.map((row) => (
          <div key={row.supplier} className="flex flex-col gap-1"
            style={{ borderTop: '1px solid var(--border-1)', paddingTop: 5 }}>
            <div className="flex items-center gap-2 text-[13px]">
              <ObjId value={row.supplier} />
              <span className="flex-1 truncate" style={{ color: 'var(--fg-3)' }}>
                {known[row.supplier] ?? ''}
              </span>
              <button type="button" className="erp-fieldaction" aria-label="Entfernen"
                data-tip="Nicht mehr zugelassen"
                onClick={() => onChange({
                  suppliers: m.suppliers.filter((x) => x.supplier !== row.supplier),
                })}
                style={{ position: 'static', transform: 'none' }}>
                <X size={14} />
              </button>
            </div>
            <input className={inputCls} value={row.ref} maxLength={200} required
              placeholder={`Artikelnummer oder Link beim ${info.party_word}en`}
              aria-label={`Bestellangabe für ${row.supplier}`}
              onChange={(e) => onChange({
                suppliers: m.suppliers.map((x) => (
                  x.supplier === row.supplier ? { ...x, ref: e.target.value } : x)),
              })} />
          </div>
        ))}
      </div>
      )}
    </div>
  );
}


/**
 * **Was ein Modultyp ZUSÄTZLICH hat.** Eine Zuordnung, keine Bedingung – und jeder Typ
 * steht darin, auch der mit `null`: die Liste beantwortet «kennt die Oberfläche diesen
 * Typ?», und ein fehlender Schlüssel ist die Antwort «nein».
 *
 * **Der Einkaufs-Block steht bewusst NICHT hier.** Er hängt an `ModuleTypeInfo.buys`
 * (siehe `renderStep`), denn er gehört dem **Beleg** und nicht einem Modultyp – seit
 * auch das Bewegen-Modul einen tragen kann, wäre ein Eintrag je Typ die Stelle, an der
 * man den nächsten vergisst. `beschaffen` trägt darum `null`: ausser seinem Beleg hat es
 * nichts zu konfigurieren.
 */
const MODULE_FIELDS: Record<string, React.ComponentType<{
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}> | null> = {
  datenerfassung: ModuleFields,
  // Beide handelnden Module tragen `null`: ausser ihrem Beleg haben sie nichts zu
  // konfigurieren, und den rendert `renderStep` über `buys` – für jedes Modul gleich.
  beschaffen: null,
  verkauf: null,
  aussondern: DisposalFields,
  verbrauch: ConsumptionFields,
  bewegen: MoveFields,
};

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
            <button type="button" aria-label="Erfassungspunkt entfernen"
              className="flex items-center justify-center rounded flex-none"
              style={{ width: 26, height: 26, color: 'var(--danger)' }}
              onClick={() => onChange({ points: m.points.filter((_, n) => n !== i) })}>
              <Trash2 size={13} />
            </button>
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
