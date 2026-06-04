import Link from 'next/link';
import { Mail, Phone, MapPin } from 'lucide-react';

const currentYear = new Date().getFullYear();

export function Footer() {
  return (
    <footer style={{ background: 'var(--bg-dark)', color: 'var(--fg-on-dark)' }}>
      <div className="ix-wrap" style={{ paddingTop: 80, paddingBottom: 0 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 1fr 1fr 1fr',
            gap: 40,
            paddingBottom: 48,
            borderBottom: '1px solid var(--border-on-dark)',
          }}
          className="footer-grid"
        >
          {/* Brand column */}
          <div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt="Inexxio AG"
              style={{ height: 26, filter: 'brightness(0) invert(1)', marginBottom: 20 }}
            />
            <p style={{ font: 'var(--body-sm)', color: 'rgba(255,255,255,0.6)', maxWidth: 280, lineHeight: 1.65 }}>
              Präzisionsfertigung und Maschinenbau. Qualität made in Switzerland.
            </p>
            <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <a
                href="mailto:info.inexxio@gmail.com"
                style={{ display: 'flex', alignItems: 'center', gap: 10, font: 'var(--body-sm)', color: 'rgba(255,255,255,0.8)', textDecoration: 'none' }}
              >
                <Mail style={{ width: 14, height: 14, color: 'var(--ix-red-bright)', flexShrink: 0 }} />
                info.inexxio@gmail.com
              </a>
              <a
                href="tel:+41795058302"
                style={{ display: 'flex', alignItems: 'center', gap: 10, font: 'var(--body-sm)', color: 'rgba(255,255,255,0.8)', textDecoration: 'none' }}
              >
                <Phone style={{ width: 14, height: 14, color: 'var(--ix-red-bright)', flexShrink: 0 }} />
                +41 79 505 83 02
              </a>
              <span style={{ display: 'flex', alignItems: 'flex-start', gap: 10, font: 'var(--body-sm)', color: 'rgba(255,255,255,0.8)' }}>
                <MapPin style={{ width: 14, height: 14, color: 'var(--ix-red-bright)', flexShrink: 0, marginTop: 2 }} />
                Schweiz
              </span>
            </div>
          </div>

          {/* Rechtliches */}
          <div>
            <h5
              style={{
                font: '600 11px var(--font-body)',
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: 'rgba(255,255,255,0.45)',
                margin: '0 0 18px',
              }}
            >
              Rechtliches
            </h5>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { href: '/agb', label: 'AGB' },
                { href: '/datenschutz', label: 'Datenschutz' },
                { href: '/impressum', label: 'Impressum' },
              ].map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    style={{ font: 'var(--body-sm)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none' }}
                    className="footer-link"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Navigation */}
          <div>
            <h5
              style={{
                font: '600 11px var(--font-body)',
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: 'rgba(255,255,255,0.45)',
                margin: '0 0 18px',
              }}
            >
              Navigation
            </h5>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { href: '/', label: 'Startseite' },
                { href: '/ueber-uns', label: 'Über uns' },
                { href: '/kontakt', label: 'Kontakt' },
              ].map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    style={{ font: 'var(--body-sm)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none' }}
                    className="footer-link"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* ERP */}
          <div>
            <h5
              style={{
                font: '600 11px var(--font-body)',
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: 'rgba(255,255,255,0.45)',
                margin: '0 0 18px',
              }}
            >
              ERP-System
            </h5>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <li>
                <Link
                  href="/login"
                  style={{ font: 'var(--body-sm)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none' }}
                  className="footer-link"
                >
                  Anmelden
                </Link>
              </li>
            </ul>
            <div style={{ marginTop: 24 }}>
              <p style={{ font: '500 11px var(--font-body)', color: 'rgba(255,255,255,0.35)', letterSpacing: '0.06em' }}>
                MO – FR · 08:00 – 17:00
              </p>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            paddingTop: 24,
            paddingBottom: 32,
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <p style={{ font: 'var(--caption)', color: 'rgba(255,255,255,0.4)', margin: 0 }}>
            © {currentYear} Inexxio AG. Alle Rechte vorbehalten.
          </p>
          <p style={{ font: 'var(--caption)', color: 'rgba(255,255,255,0.3)', margin: 0 }}>
            Eingetragen im Handelsregister des Kantons Zürich
          </p>
        </div>
      </div>

      <style>{`
        .footer-link:hover { color: #fff !important; }
        @media (max-width: 760px) {
          .footer-grid { grid-template-columns: 1fr 1fr !important; }
        }
        @media (max-width: 480px) {
          .footer-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </footer>
  );
}
