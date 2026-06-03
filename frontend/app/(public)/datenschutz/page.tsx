import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Datenschutzerklärung",
  robots: { index: false },
};

export default function DatenschutzPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Datenschutzerklärung</h1>
      <p className="text-sm text-gray-500 mb-8">Version 1.0 – Juni 2026</p>

      <div className="space-y-8 text-sm text-gray-700">
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">1. Verantwortliche Stelle</h2>
          <p>
            Verantwortlich für die Verarbeitung Ihrer personenbezogenen Daten ist die Inexxio AG,
            Schweiz (Kontaktdaten siehe Impressum).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">2. Rechtsgrundlagen</h2>
          <p>
            Diese Datenschutzerklärung richtet sich nach dem Schweizer Datenschutzgesetz (DSG,
            in Kraft seit 1. September 2023) sowie der EU-Datenschutz-Grundverordnung (DSGVO),
            soweit EU-Bürger betroffen sind.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">3. Erhobene Daten</h2>
          <ul className="list-disc list-inside space-y-1">
            <li>Kontaktdaten (Name, E-Mail, Telefon) bei Kontaktaufnahme oder Registrierung</li>
            <li>Bestelldaten und Rechnungsadressen bei Käufen</li>
            <li>Technische Daten (IP-Adresse, Browser) für Sicherheitszwecke</li>
            <li>Nutzungsstatistiken via Plausible Analytics (anonymisiert, kein Cookie)</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">4. Analytics</h2>
          <p>
            Wir nutzen <strong>Plausible Analytics</strong> – ein datenschutzfreundliches
            Analysetool ohne Cookies und ohne persönliche Datenverarbeitung. Es ist kein
            Cookie-Banner erforderlich (Privacy-by-Design).
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">5. Aufbewahrung</h2>
          <p>
            Buchungsbelege und steuerlich relevante Daten werden gemäss OR Art. 958f 10 Jahre
            aufbewahrt. Übrige Daten werden nach Wegfall des Verwendungszwecks gelöscht.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">6. Ihre Rechte</h2>
          <p>
            Sie haben das Recht auf Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16),
            Löschung (Art. 17) und Datenübertragbarkeit (Art. 20). Für Anfragen wenden
            Sie sich bitte an{" "}
            <a href="mailto:info@inexxio.com" className="text-brand-600 hover:underline">
              info@inexxio.com
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
