/**
 * **Rechtsformen je Land** – Vorschläge für ein **Freitextfeld** (`datalist`), keine
 * Auswahlliste; träge Daten ohne brauchbare API, darum im Code.
 *
 * ►►► **EINE Liste für jede Stelle, die die Rechtsform fragt.** ◄◄◄ Im Frontend, weil das
 * System nie mit der Rechtsform rechnet, es setzt sie nur an den Namen (`sites.legal_name`).
 */

import { toIso2 } from '@/components/erp/address-field';

const LEGAL_FORMS_BY_ISO2: Record<string, string[]> = {
  CH: ['AG', 'GmbH', 'Einzelunternehmen', 'Kollektivgesellschaft', 'Kommanditgesellschaft',
       'Genossenschaft', 'Verein', 'Stiftung', 'Zweigniederlassung'],
  LI: ['AG', 'GmbH', 'Anstalt', 'Stiftung', 'Treuunternehmen'],
  DE: ['GmbH', 'UG (haftungsbeschränkt)', 'AG', 'GmbH & Co. KG', 'KG', 'OHG', 'e.K.', 'GbR', 'eG', 'e.V.'],
  AT: ['GmbH', 'AG', 'OG', 'KG', 'e.U.', 'Genossenschaft'],
  US: ['Inc.', 'LLC', 'Corp.', 'LP', 'LLP', 'Sole Proprietorship'],
  GB: ['Ltd', 'PLC', 'LLP', 'Sole Trader'],
  FR: ['SARL', 'SAS', 'SASU', 'SA', 'EURL', 'SCI'],
  IT: ['S.r.l.', 'S.p.A.', 'S.n.c.', 'S.a.s.', 'Ditta individuale'],
  ES: ['S.L.', 'S.A.', 'Autónomo'],
  NL: ['B.V.', 'N.V.', 'Eenmanszaak', 'V.O.F.'],
  BE: ['BV', 'NV', 'VOF', 'CommV'],
  LU: ['S.à r.l.', 'S.A.', 'SCS'],
  PT: ['Lda.', 'S.A.', 'Unipessoal Lda.'],
  IE: ['Ltd', 'PLC', 'DAC', 'Sole Trader'],
};

/** Die Vorschläge für ein Land – leer, wo wir keine kennen (dann bleibt es Freitext). */
export function legalForms(country: string | undefined): string[] {
  return LEGAL_FORMS_BY_ISO2[toIso2(country)] ?? [];
}
