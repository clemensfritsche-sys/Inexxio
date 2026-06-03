import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Allgemeine Geschäftsbedingungen",
};

export default function AGBPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">
        Allgemeine Geschäftsbedingungen
      </h1>
      <p className="text-sm text-gray-500 mb-8">Version 1.0 – Juni 2026</p>

      <div className="space-y-8 text-sm text-gray-700">
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">1. Geltungsbereich</h2>
          <p>
            Diese AGB gelten für alle Verträge zwischen der Inexxio AG (nachfolgend
            «Inexxio») und ihren Kunden. Abweichende AGB des Kunden gelten nur, wenn
            Inexxio diesen ausdrücklich schriftlich zugestimmt hat.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">2. Vertragsabschluss</h2>
          <p>
            Angebote von Inexxio sind freibleibend. Ein Vertrag kommt erst mit schriftlicher
            Auftragsbestätigung oder Lieferung zustande.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">3. Preise und Zahlung</h2>
          <p>
            Alle Preise verstehen sich in CHF, zzgl. gesetzlicher MWST. Zahlungsfrist:
            30 Tage netto, sofern nicht anders vereinbart. Bei Skonto gelten die auf der
            Rechnung angegebenen Konditionen.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">4. Lieferung</h2>
          <p>
            Liefertermine sind unverbindlich, sofern nicht ausdrücklich als verbindlich
            bezeichnet. Lieferverzögerungen berechtigen nicht zur Stornierung des Auftrags,
            es sei denn, die Verzögerung überschreitet 60 Tage.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            5. Eigentumsvorbehalt (B2B)
          </h2>
          <p>
            Die gelieferten Waren bleiben bis zur vollständigen Bezahlung Eigentum
            von Inexxio.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">6. Gewährleistung</h2>
          <p>
            Gewährleistungsfrist: 12 Monate ab Lieferdatum. Bei Mängeln hat Inexxio
            das Recht zur Nachbesserung oder Ersatzlieferung.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            7. Haftungsbeschränkung
          </h2>
          <p>
            Inexxio haftet nur für grobe Fahrlässigkeit und Vorsatz. Die Haftung ist
            auf den Auftragswert begrenzt.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">8. Widerrufsrecht (B2C)</h2>
          <p>
            Konsumentinnen und Konsumenten haben bei Fernabsatzverträgen ein Widerrufsrecht
            von 14 Tagen nach Erhalt der Ware. Das Widerrufsrecht gilt nicht für
            massangefertigte Produkte.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">9. Gerichtsstand</h2>
          <p>
            Ausschliesslicher Gerichtsstand ist der Sitz von Inexxio in der Schweiz.
            Es gilt Schweizer Recht.
          </p>
        </section>
      </div>
    </div>
  );
}
