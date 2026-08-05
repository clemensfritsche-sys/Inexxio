import { ShoppingCart, ClipboardCheck, ArrowLeftRight, User as UserIcon, Boxes, Blocks, Wrench, Loader, PackageX, CheckCircle2, XCircle, PackageMinus, Trash2, Receipt, Banknote, Lock, Ban, FileText, Building2 } from 'lucide-react';
import type { StepType, LocationType } from '@/types';
import { TONE, type StatusCfg } from '@/lib/status-flow';

export const STEP_META: Record<StepType, { label: string; icon: React.ElementType }> = {
  purchase:   { label: 'Beschaffen',     icon: ShoppingCart },   // Verb: was man tut (#274)
  inspection: { label: 'Datenerfassung', icon: ClipboardCheck },
  movement:   { label: 'Bewegung',       icon: ArrowLeftRight },
  // «Blocks» statt «Wrench» (Notiz #234): der Schritt setzt BEIDES ein – Material, das
  // verbraucht wird, und Werkzeug, das genutzt wird. Der Schraubenschlüssel behauptete nur
  // das Werkzeug (und ist innerhalb der Zeilen genau dafür reserviert).
  resource:   { label: 'Ressource',      icon: Blocks },   // Verbrauch + Betriebsmittel (Modus pro Zeile)
  // **Aussondern** ist EIN Modul mit zwei Wirkungen (Notiz #277): etwas aus dem
  // verwendbaren Bestand nehmen. Der Name kommt aus der Qualitätssicherung, wo genau
  // das «Aussonderung fehlerhafter Teile» heisst – «Ausschleusen» klang nach Logistik
  // und sagte nicht, was mit dem Teil geschieht (Notiz #328).
  // verwendbaren Bestand nehmen – **Verschrotten** endgültig (Bestandsabgang, standortlos)
  // oder **Sperren** vorübergehend (quality='blocked', an der Instanz aufhebbar). Der
  // Unterschied ist die Wirkung, nicht die Sache; beide sind rot, beide verlangen einen
  // Grund. Die zwei Schritttypen bleiben im Datenmodell getrennt – ihre Fachwirkung ist
  // grundverschieden –, an der Oberfläche sind sie EIN Modul.
  scrap:      { label: 'Aussondern',     icon: PackageX },
  block:      { label: 'Aussondern',     icon: PackageX },
  sale:       { label: 'Verkauf',        icon: Receipt },   // bedient auch die Gutschrift/Erstattung (Kredit-Modus)
  document:   { label: 'Dokument',       icon: FileText },  // erzeugt ein nummeriertes Dokument (Vertrag/AGB/Zertifikat)
};

/**
 * **Wie viel dieser Instanz gehört DIESEM Auftrag?** – die eine Antwort im Frontend
 * (Testnotizen #412/#414), Spiegel von ``subject.held_quantity``.
 *
 * Eine Instanz ist eine Menge, und ihre Menge ist auf Aufträge aufgeteilt. Jede Aussage
 * eines Auftrags über «diese Instanz» meint seinen **Anteil** – wie viele Stück er bewegt,
 * aussondert oder anzeigt. Wer stattdessen ``quantity`` liest, rechnet mit fremdem Material:
 * genau so verschrottete eine Abweichung, die 2 von 4 hielt, die ganze Charge.
 *
 * Der Rückfall auf ``quantity`` gilt für Zusammenhänge ohne Auftrag (Instanz-Detail,
 * Bestandsliste) – dort ist die ganze Instanz die richtige Antwort.
 */
export function heldOf(i: { held_quantity?: number | null; quantity?: number | null }): number {
  return i.held_quantity ?? i.quantity ?? 0;
}

