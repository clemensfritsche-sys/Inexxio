import type { Metadata } from 'next';
import Link from 'next/link';
import {
  Cog,
  Ruler,
  Layers,
  ShieldCheck,
  Zap,
  Award,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';

export const metadata: Metadata = {
  title: 'Inexxio AG – Präzisionsfertigung Swiss Made',
  description:
    'Inexxio AG entwickelt und fertigt hochpräzise Maschinenkomponenten und Baugruppen. Toleranzen bis 0,001 mm. ISO 9001. Made in Switzerland.',
};

const features = [
  {
    icon: <Cog className="h-6 w-6" />,
    title: 'Präzisionsfertigung',
    description:
      'CNC-Bearbeitung mit Toleranzen bis 0,001 mm. Modernste Mehrachsbearbeitungszentren für höchste Anforderungen in der Luft- und Raumfahrt, Medizintechnik und im Maschinenbau.',
    highlights: ['5-Achs CNC-Fräsen', 'Toleranzen bis 0,001 mm', 'Qualitätsprüfung CMM'],
  },
  {
    icon: <Ruler className="h-6 w-6" />,
    title: 'Entwicklung & Konstruktion',
    description:
      'Von der Idee bis zum Serienteil begleiten wir Sie durch den gesamten Entwicklungsprozess. Konstruktion, Prototypenbau und Serienproduktion aus einer Hand.',
    highlights: ['CAD/CAM Konstruktion', 'Rapid Prototyping', 'Serienreife Optimierung'],
  },
  {
    icon: <Layers className="h-6 w-6" />,
    title: 'Komplettlösungen',
    description:
      'Ob Einzelteile, Baugruppen oder komplette Systemlösungen – wir decken die gesamte Wertschöpfungskette ab und koordinieren alle Lieferanten für Sie.',
    highlights: ['Einzelteile & Serien', 'Baugruppen-Montage', 'Just-in-Time Lieferung'],
  },
];

const whyItems = [
  {
    icon: <ShieldCheck className="h-8 w-8 text-blue-600" />,
    title: 'ISO 9001 Qualitätsgarantie',
    description:
      'Unser gesamter Fertigungsprozess ist nach ISO 9001 zertifiziert. Lückenlose Qualitätsdokumentation und 100%-Endkontrolle gewährleisten gleichbleibend hohe Qualität.',
  },
  {
    icon: <Zap className="h-8 w-8 text-blue-600" />,
    title: 'Maximale Flexibilität',
    description:
      'Von der Losgrösse 1 bis zur Grossserie – wir passen uns Ihren Anforderungen an. Kurze Rüstzeiten und flexible Kapazitäten ermöglichen schnelle Reaktion auf Ihren Bedarf.',
  },
  {
    icon: <Award className="h-8 w-8 text-blue-600" />,
    title: 'Schweizer Qualitätsversprechen',
    description:
      'Präzise, zuverlässig, termingerecht. Was wir zusagen, halten wir. Jahrzehntelange Erfahrung und tiefes Fachwissen machen uns zum verlässlichen Partner für anspruchsvolle Projekte.',
  },
];

export default function HomePage() {
  return (
    <>
      {/* Hero Section */}
      <section className="relative bg-slate-900 pt-32 pb-24 overflow-hidden">
        {/* Background pattern */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-blue-600 opacity-10 rounded-full blur-3xl" />
          <div className="absolute -bottom-20 -left-20 w-80 h-80 bg-blue-800 opacity-10 rounded-full blur-3xl" />
          {/* Grid lines */}
          <div
            className="absolute inset-0 opacity-5"
            style={{
              backgroundImage:
                'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
              backgroundSize: '60px 60px',
            }}
          />
        </div>

        <div className="container relative">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: text */}
            <div>
              <div className="inline-flex items-center gap-2 bg-blue-600/20 border border-blue-500/30 rounded-full px-4 py-1.5 text-sm text-blue-300 mb-6">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                Swiss Made · ISO 9001 · Maschinenbau
              </div>

              <h1 className="text-5xl lg:text-6xl font-bold text-white leading-tight tracking-tight mb-6">
                Präzision für
                <br />
                <span className="text-blue-400">anspruchsvolle</span>
                <br />
                Industrie
              </h1>

              <p className="text-lg text-slate-300 leading-relaxed mb-8 max-w-xl">
                Inexxio AG entwickelt und fertigt hochpräzise Maschinenkomponenten und
                Baugruppen für die Industrie. Von der Konstruktion bis zur Auslieferung –
                alles aus einer Hand.
              </p>

              <div className="flex flex-wrap gap-4">
                <Link
                  href="/kontakt"
                  className="btn-primary text-base px-6 py-3 shadow-lg shadow-blue-600/30"
                >
                  Kontakt aufnehmen
                  <ArrowRight className="h-5 w-5" />
                </Link>
                <Link
                  href="/ueber-uns"
                  className="inline-flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white border border-white/20 px-6 py-3 rounded-lg font-medium transition-colors"
                >
                  Über uns
                </Link>
              </div>
            </div>

            {/* Right: stats panel */}
            <div className="hidden lg:block">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                  <div className="text-4xl font-bold text-white mb-1">1&#700;000+</div>
                  <div className="text-sm text-slate-400">Aktive Artikel im ERP</div>
                  <div className="mt-3 flex gap-1">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="h-1 flex-1 bg-blue-500 rounded-full opacity-70" />
                    ))}
                  </div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <ShieldCheck className="h-6 w-6 text-green-400" />
                    <span className="text-lg font-bold text-white">ISO 9001</span>
                  </div>
                  <div className="text-sm text-slate-400">Zertifiziertes Qualitätsmanagementsystem</div>
                </div>
                <div className="bg-blue-600/20 border border-blue-500/30 rounded-2xl p-6 backdrop-blur-sm col-span-2">
                  <div className="flex items-center gap-3 mb-3">
                    <Award className="h-7 w-7 text-blue-400" />
                    <span className="text-xl font-bold text-white">Swiss Made</span>
                  </div>
                  <p className="text-sm text-slate-400">
                    Alle Produkte werden ausschliesslich in der Schweiz entwickelt und gefertigt.
                  </p>
                  <div className="mt-4 flex items-center gap-2">
                    {['CNC', '5-Achse', 'CMM', 'EDM'].map((tag) => (
                      <span
                        key={tag}
                        className="px-2.5 py-0.5 rounded-full bg-blue-600/30 text-blue-300 text-xs font-medium border border-blue-500/30"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                  <div className="text-4xl font-bold text-white mb-1">0,001</div>
                  <div className="text-sm text-slate-400">mm Toleranz</div>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                  <div className="text-4xl font-bold text-white mb-1">24h</div>
                  <div className="text-sm text-slate-400">Angebots&shy;erstellung</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="section bg-white">
        <div className="container">
          <div className="text-center mb-14">
            <p className="text-sm font-semibold text-blue-600 uppercase tracking-widest mb-3">
              Unsere Stärken
            </p>
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Unsere Kernkompetenzen</h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Drei Säulen, die unsere Leistungsfähigkeit definieren und Ihnen maximale
              Sicherheit in der Lieferkette geben.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="group bg-white rounded-2xl border border-slate-200 hover:border-blue-200 hover:shadow-lg transition-all duration-300 p-6"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 mb-5 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-slate-900 mb-3">{feature.title}</h3>
                <p className="text-slate-600 leading-relaxed mb-5 text-sm">{feature.description}</p>
                <ul className="space-y-2">
                  {feature.highlights.map((item) => (
                    <li key={item} className="flex items-center gap-2 text-sm text-slate-700">
                      <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why Inexxio Section */}
      <section className="section bg-slate-50">
        <div className="container">
          <div className="text-center mb-14">
            <p className="text-sm font-semibold text-blue-600 uppercase tracking-widest mb-3">
              Warum Inexxio
            </p>
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Was uns von anderen unterscheidet
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Wir verbinden Schweizer Präzision mit modernen Fertigungsmethoden und einem
              kompromisslosen Qualitätsanspruch.
            </p>
          </div>

          <div className="space-y-6">
            {whyItems.map((item, index) => (
              <div
                key={item.title}
                className={`flex flex-col md:flex-row items-start gap-8 p-8 rounded-2xl ${
                  index % 2 === 0 ? 'bg-white' : 'bg-blue-600'
                } border ${index % 2 === 0 ? 'border-slate-200' : 'border-blue-500'} shadow-sm`}
              >
                <div
                  className={`shrink-0 flex h-16 w-16 items-center justify-center rounded-2xl ${
                    index % 2 === 0 ? 'bg-blue-50' : 'bg-white/20'
                  }`}
                >
                  <span className={index % 2 === 0 ? '' : '[&_*]:text-white'}>{item.icon}</span>
                </div>
                <div>
                  <h3
                    className={`text-xl font-semibold mb-2 ${
                      index % 2 === 0 ? 'text-slate-900' : 'text-white'
                    }`}
                  >
                    {item.title}
                  </h3>
                  <p
                    className={`leading-relaxed ${
                      index % 2 === 0 ? 'text-slate-600' : 'text-blue-100'
                    }`}
                  >
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section className="bg-blue-600 py-20">
        <div className="container text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Bereit für ein unverbindliches Gespräch?
          </h2>
          <p className="text-lg text-blue-100 mb-8 max-w-xl mx-auto">
            Kontaktieren Sie uns für ein kostenloses Beratungsgespräch. Wir melden uns innert
            24 Stunden bei Ihnen zurück.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link
              href="/kontakt"
              className="inline-flex items-center gap-2 bg-white text-blue-600 hover:bg-blue-50 font-semibold px-8 py-3 rounded-xl transition-colors shadow-lg"
            >
              Jetzt anfragen
              <ArrowRight className="h-5 w-5" />
            </Link>
            <a
              href="mailto:info@inexxio.com"
              className="inline-flex items-center gap-2 bg-blue-700 hover:bg-blue-800 text-white font-medium px-8 py-3 rounded-xl transition-colors"
            >
              info@inexxio.com
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
