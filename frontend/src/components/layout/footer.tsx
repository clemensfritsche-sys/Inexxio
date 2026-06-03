import Link from 'next/link';
import { Settings2, Mail, Phone, MapPin } from 'lucide-react';

const currentYear = new Date().getFullYear();

export function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300">
      <div className="container py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12">
          {/* Brand column */}
          <div className="md:col-span-1">
            <Link href="/" className="flex items-center gap-2 group mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 group-hover:bg-blue-500 transition-colors">
                <Settings2 className="h-4 w-4 text-white" />
              </div>
              <span className="font-bold text-lg text-white">Inexxio AG</span>
            </Link>
            <p className="text-sm text-slate-400 leading-relaxed">
              Ihr Schweizer Spezialist für Präzisionsfertigung und Maschinenbau. Qualität
              made in Switzerland.
            </p>
            <div className="mt-4 flex items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-slate-800 px-2 py-1 text-xs font-medium text-slate-300">
                Swiss Made
              </span>
              <span className="inline-flex items-center rounded-md bg-slate-800 px-2 py-1 text-xs font-medium text-slate-300">
                ISO 9001
              </span>
            </div>
          </div>

          {/* Unternehmen */}
          <div>
            <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
              Rechtliches
            </h4>
            <ul className="space-y-2.5">
              <li>
                <Link href="/agb" className="text-sm text-slate-400 hover:text-white transition-colors">
                  AGB
                </Link>
              </li>
              <li>
                <Link href="/datenschutz" className="text-sm text-slate-400 hover:text-white transition-colors">
                  Datenschutz
                </Link>
              </li>
              <li>
                <Link href="/impressum" className="text-sm text-slate-400 hover:text-white transition-colors">
                  Impressum
                </Link>
              </li>
            </ul>
          </div>

          {/* Navigation */}
          <div>
            <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
              Navigation
            </h4>
            <ul className="space-y-2.5">
              <li>
                <Link href="/" className="text-sm text-slate-400 hover:text-white transition-colors">
                  Startseite
                </Link>
              </li>
              <li>
                <Link href="/ueber-uns" className="text-sm text-slate-400 hover:text-white transition-colors">
                  Über uns
                </Link>
              </li>
              <li>
                <Link href="/kontakt" className="text-sm text-slate-400 hover:text-white transition-colors">
                  Kontakt
                </Link>
              </li>
            </ul>
          </div>

          {/* Kontakt */}
          <div>
            <h4 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
              Kontakt
            </h4>
            <ul className="space-y-3">
              <li className="flex items-start gap-2.5">
                <MapPin className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />
                <span className="text-sm text-slate-400">
                  Inexxio AG
                  <br />
                  Musterstrasse 1
                  <br />
                  8001 Zürich, Schweiz
                </span>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="h-4 w-4 text-slate-500 shrink-0" />
                <a
                  href="mailto:info@inexxio.com"
                  className="text-sm text-slate-400 hover:text-white transition-colors"
                >
                  info@inexxio.com
                </a>
              </li>
              <li className="flex items-center gap-2.5">
                <Phone className="h-4 w-4 text-slate-500 shrink-0" />
                <a
                  href="tel:+41441234567"
                  className="text-sm text-slate-400 hover:text-white transition-colors"
                >
                  +41 44 123 45 67
                </a>
              </li>
            </ul>
            <div className="mt-4">
              <p className="text-xs text-slate-500">
                Mo–Fr: 08:00–17:00 Uhr
                <br />
                Sa–So: Geschlossen
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-slate-800">
        <div className="container py-5 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-xs text-slate-500">
            © {currentYear} Inexxio AG. Alle Rechte vorbehalten.
          </p>
          <p className="text-xs text-slate-600">
            Eingetragen im Handelsregister des Kantons Zürich
          </p>
        </div>
      </div>
    </footer>
  );
}
