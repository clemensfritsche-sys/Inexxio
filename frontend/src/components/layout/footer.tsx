import { Clock, Mail, MapPin, Phone, Siren } from 'lucide-react';
import { CookieSettingsLink } from './cookie-settings-link';
import shell from '@/lib/site-shell.json';

/**
 * ►►► Der Fuss des Konto-/ERP-Bereichs – ein Spiegel des Website-Fusses. ◄◄◄
 *
 * Dieselbe Anordnung wie `website/src/components/Footer.astro` (Logo und Satz · drei
 * Bereiche · Kontakt; unten © · Impressum · Datenschutz · UID), dieselben Inhalte aus
 * `lib/site-shell.json` (generiert aus `website/src/config/site.mjs`). Hier stand vorher
 * ein Fuss eines anderen Geschäfts – «Präzisionsfertigung», eine fremde Telefonnummer und
 * ein Handelsregister-Satz, der nirgends belegt war. Ein Spiegel kann das nicht mehr: er
 * hat keine eigenen Wörter.
 *
 * Der Anmelde-Link der Website fehlt hier bewusst – wer diesen Fuss sieht, ist schon im
 * Konto oder im ERP. Dafür steht hier, was nur dieser Bereich setzt: die
 * Cookie-Einstellungen (Einwilligung `inexxio_consent`).
 */
export function Footer() {
  const year = new Date().getFullYear();
  const company = [...shell.company, { label: shell.service.overview, href: shell.service.href }];
  return (
    <footer className="sf">
      <div className="site-wrap">
        <div className="sf-grid">
          <div>
            <a href="/" className="sf-home" aria-label={`${shell.brand.full} – zur Startseite`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={shell.logo.light} alt={shell.brand.full} className="site-lockup" />
            </a>
            <p className="sf-claim">{shell.claim}</p>
            <nav aria-label="Unternehmen">
              <ul className="sf-company">
                {company.map((c) => <li key={c.href}><a href={c.href}>{c.label}</a></li>)}
              </ul>
            </nav>
          </div>

          {shell.areas.map((area) => (
            <nav key={area.href} className="sf-col" aria-label={area.label}>
              <h2 className="sf-title"><a href={area.href}>{area.label}</a></h2>
              <ul>
                {area.children.map((c) => <li key={c.href}><a href={c.href}>{c.label}</a></li>)}
              </ul>
            </nav>
          ))}

          <div className="sf-col">
            <h2 className="sf-title">Kontakt</h2>
            <address className="sf-contact">
              <p>
                <MapPin size={16} aria-hidden />
                <span>{shell.address.map((line, i) => <span key={line}>{i > 0 && <br />}{line}</span>)}</span>
              </p>
              <p>
                <Phone size={16} aria-hidden />
                <span>Telefon <a href={`tel:${shell.phone.e164}`} className="sf-tnum">{shell.phone.display}</a></span>
              </p>
              {shell.notfall && (
                <p>
                  <Siren size={16} aria-hidden />
                  <span>Notfall <a href={`tel:${shell.notfall.e164}`} className="sf-tnum">{shell.notfall.display}</a></span>
                </p>
              )}
              <p>
                <Mail size={16} aria-hidden />
                <span><a href={`mailto:${shell.email}`}>{shell.email}</a></span>
              </p>
              <p>
                <Clock size={16} aria-hidden />
                <span>{shell.hours}</span>
              </p>
            </address>
          </div>
        </div>

        <div className="sf-bottom">
          <p>© {year} {shell.brand.legalName}</p>
          <ul>
            {shell.legal.map((l) => <li key={l.href}><a href={l.href}>{l.label}</a></li>)}
            <li><a href="/agb">AGB</a></li>
            <li><CookieSettingsLink /></li>
            {shell.uid && <li>UID {shell.uid}</li>}
          </ul>
        </div>
      </div>
    </footer>
  );
}
