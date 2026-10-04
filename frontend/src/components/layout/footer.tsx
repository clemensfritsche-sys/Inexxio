'use client';

import { useEffect, useState } from 'react';
import { Mail, MapPin, Phone } from 'lucide-react';
import { CookieSettingsLink } from './cookie-settings-link';
import { api } from '@/lib/api';
import shell from '@/lib/site-shell.json';

type Contact = { address: string[]; phone: string; tel: string; email: string };
const BUILT: Contact = { address: shell.address, phone: shell.phone.display, tel: shell.phone.e164, email: shell.email };

/**
 * Kontaktdaten aus dem ERP (Testnotiz #1094) – dieselbe Antwort, die die Website liest.
 * Bis sie da ist (oder wenn sie fehlt), gelten die Angaben aus `site-shell.json`.
 */
function useErpContact(): Contact {
  const [contact, setContact] = useState(BUILT);
  useEffect(() => {
    let alive = true;
    api.getPublicContact().then((c) => {
      if (!alive) return;
      const lines = c.address_lines.filter((l) => l.trim() && l.trim().toUpperCase() !== 'CH');
      setContact({
        address: c.name && lines.length ? [c.name, ...lines] : BUILT.address,
        phone: (c.phone_e164 && c.phone) || BUILT.phone,
        tel: c.phone_e164 || BUILT.tel,
        email: c.email || BUILT.email,
      });
    }).catch(() => { /* Vorgabe bleibt */ });
    return () => { alive = false; };
  }, []);
  return contact;
}

/**
 * ►►► Der Fuss des Konto-/ERP-Bereichs – ein Spiegel des Website-Fusses. ◄◄◄
 *
 * Dieselbe Anordnung wie `website/src/components/Footer.astro` (Logo und Satz · drei
 * Bereiche · Unternehmen · Kontakt; unten © · Impressum · Datenschutz), dieselben Inhalte aus
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
  const contact = useErpContact();
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
          </div>

          {shell.areas.map((area) => (
            <nav key={area.href} className="sf-col" aria-label={area.label}>
              <h2 className="sf-title"><a href={area.href}>{area.label}</a></h2>
              <ul>
                {area.children.map((c) => <li key={c.href}><a href={c.href}>{c.label}</a></li>)}
              </ul>
            </nav>
          ))}

          <nav className="sf-col" aria-label="Unternehmen">
            <h2 className="sf-title">Unternehmen</h2>
            <ul>
              {company.map((c) => <li key={c.href}><a href={c.href}>{c.label}</a></li>)}
            </ul>
          </nav>

          <div className="sf-col">
            <h2 className="sf-title"><a href="/kontakt">Kontakt</a></h2>
            <address className="sf-contact">
              <p>
                <MapPin size={16} aria-hidden />
                <span>{contact.address.map((line, i) => <span key={line}>{i > 0 && <br />}{line}</span>)}</span>
              </p>
              <p>
                <Phone size={16} aria-hidden />
                <span><a href={`tel:${contact.tel}`} className="sf-tnum">{contact.phone}</a></span>
              </p>
              <p>
                <Mail size={16} aria-hidden />
                <span><a href={`mailto:${contact.email}`}>{contact.email}</a></span>
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
          </ul>
        </div>
      </div>
    </footer>
  );
}
