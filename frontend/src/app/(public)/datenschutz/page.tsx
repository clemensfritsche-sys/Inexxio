import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Datenschutzerklärung',
  description: 'Datenschutzerklärung der Inexxio AG gemäss DSGVO und Schweizer DSG.',
};

const VERSION = '1.0';
const VALID_FROM = '01.01.2026';

export default function DatenschutzPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Hero */}
      <section className="bg-slate-900 py-16">
        <div className="container">
          <h1 className="text-4xl font-bold text-white">Datenschutzerklärung</h1>
          <p className="mt-2 text-slate-400">
            Gemäss DSGVO und Schweizer DSG (01.09.2023) | Version {VERSION} | Stand {VALID_FROM}
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container max-w-3xl">
          <div className="mb-8 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
            <p className="text-sm text-blue-800">
              Wir nehmen den Schutz Ihrer persönlichen Daten sehr ernst. Diese Datenschutzerklärung
              informiert Sie über Art, Umfang und Zweck der Verarbeitung Ihrer personenbezogenen
              Daten durch die Inexxio AG.
            </p>
          </div>

          <Section title="1. Verantwortlicher">
            <p>
              Verantwortliche Stelle im Sinne der DSGVO und des Schweizer DSG ist:
            </p>
            <div className="mt-3 rounded-lg bg-slate-50 border border-slate-200 p-4 text-sm">
              <p className="font-medium">Inexxio AG</p>
              <p className="text-slate-600 mt-1">
                [Strasse Nr.], [PLZ Ort], Schweiz<br />
                E-Mail: info@inexxio.com<br />
                Website: https://inexxio.com
              </p>
            </div>
          </Section>

          <Section title="2. Erhobene Daten und Zweck der Verarbeitung">
            <SubSection title="2.1 Kontaktformular">
              <p>
                Wenn Sie uns über das Kontaktformular kontaktieren, erheben wir:
              </p>
              <DataList items={[
                'Name',
                'E-Mail-Adresse',
                'Telefonnummer (optional)',
                'Betreff und Inhalt Ihrer Nachricht',
              ]} />
              <p className="mt-3">
                <strong>Zweck:</strong> Bearbeitung Ihrer Anfrage und Kommunikation mit Ihnen.<br />
                <strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b DSGVO (Vertragsanbahnung)
                bzw. Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an der Beantwortung von
                Anfragen).<br />
                <strong>Speicherdauer:</strong> Bis zur abschliessenden Bearbeitung der Anfrage,
                maximal 3 Jahre.
              </p>
            </SubSection>

            <SubSection title="2.2 Kundenkonto und Bestellungen">
              <p>
                Wenn Sie ein Kundenkonto anlegen oder eine Bestellung aufgeben, erheben wir:
              </p>
              <DataList items={[
                'E-Mail-Adresse',
                'Name und Vorname',
                'Lieferadresse und Rechnungsadresse',
                'Bestellhistorie und Rechnungen',
                'Zahlungsdaten (über Stripe verarbeitet, nicht direkt von uns gespeichert)',
              ]} />
              <p className="mt-3">
                <strong>Zweck:</strong> Vertragserfüllung, Rechnungsstellung, Kundenkommunikation.<br />
                <strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung).<br />
                <strong>Speicherdauer:</strong> Buchhaltungsrelevante Daten 10 Jahre (OR Art. 958f),
                übrige Kundendaten bis zur Kontolöschung.
              </p>
            </SubSection>

            <SubSection title="2.3 Authentifizierung (Firebase)">
              <p>
                Für die Anmeldung nutzen wir Firebase Authentication von Google. Dabei werden
                verarbeitet:
              </p>
              <DataList items={[
                'E-Mail-Adresse',
                'Anmeldedatum und -zeitpunkt (UTC)',
                'Geräteinformationen (für Sicherheitszwecke)',
              ]} />
              <p className="mt-3">
                <strong>Zweck:</strong> Sichere Benutzerauthentifizierung und Kontoverwaltung.<br />
                <strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung).<br />
                <strong>Anbieter:</strong> Google Ireland Limited, Gordon House, Barrow Street,
                Dublin 4, Irland. Datenschutzerklärung:{' '}
                <a
                  href="https://firebase.google.com/support/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  firebase.google.com/support/privacy
                </a>
              </p>
            </SubSection>

            <SubSection title="2.4 Zahlungsabwicklung (Stripe)">
              <p>
                Die Zahlungsabwicklung erfolgt über Stripe Payments Europe Ltd. Stripe verarbeitet
                Zahlungsdaten wie Kreditkartennummern direkt in seiner gesicherten Umgebung.
                Inexxio AG hat keinen Zugriff auf vollständige Zahlungsdaten.
              </p>
              <p className="mt-3">
                <strong>Anbieter:</strong> Stripe Payments Europe Ltd., 1 Grand Canal Street Lower,
                Grand Canal Dock, Dublin D02 H210, Irland.<br />
                <strong>Datenschutzerklärung:</strong>{' '}
                <a
                  href="https://stripe.com/ch/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  stripe.com/ch/privacy
                </a>
              </p>
            </SubSection>

            <SubSection title="2.5 Analytics (Plausible)">
              <p>
                Wir nutzen Plausible Analytics für datenschutzfreundliche Websiteanalysen.
                Plausible erhebt keine personenbezogenen Daten, setzt keine Cookies und trackt
                keine Nutzer über mehrere Websites.
              </p>
              <DataList items={[
                'Aufgerufene Seiten (aggregiert, ohne Personenbezug)',
                'Verweisende Website (Referrer)',
                'Gerätekategorie (Desktop/Mobile/Tablet)',
                'Land (aus IP-Adresse, die nicht gespeichert wird)',
              ]} />
              <p className="mt-3">
                <strong>Zweck:</strong> Verstehen, wie unsere Website genutzt wird, um sie zu
                verbessern.<br />
                <strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. f DSGVO (berechtigtes
                Interesse). Kein Cookie-Banner erforderlich.<br />
                <strong>Anbieter:</strong> Plausible Analytics, Tallinn, Estland.
              </p>
            </SubSection>

            <SubSection title="2.6 Hosting (Google Cloud)">
              <p>
                Unsere Website und Backend-Dienste werden auf der Google Cloud Platform gehostet
                (Region europe-west6, Zürich). Google verarbeitet dabei technische Zugriffsdaten
                (IP-Adresse, Zeitstempel, Anfrage-Details) für den Betrieb der Infrastruktur.
              </p>
              <p className="mt-3">
                <strong>Anbieter:</strong> Google Cloud EMEA Limited, 70 Sir John Rogerson's
                Quay, Dublin 2, Irland.<br />
                <strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. f DSGVO (berechtigtes
                Interesse an sicherem Hosting).
              </p>
            </SubSection>
          </Section>

          <Section title="3. Cookies">
            <p>
              Wir verwenden nur technisch notwendige Cookies für den Betrieb der Website:
            </p>
            <div className="mt-4 overflow-hidden rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="px-4 py-2 text-left font-medium text-slate-600">Cookie</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-600">Zweck</th>
                    <th className="px-4 py-2 text-left font-medium text-slate-600">Dauer</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-slate-100">
                    <td className="px-4 py-3 font-mono text-xs">session_token</td>
                    <td className="px-4 py-3 text-slate-700">Authentifizierung</td>
                    <td className="px-4 py-3 text-slate-600">Session</td>
                  </tr>
                  <tr className="border-b border-slate-100">
                    <td className="px-4 py-3 font-mono text-xs">lang</td>
                    <td className="px-4 py-3 text-slate-700">Spracheinstellung</td>
                    <td className="px-4 py-3 text-slate-600">1 Jahr</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3 font-mono text-xs">cart</td>
                    <td className="px-4 py-3 text-slate-700">Warenkorb (Gäste)</td>
                    <td className="px-4 py-3 text-slate-600">7 Tage</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Es werden keine Tracking-Cookies gesetzt. Ein Cookie-Banner ist daher nicht
              erforderlich.
            </p>
          </Section>

          <Section title="4. Aufbewahrungsdauer">
            <p>
              Wir speichern Ihre Daten nur so lange, wie es für die jeweiligen Zwecke erforderlich
              ist:
            </p>
            <ul className="mt-3 space-y-2 text-slate-700">
              <li>
                <strong>Buchhaltungsunterlagen:</strong> 10 Jahre (gesetzliche Pflicht gem.
                OR Art. 958f) – unveränderlich archiviert
              </li>
              <li>
                <strong>Bestelldaten:</strong> 10 Jahre (Buchungsrelevanz)
              </li>
              <li>
                <strong>Kundenkontodaten:</strong> Bis zur Löschung des Kontos (auf Antrag)
              </li>
              <li>
                <strong>Kontaktanfragen:</strong> Maximal 3 Jahre nach Abschluss der Anfrage
              </li>
              <li>
                <strong>Server-Logs:</strong> 30 Tage
              </li>
            </ul>
          </Section>

          <Section title="5. Weitergabe an Dritte">
            <p>
              Eine Weitergabe Ihrer personenbezogenen Daten an Dritte erfolgt nur, wenn:
            </p>
            <ul className="mt-3 space-y-2 text-slate-700">
              <li>Sie ausdrücklich eingewilligt haben</li>
              <li>Es zur Vertragserfüllung notwendig ist (Lieferanten, Logistikpartner)</li>
              <li>Wir gesetzlich dazu verpflichtet sind</li>
              <li>Es zum Schutz berechtigter Interessen notwendig ist</li>
            </ul>
            <p className="mt-3">
              <strong>Datenübermittlung ins Ausland:</strong> Stripe und Firebase/Google Cloud
              können Daten in die USA übermitteln. Die Übermittlung erfolgt auf Basis von
              Standardvertragsklauseln (SCC) gemäss Art. 46 DSGVO.
            </p>
          </Section>

          <Section title="6. Ihre Rechte">
            <p>
              Sie haben gegenüber uns folgende Rechte hinsichtlich der Sie betreffenden
              personenbezogenen Daten:
            </p>
            <div className="mt-4 space-y-3">
              {[
                { title: 'Auskunftsrecht (Art. 15 DSGVO)', desc: 'Sie haben das Recht, eine Bestätigung darüber zu verlangen, ob wir Daten über Sie verarbeiten, und Auskunft über diese Daten zu erhalten.' },
                { title: 'Recht auf Berichtigung (Art. 16 DSGVO)', desc: 'Sie haben das Recht, unrichtige Daten über Sie berichtigen zu lassen.' },
                { title: 'Recht auf Löschung (Art. 17 DSGVO)', desc: 'Sie haben das Recht, die Löschung Ihrer Daten zu verlangen, sofern keine gesetzlichen Aufbewahrungspflichten bestehen.' },
                { title: 'Recht auf Einschränkung (Art. 18 DSGVO)', desc: 'Sie haben das Recht, die Einschränkung der Verarbeitung Ihrer Daten zu verlangen.' },
                { title: 'Datenübertragbarkeit (Art. 20 DSGVO)', desc: 'Sie haben das Recht, Ihre Daten in einem strukturierten, maschinenlesbaren Format zu erhalten.' },
                { title: 'Widerspruchsrecht (Art. 21 DSGVO)', desc: 'Sie haben das Recht, gegen die Verarbeitung Ihrer Daten Widerspruch einzulegen.' },
              ].map((right) => (
                <div key={right.title} className="rounded-lg border border-slate-200 p-3">
                  <p className="font-medium text-slate-900 text-sm">{right.title}</p>
                  <p className="mt-1 text-sm text-slate-600">{right.desc}</p>
                </div>
              ))}
            </div>
            <p className="mt-4">
              <strong>Beschwerderecht:</strong> Sie haben das Recht, sich bei der zuständigen
              Datenschutzaufsichtsbehörde zu beschweren. In der Schweiz ist dies der
              Eidgenössische Datenschutz- und Öffentlichkeitsbeauftragte (EDÖB),
              Feldeggweg 1, 3003 Bern.
            </p>
            <p className="mt-3">
              <strong>Zur Ausübung Ihrer Rechte</strong> wenden Sie sich bitte an:{' '}
              <a href="mailto:info@inexxio.com" className="text-blue-600 hover:underline">
                info@inexxio.com
              </a>
            </p>
          </Section>

          <Section title="7. Sicherheit">
            <p>
              Wir setzen technische und organisatorische Massnahmen ein, um Ihre Daten vor
              unbefugtem Zugriff, Verlust oder Missbrauch zu schützen:
            </p>
            <DataList items={[
              'SSL/TLS-Verschlüsselung für alle Datenübertragungen',
              'Verschlüsselte Speicherung sensibler Daten (IBAN, Anmeldedaten)',
              'Rollenbasierte Zugriffskontrollen',
              'Zwei-Faktor-Authentifizierung für Administratoren',
              'Regelmässige Sicherheitsupdates',
              'Hosting in ISO 27001-zertifizierten Rechenzentren in der Schweiz',
            ]} />
          </Section>

          <Section title="8. Änderungen" isLast>
            <p>
              Wir behalten uns vor, diese Datenschutzerklärung bei Bedarf anzupassen, um
              Änderungen in der Rechtslage oder bei unseren Dienstleistungen zu berücksichtigen.
              Bei wesentlichen Änderungen werden registrierte Nutzer per E-Mail informiert.
            </p>
            <p className="mt-3">
              Die aktuelle Version dieser Datenschutzerklärung ist stets unter{' '}
              <Link href="/datenschutz" className="text-blue-600 hover:underline">
                inexxio.com/datenschutz
              </Link>{' '}
              abrufbar.
            </p>
            <p className="mt-4 text-sm text-slate-500">
              Version {VERSION} | Stand {VALID_FROM} | Inexxio AG
            </p>
          </Section>
        </div>
      </section>
    </div>
  );
}

function Section({
  title,
  children,
  isLast = false,
}: {
  title: string;
  children: React.ReactNode;
  isLast?: boolean;
}) {
  return (
    <div className={`${isLast ? '' : 'mb-10 pb-10 border-b border-slate-100'}`}>
      <h2 className="mb-4 text-xl font-bold text-slate-900">{title}</h2>
      <div className="text-slate-700 leading-relaxed text-sm space-y-0">{children}</div>
    </div>
  );
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h3 className="mb-2 font-semibold text-slate-800">{title}</h3>
      {children}
    </div>
  );
}

function DataList({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 ml-4 space-y-1 text-slate-700">
      {items.map((item) => (
        <li key={item} className="list-disc">{item}</li>
      ))}
    </ul>
  );
}
