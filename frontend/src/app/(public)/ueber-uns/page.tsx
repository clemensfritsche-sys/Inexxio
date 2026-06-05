import type { Metadata } from 'next';
import Link from 'next/link';
import { Target, Heart, Globe, Lightbulb, Users, ArrowRight, CheckCircle2 } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Über uns',
  description:
    'Erfahren Sie mehr über Inexxio AG – Ihr Schweizer Spezialist für Präzisionsfertigung. Unsere Mission, Werte und unser Team.',
};

const values = [
  {
    icon: <Target className="h-6 w-6" />,
    title: 'Präzision',
    description:
      'Wir setzen den Massstab höher als der Markt es fordert. Jedes Werkstück verlässt unser Haus erst nach bestandener 100%-Kontrolle.',
  },
  {
    icon: <Heart className="h-6 w-6" />,
    title: 'Verlässlichkeit',
    description:
      'Unsere Kunden können sich auf uns verlassen. Zugesagte Termine und Qualitäten halten wir – auch wenn es schwierig wird.',
  },
  {
    icon: <Globe className="h-6 w-6" />,
    title: 'Nachhaltigkeit',
    description:
      'Wir produzieren ressourcenschonend und setzen auf langlebige Lösungen. Qualität ist die beste Form der Nachhaltigkeit.',
  },
  {
    icon: <Lightbulb className="h-6 w-6" />,
    title: 'Innovation',
    description:
      'Wir investieren kontinuierlich in neue Technologien und Prozesse, um unseren Kunden stets die beste Lösung bieten zu können.',
  },
];

const milestones = [
  { year: '2010', text: 'Gründung der Inexxio AG in Zürich' },
  { year: '2013', text: 'Erstes ISO 9001 Zertifikat' },
  { year: '2016', text: 'Ausbau auf 5-Achs-Bearbeitungszentren' },
  { year: '2019', text: 'Einführung des digitalen ERP-Systems' },
  { year: '2022', text: 'Erweiterung der Produktionsfläche auf 2\'500 m²' },
  { year: '2025', text: 'Launch des Inexxio Enterprise Central Systems' },
];

