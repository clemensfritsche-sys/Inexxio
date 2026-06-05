import type { Metadata } from 'next';
import Link from 'next/link';
import { ExternalLink, AlertCircle } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Impressum',
  description: 'Impressum der Inexxio AG gemäss Art. 11 UWG.',
  robots: { index: true, follow: false },
};

interface PublicSettings {
  company_name: string;
  legal_form: string;
  street?: string;
  street_nr?: string;
  zip_code?: string;
  city?: string;
  country: string;
  uid_number?: string;
  vat_number?: string;
  trade_register_nr?: string;
  trade_register_canton?: string;
  share_capital?: string;
  email: string;
  phone?: string;
  website: string;
}

async function getCompanySettings(): Promise<PublicSettings | null> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const res = await fetch(`${apiUrl}/api/v1/admin/settings/public`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default async function ImpressumPage() {
  const settings = await getCompanySettings();

  const companyName = settings?.company_name || 'Inexxio AG';
  const legalForm = settings?.legal_form || 'AG';
  const address = settings
    ? [
        `${settings.street || ''} ${settings.street_nr || ''}`.trim(),
        `${settings.zip_code || ''} ${settings.city || ''}`.trim(),
        settings.country,
      ]
        .filter(Boolean)
        .join(', ')
    : null;
  const fullName = `${companyName} (${legalForm})`;

  return (
    <div className="min-h-screen bg-white">
      {/* Hero */}
      <section className="bg-slate-900 py-16">
        <div className="container">
          <h1 className="text-4xl font-bold text-white">Impressum</h1>
          <p className="mt-2 text-slate-400">
            Angaben gemäss Art. 11 UWG und Art. 13 DSG
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container max-w-3xl">
          {!settings && (
            <div className="mb-8 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
              <div>
                <p className="font-medium text-amber-800">Firmeneinstellungen nicht konfiguriert</p>
                <p className="mt-1 text-sm text-amber-700">
                  Bitte melden Sie sich im{' '}
                  <Link href="/admin/einstellungen" className="underline">
                    Admin-Bereich
                  </Link>{' '}
                  an und hinterlegen Sie die Unternehmensdaten.
                </p>
              </div>
            </div>
          )}

          {/* Section 1: Unternehmensangaben */}
          <div className="mb-10">
            <h2 className="mb-4 text-2xl font-bold text-slate-900">
              Angaben gemäss Art. 11 UWG
            </h2>
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <tbody>
                  <Row label="Firma">
                    <span className="font-medium">{fullName}</span>
                  </Row>
                  {address && <Row label="Sitz">{address}</Row>}
                  {settings?.uid_number && (
                    <Row label="UID-Nummer">
                      <span className="font-mono">{settings.uid_number}</span>
                    </Row>
                  )}
                  {settings?.vat_number && (
                    <Row label="MWST-Nummer">
                      <span className="font-mono">{settings.vat_number}</span>
                    </Row>
                  )}
                  {settings?.trade_register_nr && (
                    <Row label="Handelsregister-Nr.">
                      <span className="font-mono">{settings.trade_register_nr}</span>
                    </Row>
                  )}
                  {settings?.trade_register_canton && (
                    <Row label="Handelsregister Kanton">{settings.trade_register_canton}</Row>
                  )}
                  {settings?.share_capital && (
                    <Row label="Aktienkapital">{settings.share_capital}</Row>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 2: Kontakt */}
          <div className="mb-10">
            <h2 className="mb-4 text-2xl font-bold text-slate-900">Kontakt</h2>
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <tbody>
                  <Row label="E-Mail">
                    <a
                      href={`mailto:${settings?.email || 'info@inexxio.com'}`}
                      className="text-blue-600 hover:underline"
                    >
                      {settings?.email || 'info@inexxio.com'}
                    </a>
                  </Row>
                  {settings?.phone && (
                    <Row label="Telefon">
                      <a href={`tel:${settings.phone}`} className="text-blue-600 hover:underline">
                        {settings.phone}
                      </a>
                    </Row>
                  )}
                  <Row label="Website">
                    <a
                      href={settings?.website || 'https://inexxio.com'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                    >
                      {settings?.website || 'https://inexxio.com'}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </Row>
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 3: Verantwortlich */}
          <div className="mb-10">
            <h2 className="mb-4 text-2xl font-bold text-slate-900">
              Verantwortlich für den Inhalt
            </h2>
            <p className="text-slate-700">
              {fullName}
              {address && (
                <>
                  <br />
                  {settings!.street} {settings!.street_nr}
                  <br />
                  {settings!.zip_code} {settings!.city}
                  <br />
                  {settings!.country}
                </>
              )}
            </p>
          </div>

          {/* Section 4: Haftungsausschluss */}
          <LegalSection title="Haftungsausschluss">
            <p>
              Die Inhalte dieser Website wurden mit grösster Sorgfalt erstellt. Für die
              Richtigkeit, Vollständigkeit und Aktualität der Inhalte können wir jedoch keine
              Gewähr übernehmen. Als Diensteanbieter sind wir für eigene Inhalte auf diesen Seiten
              nach den allgemeinen Gesetzen verantwortlich. Wir sind jedoch nicht verpflichtet,
              übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen
              zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen.
            </p>
            <p className="mt-3">
              Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den
              allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung ist jedoch
              erst ab dem Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei
              Bekanntwerden von entsprechenden Rechtsverletzungen werden wir diese Inhalte umgehend
              entfernen.
            </p>
          </LegalSection>

          {/* Section 5: Haftung für Links */}
          <LegalSection title="Haftung für Links">
            <p>
              Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen
              Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr
              übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter
              oder Betreiber der Seiten verantwortlich.
            </p>
            <p className="mt-3">
              Die verlinkten Seiten wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstösse
              überprüft. Rechtswidrige Inhalte waren zum Zeitpunkt der Verlinkung nicht erkennbar.
              Eine permanente inhaltliche Kontrolle der verlinkten Seiten ist jedoch ohne konkrete
              Anhaltspunkte einer Rechtsverletzung nicht zumutbar. Bei Bekanntwerden von
              Rechtsverletzungen werden wir derartige Links umgehend entfernen.
            </p>
          </LegalSection>

          {/* Section 6: Urheberrecht */}
          <LegalSection title="Urheberrecht">
            <p>
              Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten
              unterliegen dem Schweizer Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung
              und jede Art der Verwertung ausserhalb der Grenzen des Urheberrechtes bedürfen der
              schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers.
            </p>
            <p className="mt-3">
              Downloads und Kopien dieser Seite sind nur für den privaten, nicht kommerziellen
              Gebrauch gestattet. Soweit die Inhalte auf dieser Seite nicht vom Betreiber erstellt
              wurden, werden die Urheberrechte Dritter beachtet. Insbesondere werden Inhalte Dritter
              als solche gekennzeichnet. Sollten Sie trotzdem auf eine Urheberrechtsverletzung
              aufmerksam werden, bitten wir um einen entsprechenden Hinweis. Bei Bekanntwerden von
              Rechtsverletzungen werden wir derartige Inhalte umgehend entfernen.
            </p>
          </LegalSection>

          {/* Section 7: Datenschutz */}
          <LegalSection title="Datenschutz" isLast>
            <p>
              Informationen zur Verarbeitung Ihrer personenbezogenen Daten finden Sie in unserer{' '}
              <Link href="/datenschutz" className="text-blue-600 hover:underline">
                Datenschutzerklärung
              </Link>
              .
            </p>
          </LegalSection>
        </div>
      </section>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="w-48 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-600">{label}</td>
      <td className="px-4 py-3 text-slate-900">{children}</td>
    </tr>
  );
}

function LegalSection({
  title,
  children,
  isLast = false,
}: {
  title: string;
  children: React.ReactNode;
  isLast?: boolean;
}) {
  return (
    <div className={isLast ? '' : 'mb-8'}>
      <h2 className="mb-3 text-xl font-bold text-slate-900">{title}</h2>
      <div className="text-slate-700 leading-relaxed">{children}</div>
    </div>
  );
}
