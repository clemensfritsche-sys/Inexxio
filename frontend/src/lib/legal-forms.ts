/**
 * **Rechtsformen je Land** (Testnotiz #303) – Vorschläge, keine Auswahlliste.
 *
 * Eine brauchbare API dafür gibt es nicht: die einzige verbindliche Quelle ist die
 * ISO-20275-Liste der GLEIF («Entity Legal Forms»), ein Download mit ~2600 Einträgen ohne
 * Abfrage-Endpunkt – für eine Vorbelegung von acht Zeilen der falsche Preis. Die Liste ist
 * ausserdem träge (Rechtsformen ändern sich in Jahrzehnten, nicht in Wochen), also ist sie
 * im Code richtig aufgehoben.
 *
 * Es bleibt ein **Freitextfeld** mit `datalist`: die Vorschläge decken den Normalfall,
 * jede Exotik (Anstalt, SCE, Zweigniederlassung) bleibt tippbar.
 *
 * ►►► **EINE Liste, zwei Aufrufstellen** (Testnotiz #1042). ◄◄◄ Sie lag in
 * `organization-detail.tsx` – dort wird die Rechtsform **unserer** Gesellschaften
 * gepflegt. Seit ein Geschäftskonto am Benutzer dieselbe Angabe trägt, gibt es eine
 * zweite Stelle, die sie fragt; kopiert wäre sie die Liste, die beim nächsten Land
 * auseinanderläuft. *Sie steht darum hier und nicht im Backend: das System rechnet nie
 * mit der Rechtsform, es setzt sie an den Namen (`sites.legal_name`) – eine Liste von
 * Vorschlägen ist eine Eingabehilfe, kein Fachmodell.*
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