/**
 * **Der Zustand eines Prozessschritts in Worten** – EINE Stelle für das ganze Frontend.
 *
 * Im Fluss selbst steht der Zustand als Symbol (Haken · Pause · Kreuz) und über die Farbe;
 * ausgeschrieben wird er nur dort, wo kein Platz für ein Symbol ist – im Hover. Damit dieses
 * Wort nicht in jeder Ansicht neu erfunden wird, steht es hier neben ``STEP_META``.
 *
 * «Im Prozess» ist dabei der EINE Name für «läuft gerade» (Notizen #89/#90) – derselbe wie
 * am Auftrag und an der Instanz.
 */
export const STEP_STATE_LABEL: Record<string, string> = {
  done: 'Erledigt',
  active: 'Im Prozess',
  blocked: 'Angehalten',
  locked: 'Wartet',
  failed: 'Fehlgeschlagen',
};

export function stepStateLabel(state: string): string {
  return STEP_STATE_LABEL[state] ?? state;
}

// Standort-Typen (Bewegung): Label + Icon
export const LOCATION_META: Record<LocationType, { label: string; icon: React.ElementType }> = {
  user:       { label: 'Person',     icon: UserIcon },
  instance:   { label: 'Instanz',    icon: Boxes },
  company:    { label: 'Unternehmen', icon: Building2 },
};

export function locationTypeLabel(type: string | null | undefined): string {
  return type ? (LOCATION_META[type as LocationType]?.label ?? type) : '—';
}

/** Eine Instanz heisst schlicht «Instanz». Bei einer Charge (kind='batch') kann
 *  optional die Menge ergänzt werden (z. B. «Instanz · 5 Stk»). */
/**
 * Beschriftung einer Instanz-Zeile: «Instanz · 5 Stk».
 *
 * Die Menge steht bei **jeder** Instanz, auch beim Einzelstück (Notiz #285) – bei einer
 * Charge trägt sie die eigentliche Information, beim Einzelteil schafft sie Einheitlichkeit:
 * man sucht die Angabe nicht mal hier, mal dort. Fehlt die Menge, bleibt es beim Wort.
 */
export function instanceLabel(quantity?: number | null, unit?: string): string {
  if (quantity != null) return `Instanz · ${formatQty(quantity)} ${unit ?? ''}`.trim();
  return 'Instanz';
}

/**
 * **Menge lesbar machen** – ganze Zahlen ohne Nachkommastellen, Bruchmengen (kg, m², l)
 * mit bis zu drei. EINE Stelle, damit «2» und «2.000» nicht nebeneinander stehen.
 */
export function formatQty(v: number): string {
  return v.toLocaleString('de-CH', { maximumFractionDigits: 3 });
}

/**
 * **Wie viel ist das?** – Summe der Mengen, NICHT die Zahl der Zeilen.
 *
 * Die wiederkehrende Fehlerklasse rund um Instanzen ist «Zeilen zählen statt Mengen
 * summieren»: eine Charge à 500 Schrauben ist EINE Instanz und FÜNFHUNDERT Stück, also
 * liefert `items.length` die Zahl 1, wo 500 gemeint sind (Testnotizen #72, #333). Wer eine
 * Menge braucht, nimmt diese Funktion; `length` sagt nur, wie viele Datensätze es sind.
 * Das Backend erzwingt dieselbe Regel über `tests/test_quantity_rules.py`.
 */
export function sumQuantity(items: { quantity?: number | null }[]): number {
  return items.reduce((sum, i) => sum + Number(i.quantity ?? 1), 0);
}

// **Herstellung vs. Bestands-Operation** ist keine Frage der Schritt-TYPEN mehr
// (Testnotiz #622): Instanzen entstehen ausschliesslich aus dem Prozess des ARTIKELS,
// also ist jeder Auftrag mit **eigenem** Ablauf ein Zugriff auf vorhandenen Bestand.
// Die frühere Rollen-Tabelle (Beschaffung/Ressource = «produce» …) war ein Spiegel einer
// Backend-Ableitung, die es nicht mehr gibt – und sie überstimmte die ausdrückliche Wahl
// «Ab Lager» im Bedarf. Die eine Bedingung lautet jetzt schlicht: `steps.length > 0`.


