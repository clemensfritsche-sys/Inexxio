import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Impressum",
  robots: { index: false },
};

// Company data is loaded dynamically from backend in production.
// This is a static placeholder for Phase 1.
async function getCompanySettings() {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/company-settings`,
      { next: { revalidate: 3600 } }
    );
    if (res.ok) return res.json();
  } catch {}
  return null;
}

export default async function ImpressumPage() {
  const s = await getCompanySettings();

  return (
    <div className="max-w-3xl mx-auto px-4 py-16">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Impressum</h1>

      <div className="prose prose-gray max-w-none space-y-6 text-sm text-gray-700">
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Unternehmensangaben</h2>
          <p>
            <strong>{s?.company_name ?? "Inexxio AG"}</strong><br />
            {s?.street ?? "[Adresse]"}<br />
            {s?.zip_code ?? "[PLZ]"} {s?.city ?? "[Ort]"}<br />
            {s?.country ?? "Schweiz"}
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Rechtsform &amp; Register</h2>
          <p>
            Rechtsform: {s?.legal_form ?? "Aktiengesellschaft (AG)"}<br />
            UID-Nummer: {s?.uid_number ?? "CHE-123.456.789"}<br />
            MWST-Nummer: {s?.vat_number ?? "CHE-123.456.789 MWST"}<br />
            Handelsregister-Nr.: {s?.commercial_register_nr ?? "[Ausstehend]"}<br />
            Handelsregisterkanton: {s?.commercial_register_canton ?? "[Kanton]"}<br />
            {s?.share_capital && (
              <>Aktienkapital: CHF {Number(s.share_capital).toLocaleString("de-CH")}<br /></>
            )}
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Kontakt</h2>
          <p>
            E-Mail:{" "}
            <a href={`mailto:${s?.email ?? "info@inexxio.com"}`} className="text-brand-600 hover:underline">
              {s?.email ?? "info@inexxio.com"}
            </a>
            {s?.phone && (
              <>
                <br />Telefon: <a href={`tel:${s.phone}`} className="text-brand-600 hover:underline">{s.phone}</a>
              </>
            )}
            <br />
            Website:{" "}
            <a href={s?.website ?? "https://inexxio.com"} className="text-brand-600 hover:underline">
              {s?.website ?? "https://inexxio.com"}
            </a>
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Haftungsausschluss</h2>
          <p>
            Die Inhalte dieser Website wurden sorgfältig zusammengestellt. Für die Richtigkeit,
            Vollständigkeit und Aktualität der Inhalte kann keine Gewähr übernommen werden.
          </p>
        </section>
      </div>
    </div>
  );
}
