import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Inexxio – Enterprise Central System",
  description: "Maschinenbau-KMU Systemlösung – Website, Shop & ERP in einem.",
};

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-brand-950 to-brand-800 text-white py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-bold mb-6 leading-tight">
            Inexxio
          </h1>
          <p className="text-xl md:text-2xl text-brand-200 mb-4 font-light">
            Enterprise Central System
          </p>
          <p className="text-lg text-brand-300 mb-10 max-w-2xl mx-auto">
            Website, Online-Shop und ERP in einem System – entwickelt für
            produzierendes KMU in der Schweiz.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/shop"
              className="bg-white text-brand-800 font-semibold px-8 py-3 rounded-xl hover:bg-brand-50 transition-colors"
            >
              Zum Shop
            </Link>
            <Link
              href="/kontakt"
              className="border border-brand-300 text-white font-semibold px-8 py-3 rounded-xl hover:bg-brand-700 transition-colors"
            >
              Kontakt aufnehmen
            </Link>
          </div>
        </div>
      </section>

      {/* USPs */}
      <section className="py-20 px-4 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Unsere Stärken
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {USPs.map((usp) => (
              <div key={usp.title} className="card p-6">
                <div className="text-4xl mb-4">{usp.icon}</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {usp.title}
                </h3>
                <p className="text-gray-600 text-sm">{usp.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 px-4 bg-brand-600 text-white text-center">
        <h2 className="text-2xl font-bold mb-4">Bereit loszulegen?</h2>
        <p className="text-brand-100 mb-8">
          Kontaktieren Sie uns für eine persönliche Beratung.
        </p>
        <Link
          href="/kontakt"
          className="bg-white text-brand-700 font-semibold px-8 py-3 rounded-xl hover:bg-brand-50 transition-colors"
        >
          Jetzt kontaktieren
        </Link>
      </section>
    </>
  );
}

const USPs = [
  {
    icon: "⚙️",
    title: "Präzision im Maschinenbau",
    description:
      "Hochwertige Komponenten und Baugruppen für anspruchsvolle Industrieanwendungen.",
  },
  {
    icon: "🇨🇭",
    title: "Schweizer Qualität",
    description:
      "Als Schweizer AG stehen wir für höchste Qualitätsstandards und zuverlässige Lieferzeiten.",
  },
  {
    icon: "🔒",
    title: "ISO 9001 zertifiziert",
    description:
      "Lückenlose Qualitätssicherung von der Entwicklung bis zur Auslieferung.",
  },
];
