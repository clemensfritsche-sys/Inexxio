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
export function instanceLabel(
  kind?: string | null,
  quantity?: number | null,
  unit?: string,
): string {
  if (quantity != null) return `Instanz · ${quantity} ${unit ?? ''}`.trim();
  return 'Instanz';
}

// Deklarierte Subjekt-Rolle je Schritttyp – **Spiegel** der Backend-Registry
// (`app/domain/event_types.py`). Ein Schritt, der Bestand HEREINBRINGT (Beschaffung/
// Ressource), ist «produce»; ein Zugriff auf vorhandenen Bestand (Verkauf) «stock»,
// eine Bearbeitung bestehender Instanzen (Bewegung/Prüfung/Verschrottung) «instance».
const STEP_SUBJECT_ROLE: Record<StepType, 'produce' | 'stock' | 'instance'> = {
  purchase:   'produce',
  resource:   'produce',
  sale:       'stock',
  movement:   'instance',
  inspection: 'instance',
  block:      'instance',
  scrap:      'instance',
  document:   'produce',   // erzeugt einen (nicht-physischen) Liefergegenstand – kein Bestandszugriff
};

/** Ist der Ablauf eine **Bestands-Operation** (wirkt auf vorhandenen Bestand) statt einer
 *  **Herstellung** (erzeugt neue Instanzen)? Ableitung über die deklarierte Subjekt-Rolle
 *  der Schritte mit Vorrang STOCK ≻ PRODUCE ≻ INSTANCE – identisch zu
 *  `event_types.derive_subject_mode` im Backend. Ohne Schritte = Herstellung (false). */
export function isStockOperation(stepTypes: StepType[]): boolean {
  if (stepTypes.length === 0) return false;               // keine Schritte → Herstellung
  const roles = new Set(stepTypes.map((t) => STEP_SUBJECT_ROLE[t] ?? 'instance'));
  if (roles.has('stock')) return true;                    // Verkauf ab Lager
  if (roles.has('produce')) return false;                 // Beschaffung/Ressource → Herstellung
  return true;                                            // nur Bewegung/Prüfung/Verschrotten
}


// Anzeige-Projektion der ZWEI Achsen (quality + disposition) auf EINE Badge.
// Bedeutungs-Vorrang: Verbleib (scrapped/sold/consumed) ≻ Verdikt (failed) ≻
// am Lager (passed+in_stock) ≻ sonst «Im Prozess». Das Datenmodell bleibt getrennt;
// nur die Darstellung fasst beides zu einem Status zusammen.
// Reine Ampel (TONE): «Im Prozess»/«Reserviert» = GELB (läuft/gebunden), «Freigegeben»
// = GRÜN (am Lager, frei). Terminal: «Verbaut»/«Verkauft» = GRÜN (positiv erfüllt),
// «Gesperrt»/«Verschrottet» = ROT (Ampel auf «Stopp», nicht mehr verwendbar).
const INSTANCE_STATUS: Record<string, StatusCfg> = {
  in_process: { label: 'Im Prozess',   ...TONE.pending, icon: Loader },
  in_stock:   { label: 'Freigegeben',  ...TONE.done,    icon: CheckCircle2 },
  reserved:   { label: 'Reserviert',   ...TONE.pending, icon: Lock },
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

// Projektion der zwei Achsen (quality + disposition) PLUS Reservierung auf EINE Badge.
// Eine **fest reservierte** (für einen freigegebenen Auftrag gebundene) Lagerinstanz
// wird als «Reserviert» gezeigt. Teil-/Chargen-Reservierung ist nicht nötig: bei der
// Allokation wird eine Charge **geteilt** (reservierter Teil = eigene Instanz), sodass
// Reservierung je Instanz immer ganz-oder-gar-nicht ist.
export function instanceStatusConfig(
  quality: string | null | undefined,
  disposition: string | null | undefined,
  reserved: boolean = false,
): StatusCfg {
  if (disposition === 'scrapped') return INSTANCE_STATUS.scrapped;
  if (disposition === 'sold') return INSTANCE_STATUS.sold;
  if (disposition === 'consumed') return INSTANCE_STATUS.consumed;
  // 'failed' ist Altbestand vor Migration 085 und meint dasselbe wie 'blocked'.
  if (quality === 'blocked' || quality === 'failed') return INSTANCE_STATUS.blocked;
  if (quality === 'passed' && disposition === 'in_stock')
    return reserved ? INSTANCE_STATUS.reserved : INSTANCE_STATUS.in_stock;
  return INSTANCE_STATUS.in_process;
}
