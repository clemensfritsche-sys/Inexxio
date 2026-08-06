/**
 * Spiegel von `backend/app/core/features.py` – der EINE Schalter.
 *
 * Was hier steht, muss dort genauso stehen: `backend/tests/test_frontend_mirrors.py`
 * vergleicht beide Seiten. Ein Modul, das nur auf einer Seite abgeschaltet ist, wäre
 * genau die Art von zweiter Wahrheit, die dieses Projekt nicht will.
 *
 * Die Oberfläche liest das hier, um abgeschaltete Bereiche gar nicht erst anzubieten.
 * Was trotzdem beim Backend landet, bekommt dort 503 mit `code: "MODULE_DISABLED"` –
 * die Oberfläche ist die Höflichkeit, das Backend die Grenze.
 */

export type FeatureModule =
  | 'core'
  | 'catalog'
  | 'capture'
  | 'process'
  | 'sales'
  | 'documents'
  | 'ai';

export const MODULE_LABEL: Record<FeatureModule, string> = {
  core: 'Anmeldung, Benutzer, Unternehmen, Feed, Objektnummern',
  catalog: 'Artikel, Instanzen, Einzelinstanzen',
  capture: 'Datenerfassung',
  process: 'Auftrag und Prozesslogik',
  sales: 'Verkauf und Shop',
  documents: 'Dokumente, Belege, Rechtstexte, Einwilligungen',
  ai: 'KI-Assistent',
};

/** DIE Entscheidung – identisch mit ACTIVE in features.py. */
export const ACTIVE: readonly FeatureModule[] = ['core', 'catalog', 'capture'];

export function isActive(module: FeatureModule): boolean {
  return ACTIVE.includes(module);
}

/** Text für eine abgeschaltete Fläche – überall derselbe Satz. */
export function disabledNotice(module: FeatureModule): string {
  return `Das Modul «${MODULE_LABEL[module]}» ist abgeschaltet, solange die Basis neu aufgebaut wird.`;
}
