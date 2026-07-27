import { ShoppingCart, ClipboardCheck, ArrowLeftRight, User as UserIcon, Boxes, Wrench, Clock, CheckCircle2, XCircle, PackageMinus, Trash2, Receipt, Banknote, Lock, Ban, FileText, Building2 } from 'lucide-react';
import type { StepType, LocationType } from '@/types';
import type { StepState } from '@/components/erp/process-stepper';
import { TONE, type StatusCfg } from '@/lib/status-flow';

export const STEP_META: Record<StepType, { label: string; icon: React.ElementType }> = {
  purchase:   { label: 'Beschaffung',    icon: ShoppingCart },
  inspection: { label: 'Datenerfassung', icon: ClipboardCheck },
  movement:   { label: 'Bewegung',       icon: ArrowLeftRight },
  resource:   { label: 'Ressource',      icon: Wrench },   // Verbrauch + Betriebsmittel (Modus pro Zeile)
  scrap:      { label: 'Verschrotten',   icon: Trash2 },
  // Sperren = das reversible Gegenstück: die Instanz bleibt, darf aber nicht verwendet
  // werden (quality='blocked'); aufhebbar an der Instanz.
  block:      { label: 'Sperren',        icon: Lock },
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
export function instanceLabel(
  kind?: string | null,
  quantity?: number | null,
  unit?: string,
): string {
  if (kind === 'batch' && quantity != null) return `Instanz · ${quantity} ${unit ?? ''}`.trim();
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

// Auftrag-Schrittstatus (Backend) → Stepper-Knotenstatus
export function toStepperState(state: string): StepState {
  if (state === 'done') return 'done';
  if (state === 'active') return 'active';
  if (state === 'failed') return 'rejected';
  if (state === 'blocked') return 'blocked';   // wartet auf Material (Nachschub)
  return 'pending'; // locked
}

// Anzeige-Projektion der ZWEI Achsen (quality + disposition) auf EINE Badge.
// Bedeutungs-Vorrang: Verbleib (scrapped/sold/consumed) ≻ Verdikt (failed) ≻
// am Lager (passed+in_stock) ≻ sonst «In Arbeit». Das Datenmodell bleibt getrennt;
// nur die Darstellung fasst beides zu einem Status zusammen.
// Reine Ampel (TONE): «In Arbeit»/«Reserviert» = GELB (läuft/gebunden), «Freigegeben»
// = GRÜN (am Lager, frei). Terminal: «Verbaut»/«Verkauft» = GRÜN (positiv erfüllt),
// «Gesperrt»/«Verschrottet» = ROT (Ampel auf «Stopp», nicht mehr verwendbar).
const INSTANCE_STATUS: Record<string, StatusCfg> = {
  in_process: { label: 'In Arbeit',    ...TONE.pending, icon: Clock },
  in_stock:   { label: 'Freigegeben',  ...TONE.done,    icon: CheckCircle2 },
  reserved:   { label: 'Reserviert',   ...TONE.pending, icon: Lock },
  // «Durchgefallen» (Prüfung) und «Gesperrt» (bewusst ausgesetzt) sind zwei
  // verschiedene Dinge – vorher trugen beide dasselbe Wort.
  failed:     { label: 'Durchgefallen', ...TONE.danger,  icon: XCircle },
  // Gesperrt ist WARTEND, nicht tot: die Instanz kommt zurück (Wartung/Prüfung) –
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
  if (quality === 'blocked') return INSTANCE_STATUS.blocked;
  if (quality === 'failed') return INSTANCE_STATUS.failed;
  if (quality === 'passed' && disposition === 'in_stock')
    return reserved ? INSTANCE_STATUS.reserved : INSTANCE_STATUS.in_stock;
  return INSTANCE_STATUS.in_process;
}
