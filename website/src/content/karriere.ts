/**
 * Karriere – eigenes Layout v4 (Oktober 2026): Kopf wie Porsche → Warum hier arbeiten
 * (#warum) → Wer zu uns passt (drei Karten, keine ausgeschriebenen Stellen) → So bewerben Sie sich (Weg)
 * → Bewerbung (dunkle Karte, #bewerbung). Keine erfundenen Stellen, Leistungen oder Zahlen.
 */
import type { IconName } from '../components/Icon.astro';

const apply = { subject: 'Bewerbung' };

export const karriere = {
  title: 'Karriere',
  description:
    'Arbeiten bei INEXXIO in {{address.home}}: Krane, Fahrmischer und Spezialmaschinen bauen, in einem kleinen Team. Bewerbung per E-Mail oder Telefon.',
  hero: {
    h1: 'Gemeinsam bauen, was es ==nicht von der Stange== gibt.',
    lead:
      'Ein kleines Team in {{address.home}}: Wir bauen und betreuen Krane, tauschen Trommeln von Fahrmischern und bauen Spezialmaschinen – bei uns und bei unseren Kunden.',
  },
  apply,
  /** Warum hier arbeiten (Anker #warum) – components/FactGrid, vier Punkte mit Symbol. */
  why: {
    title: 'Warum hier arbeiten.',
    items: [
      { icon: 'route' as IconName, title: 'Abwechslung', text: 'Heute ein Brückenkran in einer Produktionshalle, morgen ein Heukran auf dem Hof, danach ein Fahrmischer bei uns in {{address.city}}.' },
      { icon: 'wrench' as IconName, title: 'Technik, die man versteht', text: 'Mechanik, Hydraulik, Elektrik, Steuerung und Stahlbau – an Maschinen, die man versteht, wenn man sie einmal repariert hat.' },
      { icon: 'users' as IconName, title: 'Kleines Team', text: 'Kurze Wege, klare Absprachen, jeder kennt jeden.' },
      { icon: 'drafting-compass' as IconName, title: 'Ingenieurwissen im Haus', text: 'Konstruktion und Fertigung arbeiten Hand in Hand – Fragen klären wir am Werkstück, gemeinsam.' },
    ],
  },
  /** Wer zu uns passt – drei Karten (components/spezial/FieldCards). Keine ausgeschriebenen Stellen. */
  profiles: {
    title: 'Wer zu uns passt.',
    lead: 'Auch ohne ausgeschriebene Stelle – gute Leute sind bei uns jederzeit willkommen.',
    items: [
      { id: 'mechanik', illo: 'menu/trommeltausch', alt: 'Zeichnung: Fahrmischer mit roter Trommel', title: 'Mechanik', text: 'Mechanikerinnen und Mechaniker für Hydraulik, Mechanik und Stahlbau – an Fahrmischern, Kranen und Spezialmaschinen.' },
      { id: 'service', illo: 'menu/kranservice', alt: 'Zeichnung: roter Werkzeugkasten und Prüfprotokoll', title: 'Service', text: 'Servicetechnikerinnen und Servicetechniker, die prüfen, warten und reparieren – bei uns und bei Kunden vor Ort.' },
      { id: 'konstruktion', illo: 'menu/krane-nach-mass', alt: 'Zeichnung: Kran mit roter Brücke', title: 'Konstruktion', text: 'Konstrukteurinnen und Konstrukteure für Krane und Spezialmaschinen nach Mass – von der Idee bis zur Fertigung.' },
    ],
  },
  /** So bewerben Sie sich – drei Stationen (components/spezial/SolutionPath). */
  path: {
    title: 'So bewerben Sie sich.',
    start: 'Ihre Bewerbung',
    end: 'Willkommen im Team',
    items: [
      { icon: 'mail' as IconName, who: 'Sie', title: 'E-Mail oder Anruf', text: 'Lebenslauf und ein paar Sätze zu Ihnen – oder rufen Sie einfach an.' },
      { icon: 'phone' as IconName, who: 'Wir', title: 'Wir melden uns', text: 'Wir lesen jede Bewerbung und melden uns persönlich bei Ihnen.' },
      { icon: 'handshake' as IconName, who: 'Gemeinsam', title: 'Kennenlernen', text: 'Im Betrieb in {{address.city}} – Sie sehen, woran wir gerade arbeiten.' },
    ],
  },
  /** Bewerbung (Anker #bewerbung) – components/CallPanel. */
  contact: {
    label: 'Bewerbung',
    title: 'Wir freuen uns auf Sie.',
    text: 'Schicken Sie uns Ihren Lebenslauf an {{email.link}} – oder rufen Sie an: {{phone.link}}.',
  },
};