export default function UeberUnsPage() {
  return (
    <>
      {/* Hero */}
      <section className="bg-slate-900 pt-28 pb-16">
        <div className="container">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-blue-400 uppercase tracking-widest mb-4">
              Über Inexxio
            </p>
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-6">
              Schweizer Präzision seit über einem Jahrzehnt
            </h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Inexxio AG ist ein führender Schweizer Spezialist für Präzisionsfertigung und
              Maschinenbau. Wir stehen für kompromisslose Qualität, Zuverlässigkeit und die
              Überzeugung, dass Schweizer Fertigung in einer globalisierten Welt seinen
              Mehrwert hat.
            </p>
          </div>
        </div>
      </section>

      {/* Mission */}
      <section className="section bg-white">
        <div className="container">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <p className="text-sm font-semibold text-blue-600 uppercase tracking-widest mb-4">
                Unsere Mission
              </p>
              <h2 className="text-3xl font-bold text-slate-900 mb-6">
                Präzision, die Vertrauen schafft
              </h2>
              <p className="text-slate-600 leading-relaxed mb-6">
                Unsere Mission ist es, Industrieunternehmen mit hochpräzisen
                Maschinenkomponenten und Systemlösungen zu beliefern, die die Grundlage
                für zuverlässige und langlebige Produkte bilden.
              </p>
              <p className="text-slate-600 leading-relaxed mb-8">
                Wir glauben, dass exzellente Fertigung mehr ist als das Einhalten von
                Toleranzen. Sie umfasst Kommunikation, Verlässlichkeit, Expertise und den
                unbedingten Willen, die beste Lösung für den Kunden zu finden.
              </p>
              <ul className="space-y-3">
                {[
                  'Höchste Präzision in jedem Bauteil',
                  'Partnerschaftliche Zusammenarbeit',
                  'Transparente Prozesse und Preise',
                  'Kontinuierliche technologische Weiterentwicklung',
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
                    <span className="text-slate-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-slate-50 rounded-2xl p-8">
              <h3 className="text-lg font-semibold text-slate-900 mb-6">
                Meilensteine unserer Entwicklung
              </h3>
              <div className="relative">
                <div className="absolute left-4 top-2 bottom-2 w-0.5 bg-slate-200" />
                <div className="space-y-6">
                  {milestones.map((m) => (
                    <div key={m.year} className="flex gap-4 relative">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white z-10 relative">
                        {m.year.slice(2)}
                      </div>
                      <div className="pt-1">
                        <span className="text-xs font-semibold text-blue-600">{m.year}</span>
                        <p className="text-sm text-slate-700 mt-0.5">{m.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="section bg-slate-50">
        <div className="container">
          <div className="text-center mb-14">
            <p className="text-sm font-semibold text-blue-600 uppercase tracking-widest mb-3">
              Unsere Werte
            </p>
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Was uns antreibt</h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Vier Grundsätze, die jeden Tag unser Handeln leiten und das Fundament
              unserer Unternehmenskultur bilden.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map((v) => (
              <div
                key={v.title}
                className="bg-white rounded-2xl border border-slate-200 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-600 mb-4">
                  {v.icon}
                </div>
                <h3 className="font-semibold text-slate-900 mb-2">{v.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">{v.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Swiss Excellence */}
      <section className="section bg-white">
        <div className="container">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-10">
              <p className="text-sm font-semibold text-blue-600 uppercase tracking-widest mb-3">
                Swiss Manufacturing Excellence
              </p>
              <h2 className="text-3xl font-bold text-slate-900 mb-4">
                Die Infrastruktur hinter der Präzision
              </h2>
            </div>
            <div className="grid md:grid-cols-3 gap-6">
              {[
                {
                  title: 'Modernste CNC-Bearbeitungszentren',
                  desc: '5-Achs-Fräsen von DMG Mori und Hermle. Drehen, Schleifen, EDM-Senken und EDM-Drahterodieren.',
                },
                {
                  title: 'Mess- und Prüftechnik',
                  desc: 'Koordinatenmessgeräte (CMM) von Zeiss. Optische Messsysteme. Rauheitsmessung. Leckage-Tests.',
                },
                {
                  title: 'Digitale Fertigungssteuerung',
                  desc: 'Vollständige Rückverfolgbarkeit aller Prozessschritte. Digitale Fertigungsaufträge und Qualitätsdokumentation.',
                },
              ].map((item) => (
                <div key={item.title} className="bg-slate-50 rounded-xl p-5">
                  <h4 className="font-semibold text-slate-900 mb-2">{item.title}</h4>
                  <p className="text-sm text-slate-600 leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Team section */}
      <section className="section bg-slate-50">
        <div className="container">
          <div className="text-center mb-14">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-100 text-blue-600 mx-auto mb-4">
              <Users className="h-8 w-8" />
            </div>
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Unser Team</h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Hinter Inexxio steht ein erfahrenes Team aus Ingenieuren, Maschinisten und
              Qualitätsspezialisten, das jeden Tag mit Leidenschaft an der perfekten
              Lösung arbeitet.
            </p>
            <p className="text-slate-500 mt-4">
              Möchten Sie Teil unseres Teams werden?{' '}
              <Link href="/kontakt" className="text-blue-600 hover:underline font-medium">
                Wir freuen uns auf Ihre Bewerbung.
              </Link>
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-blue-600 py-16">
        <div className="container text-center">
          <h2 className="text-2xl font-bold text-white mb-4">
            Lernen Sie uns persönlich kennen
          </h2>
          <p className="text-blue-100 mb-6 max-w-lg mx-auto">
            Vereinbaren Sie einen Besuch in unserer Fertigungsstätte oder ein
            unverbindliches Beratungsgespräch.
          </p>
          <Link
            href="/kontakt"
            className="inline-flex items-center gap-2 bg-white text-blue-600 hover:bg-blue-50 font-semibold px-6 py-3 rounded-xl transition-colors"
          >
            Kontakt aufnehmen
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </>
  );
}