// Anzeige-Projektion der ZWEI Achsen (quality + disposition) auf EINE Badge.
// Bedeutungs-Vorrang: Verbleib (scrapped/sold/consumed) ≻ Verdikt (failed) ≻
// am Lager (passed+in_stock) ≻ sonst «Im Prozess». Das Datenmodell bleibt getrennt;
// nur die Darstellung fasst beides zu einem Status zusammen.
// Reine Ampel (TONE): «Im Prozess»/«Gesperrt» = GELB (läuft oder ausgesetzt – jedenfalls
// **umkehrbar**), «Freigegeben» = GRÜN (am Lager, frei). Terminal: «Verbaut»/«Verkauft» =
// GRÜN (positiv erfüllt), «Verschrottet» = ROT – der EINE endgültige Zustand (Notiz #360:
// gesperrt lässt sich entsperren, verschrottet nie).
//
// **«Reserviert» gibt es nicht mehr** (Testnotizen #625/#626): es war ein dritter Zustand
// für etwas, das «Im Prozess» längst sagt – ein Stück, das ein laufender Auftrag hält, IST
// in einem Prozess. Der Unterschied («schon im Prozess» ↔ «am Lager und gebunden») war eine
// Frage des Zeitpunkts, nicht der Sache: verwendbar ist es in beiden Fällen nicht, und wer
// es hält, steht daneben. Ein Zustand weniger, dieselbe Aussage.
const INSTANCE_STATUS: Record<string, StatusCfg> = {
  in_process: { label: 'Im Prozess',   ...TONE.pending, icon: Loader },
  in_stock:   { label: 'Freigegeben',  ...TONE.done,    icon: CheckCircle2 },
  // EIN Zustand «vorhanden, aber nicht verwendbar» – gleich ob eine Datenerfassung die
  // Instanz durchfallen liess oder ein «Sperren»-Schritt sie bewusst ausgesetzt hat.
  // Beides verhält sich identisch (fällt aus FIFO/Bestand, ist aufhebbar) und heisst
  // darum auch gleich. Gesperrt ist WARTEND, nicht tot: die Instanz kommt zurück –
  // darum gelb wie alles Offene, nicht rot wie das endgültige Verschrotten.
  blocked:    { label: 'Gesperrt',     ...TONE.pending, icon: Ban },
  consumed:   { label: 'Verbaut',      ...TONE.done,    icon: PackageMinus },
  scrapped:   { label: 'Verschrottet', ...TONE.danger,  icon: Trash2 },
  sold:       { label: 'Verkauft',     ...TONE.done,    icon: Banknote },
};

/**
 * Projektion der zwei Achsen (quality + disposition) auf EINE Badge.
 *
 * `held` = «ein laufender Auftrag hält das» – dann ist es **Im Prozess**, nicht
 * «Freigegeben»: am Lager zu liegen und trotzdem gebunden zu sein, ist kein eigener
 * Zustand (#626). Wer es hält, steht daneben (die Stück-Zeile nennt den Auftrag).
 */
export function instanceStatusConfig(
  quality: string | null | undefined,
  disposition: string | null | undefined,
  held: boolean = false,
): StatusCfg {
  if (disposition === 'scrapped') return INSTANCE_STATUS.scrapped;
  if (disposition === 'sold') return INSTANCE_STATUS.sold;
  if (disposition === 'consumed') return INSTANCE_STATUS.consumed;
  // 'failed' ist Altbestand vor Migration 085 und meint dasselbe wie 'blocked'.
  if (quality === 'blocked' || quality === 'failed') return INSTANCE_STATUS.blocked;
  if (quality === 'passed' && disposition === 'in_stock' && !held)
    return INSTANCE_STATUS.in_stock;
  return INSTANCE_STATUS.in_process;
}
