// @ts-check
/**
 * Prüfpflicht für Krane in der Schweiz – Daten für den Prüfpflicht-Check, die Tabelle auf
 * /krantechnik/kranservice und den Ratgeber. Eine Quelle, drei Darstellungen.
 *
 * Grundlage (Stand der Recherche Oktober 2026):
 *  - Kranverordnung (SR 832.312.15): zu jedem Kran gehört ein Kranbuch; die Form ist frei.
 *  - EKAS-Richtlinie 6511 (Ausgabe 17.10.2023): Fahrzeug- und Turmdrehkrane jährlich durch
 *    Kranfachleute überprüfen; periodische Kontrolle durch einen Kranexperten – bis 20 Jahre
 *    alle 4 Jahre, 21 bis 30 Jahre alle 2 Jahre, ab 31 Jahren jährlich.
 *  - Alle anderen Krane: regelmässige Überprüfung nach Herstellerangaben durch Kranfachleute.
 * Nicht behaupten: dass INEXXIO Kranexperten-Kontrollen durchführt oder Suva-anerkannt ist.
 */
export const inspection = {
  note: 'Unverbindliche Orientierung. Massgebend sind die Angaben des Herstellers und die Vorgaben der Suva.',
  types: [
    {
      value: 'halle',
      label: 'Hallenkran',
      hint: 'Brücken-, Hänge-, Schwenk- oder Drehkran in Halle oder Werkhof',
      expert: false,
    },
    {
      value: 'heukran',
      label: 'Heukran',
      hint: 'Kran in der Landwirtschaft, z. B. eine HS-Krananlage',
      expert: false,
    },
    {
      value: 'fahrzeug',
      label: 'Fahrzeugkran',
      hint: 'Mobil- oder Raupenkran, grosser Lastwagen-Ladekran',
      expert: true,
    },
    {
      value: 'turm',
      label: 'Turmdrehkran',
      hint: 'Baukran (oben- oder untendrehend)',
      expert: true,
    },
  ],
  ages: [
    { value: 'bis20', label: 'bis 20 Jahre', expertEvery: 'alle 4 Jahre' },
    { value: '21-30', label: '21 bis 30 Jahre', expertEvery: 'alle 2 Jahre' },
    { value: 'ab31', label: 'über 30 Jahre', expertEvery: 'jährlich' },
  ],
  text: {
    all: 'Überprüfung durch Kranfachleute – regelmässig, nach den Angaben des Herstellers.',
    yearly: 'Jährlich: Überprüfung durch Kranfachleute.',
    expert: 'Periodische Kontrolle durch einen von der Suva anerkannten Kranexperten:',
    book: 'Jede Überprüfung gehört ins Kranbuch – auf Papier oder digital.',
    heukran: 'Unsere Empfehlung: ein Saison-Check vor dem ersten Schnitt.',
    older: 'Älter als 20 Jahre: Steuerung, Endschalter und Überlastsicherung verdienen einen genauen Blick.',
  },
  /** Quellen – dieselben im Ratgeber. */
  sources: [
    {
      label: 'Kranverordnung (SR 832.312.15), Fedlex',
      href: 'https://www.fedlex.admin.ch/eli/cc/2000/27/de',
    },
    {
      label: 'EKAS-Richtlinie 6511: Überprüfung und Kontrolle von Fahrzeugkranen und Turmdrehkranen',
      href: 'https://www.suva.ch/de-ch/download/richtlinien-und-gesetze/richtlinie-ueberpruefung-und-kontrolle-von-fahrzeugkranen-und-turmdrehkranen--ekas/richtlinie-ueberpruefung-und-kontrolle-von-fahrzeugkranen-und-turmdrehkranen--ekas--6511.D',
    },
    {
      label: 'Suva: Fahrzeug- und Turmdrehkrane – Überprüfung und Kontrollen',
      href: 'https://www.suva.ch/de-ch/praevention/nach-gefahren/maschinen-und-werkzeuge/krane-sicher-montieren-und-betreiben/ueberpruefung-und-kontrolle-von-fahrzeug-und-turmdrehkranen',
    },
    {
      label: 'Suva-Merkblatt 66120: Krane in Industrie und Gewerbe (z. B. Brückenkrane, Portalkrane)',
      href: 'https://www.suva.ch/de-ch/download/dokument/krane-in-industrie-und-gewerbe--z-b--brueckenkrane--portalkrane/standard-variante--66120.D',
    },
  ],
};
